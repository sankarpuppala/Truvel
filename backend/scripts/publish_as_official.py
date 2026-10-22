"""Make the official account the publisher of every place, and tidy the catalogue.

Imported places have no person who found them. The product decision is that
they are *posted by* the official @truvel account, so the place page can say
"Posted by @truvel" and people who add their own places stand apart from it.
Because the account is a publisher and not a person, the app never pays it
kadam, never credits it with visits and never lists it in the Partner Program
(see `User.official`).

Also:
  * removes viewpoints that have no photograph (mis-tagged OpenStreetMap nodes),
  * marks little-known places that have a credited photograph as `hidden`
    fame, so the Hidden gems tab has honest cold-start content.

    python -m scripts.publish_as_official [--password ...]
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text
from sqlmodel import Session, select

from app import auth
from app.db import engine, rebuild_fts
from app.models import User

HAS_PHOTO = (
    "exists (select 1 from media m where m.place_id = p.id "
    "and m.status = 'ok' and m.licence != '')"
)


def remove_photoless_viewpoints(session: Session) -> int:
    """Viewpoint places with no credited photograph, and nothing anyone did to them."""
    ids = [
        int(row[0])
        for row in session.exec(
            text(
                "select p.id from place p where p.category = 'viewpoint' "
                f"and p.source = 'osm' and not {HAS_PHOTO}"
            )
        ).all()
    ]
    tables = [
        row[0]
        for row in session.exec(
            text("select name from sqlite_master where type = 'table' and name != 'place'")
        ).all()
    ]
    for pid in ids:
        for table in tables:
            columns = [c[1] for c in session.exec(text(f'pragma table_info("{table}")')).all()]
            if "place_id" in columns and not table.startswith("placename_fts"):
                session.exec(text(f'delete from "{table}" where place_id = :p').bindparams(p=pid))
        session.exec(text("delete from place where id = :p").bindparams(p=pid))
    session.commit()
    return len(ids)


def mark_hidden_fame(session: Session) -> int:
    """Photographed places with no Wikidata entry and no Wikipedia pages are hidden."""
    result = session.exec(
        text(
            "update place as p set fame = 'hidden' "
            "where (p.wikidata is null or p.wikidata = '') and p.sitelinks = 0 "
            f"and p.fragile = 0 and {HAS_PHOTO}"
        )
    )
    session.commit()
    return int(result.rowcount or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--password", default="")
    args = parser.parse_args()

    with Session(engine) as session:
        official = session.exec(select(User).where(User.official == True)).first()  # noqa: E712
        if official is None:
            print("No official account yet; run scripts.official_account first.")
            return 1
        if args.password:
            auth.validate_password(
                args.password, email=official.email, username=official.username
            )
            official.password_hash = auth.hash_password(args.password)
            session.add(official)
            session.commit()
            print(f"Password set for @{official.username}.")

        removed = remove_photoless_viewpoints(session)
        print(f"Removed {removed} photo-less viewpoints.")
        hidden = mark_hidden_fame(session)
        print(f"Marked {hidden} photographed, little-known places as hidden gems.")

        result = session.exec(
            text("update place set added_by = :u where added_by is null").bindparams(
                u=int(official.id)
            )
        )
        session.commit()
        print(f"{result.rowcount} places now posted by @{official.username}.")
    rebuild_fts()
    return 0


if __name__ == "__main__":
    sys.exit(main())
