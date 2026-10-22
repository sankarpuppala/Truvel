"""Clear the demo population and leave one official account behind.

The demo data in `demo_data.py` exists so the nine screens can be judged with
something in them. It is, by construction, invented: 252 accounts, their likes,
views, visits, tips, live reports and last-mile directions, plus four places
that do not exist. None of it should be mistaken for real use.

This script takes the database the other way. It keeps only what came from a
source we can name -- OpenStreetMap, Wikidata and Wikimedia Commons -- attributes
every place to the app's own account, and leaves every counter at zero. What is
left is true, and empty, which is what a product looks like before anyone has
used it.

    python -m scripts.official_account --reset
    python -m scripts.official_account --reset --email you@example.com

`demo_data.py` still works, so a demo population is one command away again.
"""
from __future__ import annotations

import argparse
import secrets
import sys

from sqlalchemy import delete as sa_delete
from sqlalchemy import text
from sqlmodel import Session, func, select

from app import auth
from app.config import cfg
from app.db import engine, init_db
from app.models import (
    Attribution,
    City,
    CategoryPref,
    EarningLine,
    EarningPeriod,
    Follow,
    KadamEntry,
    LastMileStep,
    LastMileVote,
    Like,
    Media,
    MediaLike,
    MediaView,
    Place,
    PlaceName,
    Pulse,
    Report,
    Save,
    Session as SessionRow,
    Swipe,
    Touch,
    User,
    View,
    Visit,
)

OFFICIAL_USERNAME = "truvel"
OFFICIAL_DISPLAY = "Truvel"
OFFICIAL_BIO = "Discover Hidden India. Places here come from OpenStreetMap, Wikidata and Wikimedia Commons."
DEFAULT_EMAIL = "hello@truvel.app"

# Everything in here is something a person did. None of it survives a reset.
# Children before parents: an Attribution points at a Visit and a vote points
# at a step, so deleting the parent first trips the foreign key.
PEOPLE_TABLES = [
    Like,
    Save,
    View,
    Swipe,
    CategoryPref,
    Pulse,
    Attribution,
    Visit,
    Touch,
    KadamEntry,
    EarningLine,
    EarningPeriod,
    Report,
    Follow,
    MediaLike,
    MediaView,
    LastMileVote,
    LastMileStep,
    SessionRow,
]

# Written onto real places by demo_data: plausible, unsourced, and therefore
# out. Each value is a factory, so no two places end up sharing one dict.
INVENTED_FIELDS: dict[str, object] = {
    "description": str,
    "best_time": dict,
    "entry_fee_text": str,
    "timings_text": str,
    "access": dict,
    "accessibility": dict,
    "safety": dict,
    "activities": list,
}


def add_missing_columns() -> None:
    """Bring an existing database up to the current User table.

    SQLModel creates tables but never alters them, and the project has no
    migration tool on purpose (CLAUDE.md: no Postgres, no Alembic). Two
    `ADD COLUMN`s are cheaper than the tool that would manage them.
    """
    with engine.begin() as connection:
        existing = {
            row[1] for row in connection.execute(text("PRAGMA table_info(user)")).fetchall()
        }
        if "email" not in existing:
            connection.execute(text("ALTER TABLE user ADD COLUMN email TEXT DEFAULT '' NOT NULL"))
            print("  added user.email")
        if "official" not in existing:
            connection.execute(
                text("ALTER TABLE user ADD COLUMN official BOOLEAN DEFAULT 0 NOT NULL")
            )
            print("  added user.official")


def make_passphrase() -> str:
    """Four words and a number: long enough to be strong, short enough to type.

    A demo gets typed in front of people, so a 32-character random string is
    the wrong shape. Length is what makes a password strong (NIST SP 800-63B),
    and four unrelated words are long.
    """
    words = [
        "marigold", "footpath", "granite", "monsoon", "lantern", "harbour",
        "banyan", "terrace", "compass", "kiln", "sandstone", "orchard",
        "stepwell", "ridge", "almond", "cardamom", "estuary", "millet",
    ]
    picked = [secrets.choice(words) for _ in range(4)]
    return "-".join(picked) + "-" + str(secrets.randbelow(9000) + 1000)


def reset(session: Session, email: str, password: str) -> dict:
    before = {
        "users": session.exec(select(func.count()).select_from(User)).one(),
        "places": session.exec(select(func.count()).select_from(Place)).one(),
        "media": session.exec(select(func.count()).select_from(Media)).one(),
    }

    # 1. Everything anyone did.
    for model in PEOPLE_TABLES:
        session.exec(sa_delete(model))
    session.commit()

    # 2. Photos and videos that were generated rather than sourced. A Commons
    #    photo stays: it has an author, a licence and a file page.
    demo_media = session.exec(select(Media).where(Media.source != "commons")).all()
    for item in demo_media:
        session.delete(item)
    session.commit()

    # 3. Places that were invented outright, and their names and photos.
    invented = session.exec(select(Place).where(Place.source == "community")).all()
    for place in invented:
        for name in session.exec(select(PlaceName).where(PlaceName.place_id == place.id)).all():
            session.delete(name)
        for item in session.exec(select(Media).where(Media.place_id == place.id)).all():
            session.delete(item)
        session.delete(place)
    session.commit()

    # 4. Every account.
    for user in session.exec(select(User)).all():
        session.delete(user)
    session.commit()

    # 5. The one account that remains.
    # The default city gives the deck and Explore somewhere to open, the same
    # way a newly registered account gets one (SPEC §8.2).
    home = session.exec(select(City).where(City.slug == str(cfg("city_default")))).first()

    official = User(
        username=OFFICIAL_USERNAME,
        email=email,
        password_hash=auth.hash_password(password),
        display_name=OFFICIAL_DISPLAY,
        bio=OFFICIAL_BIO,
        role="admin",
        official=True,
        home_city_id=home.id if home else None,
    )
    session.add(official)
    session.commit()
    session.refresh(official)

    # 6. Every place is published by the app, and carries only sourced facts.
    stripped = 0
    for place in session.exec(select(Place)).all():
        place.added_by = official.id
        if place.description or place.safety or place.entry_fee_text:
            for field, empty in INVENTED_FIELDS.items():
                setattr(place, field, empty())
            place.fragile = False
            stripped += 1
        session.add(place)
    session.commit()

    after = {
        "users": session.exec(select(func.count()).select_from(User)).one(),
        "places": session.exec(select(func.count()).select_from(Place)).one(),
        "media": session.exec(select(func.count()).select_from(Media)).one(),
    }
    return {
        "before": before,
        "after": after,
        "invented_places_removed": len(invented),
        "demo_media_removed": len(demo_media),
        "places_stripped_of_invented_prose": stripped,
        "official_id": official.id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Leave one official account (SPEC §11)")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="required: this deletes every account and all engagement",
    )
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default="", help="default: a generated passphrase")
    args = parser.parse_args()

    if not args.reset:
        print("This deletes every account and all engagement. Pass --reset to mean it.")
        return 1

    init_db()
    print("Checking the schema...")
    add_missing_columns()

    email = auth.validate_email(args.email)
    password = args.password or make_passphrase()
    auth.validate_password(password, email=email, username=OFFICIAL_USERNAME)

    with Session(engine) as session:
        summary = reset(session, email, password)

    print("\nBefore:", summary["before"])
    print("After: ", summary["after"])
    print(f"  invented places removed:   {summary['invented_places_removed']}")
    print(f"  generated media removed:   {summary['demo_media_removed']}")
    print(f"  places stripped of prose:  {summary['places_stripped_of_invented_prose']}")

    print("\nThe official account:")
    print(f"  handle    @{OFFICIAL_USERNAME}")
    print(f"  email     {email}")
    print(f"  password  {password}")
    print("\nWrite the password down now; it is hashed with argon2id and cannot be read back.")
    print("Change the email to one you own before anyone else uses this.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
