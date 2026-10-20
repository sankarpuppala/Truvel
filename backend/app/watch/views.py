"""Engaged views, completion, and invalid traffic (SPEC §9.10).

The client sends one heartbeat when the viewer leaves a video: how long they
watched and how long the video is. **The server decides** what that means --
never the client -- because engaged views feed the Partner Program and anything
the client can assert, a fraudster can assert too (AC-11).

Definitions:
  engaged view  watched >= 3 s, or >= 50 % of a video shorter than 6 s
  completion    watched >= 90 % of the duration

A view is invalid (and earns nothing) if the viewer is the creator, the account
is under 24 h old, it repeats the same user + item inside 24 h, or the session
is flagged as simulated by the dev tools.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..config import cfg

# Reason strings. Kept as constants so the rules and their tests cannot drift.
SELF_VIEW = "self_view"
NEW_ACCOUNT = "new_account"
REPEAT = "repeat"
SIMULATED = "simulated"
VELOCITY_HOLD = "velocity_hold"


def is_engaged(watched_s: float, duration_s: float) -> bool:
    """SPEC §9.10: >= 3 s, or >= 50 % of a video shorter than 6 s.

    The short-video clause exists so a genuine 4-second clip watched right
    through is not punished for being short.
    """
    min_s = float(cfg("watch.engaged_min_s", 3))
    if duration_s > 0 and duration_s < 6.0:
        return watched_s >= 0.5 * duration_s
    return watched_s >= min_s


def is_completed(watched_s: float, duration_s: float) -> bool:
    """>= 90 % watched. A zero-duration video can never complete."""
    ratio = float(cfg("watch.completion_ratio", 0.9))
    if duration_s <= 0:
        return False
    return watched_s >= ratio * duration_s


def clamp_watched(watched_s: float, duration_s: float) -> float:
    """Trust the clock, not the client: watched time cannot exceed the video.

    Without this, a client could post watched_s = 10_000 and inflate watch time.
    """
    w = max(0.0, float(watched_s))
    if duration_s > 0:
        # A second of slack absorbs honest rounding at the end of playback.
        return min(w, float(duration_s) + 1.0)
    return w


def invalid_reason(
    *,
    viewer_id: int | None,
    creator_id: int,
    viewer_created_at: datetime | None,
    now: datetime,
    previous_view_at: datetime | None,
    simulated_session: bool = False,
) -> str | None:
    """The §9.10 Tier-1 rules, in order. None means the view counts.

    Order matters only for which reason is reported; any one of them makes the
    view invalid.
    """
    if simulated_session:
        return SIMULATED
    if viewer_id is not None and viewer_id == creator_id:
        return SELF_VIEW
    if viewer_created_at is not None:
        hours = float(cfg("invalid_traffic.new_account_hours", 24))
        if (now - viewer_created_at) < timedelta(hours=hours):
            return NEW_ACCOUNT
    if previous_view_at is not None:
        window = float(cfg("invalid_traffic.repeat_window_hours", 24))
        if (now - previous_view_at) < timedelta(hours=window):
            return REPEAT
    return None


def classify(
    *,
    watched_s: float,
    duration_s: float,
    viewer_id: int | None,
    creator_id: int,
    viewer_created_at: datetime | None,
    now: datetime,
    previous_view_at: datetime | None = None,
    simulated_session: bool = False,
) -> dict[str, object]:
    """Everything the server needs to store for one view, in one call."""
    watched = clamp_watched(watched_s, duration_s)
    reason = invalid_reason(
        viewer_id=viewer_id,
        creator_id=creator_id,
        viewer_created_at=viewer_created_at,
        now=now,
        previous_view_at=previous_view_at,
        simulated_session=simulated_session,
    )
    engaged = is_engaged(watched, duration_s) and reason is None
    return {
        "watched_s": watched,
        "engaged": engaged,
        "completed": is_completed(watched, duration_s),
        "invalid_reason": reason,
    }
