"""Undo most of a `seed_osm_states` run: keep only the genuinely famous finds.

A plain OSM `name` tag is not fame -- half of India's rocks and footbridges
have one. This removes every place the run added that has neither an OSM
`wikipedia` tag (-> `fame="famous"`) nor a `wikidata` id: the two real
notability signals the importer can check without asking a person. It is a
one-time correction for a run that was too broad, not a general tool.

    python -m scripts.undo_state_seed --since 2026-10-23 --dry-run
    python -m scripts.undo_state_seed --since 2026-10-23
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text
from sqlmodel import Session, select

from app.db import engine, rebuild_fts
from app.models import Place


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", required=True, help="only touch places created on/after this date")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with Session(engine) as session:
        ids = [
            int(row[0])
            for row in session.exec(
                text(
                    "select id from place where source = 'osm' and city_id is null "
                    "and created_at >= :since and fame != 'famous' "
                    "and (wikidata is null or wikidata = '')"
                ).bindparams(since=args.since)
            ).all()
        ]
        print(f"{len(ids)} places to remove (no wikipedia tag, no wikidata id).")
        if args.dry_run or not ids:
            print("Dry run: nothing changed." if args.dry_run else "Nothing to do.")
            return 0

        tables = [
            row[0]
            for row in session.exec(
                text("select name from sqlite_master where type = 'table' and name != 'place'")
            ).all()
        ]
        removed = 0
        for pid in ids:
            for table in tables:
                columns = [c[1] for c in session.exec(text(f'pragma table_info("{table}")')).all()]
                if "place_id" in columns and not table.startswith("placename_fts"):
                    session.exec(text(f'delete from "{table}" where place_id = :p').bindparams(p=pid))
            session.exec(text("delete from place where id = :p").bindparams(p=pid))
            removed += 1
            if removed % 200 == 0:
                print(f"  ...{removed}/{len(ids)}")
        session.commit()
        rebuild_fts()
        print(f"Removed {removed} places.")

        kept = len(
            session.exec(
                select(Place.id).where(
                    Place.source == "osm", Place.city_id == None,  # noqa: E711
                    Place.created_at >= args.since,
                )
            ).all()
        )
        print(f"{kept} places from this run were kept (famous, or a wikidata id).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
