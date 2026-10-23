"""Seed famous places across all of India from Wikidata (SPEC §6.2, AC-2).

    python -m scripts.seed_wikidata                 # every configured class
    python -m scripts.seed_wikidata --verify        # check the class QIDs first
    python -m scripts.seed_wikidata --classes Q34038 Q23397

Wikidata is CC0, so we may store it outright; we credit it anyway. One SPARQL
query **per class** keeps each request under the 60 s service timeout, and every
response is cached under `data/wikidata/` so re-runs are free and idempotent
(places are matched on their Q-id).

Per item we take: labels in English and all 22 scheduled languages (that is
where most of our multilingual names come from), coordinates, the P18 image
filename, the sitelink count (which decides `fame`), a Wikivoyage sitelink, any
heritage designation, and the **state** by walking `P131*` up to an item that is
an instance/subclass of an Indian state or union territory. No boundary files
are needed, which also keeps us clear of the map-boundary rules in SPEC §14.
"""
from __future__ import annotations

import argparse
from urllib.parse import unquote
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from sqlmodel import Session, select

from app.config import DATA_DIR, cfg
from app.db import engine, init_db, rebuild_fts
from app.models import City, Media, Place, PlaceName, utcnow

SPARQL_URL = "https://query.wikidata.org/sparql"

# Q-id -> our category. Verified with --verify before a full run.
CLASS_CATEGORIES: dict[str, str] = {
    "Q570116": "other",            # tourist attraction
    "Q33506": "museum_art",        # museum
    "Q34038": "waterfall",         # waterfall
    "Q23397": "lake",              # lake
    "Q8502": "hill_trek",          # mountain
    "Q40080": "beach_river",       # beach
    "Q22698": "park_garden",       # park
    "Q46169": "park_garden",       # national park
    "Q179049": "park_garden",      # nature reserve
    "Q1107656": "park_garden",     # garden
    "Q23413": "fort_heritage",     # castle
    "Q57821": "fort_heritage",     # fortification
    "Q44539": "temple_sacred",     # temple
    "Q4989906": "fort_heritage",   # monument
    "Q839954": "fort_heritage",    # archaeological site
    "Q35509": "hill_trek",         # cave
    # Classes SPEC §6.2 asks Phase 1 to add, each checked with --verify.
    # Four of the first guesses were wrong -- Q842425 is a chef, Q1066288 is
    # "figurine", Q2082441 is a record producer and Q1129447 has no English
    # label -- which is exactly why the SPEC asks for the check.
    "Q842402": "temple_sacred",    # Hindu temple
    "Q32815": "temple_sacred",     # mosque
    "Q16970": "temple_sacred",     # church building
    "Q337986": "temple_sacred",    # gurdwara
    "Q2613100": "temple_sacred",   # Jain temple
    "Q2639699": "temple_sacred",   # dargah
    "Q1473950": "beach_river",     # stepwell
    "Q1010155": "beach_river",     # ghat
    "Q16560": "fort_heritage",     # palace
    "Q2393184": "hill_trek",       # hill station
}

# India, and the two classes that mean "a state or UT of India".
INDIA = "wd:Q668"
STATE_CLASSES = ["wd:Q12443800", "wd:Q131541"]   # state of India, UT of India


def cache_dir() -> Path:
    path = DATA_DIR / "wikidata"
    path.mkdir(parents=True, exist_ok=True)
    return path


def headers() -> dict[str, str]:
    """A descriptive User-Agent is required by the query service's policy."""
    return {
        "User-Agent": str(cfg("wikidata.user_agent", "Truvel/1.0")),
        "Accept": "application/sparql-results+json",
    }


def run_sparql(query: str, cache_key: str, refresh: bool = False) -> dict[str, Any]:
    cache_file = cache_dir() / f"{cache_key}.json"
    if cache_file.exists() and not refresh:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    response = httpx.get(
        SPARQL_URL, params={"query": query, "format": "json"}, headers=headers(), timeout=120.0
    )
    response.raise_for_status()
    payload = response.json()
    cache_file.write_text(json.dumps(payload), encoding="utf-8")
    time.sleep(1.5)
    return payload


def verify_query(qids: list[str]) -> str:
    """One query that returns the English label of each configured class."""
    values = " ".join(f"wd:{q}" for q in qids)
    return f"""
SELECT ?cls ?clsLabel WHERE {{
  VALUES ?cls {{ {values} }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def verify_state_classes() -> str:
    return f"""
SELECT ?state ?stateLabel WHERE {{
  ?state wdt:P31 ?cls .
  VALUES ?cls {{ {" ".join(STATE_CLASSES)} }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
ORDER BY ?stateLabel
"""


def items_query(class_qid: str, languages: list[str]) -> str:
    """Items of one class in India, with labels, image, sitelinks, state and locality.

    `P131*` walks the administrative hierarchy to any depth, so a temple inside
    a district inside a state still resolves to the state. `?locality` is the
    single nearest step of that same chain -- usually the city or town the
    item is actually in ("Tirupati"), which is what search needs to let
    someone browse a town the way it already lets them browse a state;
    `OPTIONAL` keeps an item that has no image, state or locality.
    """
    codes = ["en"] + [code for code in languages if code != "en"]
    lang_list = ",".join(codes)
    label_langs = ",".join(f'"{code}"' for code in codes)
    return f"""
SELECT ?item ?coord ?image ?sitelinks ?state ?stateLabel ?locality ?localityLabel ?heritage ?voyage
       (GROUP_CONCAT(DISTINCT CONCAT(?labelLang, "\\u001f", ?label); separator="\\u001e") AS ?labels)
WHERE {{
  ?item wdt:P31/wdt:P279* wd:{class_qid} ;
        wdt:P17 {INDIA} ;
        wdt:P625 ?coord ;
        wikibase:sitelinks ?sitelinks .
  OPTIONAL {{ ?item wdt:P18 ?image. }}
  OPTIONAL {{ ?item wdt:P1435 ?heritage. }}
  OPTIONAL {{
    ?item wdt:P131* ?state .
    VALUES ?stateCls {{ {" ".join(STATE_CLASSES)} }}
    ?state wdt:P31 ?stateCls .
  }}
  OPTIONAL {{ ?item wdt:P131 ?locality. }}
  OPTIONAL {{ ?voyage schema:about ?item ; schema:isPartOf <https://en.wikivoyage.org/>. }}
  ?item rdfs:label ?label .
  BIND(LANG(?label) AS ?labelLang)
  FILTER(?labelLang IN ({label_langs}))
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{lang_list}". }}
}}
GROUP BY ?item ?coord ?image ?sitelinks ?state ?stateLabel ?locality ?localityLabel ?heritage ?voyage
"""


def parse_point(wkt: str) -> tuple[float, float] | None:
    """'Point(78.4 17.3)' -> (17.3, 78.4). Wikidata puts longitude first."""
    if not wkt or not wkt.startswith("Point("):
        return None
    try:
        lng_s, lat_s = wkt[len("Point(") : -1].split()
        return (float(lat_s), float(lng_s))
    except ValueError:
        return None


def parse_labels(blob: str) -> dict[str, str]:
    """Unpack the GROUP_CONCAT of 'lang<US>label' pairs."""
    out: dict[str, str] = {}
    if not blob:
        return out
    for pair in blob.split("\u001e"):
        if "\u001f" not in pair:
            continue
        lang, label = pair.split("\u001f", 1)
        lang, label = lang.strip(), label.strip()
        if lang and label and lang not in out:
            out[lang] = label
    return out


def fame_for(sitelinks: int) -> str:
    """SPEC §6.7: famous at or above the configured sitelink threshold."""
    threshold = int(cfg("wikidata.famous_sitelinks", 15))
    return "famous" if sitelinks >= threshold else "known"


def city_for(session: Session, lat: float, lng: float) -> City | None:
    """The seeded city whose bbox contains the point, if any."""
    for city in session.exec(select(City)).all():
        bbox = city.bbox or []
        if len(bbox) == 4 and bbox[0] <= lat <= bbox[2] and bbox[1] <= lng <= bbox[3]:
            return city
    return None


def upsert_item(session: Session, row: dict, category: str) -> tuple[Place | None, bool]:
    """Create or update one place from a SPARQL row, merging with OSM by Q-id."""
    qid = row["item"]["value"].rsplit("/", 1)[-1]
    coords = parse_point((row.get("coord") or {}).get("value", ""))
    if coords is None:
        return (None, False)
    lat, lng = coords
    labels = parse_labels((row.get("labels") or {}).get("value", ""))
    if not labels:
        return (None, False)

    sitelinks = int((row.get("sitelinks") or {}).get("value", 0) or 0)
    state = (row.get("stateLabel") or {}).get("value") or None
    locality = (row.get("localityLabel") or {}).get("value") or None
    if locality and ((state and locality == state) or locality in ("India", "Bharat")):
        # The one-hop P131 landed on the state, or on the country itself (a
        # very sparsely tagged item): neither is a town to browse.
        locality = None
    image = (row.get("image") or {}).get("value") or ""
    heritage = bool((row.get("heritage") or {}).get("value"))
    voyage = (row.get("voyage") or {}).get("value") or ""

    # Merge with an OSM place that already carries this Wikidata id (SPEC §6.2).
    existing = session.exec(select(Place).where(Place.wikidata == qid)).first()
    created = existing is None
    place = existing or Place(source="wikidata")

    if place.source != "osm":
        # Do not move an OSM place: its geometry came from a surveyed dataset.
        place.lat, place.lng = lat, lng
        place.category = category
        place.source = "wikidata"
    place.wikidata = qid
    place.sitelinks = sitelinks
    place.fame = fame_for(sitelinks)
    place.status = "verified"
    if state and not place.state:
        place.state = state
    if locality and not place.locality:
        place.locality = locality
    city = city_for(session, place.lat, place.lng)
    if city is not None:
        place.city_id = int(city.id)
        place.state = place.state or city.state
    tags = set(place.tags or [])
    if heritage:
        tags.add("heritage")
    if voyage:
        tags.add("wikivoyage")
    place.tags = sorted(tags)
    place.updated_at = utcnow()
    session.add(place)
    session.commit()
    session.refresh(place)

    supported = set(cfg("languages") or [])
    for lang, label in labels.items():
        if lang not in supported:
            continue
        row_db = session.exec(
            select(PlaceName).where(
                PlaceName.place_id == place.id,
                PlaceName.lang == lang,
                PlaceName.source == "wikidata",
            )
        ).first()
        if row_db is None:
            session.add(
                PlaceName(place_id=int(place.id), lang=lang, name=label, source="wikidata")
            )
        else:
            row_db.name = label
            session.add(row_db)

    # The P18 filename is recorded now; the bytes and licence are fetched lazily
    # on first view by `app.commons` (SPEC §6.3), which is also where the
    # licence allowlist is enforced.
    if image:
        # Wikidata gives a percent-encoded URL ("Sankey%20Tank.jpg"); Commons wants the
        # plain title, so decode it first or every lookup misses.
        filename = unquote(image.rsplit("/", 1)[-1]).replace("_", " ")
        has_photo = session.exec(
            select(Media).where(Media.place_id == place.id, Media.source == "commons")
        ).first()
        if has_photo is None:
            session.add(
                Media(
                    place_id=int(place.id),
                    user_id=None,
                    kind="photo",
                    path_display=filename,       # resolved by the Commons proxy
                    caption=labels.get("en", "Photo of this place"),
                    lang="en",
                    source="commons",
                    licence="",                  # filled in when fetched
                    attribution="",
                    source_url=(
                        "https://commons.wikimedia.org/wiki/File:"
                        + filename.replace(" ", "_")
                    ),
                    status="ok",
                )
            )
    session.commit()
    return (place, created)


def verify(classes: list[str]) -> None:
    """Print each class QID with its label, and the Indian state/UT list."""
    print("Verifying class QIDs against the query service...")
    payload = run_sparql(verify_query(classes), "verify-classes", refresh=True)
    found = {
        b["cls"]["value"].rsplit("/", 1)[-1]: b["clsLabel"]["value"]
        for b in payload["results"]["bindings"]
    }
    for qid in classes:
        label = found.get(qid)
        mark = "ok  " if label else "MISS"
        print(f"  [{mark}] {qid}: {label or 'not found -- remove it from config'}")

    print("\nStates and union territories of India:")
    states = run_sparql(verify_state_classes(), "verify-states", refresh=True)
    names = sorted({b["stateLabel"]["value"] for b in states["results"]["bindings"]})
    for name in names:
        in_config = name in (cfg("state_languages", {}) or {})
        print(f"  [{'cfg' if in_config else '   '}] {name}")
    missing = [n for n in names if n not in (cfg("state_languages", {}) or {})]
    if missing:
        print(f"\n{len(missing)} state(s) have no regional language in config.yaml:")
        print("  " + ", ".join(missing))


def seed(classes: list[str], refresh: bool = False, limit_classes: int | None = None) -> dict:
    init_db()
    languages = list(cfg("languages") or [])
    summary: dict[str, Any] = {"per_class": {}, "created": 0, "updated": 0}

    with Session(engine) as session:
        for index, qid in enumerate(classes):
            if limit_classes is not None and index >= limit_classes:
                break
            category = CLASS_CATEGORIES.get(qid, "other")
            print(f"Class {qid} -> {category}")
            try:
                # v2: the query now also asks for ?locality, so a v1 cache file
                # (same class, an older query) must not be reused silently.
                payload = run_sparql(items_query(qid, languages), f"class-{qid}-v2", refresh)
            except Exception as exc:  # noqa: BLE001 - one class failing is survivable
                print(f"  ! {type(exc).__name__}: {exc} (skipping)")
                summary["per_class"][qid] = "failed"
                continue

            rows = payload["results"]["bindings"]
            created = updated = 0
            for row in rows:
                place, was_created = upsert_item(session, row, category)
                if place is None:
                    continue
                created += int(was_created)
                updated += int(not was_created)
            summary["per_class"][qid] = {"rows": len(rows), "created": created, "updated": updated}
            summary["created"] += created
            summary["updated"] += updated
            print(f"  {len(rows)} rows -> +{created} new, {updated} updated")

        rebuild_fts()
        places = session.exec(select(Place)).all()
        names = session.exec(select(PlaceName)).all()
        by_lang: dict[str, int] = {}
        for name in names:
            by_lang[name.lang] = by_lang.get(name.lang, 0) + 1

    summary["places_total"] = len(places)
    summary["names_by_lang"] = dict(sorted(by_lang.items(), key=lambda kv: -kv[1]))
    print("\nSummary (put these in PLAN.md 'Measured values'):")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed famous Indian places from Wikidata")
    parser.add_argument("--verify", action="store_true", help="check QIDs and states, seed nothing")
    parser.add_argument("--classes", nargs="*", help="only these class QIDs")
    parser.add_argument("--refresh", action="store_true", help="ignore the cache")
    parser.add_argument("--max-classes", type=int, default=None)
    args = parser.parse_args()

    configured = list(cfg("wikidata.classes") or [])
    extra = [q for q in CLASS_CATEGORIES if q not in configured]
    classes = args.classes or (configured + extra)

    if args.verify:
        verify(classes)
        return 0
    seed(classes, args.refresh, args.max_classes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
