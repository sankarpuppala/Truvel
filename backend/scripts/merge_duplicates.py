"""Merge imported places that are the same place twice (SPEC §9.6).

The seeders import from two open datasets that overlap. Golconda Fort is in
Wikidata as Q1134499, again as Q17986822, and in OpenStreetMap as a third
element -- three records for one fort, all at the same coordinates. Left alone
they show up three times in Explore and each one splits the likes and visits
the real place ought to have.

SPEC §9.6 already says how to recognise a duplicate when a *person* adds a
place: a fuzzy match on every name, or the same category within 100 m. That
rule is built to ask a human "is it one of these?". Run unattended it would
merge a fort into the temple beside it, because both are heritage within 100 m.
Merging two different places is worse than leaving one duplicate, so this
script is stricter than the human prompt:

    the names agree (below)   AND   the two pins are within 150 m

and it never merges across categories that cannot describe one place.

"Agree" is two tests, and both must pass. The SPEC's `token_set_ratio` is
deliberately generous -- it scores 100 whenever one name is a subset of the
other -- which is right for a prompt to a person and wrong for a script:
"Golconda Fort" and "Golconda Jail" both reduce to "golconda" once generic words
are dropped, and "Kacheguda Railway Station" reduces to a superset of "Railway
Museum". So a plain character ratio has to agree as well: true duplicates in
Hyderabad score 75-97 on it, and the false ones 46-69. The cost is that
"Shilparamam" and "Shilparamam Crafts Village" (59) are left as two records,
which is the safe way to be wrong.

What survives is the better-sourced record. It keeps its own id, takes every
name and photo the others had, and the others are removed. Nothing is invented.

    python -m scripts.merge_duplicates --dry-run
    python -m scripts.merge_duplicates
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict

from rapidfuzz import fuzz
from sqlalchemy import update as sa_update
from sqlmodel import Session, select

from app.db import engine
from app.geo import haversine_m
from app.integrity.dedupe import name_similarity
from app.models import (
    LastMileStep,
    Like,
    Media,
    Place,
    PlaceName,
    Pulse,
    Save,
    Swipe,
    Touch,
    View,
    Visit,
)

# Rows a person left on a place. A merge must carry these across or lose them,
# and a forgotten table is a foreign-key failure at the worst moment. Tables with
# a (user, place) uniqueness rule need their clashes dropped first.
ENGAGEMENT_UNIQUE = [Like, Save, View]          # one row per (user, place)
ENGAGEMENT_FREE = [Swipe, Visit, Touch, Pulse, LastMileStep]

NAME_SIM_MIN = 92          # SPEC §9.6's fuzzy score, with generic words dropped
RAW_SIM_MIN = 72           # and a plain character ratio on the names as written
RADIUS_M = 150

# Two places in different groups are never one place, whatever their names say:
# a lake and the fort beside it are neighbours, not duplicates.
COMPATIBLE = [
    {"fort_heritage", "museum_art", "other"},
    {"temple_sacred", "other"},
    # A park beside a lake is two places, so they do not share a group.
    {"lake", "beach_river", "other"},
    {"park_garden", "other"},
    {"hill_trek", "viewpoint", "other"},
    {"waterfall", "other"},
]


def raw_similarity(left: list[str], right: list[str]) -> int:
    """Best plain character ratio between any name of one and any name of the other."""
    best = 0
    for a in left[:6]:
        for b in right[:6]:
            best = max(best, int(fuzz.ratio(a.lower().strip(), b.lower().strip())))
    return best


def compatible(a: str, b: str) -> bool:
    if a == b:
        return True
    return any(a in group and b in group for group in COMPATIBLE)


def quality(place: Place, photos: int, names: int) -> tuple:
    """Which of two records to keep: sourced, famous, photographed, named."""
    return (
        1 if place.wikidata else 0,
        place.sitelinks,
        photos,
        names,
        1 if place.source == "osm" else 0,
        -int(place.id or 0),
    )


class Groups:
    """Union-find, so A~B and B~C land in one group."""

    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        self.parent[self.find(a)] = self.find(b)


def find_groups(session: Session) -> list[list[int]]:
    places = {int(p.id): p for p in session.exec(select(Place)).all()}
    # English names only. A shared name in another script is usually the
    # village or district the place stands in, not the place: the two temples at
    # Thiruthulaivillimangalam share a Tamil name and are two different temples.
    names: dict[int, list[str]] = defaultdict(list)
    for row in session.exec(
        select(PlaceName.place_id, PlaceName.name).where(PlaceName.lang == "en")
    ).all():
        names[int(row[0])].append(str(row[1]))

    # A ~0.003 degree grid (about 330 m): neighbours are in the same or an
    # adjacent cell, so this is linear rather than comparing 17,000 x 17,000.
    cell = 0.003
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for pid, p in places.items():
        grid[(int(p.lat / cell), int(p.lng / cell))].append(pid)

    groups = Groups()
    for (gx, gy), members in grid.items():
        nearby: list[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nearby.extend(grid.get((gx + dx, gy + dy), ()))
        for a in members:
            pa = places[a]
            for b in nearby:
                if b <= a:
                    continue
                pb = places[b]
                if not compatible(pa.category, pb.category):
                    continue
                if haversine_m(pa.lat, pa.lng, pb.lat, pb.lng) > RADIUS_M:
                    continue
                same_item = bool(pa.wikidata) and pa.wikidata == pb.wikidata
                # Wikidata keeps a separate item for each distinct thing. Two
                # different items are two things; they are only one place when
                # the *names* are near-identical (Golconda Fort is Q1134499 and
                # Q17986822), which the checks below decide.
                sim = max(
                    (name_similarity(n, names[b]) for n in names[a][:6]),
                    default=0,
                )
                raw = raw_similarity(names[a], names[b])
                if same_item or (sim >= NAME_SIM_MIN and raw >= RAW_SIM_MIN):
                    groups.union(a, b)

    found: dict[int, list[int]] = defaultdict(list)
    for pid in places:
        if pid in groups.parent:
            found[groups.find(pid)].append(pid)
    return [sorted(ids) for ids in found.values() if len(ids) > 1]


def merge(session: Session, group: list[int]) -> tuple[int, list[int]]:
    places = {pid: session.get(Place, pid) for pid in group}
    photo_count = {
        pid: len(session.exec(select(Media).where(Media.place_id == pid, Media.status == "ok")).all())
        for pid in group
    }
    name_count = {
        pid: len(session.exec(select(PlaceName).where(PlaceName.place_id == pid)).all())
        for pid in group
    }
    keeper = max(group, key=lambda pid: quality(places[pid], photo_count[pid], name_count[pid]))
    losers = [pid for pid in group if pid != keeper]

    held = {
        (row.lang, row.name)
        for row in session.exec(select(PlaceName).where(PlaceName.place_id == keeper)).all()
    }
    seen_files = {
        row.path_display
        for row in session.exec(select(Media).where(Media.place_id == keeper)).all()
    }

    for loser in losers:
        for row in session.exec(select(PlaceName).where(PlaceName.place_id == loser)).all():
            clash = (row.lang, row.name) in held or any(
                existing.lang == row.lang and existing.source == row.source
                for existing in session.exec(
                    select(PlaceName).where(PlaceName.place_id == keeper)
                ).all()
            )
            if clash:
                session.delete(row)
            else:
                row.place_id = keeper
                held.add((row.lang, row.name))
        for row in session.exec(select(Media).where(Media.place_id == loser)).all():
            if row.path_display in seen_files:
                session.delete(row)
            else:
                row.place_id = keeper
                seen_files.add(row.path_display)
        for model in ENGAGEMENT_UNIQUE:
            owned = {
                int(row.user_id)
                for row in session.exec(select(model).where(model.place_id == keeper)).all()
            }
            for row in session.exec(select(model).where(model.place_id == loser)).all():
                if int(row.user_id) in owned:
                    session.delete(row)        # they already did this to the keeper
                else:
                    row.place_id = keeper
                    owned.add(int(row.user_id))
        for model in ENGAGEMENT_FREE:
            session.exec(
                sa_update(model).where(model.place_id == loser).values(place_id=keeper)
            )
        session.flush()

        # Keep the best of each descriptive field rather than the keeper's blanks.
        gone = places[loser]
        kept = places[keeper]
        kept.sitelinks = max(kept.sitelinks, gone.sitelinks)
        if not kept.wikidata and gone.wikidata:
            kept.wikidata = gone.wikidata
        session.add(kept)
        session.delete(gone)

    session.commit()
    return keeper, losers


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge duplicate imported places")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with Session(engine) as session:
        total = len(session.exec(select(Place.id)).all())
        groups = find_groups(session)
        removable = sum(len(g) - 1 for g in groups)
        print(f"{total} places; {len(groups)} duplicate groups; {removable} records to merge away")

        for group in groups[:14]:
            label = []
            for pid in group:
                place = session.get(Place, pid)
                name = session.exec(
                    select(PlaceName.name).where(PlaceName.place_id == pid, PlaceName.lang == "en")
                ).first()
                label.append(f"#{pid} {name!r} ({place.source}, {place.wikidata or '-'})")
            print("   ", "  +  ".join(label))
        if len(groups) > 14:
            print(f"    ... and {len(groups) - 14} more groups")

        if args.dry_run:
            print("\nDry run: nothing changed.")
            return 0

        for group in groups:
            merge(session, group)
        after = len(session.exec(select(Place.id)).all())
        print(f"\nMerged. {total} -> {after} places.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
