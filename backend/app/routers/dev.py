"""Dev-only location simulator (SPEC §8.7, AC-25).

Every route here returns **404 unless the server was started with
`DEV_ALLOW_FAKE_LOCATION=1`**, so a production build has no teleport endpoint at
all -- not a disabled one, an absent one. Visits made this way are marked
`simulated=True`, shown with a "SIM" badge, and excluded from metrics,
attribution and earnings.

It exists for one reason: geolocation needs real movement, and a viva
demonstration happens in a room.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session as DbSession
from sqlmodel import select

from ..auth import current_user, require_csrf_header
from ..config import cfg, dev_allow_fake_location
from ..db import get_session
from ..errors import not_found
from ..models import City, Place, User

router = APIRouter(prefix="/dev", tags=["dev"], dependencies=[Depends(require_csrf_header)])


def _guard() -> None:
    """The flag check. A missing flag is a 404, not a 403: the route is gone."""
    if not dev_allow_fake_location():
        raise not_found("Not found.", "not_found")


class TeleportIn(BaseModel):
    place_id: int | None = None
    lat: float | None = None
    lng: float | None = None


@router.post("/teleport")
def teleport(
    body: TeleportIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Return coordinates for the client to use instead of the real GPS.

    The server does not store a position -- it hands back a point, and the
    client sends it to `/checkin` with `simulated: true`, which the check-in
    route only accepts while this flag is on.
    """
    _guard()
    if body.place_id:
        place = session.get(Place, body.place_id)
        if place is None:
            raise not_found("No such place.", "no_place")
        return {
            "lat": place.lat,
            "lng": place.lng,
            "accuracy": 12.0,
            "simulated": True,
            "place_id": place.id,
        }
    if body.lat is not None and body.lng is not None:
        return {"lat": body.lat, "lng": body.lng, "accuracy": 12.0, "simulated": True}

    city = session.exec(select(City).where(City.slug == str(cfg("city_default")))).first()
    if city is None:
        raise not_found("No city seeded.", "no_city")
    return {
        "lat": city.centre_lat,
        "lng": city.centre_lng,
        "accuracy": 12.0,
        "simulated": True,
    }


@router.get("/places")
def dev_places(
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """A short list of places to teleport to, for the demo picker."""
    _guard()
    rows = session.exec(
        select(Place).where(Place.status != "hidden").order_by(Place.id).limit(40)
    ).all()
    from .. import services

    return {
        "places": [
            {
                "id": p.id,
                "name": services.english_name(session, int(p.id)),
                "category": p.category,
                "area": p.area,
            }
            for p in rows
        ]
    }
