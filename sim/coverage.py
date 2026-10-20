"""What the seeded data actually covers (SPEC §17 item 7).

Counts of places per state and per category, the share with a photo, and the
share with a name in each of the 22 scheduled languages -- including, and
especially, where coverage is weak. A table that only showed the strong
languages would be worse than no table.

    python sim/coverage.py
"""
from __future__ import annotations

import argparse

from common import write_results  # noqa: E402

from sqlmodel import Session, func, select  # noqa: E402

from app.config import cfg  # noqa: E402
from app.db import engine  # noqa: E402
from app.models import Media, Place, PlaceName  # noqa: E402

LANG_NAMES = {
    "en": "English", "hi": "Hindi", "mr": "Marathi", "ne": "Nepali", "sa": "Sanskrit",
    "gom": "Konkani", "mai": "Maithili", "doi": "Dogri", "brx": "Bodo", "bn": "Bengali",
    "as": "Assamese", "gu": "Gujarati", "pa": "Punjabi", "or": "Odia", "te": "Telugu",
    "ta": "Tamil", "kn": "Kannada", "ml": "Malayalam", "ur": "Urdu", "ks": "Kashmiri",
    "sd": "Sindhi", "sat": "Santali", "mni": "Manipuri",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Data coverage table (SPEC §17 item 7)")
    parser.add_argument("--markdown", action="store_true", help="also write coverage.md")
    args = parser.parse_args()

    with Session(engine) as session:
        total = int(session.exec(select(func.count()).select_from(Place)).one() or 0)
        if not total:
            print("No places seeded yet. Run scripts/seed_osm.py and scripts/seed_wikidata.py.")
            return 1

        by_state = {
            str(state or "(unknown)"): int(count)
            for state, count in session.exec(
                select(Place.state, func.count()).group_by(Place.state).order_by(func.count().desc())
            ).all()
        }
        by_category = {
            str(category): int(count)
            for category, count in session.exec(
                select(Place.category, func.count())
                .group_by(Place.category)
                .order_by(func.count().desc())
            ).all()
        }
        by_source = {
            str(source): int(count)
            for source, count in session.exec(
                select(Place.source, func.count()).group_by(Place.source)
            ).all()
        }
        by_fame = {
            str(fame): int(count)
            for fame, count in session.exec(
                select(Place.fame, func.count()).group_by(Place.fame)
            ).all()
        }
        with_photo = int(
            session.exec(
                select(func.count(func.distinct(Media.place_id))).where(Media.status == "ok")
            ).one()
            or 0
        )
        by_lang = {
            str(lang): int(count)
            for lang, count in session.exec(
                select(PlaceName.lang, func.count(func.distinct(PlaceName.place_id))).group_by(
                    PlaceName.lang
                )
            ).all()
        }

    languages = list(cfg("languages") or [])
    language_rows = []
    for lang in languages:
        count = by_lang.get(lang, 0)
        language_rows.append(
            {
                "lang": lang,
                "name": LANG_NAMES.get(lang, lang),
                "places": count,
                "share": round(count / total, 4),
            }
        )
    language_rows.sort(key=lambda row: -row["places"])

    metrics = {
        "places_total": total,
        "with_photo": with_photo,
        "photo_share": round(with_photo / total, 4),
        "by_source": by_source,
        "by_fame": by_fame,
        "by_category": by_category,
        "states_covered": len(by_state),
        "by_state": by_state,
        "names_by_language": language_rows,
        "languages_with_no_names": [
            row["lang"] for row in language_rows if row["places"] == 0
        ],
    }

    print(f"\nPlaces: {total:,}   with a photo: {with_photo:,} ({with_photo / total:.1%})")
    print(f"States and UTs covered: {len(by_state)}")
    print("\nBy source:   " + ", ".join(f"{k} {v:,}" for k, v in by_source.items()))
    print("By fame:     " + ", ".join(f"{k} {v:,}" for k, v in by_fame.items()))
    print("\nTop states:")
    for state, count in list(by_state.items())[:12]:
        print(f"  {state:<34} {count:>7,}")
    print("\nBy category:")
    for category, count in by_category.items():
        print(f"  {category:<34} {count:>7,}")
    print("\nPlaces with a name in each language:")
    for row in language_rows:
        bar = "#" * int(row["share"] * 40)
        print(f"  {row['name']:<12} {row['lang']:<4} {row['places']:>7,}  {row['share']:>6.1%} {bar}")
    missing = metrics["languages_with_no_names"]
    if missing:
        print(
            "\n  No names at all in: "
            + ", ".join(f"{LANG_NAMES.get(l, l)} ({l})" for l in missing)
        )
        print("  These are the gaps Tier-2 transliteration (SPEC §9.12) would fill.")

    path = write_results(
        "coverage",
        metrics,
        seeds=[],
        assumptions=[
            "Counted from the local database as seeded; not a claim about India.",
            "'With a photo' counts places with any media row, including a Wikimedia "
            "Commons image recorded but not yet fetched.",
            "A place counts for a language if it has any name row in it, from any source.",
        ],
    )

    if args.markdown:
        lines = [
            "# Data coverage",
            "",
            f"{total:,} places, {with_photo:,} with a photo ({with_photo / total:.1%}), "
            f"across {len(by_state)} states and union territories.",
            "",
            "## Names per language",
            "",
            "| Language | Code | Places | Share |",
            "|---|---|---:|---:|",
        ]
        for row in language_rows:
            lines.append(
                f"| {row['name']} | `{row['lang']}` | {row['places']:,} | {row['share']:.1%} |"
            )
        lines += ["", "## Places per category", "", "| Category | Places |", "|---|---:|"]
        for category, count in by_category.items():
            lines.append(f"| {category} | {count:,} |")
        lines += ["", "## Places per state", "", "| State / UT | Places |", "|---|---:|"]
        for state, count in by_state.items():
            lines.append(f"| {state} | {count:,} |")
        (path / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (path.parent / "latest" / "coverage.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    print(f"\nWrote {path}")
    return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
