"""Visit fraud rules (SPEC §9.8).

The app pays attention -- and eventually money -- for visits, so a visit has to
be expensive to fake. Physically going somewhere already is; these rules close
the cheap shortcuts:

* **Impossible travel.** Two consecutive visits more than 120 km/h apart flag
  the second one `speed`. A flagged visit earns no kadam, verifies no place and
  attributes to nobody. 120 km/h is generous on purpose: an Indian highway
  drive or a train should never trip it, a GPS spoof usually will.
* **New accounts** (< 24 h) earn no kadam from likes given or received, so
  mass-registering accounts to farm points buys nothing.
* **No self-dealing**: your own likes, visits, views and attribution on your
  own content are worth nothing to you.
* **Rate limits** per user per hour, from config.
* **A place's discovery reward** waits until 2 *different* unflagged users --
  neither the discoverer -- have checked in.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..config import cfg
from ..geo import haversine_km, speed_kmh

SPEED_FLAG = "speed"


@dataclass
class PriorVisit:
    """The user's previous visit: when, and where the place was."""

    at: datetime
    lat: float
    lng: float


def impossible_travel(
    previous: PriorVisit | None,
    now: datetime,
    lat: float,
    lng: float,
    max_kmh: float | None = None,
) -> bool:
    """True when getting from the previous visit to this one is too fast.

    No previous visit means nothing to compare, so the visit stands.
    """
    if previous is None:
        return False
    if max_kmh is None:
        max_kmh = float(cfg("verification.max_speed_kmh", 120))
    hours = (now - previous.at).total_seconds() / 3600.0
    distance = haversine_km(previous.lat, previous.lng, lat, lng)
    if distance <= 0:
        return False                     # same place twice is not travel
    return speed_kmh(distance, hours) > max_kmh


def is_new_account(created_at: datetime, now: datetime, hours: float | None = None) -> bool:
    """Accounts under the configured age earn no like-based kadam (SPEC §9.8)."""
    if hours is None:
        hours = float(cfg("kadam.new_account_hours", 24))
    return (now - created_at) < timedelta(hours=hours)


def is_self_dealing(actor_id: int | None, owner_id: int | None) -> bool:
    """Whether an action is the user acting on their own content."""
    return actor_id is not None and owner_id is not None and actor_id == owner_id


def rate_limited(count_last_hour: int, limit_key: str) -> bool:
    """Whether a user has used up an hourly allowance from `rate_limits`."""
    limit = cfg(f"rate_limits.{limit_key}")
    if limit is None:
        return False
    return count_last_hour >= int(limit)


def place_can_verify(
    discoverer_id: int | None,
    visits: list[dict],
    needed: int | None = None,
) -> bool:
    """Whether a community place has earned `verified` status (SPEC §9.8).

    `visits` items need keys: user_id, verified, flag, simulated. The visit must
    be verified, unflagged, not simulated, and not by the discoverer; and the
    required count is of *distinct* users, so one person checking in twice does
    not confirm a place on their own.
    """
    if needed is None:
        needed = int(cfg("verification.verify_visits_needed", 2))
    qualifying: set[int] = set()
    for v in visits:
        if not v.get("verified"):
            continue
        if v.get("flag"):
            continue
        if v.get("simulated"):
            continue
        uid = v.get("user_id")
        if uid is None or uid == discoverer_id:
            continue
        qualifying.add(int(uid))
    return len(qualifying) >= needed
