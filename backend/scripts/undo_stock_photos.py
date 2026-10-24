"""Remove the stand-in photos that `add_photos_all.py` attached to places.

That script did not find photos *of* each place: it searched Commons for
generic category queries ("Hindu temple India", hills, lakes...) and handed the
results out in rotation, so a museum in Karnataka showed a cliff in Australia.
README and SPEC promise the opposite: no photo rather than a wrong one; the
category illustration is the designed fallback.

A row is removed when its file came from that script's photo bank
(`data/wikidata/online_photo_bank.json`) **unless** it looks like a real match:
the file is used by exactly one place and its name contains a word (4+ letters)
of that place's English name. Real photos from the Wikidata seed or
`fetch_photos.py` are not in the bank and are never touched.

    python -m scripts.undo_stock_photos            # dry run: counts and samples
    python -m scripts.undo_stock_photos --apply    # delete
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter

from sqlalchemy import delete as sa_delete
from sqlmodel import Session, select

from app.config import DATA_DIR
from app.db import engine
from app.models import Comment, Media, MediaLike, MediaView, PlaceName

BANK_FILE = DATA_DIR / "wikidata" / "online_photo_bank.json"


def bank_filenames() -> set[str]:
    data = json.loads(BANK_FILE.read_text(encoding="utf-8"))
    return {p["filename"] for photos in data.values() for p in photos if p.get("filename")}


def looks_like_this_place(filename: str, place_name: str) -> bool:
    """True when a word of the place's name (4+ letters) appears in the file name."""
    words = {w for w in re.findall(r"[a-z]+", place_name.lower()) if len(w) >= 4}
    file_words = set(re.findall(r"[a-z]+", filename.lower()))
    return bool(words & file_words)


def main(apply: bool) -> int:
    if not BANK_FILE.is_file():
        print(f"No photo bank at {BANK_FILE}; nothing to identify. Stop.")
        return 1
    bank = bank_filenames()
    with Session(engine) as session:
        rows = session.exec(
            select(Media).where(Media.source == "commons", Media.user_id == None)  # noqa: E711
        ).all()
        suspects = [m for m in rows if m.path_display in bank]
        uses = Counter(m.path_display for m in suspects)
        names = dict(
            session.exec(
                select(PlaceName.place_id, PlaceName.name).where(PlaceName.lang == "en")
            ).all()
        )
        remove = [
            m for m in suspects
            if uses[m.path_display] > 1
            or not looks_like_this_place(m.path_display, names.get(m.place_id, ""))
        ]
        keep = len(suspects) - len(remove)
        print(f"Photo-bank rows: {len(suspects)} · keep (real match): {keep} · remove: {len(remove)}")
        for m in remove[:8]:
            print(f"  remove  {names.get(m.place_id, m.place_id)!s:40.40}  ←  {m.path_display}")
        if not apply:
            print("Dry run. Re-run with --apply to delete.")
            return 0
        ids = [int(m.id) for m in remove]
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            for related in (MediaLike, MediaView, Comment):
                session.exec(sa_delete(related).where(related.media_id.in_(chunk)))
            session.exec(sa_delete(Media).where(Media.id.in_(chunk)))
        session.commit()
        print(f"Deleted {len(ids)} stand-in photos.")
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv))
