"""Give places real photographs, with the credit that has to travel with them.

Three jobs, in order:

  resolve   Every Commons image we recorded a filename for, but never asked
            about. Until a photo has its author and licence it cannot legally
            be shown (invariant 6), so the app was falling back to the category
            illustration. One request covers 50 files.

  geosearch Places with no photo at all. Commons records where a great many
            photographs were taken, so a temple with no Wikidata entry can
            still have a real picture of itself. The radius is small on
            purpose: a photo of the wrong thing is worse than no photo.

  cache     Pull the bytes for a city so its pages are instant, rather than
            fetching on first view.

    python -m scripts.fetch_photos --city hyderabad
    python -m scripts.fetch_photos --resolve-all          # metadata everywhere
    python -m scripts.fetch_photos --city hyderabad --no-geosearch
    python -m scripts.fetch_photos --all                  # geosearch every place, any city

Nothing here invents anything: a place either gets a photograph that someone
licensed for reuse, or it keeps its illustration.
"""
from __future__ import annotations

import argparse
import sys

import httpx
from sqlmodel import Session, func, select

from app import commons
from app.config import cfg
from app.db import engine
from app.models import City, Media, Place

# A photo this far from the pin is probably of something else.
GEOSEARCH_RADIUS_M = 250


def user_agent() -> dict[str, str]:
    return {"User-Agent": str(cfg("wikidata.user_agent", "Truvel/1.0"))}


def resolve_metadata(session: Session, limit: int | None, client: httpx.Client) -> dict:
    """Fill in author and licence for Commons rows that have neither."""
    query = select(Media).where(Media.source == "commons", Media.licence == "")
    if limit:
        query = query.limit(limit)
    rows = list(session.exec(query).all())
    if not rows:
        return {"looked_at": 0, "credited": 0, "hidden": 0}

    by_name: dict[str, list[Media]] = {}
    for row in rows:
        by_name.setdefault(row.path_display, []).append(row)

    print(f"  resolving {len(rows)} photos in {-(-len(by_name) // 50)} requests...")
    found = commons.fetch_metadata_batch(list(by_name), client=client)

    credited = hidden = 0
    for name, items in by_name.items():
        photo = found.get(name)
        for item in items:
            if photo is None:
                # No usable licence, or no such file: it must not be shown.
                item.status = "hidden"
                hidden += 1
            else:
                item.licence = photo.licence
                item.attribution = commons.attribution_text(photo.author, photo.licence)
                item.source_url = photo.file_page
                item.status = "ok"
                credited += 1
            session.add(item)
    session.commit()
    return {"looked_at": len(rows), "credited": credited, "hidden": hidden}


def add_geosearch_photos(
    session: Session, places: list[Place], client: httpx.Client
) -> dict:
    """Find a nearby, freely-licensed photograph for places that have none."""
    added = 0
    searched = 0
    for place in places:
        searched += 1
        if searched % 100 == 0:
            print(f"    ...{searched}/{len(places)} searched, {added} found")

        photos = commons.geosearch(
            place.lat, place.lng, radius_m=GEOSEARCH_RADIUS_M, client=client
        )
        if not photos:
            continue

        photo = photos[0]
        # Two places a few metres apart must not end up with the same picture.
        taken = session.exec(
            select(Media).where(Media.path_display == photo.filename)
        ).first()
        if taken is not None:
            continue

        session.add(
            Media(
                place_id=int(place.id),
                kind="photo",
                path_display=photo.filename,
                caption="",
                source="commons",
                licence=photo.licence,
                attribution=commons.attribution_text(photo.author, photo.licence),
                source_url=photo.file_page,
                width=photo.width,
                height=photo.height,
                status="ok",
            )
        )
        session.commit()
        added += 1
    return {"searched": searched, "added": added}


def cache_city(session: Session, city: City, client: httpx.Client) -> dict:
    """Download the bytes for one city, so its pages do not wait on Commons."""
    rows = session.exec(
        select(Media)
        .join(Place, Place.id == Media.place_id)
        .where(Place.city_id == city.id, Media.source == "commons", Media.status == "ok")
    ).all()

    cached = failed = already = 0
    for index, item in enumerate(rows, 1):
        if index % 25 == 0:
            print(f"    ...{index}/{len(rows)} cached")
        if commons.cached_path(item.path_display) is not None:
            already += 1
            continue
        try:
            photo = commons.fetch_and_cache(item.path_display, client=client)
        except (httpx.HTTPError, OSError):
            photo = None
        if photo is None:
            failed += 1
        else:
            cached += 1
    return {"photos": len(rows), "downloaded": cached, "already_cached": already, "failed": failed}


def coverage(session: Session, city: City | None) -> str:
    place_query = select(func.count()).select_from(Place)
    media_query = select(func.count(func.distinct(Media.place_id))).select_from(Media).join(
        Place, Place.id == Media.place_id
    ).where(Media.status == "ok", Media.licence != "")   # uncredited cannot be shown
    if city is not None:
        place_query = place_query.where(Place.city_id == city.id)
        media_query = media_query.where(Place.city_id == city.id)

    total = session.exec(place_query).one() or 0
    with_photo = session.exec(media_query).one() or 0
    where = city.name_en if city else "everywhere"
    share = f"{with_photo / total:.1%}" if total else "n/a"
    return f"{where}: {with_photo} of {total} places have a credited photo ({share})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch real photos for places")
    parser.add_argument("--city", default="", help="limit geosearch and caching to one city")
    parser.add_argument(
        "--all", action="store_true",
        help="geosearch every place missing a photo, in any city (most places have none)",
    )
    parser.add_argument("--resolve-all", action="store_true", help="credit every Commons row")
    parser.add_argument("--resolve-limit", type=int, default=0)
    parser.add_argument("--no-geosearch", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="stop after this many geosearches")
    args = parser.parse_args()

    with Session(engine) as session, httpx.Client(
        timeout=60.0, headers=user_agent(), follow_redirects=True
    ) as client:
        city = None
        if args.city:
            city = session.exec(select(City).where(City.slug == args.city)).first()
            if city is None:
                print(f"No city with slug {args.city!r}.")
                return 1

        print("Before:", coverage(session, city))

        if args.resolve_all or args.resolve_limit:
            print("\nCrediting photos we already knew about...")
            summary = resolve_metadata(
                session, args.resolve_limit or None, client
            )
            print(
                f"  {summary['credited']} credited, {summary['hidden']} hidden "
                "(no usable licence)"
            )

        if (city is not None or args.all) and not args.no_geosearch:
            query = select(Place).where(Place.status != "hidden").where(
                ~select(Media.id)
                .where(Media.place_id == Place.id, Media.status == "ok")
                .exists()
            )
            if city is not None:
                query = query.where(Place.city_id == city.id)
            without = list(session.exec(query).all())
            if args.limit:
                without = without[: args.limit]
            seconds = len(without) / float(cfg("commons.max_requests_per_second", 2))
            print(
                f"\nLooking for photographs near {len(without)} places with none "
                f"(about {seconds / 60:.0f} min at the configured rate)..."
            )
            summary = add_geosearch_photos(session, without, client)
            print(f"  {summary['added']} places gained a real photograph")

        if city is not None and not args.no_cache:
            print(f"\nCaching {city.name_en} so its pages do not wait on Commons...")
            summary = cache_city(session, city, client)
            print(
                f"  {summary['downloaded']} downloaded, {summary['already_cached']} already "
                f"here, {summary['failed']} failed"
            )

        print("\nAfter: ", coverage(session, city))
        if city is not None:
            print("       ", coverage(session, None))
        print("\nPlaces without a photograph keep their category illustration (SPEC §12.6).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
