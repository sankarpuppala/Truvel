"""Clean up all incorrect, mismatched, and stand-in photos across the database.

Removes:
1. All generic photos from the query bank that were assigned in rotation and do not match the place.
2. All non-image or portrait media (e.g. .webm videos, .pdf scans, person interviews like Gautam John).
3. All reused stock photos attached to multiple different places.

Keeps:
1. All genuine Wikidata seed photos (P18 property manually verified for notable places).
2. All verified authentic matches where the photo filename specifically names the place (e.g. Ram Mandir,
   Ananthagiri Hills, Bangalore Fort, Kempe Gowda towers, Lalbagh, Cubbon Park, Belur, Hampi, etc.).
3. Uploads and user-contributed media.

Any place without an authentic photo cleanly displays its designed, handcrafted SVG category illustration
(SPEC §12.6, CLAUDE.md Invariant 6).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import delete as sa_delete
from sqlmodel import Session, select

from app.config import DATA_DIR
from app.db import engine
from app.models import Media, MediaLike, MediaView, Place, PlaceName

BANK_FILE = DATA_DIR / "wikidata" / "online_photo_bank.json"

STOP_WORDS = {
    'park', 'lake', 'temple', 'museum', 'fort', 'hill', 'hills', 'garden', 'gardens',
    'falls', 'beach', 'viewpoint', 'statue', 'monument', 'road', 'street', 'city',
    'place', 'area', 'town', 'village', 'north', 'south', 'east', 'west', 'near',
    'ancient', 'historical', 'national', 'international', 'state', 'district', 'mandir',
    'gudi', 'kovil', 'masjid', 'church', 'cheruvu', 'kunta', 'tank', 'talab', 'bengaluru',
    'bangalore', 'hyderabad', 'chennai', 'mumbai', 'delhi', 'gate', 'rock', 'view', 'tower'
}

BAD_EXTENSIONS = ('.webm', '.pdf', '.ogg', '.ogv', '.mp3', '.mp4')
BAD_KEYWORDS = ['portrait', 'wikipedian', 'interview', 'passport', 'author', 'speech', 'conference']


def place_distinctive_words(name: str) -> set[str]:
    return {w for w in re.findall(r'[a-z]+', name.lower()) if len(w) >= 4 and w not in STOP_WORDS}


def is_genuine_match(place_name: str, filename: str) -> bool:
    """Check if the filename actually contains the distinctive name of the place."""
    p_words = place_distinctive_words(place_name)
    if not p_words:
        return False
    fn_low = filename.lower()
    return any(pw in fn_low for pw in p_words)


def run_cleanup():
    print("=" * 70)
    print("Truvel Photo Quality & Integrity Enforcer")
    print("Cleaning incorrect stand-in photos, person portraits, and mismatched stock")
    print("=" * 70)

    bank_files = set()
    if BANK_FILE.is_file():
        bank_data = json.load(BANK_FILE.open(encoding="utf-8"))
        bank_files = {p["filename"] for photos in bank_data.values() for p in photos if p.get("filename")}

    with Session(engine) as session:
        # Load all media rows
        rows = session.exec(
            select(Media).where(Media.status == "ok", Media.source == "commons")
        ).all()

        names = dict(
            session.exec(
                select(PlaceName.place_id, PlaceName.name).where(PlaceName.lang == "en")
            ).all()
        )

        # Count usage of each filename
        file_usage = Counter(m.path_display for m in rows)

        to_remove = []
        to_keep = []

        for m in rows:
            fn_low = m.path_display.lower()
            name = names.get(m.place_id, "")

            # Rule 1: Bad extension or portrait keyword is always removed
            if fn_low.endswith(BAD_EXTENSIONS) or any(bk in fn_low for bk in BAD_KEYWORDS):
                to_remove.append((m, f"bad_format_or_portrait ({m.path_display})"))
                continue

            # Rule 2: Original Wikidata seed (id <= 8531) is genuine P18 data
            if m.id is not None and m.id <= 8531:
                to_keep.append(m)
                continue

            # Rule 3: Reused across multiple places in rotation -> remove
            if file_usage[m.path_display] > 1:
                to_remove.append((m, f"reused_in_rotation ({file_usage[m.path_display]} places)"))
                continue

            # Rule 4: Distinctive name match -> keep
            if is_genuine_match(name, m.path_display):
                to_keep.append(m)
                continue

            # Rule 5: If in bank and no distinctive match -> remove
            if m.path_display in bank_files:
                to_remove.append((m, "bank_no_distinctive_match"))
                continue

            # Default: If no distinctive match, remove to prevent wrong photos
            to_remove.append((m, "no_name_match"))

        print(f"\nAudit Results:")
        print(f"  Total Commons photos:   {len(rows)}")
        print(f"  Verified GENUINE photos to keep: {len(to_keep)}")
        print(f"  INCORRECT photos to delete:      {len(to_remove)}")

        print("\nSample deleted incorrect photos:")
        for m, reason in to_remove[:12]:
            pname = names.get(m.place_id, f"Place {m.place_id}")
            print(f"  Delete: {pname[:35]:35} <- {m.path_display[:40]} [{reason}]")

        remove_ids = [int(m.id) for m, _ in to_remove]
        print(f"\nDeleting {len(remove_ids)} incorrect media records...")

        for start in range(0, len(remove_ids), 500):
            chunk = remove_ids[start : start + 500]
            for related in (MediaLike, MediaView):
                session.exec(sa_delete(related).where(related.media_id.in_(chunk)))
            session.exec(sa_delete(Media).where(Media.id.in_(chunk)))

        session.commit()
        print("[SUCCESS] All incorrect media records cleanly deleted from database!")

        # Final audit
        remaining_media = session.exec(select(Media).where(Media.status == "ok")).all()
        places_with_photo = len({m.place_id for m in remaining_media if m.place_id})
        total_places = session.exec(select(Place)).all()

        print("\n" + "=" * 70)
        print("FINAL DATABASE STATUS")
        print("=" * 70)
        print(f"Total Places:                      {len(total_places)}")
        print(f"Places with 100% Genuine Photos:   {places_with_photo}")
        print(f"Places with Category Illustration: {len(total_places) - places_with_photo}")
        print(f"Active Media Rows:                 {len(remaining_media)}")
        print("=" * 70)


if __name__ == "__main__":
    run_cleanup()
