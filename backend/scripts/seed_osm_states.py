"""Seed the smaller, lesser-known places OSM knows about, one state at a time.

`seed_osm.py` goes deep on one named city (a bbox). `seed_wikidata.py` goes
wide across every notable place in India, but "notable" means it has enough
Wikipedia coverage to be in Wikidata -- a real viewpoint, waterfall or temple
that nobody has written an article about is invisible to it. This script finds
those: the same Overpass categories as `seed_osm.py`, over one Indian *state*
at a time instead of one city's bbox.

A state is queried by its OSM administrative boundary, by ISO3166-2 code
(`area["ISO3166-2"="IN-TG"]`) -- Overpass resolves the shape itself, so this
script never downloads or draws a boundary (CLAUDE.md invariant 12: we never
render state or country borders; this is a server-side *filter*, not a map
layer). Overpass is one shared, free, best-effort service for the whole
OpenStreetMap community, so this runs **one query at a time, one state at a
time**, with the same politeness pause and mirror fallback `seed_osm.py` uses.
Querying 28 states in parallel would not be faster -- the mirrors are the
shared bottleneck -- and risks the whole project losing access to them.

    python -m scripts.seed_osm_states --state Goa
    python -m scripts.seed_osm_states --all               # all 28 states, in turn
    python -m scripts.seed_osm_states --all --from Kerala # resume a long run

A place is matched on (osm_type, osm_id), the same key `seed_osm.py` uses, so
running this after `seed_osm.py` or Wikidata's import never duplicates a place
that is already here -- it is caught at commit time, and `merge_duplicates.py`
catches the rest (two sources describing the same temple by different ids).
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from sqlmodel import Session, select

from app.db import engine, rebuild_fts
from app.models import Place, PlaceName, utcnow
from scripts.seed_osm import (
    CATEGORY_OUT,
    CATEGORY_QUERIES,
    MIN_PARK_AREA_HA,
    access_from_tags,
    accessibility_from_tags,
    bbox_area_ha,
    centre_of,
    fame_for,
    fetch,
    names_from_tags,
)

# The 28 states of India (the 8 Union Territories are not states, and most are
# small enough that the Wikidata pass already covers what is notable in them).
STATE_CODES: dict[str, str] = {
    "Andhra Pradesh": "IN-AP",
    "Arunachal Pradesh": "IN-AR",
    "Assam": "IN-AS",
    "Bihar": "IN-BR",
    "Chhattisgarh": "IN-CT",
    "Goa": "IN-GA",
    "Gujarat": "IN-GJ",
    "Haryana": "IN-HR",
    "Himachal Pradesh": "IN-HP",
    "Jharkhand": "IN-JH",
    "Karnataka": "IN-KA",
    "Kerala": "IN-KL",
    "Madhya Pradesh": "IN-MP",
    "Maharashtra": "IN-MH",
    "Manipur": "IN-MN",
    "Meghalaya": "IN-ML",
    "Mizoram": "IN-MZ",
    "Nagaland": "IN-NL",
    "Odisha": "IN-OR",
    "Punjab": "IN-PB",
    "Rajasthan": "IN-RJ",
    "Sikkim": "IN-SK",
    "Tamil Nadu": "IN-TN",
    "Telangana": "IN-TG",
    "Tripura": "IN-TR",
    "Uttar Pradesh": "IN-UP",
    "Uttarakhand": "IN-UT",
    "West Bengal": "IN-WB",
}


def build_area_query(iso: str, clauses: list[str], out: str) -> str:
    """One Overpass QL query for a category, filtered to a state by ISO3166-2.

    `timeout:180`: a whole state is a far bigger area than a city bbox, so the
    free mirrors need longer than the 120 s `seed_osm.py` asks for.
    """
    area = f'area["ISO3166-2"="{iso}"]["admin_level"="4"]->.a;'
    parts = []
    for clause in clauses:
        named = clause if '["name"]' in clause else f'{clause}["name"]'
        parts.append(f"{named}(area.a);")
    body = "\n  ".join(parts)
    return f"[out:json][timeout:180];\n{area}\n(\n  {body}\n);\nout {out};"


def upsert_state_place(session: Session, state: str, category: str, element: dict) -> Place | None:
    """Create or update one place from an Overpass element. No city: this is
    a state-wide find, not a deep city seed, so it has no neighbourhood to
    belong to; a later visit or Explore search still finds it by state/FTS."""
    tags = element.get("tags") or {}
    coords = centre_of(element)
    if coords is None or not tags.get("name"):
        return None

    osm_type = str(element.get("type"))
    osm_id = int(element.get("id"))
    lat, lng = coords

    existing = session.exec(
        select(Place).where(Place.osm_type == osm_type, Place.osm_id == osm_id)
    ).first()
    place = existing or Place(source="osm")

    place.state = place.state or state
    place.lat, place.lng = lat, lng
    place.category = category
    place.source = place.source or "osm"
    place.osm_type = osm_type
    place.osm_id = osm_id
    place.wikidata = tags.get("wikidata") or place.wikidata
    place.fame = place.fame if existing else fame_for(tags)
    place.status = place.status if existing else "verified"
    place.tags = sorted({k for k in ("historic", "tourism", "natural", "leisure") if tags.get(k)})
    place.entry_fee_text = tags.get("fee") or place.entry_fee_text
    place.timings_text = tags.get("opening_hours") or place.timings_text
    if not place.access:
        place.access = access_from_tags(tags)
    if not place.accessibility:
        place.accessibility = accessibility_from_tags(tags)
    if not place.description:
        place.description = (tags.get("description") or "").strip()[:600]
    place.updated_at = utcnow()
    session.add(place)
    session.commit()
    session.refresh(place)

    for lang, name in names_from_tags(tags).items():
        row = session.exec(
            select(PlaceName).where(
                PlaceName.place_id == place.id, PlaceName.lang == lang, PlaceName.source == "osm"
            )
        ).first()
        if row is None:
            session.add(PlaceName(place_id=int(place.id), lang=lang, name=name, source="osm"))
        else:
            row.name = name
            session.add(row)
    session.commit()
    return place


def seed_state(state: str, refresh: bool = False) -> dict[str, Any]:
    iso = STATE_CODES[state]
    slug = state.lower().replace(" ", "-")
    print(f"\n=== {state} ({iso}) ===")

    with Session(engine) as session:
        before = len(session.exec(select(Place.id).where(Place.state == state)).all())
        created_total = 0
        per_category: dict[str, int] = {}

        for category, clauses in CATEGORY_QUERIES.items():
            print(f"  category {category}")
            try:
                payload = fetch(
                    build_area_query(iso, clauses, CATEGORY_OUT.get(category, "center tags")),
                    f"state-{slug}-{category}",
                    refresh,
                )
            except RuntimeError as exc:
                print(f"  ! skipping {category}: {exc}")
                continue

            count = 0
            for element in payload.get("elements", []):
                tags = element.get("tags") or {}
                if category == "park_garden" and not tags.get("wikidata"):
                    area = bbox_area_ha(element)
                    if area is None or area < MIN_PARK_AREA_HA:
                        continue
                was_new = (
                    session.exec(
                        select(Place.id).where(
                            Place.osm_type == str(element.get("type")),
                            Place.osm_id == int(element.get("id", 0)),
                        )
                    ).first()
                    is None
                )
                place = upsert_state_place(session, state, category, element)
                if place is None:
                    continue
                count += 1
                created_total += int(was_new)
            per_category[category] = count
            print(f"    {count} places")

        rebuild_fts()
        after = len(session.exec(select(Place.id).where(Place.state == state)).all())

    summary = {
        "state": state,
        "before": before,
        "after": after,
        "new": created_total,
        "per_category": per_category,
    }
    print(f"  {state}: {before} -> {after} places (+{created_total} new)")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed OSM's lesser-known places, one state at a time"
    )
    parser.add_argument("--state", default="", help="one state, by its full English name")
    parser.add_argument("--all", action="store_true", help="every one of the 28 states, in turn")
    parser.add_argument(
        "--from", dest="from_state", default="", help="with --all, resume from this state"
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    if args.all:
        states = list(STATE_CODES)
        if args.from_state:
            if args.from_state not in STATE_CODES:
                print(f"Unknown state {args.from_state!r}.")
                return 1
            states = states[states.index(args.from_state):]
        total_new = 0
        for index, state in enumerate(states, 1):
            print(f"\n[{index}/{len(states)}]", end="")
            summary = seed_state(state, args.refresh)
            total_new += summary["new"]
            time.sleep(2)
        print(f"\n\nAll states done. {total_new} new places in total.")
        return 0

    if not args.state:
        print("Pass --state 'Kerala' or --all.")
        return 1
    if args.state not in STATE_CODES:
        print(f"Unknown state {args.state!r}. Known: {', '.join(STATE_CODES)}")
        return 1
    seed_state(args.state, args.refresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
