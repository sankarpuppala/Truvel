"""Seed one city deep from OpenStreetMap (SPEC §6.1, AC-1).

    python -m scripts.seed_osm --city hyderabad

One Overpass query per category inside the city bbox, named features only,
`out center` so ways and relations come back with a centroid. Responses are
cached under `data/osm/` so a re-run costs nothing and the script is idempotent:
places are matched on (osm_type, osm_id), so running it twice updates rather
than duplicates.

Every `name:<lang>` tag becomes a `PlaceName` row (that is where names in 22
languages come from for free), and `place=suburb|neighbourhood` nodes become
`Neighbourhood` rows, which is what the fog map counts.

ODbL: "(c) OpenStreetMap contributors" is shown on every seeded place and on
every map (CLAUDE.md invariant 6).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from sqlmodel import Session, select

from app.config import DATA_DIR, cfg, regional_langs
from app.db import engine, init_db, rebuild_fts
from app.models import City, Neighbourhood, Place, PlaceName, utcnow

# Several public mirrors, tried in turn. Overpass is a free shared service and a
# 504 under load is routine, so each mirror gets a couple of attempts before we
# move on; everything successful is cached so a re-run never re-queries.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]
ATTEMPTS_PER_MIRROR = 2

# SPEC §6.1 category table, as Overpass filters. Each entry is a list of
# clauses; a feature matching any clause lands in that category.
CATEGORY_QUERIES: dict[str, list[str]] = {
    "viewpoint": ['node["tourism"="viewpoint"]', 'way["tourism"="viewpoint"]'],
    "waterfall": [
        'node["waterway"="waterfall"]',
        'way["waterway"="waterfall"]',
        'node["natural"="waterfall"]',
    ],
    # Lakes need a reason to be interesting: tourism tagging or a Wikidata id.
    "lake": [
        'way["natural"="water"]["water"~"lake|reservoir"]["wikidata"]',
        'way["natural"="water"]["water"~"lake|reservoir"]["tourism"]',
        'relation["natural"="water"]["water"~"lake|reservoir"]["wikidata"]',
    ],
    "hill_trek": ['node["natural"="peak"]', 'node["natural"="rock"]', 'way["natural"="rock"]'],
    "fort_heritage": [
        'way["historic"~"fort|castle|ruins|monument|archaeological_site|tomb"]',
        'node["historic"~"fort|castle|ruins|monument|archaeological_site|tomb"]',
        'relation["historic"~"fort|castle|ruins|monument|archaeological_site|tomb"]',
    ],
    # Places of worship only when they are also an attraction or notable.
    "temple_sacred": [
        'way["amenity"="place_of_worship"]["tourism"="attraction"]',
        'node["amenity"="place_of_worship"]["tourism"="attraction"]',
        'way["amenity"="place_of_worship"]["wikidata"]',
        'node["amenity"="place_of_worship"]["wikidata"]',
    ],
    # SPEC §6.1: a park counts when it is at least 2 ha or has a Wikidata id.
    # The area test runs in Python, which needs each way's bounding box, so this
    # category is fetched with `out bb` instead of `out center` (see CATEGORY_OUT).
    "park_garden": [
        'way["leisure"~"park|garden|nature_reserve"]["wikidata"]',
        'way["leisure"~"park|garden|nature_reserve"]["name"]',
        'relation["leisure"~"park|garden|nature_reserve"]["wikidata"]',
    ],
    "museum_art": [
        'node["tourism"~"museum|gallery|artwork"]',
        'way["tourism"~"museum|gallery|artwork"]',
    ],
    "market_street": [
        'node["tourism"="attraction"]["amenity"="marketplace"]',
        'way["tourism"="attraction"]["amenity"="marketplace"]',
        'way["tourism"="attraction"]["highway"="pedestrian"]',
    ],
    "beach_river": [
        'node["natural"="beach"]',
        'way["natural"="beach"]',
        'node["man_made"="ghat"]',
        'way["man_made"="ghat"]',
    ],
    "other": ['node["tourism"="attraction"]', 'way["tourism"="attraction"]'],
}

# Park/garden needs an area check. Overpass's `area()` evaluator is not
# accepted in an `(if:)` filter on these mirrors (HTTP 400), so we ask for each
# way's bounding box and do the arithmetic here.
MIN_PARK_AREA_HA = 2.0

# Overpass honours one geometry mode per query: `center` gives a centroid and no
# bounds, `bb` gives bounds and no centroid. Categories that need an area test
# take `bb`, and `centre_of` derives the centre from the bounds.
CATEGORY_OUT: dict[str, str] = {"park_garden": "bb tags"}
DEFAULT_OUT = "center tags"


def cache_dir() -> Path:
    path = DATA_DIR / "osm"
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_query(bbox: list[float], clauses: list[str], out: str = DEFAULT_OUT) -> str:
    """One Overpass QL query for a category.

    Named features only, inside the city bbox. `out` picks the geometry mode:
    `center tags` for a centroid (most categories), `bb tags` for bounds, which
    the park area rule needs (SPEC §6.1).
    """
    south, west, north, east = bbox
    box = f"({south},{west},{north},{east})"
    parts: list[str] = []
    for clause in clauses:
        # Add the `["name"]` filter only when the clause has not asked for it,
        # so a clause can be specific without ending up with it twice.
        named = clause if '["name"]' in clause else f'{clause}["name"]'
        parts.append(f"{named}{box};")
    body = "\n  ".join(parts)
    return f"[out:json][timeout:120];\n(\n  {body}\n);\nout {out};"


def fetch(query: str, cache_key: str, refresh: bool = False) -> dict[str, Any]:
    """Run a query, or read the cached response. Tries mirrors in turn."""
    cache_file = cache_dir() / f"{cache_key}.json"
    if cache_file.exists() and not refresh:
        return json.loads(cache_file.read_text(encoding="utf-8"))

    headers = {"User-Agent": str(cfg("wikidata.user_agent", "Pagdandi/1.0"))}
    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        for attempt in range(1, ATTEMPTS_PER_MIRROR + 1):
            try:
                print(f"  querying {url} (attempt {attempt})")
                response = httpx.post(url, data={"data": query}, headers=headers, timeout=180.0)
                response.raise_for_status()
                payload = response.json()
                cache_file.write_text(json.dumps(payload), encoding="utf-8")
                time.sleep(2)              # be polite to a free, shared service
                return payload
            except Exception as exc:       # noqa: BLE001 - retry, then next mirror
                last_error = exc
                print(f"  ! {type(exc).__name__}: {str(exc)[:120]}")
                if attempt < ATTEMPTS_PER_MIRROR:
                    time.sleep(5)
    raise RuntimeError(f"Overpass failed on every mirror: {last_error}")


def centre_of(element: dict) -> tuple[float, float] | None:
    """Coordinates of a node, or the centroid Overpass computed for a way."""
    if element.get("type") == "node":
        if "lat" in element and "lon" in element:
            return (float(element["lat"]), float(element["lon"]))
        return None
    centre = element.get("center")
    if centre:
        return (float(centre["lat"]), float(centre["lon"]))
    bounds = element.get("bounds")
    if bounds:
        # `out bb` returns bounds and no centroid; the middle of the box is a
        # good enough centre for a park, and it is what we show on the map.
        return (
            (float(bounds["minlat"]) + float(bounds["maxlat"])) / 2,
            (float(bounds["minlon"]) + float(bounds["maxlon"])) / 2,
        )
    return None


def bbox_area_ha(element: dict) -> float | None:
    """Rough area in hectares from the element's bounds, for the park filter."""
    bounds = element.get("bounds")
    if not bounds:
        return None
    lat_span = abs(float(bounds["maxlat"]) - float(bounds["minlat"])) * 111_320.0
    lng_span = abs(float(bounds["maxlon"]) - float(bounds["minlon"])) * 111_320.0
    return (lat_span * lng_span) / 10_000.0


def names_from_tags(tags: dict[str, str]) -> dict[str, str]:
    """Every `name:<lang>` tag we support, plus the plain `name` as English.

    `name` is not necessarily English, but in Indian cities it is overwhelmingly
    the Latin-script form, which is what the English line of the name block
    wants. A real Wikidata label later overrides it by source precedence.
    """
    supported = set(cfg("languages") or [])
    out: dict[str, str] = {}
    if tags.get("name"):
        out["en"] = tags["name"].strip()
    for key, value in tags.items():
        if not key.startswith("name:") or not value.strip():
            continue
        lang = key.split(":", 1)[1]
        if lang in supported:
            out[lang] = value.strip()
    if tags.get("name:en"):
        out["en"] = tags["name:en"].strip()
    return out


def fame_for(tags: dict[str, str]) -> str:
    """SPEC §6.7: an OSM item with a Wikipedia link is famous, else known."""
    if tags.get("wikipedia"):
        return "famous"
    return "known"


def access_from_tags(tags: dict[str, str]) -> dict[str, Any]:
    return {
        "road": tags.get("surface") or "",
        "walk_min_from_road": None,
        "nearest_transit_text": "",
        "parking": tags.get("parking") or "",
    }


def accessibility_from_tags(tags: dict[str, str]) -> dict[str, Any]:
    wheelchair = tags.get("wheelchair")
    return {
        "wheelchair": wheelchair if wheelchair in ("yes", "limited", "no") else "unknown",
        "steps_count_text": "",
        "toilets": tags.get("toilets") or "unknown",
        "drinking_water": tags.get("drinking_water") or "unknown",
        "shade": "unknown",
        "food_nearby": "unknown",
    }


def nearest_area(lat: float, lng: float, hoods: list[Neighbourhood]) -> str:
    """The nearest neighbourhood node, used as the place's area label."""
    from app.geo import haversine_km

    if not hoods:
        return ""
    best = min(hoods, key=lambda h: haversine_km(lat, lng, h.lat, h.lng))
    return best.name


def seed_neighbourhoods(session: Session, city: City, refresh: bool) -> int:
    """`place=suburb|neighbourhood` nodes -> Neighbourhood rows (AC-1)."""
    query = build_query(
        city.bbox,
        ['node["place"~"^(suburb|neighbourhood)$"]'],
    )
    payload = fetch(query, f"{city.slug}-neighbourhoods", refresh)
    added = 0
    for element in payload.get("elements", []):
        coords = centre_of(element)
        name = (element.get("tags") or {}).get("name")
        if coords is None or not name:
            continue
        existing = session.exec(
            select(Neighbourhood).where(
                Neighbourhood.city_id == city.id, Neighbourhood.name == name
            )
        ).first()
        if existing is not None:
            existing.lat, existing.lng = coords
            session.add(existing)
            continue
        session.add(
            Neighbourhood(city_id=int(city.id), name=name, lat=coords[0], lng=coords[1])
        )
        added += 1
    session.commit()
    return added


def upsert_place(
    session: Session,
    city: City,
    category: str,
    element: dict,
    hoods: list[Neighbourhood],
) -> tuple[Place | None, bool]:
    """Create or update one place from an Overpass element. (place, created)."""
    tags = element.get("tags") or {}
    coords = centre_of(element)
    if coords is None or not tags.get("name"):
        return (None, False)

    osm_type = str(element.get("type"))
    osm_id = int(element.get("id"))
    lat, lng = coords

    existing = session.exec(
        select(Place).where(Place.osm_type == osm_type, Place.osm_id == osm_id)
    ).first()
    created = existing is None
    place = existing or Place(source="osm")

    place.city_id = int(city.id)
    place.state = city.state
    place.lat, place.lng = lat, lng
    place.category = category
    place.source = "osm"
    place.osm_type = osm_type
    place.osm_id = osm_id
    place.wikidata = tags.get("wikidata") or place.wikidata
    place.fame = fame_for(tags)
    # Seeded places are verified: they are in a public, reviewed dataset.
    place.status = "verified"
    place.area = nearest_area(lat, lng, hoods)
    place.tags = sorted({k for k in ("historic", "tourism", "natural", "leisure") if tags.get(k)})
    place.entry_fee_text = tags.get("fee") or place.entry_fee_text
    place.timings_text = tags.get("opening_hours") or place.timings_text
    place.access = access_from_tags(tags) or place.access
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
            session.add(
                PlaceName(place_id=int(place.id), lang=lang, name=name, source="osm")
            )
        else:
            row.name = name
            session.add(row)
    session.commit()
    return (place, created)


def seed_city(slug: str, refresh: bool = False) -> dict[str, Any]:
    """Seed every category for one configured city."""
    cities = cfg("cities", {}) or {}
    if slug not in cities:
        raise SystemExit(f"'{slug}' is not in config.yaml -> cities. Add it first.")
    spec = cities[slug]

    init_db()
    with Session(engine) as session:
        city = session.exec(select(City).where(City.slug == slug)).first()
        if city is None:
            city = City(slug=slug, name_en=spec["name"], state=spec["state"])
        city.name_en = spec["name"]
        city.state = spec["state"]
        city.bbox = list(spec["bbox"])
        centre = spec.get("centre") or [
            (spec["bbox"][0] + spec["bbox"][2]) / 2,
            (spec["bbox"][1] + spec["bbox"][3]) / 2,
        ]
        city.centre_lat, city.centre_lng = float(centre[0]), float(centre[1])
        city.regional_langs = regional_langs(spec["state"])
        session.add(city)
        session.commit()
        session.refresh(city)

        print(f"Seeding {city.name_en} ({city.state}) from OpenStreetMap")
        hood_count = seed_neighbourhoods(session, city, refresh)
        hoods = list(
            session.exec(select(Neighbourhood).where(Neighbourhood.city_id == city.id)).all()
        )
        print(f"  neighbourhoods: +{hood_count} (total {len(hoods)})")

        created_total = 0
        updated_total = 0
        per_category: dict[str, int] = {}

        for category, clauses in CATEGORY_QUERIES.items():
            print(f"  category {category}")
            try:
                payload = fetch(
                    build_query(city.bbox, clauses, CATEGORY_OUT.get(category, DEFAULT_OUT)),
                    f"{city.slug}-{category}",
                    refresh,
                )
            except RuntimeError as exc:
                print(f"  ! skipping {category}: {exc}")
                continue

            count = 0
            for element in payload.get("elements", []):
                tags = element.get("tags") or {}
                # The 2 ha rule from SPEC §6.1, for parks with no Wikidata id.
                if category == "park_garden" and not tags.get("wikidata"):
                    area = bbox_area_ha(element)
                    if area is None or area < MIN_PARK_AREA_HA:
                        continue
                place, created = upsert_place(session, city, category, element, hoods)
                if place is None:
                    continue
                count += 1
                created_total += int(created)
                updated_total += int(not created)
            per_category[category] = count
            print(f"    {count} places")

        rebuild_fts()
        total = session.exec(select(Place).where(Place.city_id == city.id)).all()
        names = session.exec(select(PlaceName)).all()

    summary = {
        "city": slug,
        "created": created_total,
        "updated": updated_total,
        "places_total": len(total),
        "neighbourhoods": len(hoods),
        "per_category": per_category,
        "placename_rows": len(names),
    }
    print("\nSummary (put these in PLAN.md 'Measured values'):")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a city from OpenStreetMap")
    parser.add_argument("--city", default=str(cfg("city_default", "hyderabad")))
    parser.add_argument(
        "--refresh", action="store_true", help="ignore the cache and re-query Overpass"
    )
    args = parser.parse_args()
    seed_city(args.city, args.refresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
