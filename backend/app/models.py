"""All SPEC §5 tables, as SQLModel classes.

Two invariants are structural rather than tested, and must stay that way:
`Visit`, `Pulse` and `Touch` have **no latitude or longitude columns** (CLAUDE.md
invariant 1), and kadam/earnings are only ever rows in `KadamEntry` /
`EarningLine` -- there is no balance column to update (invariant 4).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import JSON, Column, Field, SQLModel, UniqueConstraint


def utcnow() -> datetime:
    """Timestamps are UTC in the DB and rendered in IST (SPEC §5)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# People and places
# --------------------------------------------------------------------------- #

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)           # a-z0-9_ 3-20
    email: str = Field(default="", index=True)               # lowercase, unique when set
    password_hash: str
    official: bool = False                                   # the app's own account
    display_name: str = ""
    bio: str = ""                                            # max 160 chars
    avatar_media_id: Optional[int] = None
    created_at: datetime = Field(default_factory=utcnow)
    role: str = "user"                                       # 'user' | 'admin'
    strikes: int = 0
    demo: bool = False
    names_mode: str = "en_local"                             # SPEC §7.2
    names_lang: str = "en"
    ui_lang: str = "en"
    theme: str = "system"
    home_city_id: Optional[int] = Field(default=None, foreign_key="city.id")


class City(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name_en: str
    state: str
    bbox: list[float] = Field(default_factory=list, sa_column=Column(JSON))
    centre_lat: float = 0.0
    centre_lng: float = 0.0
    regional_langs: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class Neighbourhood(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    city_id: int = Field(foreign_key="city.id", index=True)
    name: str
    lat: float
    lng: float


class Place(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    city_id: Optional[int] = Field(default=None, foreign_key="city.id", index=True)
    state: Optional[str] = Field(default=None, index=True)
    lat: float = Field(index=True)
    lng: float = Field(index=True)
    radius_m: int = 150
    category: str = "other"
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source: str = "community"                                 # osm | wikidata | community
    osm_type: Optional[str] = None
    osm_id: Optional[int] = None
    wikidata: Optional[str] = Field(default=None, index=True)
    sitelinks: int = 0
    fame: str = "hidden"                                      # famous | known | hidden
    status: str = "unverified"                                # verified | unverified | hidden
    fragile: bool = False
    added_by: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    added_remotely: bool = False
    description: str = ""                                     # max 600 chars
    best_time: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    entry_fee_text: str = ""
    timings_text: str = ""
    access: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    accessibility: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    safety: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    activities: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    area: str = ""                                            # neighbourhood label
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PlaceName(SQLModel, table=True):
    """One name per (place, language, source) -- SPEC §7.2."""

    __table_args__ = (UniqueConstraint("place_id", "lang", "source", name="uq_placename"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    lang: str = Field(index=True)
    name: str
    source: str = "user"                                      # osm | wikidata | user | auto
    votes: int = 0


class Media(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    kind: str = "photo"                                       # photo | video
    path_display: str = ""
    path_thumb: str = ""
    path_poster: str = ""
    width: int = 0
    height: int = 0
    duration_s: float = 0.0
    phash: Optional[str] = Field(default=None, index=True)
    caption: str = ""                                         # doubles as alt text
    lang: str = "en"
    source: str = "upload"                                    # upload | commons
    licence: str = ""
    attribution: str = ""
    source_url: str = ""
    shot_here: bool = False
    status: str = "ok"                                        # ok | hidden
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- #
# Last-mile directions
# --------------------------------------------------------------------------- #

class LastMileStep(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    author_id: int = Field(foreign_key="user.id", index=True)
    version_group: str = Field(index=True)                    # uuid per version
    order: int = 0
    text: str = ""                                            # max 140 chars
    media_id: Optional[int] = None
    status: str = "ok"
    created_at: datetime = Field(default_factory=utcnow)


class LastMileVote(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "version_group", name="uq_lmvote"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    version_group: str = Field(index=True)
    helpful: bool = True
    at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- #
# Engagement
# --------------------------------------------------------------------------- #

class Like(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "place_id", name="uq_like"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    at: datetime = Field(default_factory=utcnow)


class Save(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "place_id", name="uq_save"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    at: datetime = Field(default_factory=utcnow)
    pledged: bool = False                                     # fragile pledge (SPEC §8.14)


class View(SQLModel, table=True):
    """Distinct viewers per place: the n in Wilson's lower bound (SPEC §9.1)."""

    __table_args__ = (UniqueConstraint("user_id", "place_id", name="uq_view"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    first_seen_at: datetime = Field(default_factory=utcnow)


class Follow(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("follower_id", "creator_id", name="uq_follow"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    follower_id: int = Field(foreign_key="user.id", index=True)
    creator_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)


class MediaLike(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "media_id", name="uq_medialike"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    media_id: int = Field(foreign_key="media.id", index=True)
    at: datetime = Field(default_factory=utcnow)


class MediaView(SQLModel, table=True):
    """One row per watch. engaged/completed are decided server-side (SPEC §9.10)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    media_id: int = Field(foreign_key="media.id", index=True)
    started_at: datetime = Field(default_factory=utcnow, index=True)
    watched_s: float = 0.0
    completed: bool = False
    engaged: bool = False
    invalid_reason: Optional[str] = Field(default=None, index=True)


class Swipe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    action: str = "skip"                                      # save | skip | open
    at: datetime = Field(default_factory=utcnow, index=True)


class CategoryPref(SQLModel, table=True):
    """Beta(alpha, beta) per user per category -- Thompson sampling (SPEC §9.4)."""

    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_catpref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    category: str = Field(index=True)
    alpha: float = 1.0
    beta: float = 1.0


# --------------------------------------------------------------------------- #
# Visits, live conditions, attribution -- none of these store coordinates
# --------------------------------------------------------------------------- #

class Visit(SQLModel, table=True):
    """A check-in. Only how far and how accurate -- never where (invariant 1)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    at: datetime = Field(default_factory=utcnow, index=True)
    distance_m: float = 0.0
    accuracy_m: float = 0.0
    verified: bool = False
    flag: Optional[str] = None                                # e.g. 'speed'
    simulated: bool = False


class Pulse(SQLModel, table=True):
    """Live conditions (SPEC §8.8). No coordinates."""

    id: Optional[int] = Field(default=None, primary_key=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    at: datetime = Field(default_factory=utcnow, index=True)
    water: Optional[str] = None                               # flowing | low | dry
    crowd: Optional[str] = None                               # quiet | busy | packed
    path: Optional[str] = None                                # dry | muddy | flooded | closed
    open: Optional[str] = None                                # yes | closed_today
    note: str = ""                                            # max 80 chars
    media_id: Optional[int] = None
    visit_id: Optional[int] = Field(default=None, foreign_key="visit.id")


class Touch(SQLModel, table=True):
    """Something a user saw that might have caused a visit (SPEC §9.9). No coordinates."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    creator_id: int = Field(foreign_key="user.id", index=True)
    content_type: str = "place"                               # place | video | photo | steps
    content_id: Optional[int] = None
    at: datetime = Field(default_factory=utcnow, index=True)
    invalid_reason: Optional[str] = None


class Attribution(SQLModel, table=True):
    """Shares sum to 1 per attributed visit (SPEC §9.9, AC-16)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    visit_id: int = Field(foreign_key="visit.id", index=True)
    creator_id: int = Field(foreign_key="user.id", index=True)
    share: float = 0.0


# --------------------------------------------------------------------------- #
# Ledgers -- the only way points and money ever change (invariant 4)
# --------------------------------------------------------------------------- #

class KadamEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    delta: int = 0
    reason: str = ""
    ref_type: Optional[str] = None
    ref_id: Optional[int] = None
    at: datetime = Field(default_factory=utcnow, index=True)


class EarningPeriod(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    month: str = Field(index=True)                            # 'YYYY-MM'
    pool_paise: int = 0
    simulated: bool = True
    status: str = "computed"
    created_at: datetime = Field(default_factory=utcnow)


class EarningLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    period_id: int = Field(foreign_key="earningperiod.id", index=True)
    creator_id: int = Field(foreign_key="user.id", index=True)
    score: float = 0.0
    share: float = 0.0
    amount_paise: int = 0
    eligible: bool = False


# --------------------------------------------------------------------------- #
# Moderation and sessions
# --------------------------------------------------------------------------- #

class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    reporter_id: int = Field(foreign_key="user.id", index=True)
    target_type: str = "place"                                 # place | media | steps | comment
    target_id: int = 0
    reason: str = ""
    note: str = ""
    status: str = "open"                                       # open | actioned | dismissed
    at: datetime = Field(default_factory=utcnow)


class Session(SQLModel, table=True):
    """`id` is the SHA-256 of the cookie token, never the token itself."""

    id: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime = Field(default_factory=utcnow, index=True)


class PasswordReset(SQLModel, table=True):
    """A one-hour link to choose a new password. `id` is the SHA-256 of the token."""

    id: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime = Field(default_factory=utcnow)
    used: bool = False
