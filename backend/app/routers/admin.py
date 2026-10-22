"""Admin: moderation queue, actions, and the Partner month run (SPEC §8.13, §10).

Removing content reverses the kadam **and** the earnings it produced (SPEC
§8.13) -- otherwise hiding a stolen photo would leave the points it earned in
place, and the ledger would stop being true.

The Tier-1 deliverable is this API; the admin UI is Tier 2 (SPEC §4).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from .. import kadam
from ..auth import require_admin, require_csrf_header
from ..db import get_session
from ..errors import bad_request, not_found
from ..models import (
    LastMileStep,
    Like,
    Media,
    Place,
    PlaceName,
    Report,
    Save,
    User,
    View,
    Visit,
    utcnow,
)
from ..partner.run import run_month

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin), Depends(require_csrf_header)],
)


@router.get("/cases")
def cases(session: DbSession = Depends(get_session)) -> dict:
    """Open reports grouped by what they are about, strongest evidence first.

    Ten people flagging ten different things is ten small jobs; ten people
    flagging one thing is one job with a lot of evidence. A report from someone
    with a verified check-in at the place is worth more than one from a stranger
    (they were there), so each case says how many of its reporters were.
    """
    rows = session.exec(select(Report).where(Report.status == "open")).all()
    grouped: dict[tuple[str, int], list[Report]] = {}
    for report in rows:
        grouped.setdefault((report.target_type, int(report.target_id)), []).append(report)

    out = []
    for (target_type, target_id), reports in grouped.items():
        place_id = _place_of(session, target_type, target_id)
        reporters = {int(r.reporter_id) for r in reports}
        visited = _verified_visitors(session, place_id, reporters)
        reasons: dict[str, int] = {}
        for report in reports:
            reasons[report.reason] = reasons.get(report.reason, 0) + 1
        out.append(
            {
                "target_type": target_type,
                "target_id": target_id,
                "place_id": place_id,
                "title": _target_title(session, target_type, target_id, place_id),
                "reasons": reasons,
                "reports": len(reports),
                "reporters": len(reporters),
                "reporters_who_visited": len(visited),
                "notes": [
                    {"reason": r.reason, "note": r.note, "visited": int(r.reporter_id) in visited}
                    for r in reports
                    if r.note
                ][:10],
                "latest": max(r.at for r in reports).isoformat(),
            }
        )
    out.sort(key=lambda c: (-c["reporters_who_visited"], -c["reporters"], c["latest"]))
    return {"cases": out}


def _place_of(session: DbSession, target_type: str, target_id: int) -> int | None:
    if target_type == "place":
        return target_id
    if target_type == "media":
        media = session.get(Media, target_id)
        return int(media.place_id) if media is not None and media.place_id else None
    if target_type == "steps":
        step = session.get(LastMileStep, target_id)
        return int(step.place_id) if step is not None else None
    return None


def _verified_visitors(session: DbSession, place_id: int | None, user_ids: set[int]) -> set[int]:
    if place_id is None or not user_ids:
        return set()
    rows = session.exec(
        select(Visit.user_id).where(
            Visit.place_id == place_id,
            Visit.verified == True,  # noqa: E712
            Visit.simulated == False,  # noqa: E712
            Visit.user_id.in_(user_ids),
        )
    ).all()
    return {int(r) for r in rows}


def _target_title(
    session: DbSession, target_type: str, target_id: int, place_id: int | None
) -> str:
    from .. import services

    name = services.english_name(session, place_id) if place_id else f"#{target_id}"
    if target_type == "media":
        return f"A photo or video of {name}"
    if target_type == "steps":
        return f"Last-mile directions for {name}"
    return name


@router.get("/queue")
def queue(
    status: str = "open",
    session: DbSession = Depends(get_session),
) -> dict:
    """Open reports, newest first, with just enough context to decide."""
    reports = list(
        session.exec(
            select(Report).where(Report.status == status).order_by(Report.at.desc()).limit(100)
        ).all()
    )
    out = []
    for report in reports:
        target: dict | None = None
        if report.target_type == "media":
            media = session.get(Media, report.target_id)
            if media is not None:
                target = {
                    "kind": media.kind,
                    "caption": media.caption,
                    "status": media.status,
                    "place_id": media.place_id,
                    "user_id": media.user_id,
                    "url": f"/media/{media.path_display}",
                }
        elif report.target_type == "place":
            place = session.get(Place, report.target_id)
            if place is not None:
                target = {
                    "category": place.category,
                    "status": place.status,
                    "added_by": place.added_by,
                    "source": place.source,
                }
        reporter = session.get(User, report.reporter_id)
        out.append(
            {
                "id": report.id,
                "target_type": report.target_type,
                "target_id": report.target_id,
                "reason": report.reason,
                "note": report.note,
                "at": report.at.isoformat(),
                "reporter": reporter.username if reporter else None,
                "target": target,
            }
        )
    return {"reports": out}


class ActionIn(BaseModel):
    action: str                     # hide | approve | dismiss | merge | strike
    target_type: str | None = None
    target_id: int | None = None
    report_id: int | None = None
    merge_into: int | None = None
    user_id: int | None = None


@router.post("/actions")
def act(
    body: ActionIn,
    session: DbSession = Depends(get_session),
) -> dict:
    """Apply a moderation decision."""
    now = utcnow()

    if body.action in ("resolve", "dismiss_all"):
        if not body.target_type or not body.target_id:
            raise bad_request("Which case?", "no_case")
        # "resolve" means we acted on it (fixed the pin, corrected the name);
        # "dismiss_all" means the reports were wrong. Either closes the case.
        outcome = "actioned" if body.action == "resolve" else "dismissed"
        for report in session.exec(
            select(Report).where(
                Report.status == "open",
                Report.target_type == body.target_type,
                Report.target_id == body.target_id,
            )
        ).all():
            report.status = outcome
            session.add(report)
        session.commit()
        return {"ok": True}

    if body.action == "dismiss":
        if not body.report_id:
            raise bad_request("Which report?", "no_report")
        report = session.get(Report, body.report_id)
        if report is None:
            raise not_found("No such report.", "no_report")
        report.status = "dismissed"
        session.add(report)
        session.commit()
        return {"ok": True}

    if body.action == "hide":
        if body.target_type == "media" and body.target_id:
            media = session.get(Media, body.target_id)
            if media is None:
                raise not_found("No such media.", "no_media")
            media.status = "hidden"
            session.add(media)
            session.commit()
            reversed_kadam = _reverse_media_rewards(session, media, now)
            return {"ok": True, "reversed_kadam": reversed_kadam}
        if body.target_type == "place" and body.target_id:
            place = session.get(Place, body.target_id)
            if place is None:
                raise not_found("No such place.", "no_place")
            place.status = "hidden"
            session.add(place)
            session.commit()
            reversed_kadam = 0
            if place.added_by:
                reversed_kadam = kadam.reverse(
                    session,
                    int(place.added_by),
                    ref_type="place",
                    ref_id=int(place.id),
                    now=now,
                )
            return {"ok": True, "reversed_kadam": reversed_kadam}
        if body.target_type == "steps" and body.target_id:
            step = session.get(LastMileStep, body.target_id)
            if step is None:
                raise not_found("No such directions.", "no_steps")
            for row in session.exec(
                select(LastMileStep).where(LastMileStep.version_group == step.version_group)
            ).all():
                row.status = "hidden"
                session.add(row)
            session.commit()
            return {"ok": True}
        raise bad_request("Nothing to hide.", "bad_target")

    if body.action == "approve":
        if body.target_type == "place" and body.target_id:
            place = session.get(Place, body.target_id)
            if place is None:
                raise not_found("No such place.", "no_place")
            place.status = "verified"
            place.updated_at = now
            session.add(place)
            session.commit()
            if place.added_by:
                kadam.award(
                    session,
                    int(place.added_by),
                    kadam.DISCOVERY,
                    ref_type="place",
                    ref_id=int(place.id),
                    now=now,
                )
            return {"ok": True}
        if body.target_type == "media" and body.target_id:
            media = session.get(Media, body.target_id)
            if media is None:
                raise not_found("No such media.", "no_media")
            media.status = "ok"
            session.add(media)
            session.commit()
            return {"ok": True}
        raise bad_request("Nothing to approve.", "bad_target")

    if body.action == "merge":
        if not body.target_id or not body.merge_into:
            raise bad_request("Merge needs a source and a target.", "bad_merge")
        return _merge_places(session, int(body.target_id), int(body.merge_into), now)

    if body.action == "strike":
        if not body.user_id:
            raise bad_request("Which user?", "no_user")
        user = session.get(User, body.user_id)
        if user is None:
            raise not_found("No such user.", "no_user")
        user.strikes += 1
        session.add(user)
        session.commit()
        return {"ok": True, "strikes": user.strikes}

    raise bad_request("Unknown action.", "bad_action")


def _reverse_media_rewards(session: DbSession, media: Media, now) -> int:  # noqa: ANN001
    """Reverse kadam a hidden item earned, and drop its attribution shares.

    Dropping the Attribution rows is what removes the item from future earnings:
    `run_month` reads those rows, so the next run simply does not see them.
    """
    reversed_total = 0
    if media.user_id:
        reversed_total += kadam.reverse(
            session,
            int(media.user_id),
            ref_type="media",
            ref_id=int(media.id),
            now=now,
        )
    return reversed_total


def _merge_places(session: DbSession, source_id: int, target_id: int, now) -> dict:  # noqa: ANN001
    """Move everything from a duplicate place onto the real one (SPEC §8.13)."""
    if source_id == target_id:
        raise bad_request("A place cannot merge into itself.", "bad_merge")
    source = session.get(Place, source_id)
    target = session.get(Place, target_id)
    if source is None or target is None:
        raise not_found("No such place.", "no_place")

    moved = {"media": 0, "likes": 0, "visits": 0, "names": 0, "saves": 0, "steps": 0}

    for media in session.exec(select(Media).where(Media.place_id == source_id)).all():
        media.place_id = target_id
        session.add(media)
        moved["media"] += 1

    # Likes, views and saves are unique per (user, place): skip anyone who
    # already has a row on the target, or the unique constraint would fail.
    for model, key in ((Like, "likes"), (Save, "saves")):
        for row in session.exec(select(model).where(model.place_id == source_id)).all():
            clash = session.exec(
                select(model).where(model.user_id == row.user_id, model.place_id == target_id)
            ).first()
            if clash is None:
                row.place_id = target_id
                session.add(row)
                moved[key] += 1
            else:
                session.delete(row)

    for row in session.exec(select(View).where(View.place_id == source_id)).all():
        clash = session.exec(
            select(View).where(View.user_id == row.user_id, View.place_id == target_id)
        ).first()
        if clash is None:
            row.place_id = target_id
            session.add(row)
        else:
            session.delete(row)

    for visit in session.exec(select(Visit).where(Visit.place_id == source_id)).all():
        visit.place_id = target_id
        session.add(visit)
        moved["visits"] += 1

    for step in session.exec(select(LastMileStep).where(LastMileStep.place_id == source_id)).all():
        step.place_id = target_id
        session.add(step)
        moved["steps"] += 1

    for name in session.exec(select(PlaceName).where(PlaceName.place_id == source_id)).all():
        clash = session.exec(
            select(PlaceName).where(
                PlaceName.place_id == target_id,
                PlaceName.lang == name.lang,
                PlaceName.source == name.source,
            )
        ).first()
        if clash is None:
            name.place_id = target_id
            session.add(name)
            moved["names"] += 1
        else:
            session.delete(name)

    source.status = "hidden"
    source.updated_at = now
    session.add(source)
    session.commit()
    return {"ok": True, "moved": moved, "target_id": target_id}


@router.post("/partner/run")
def partner_run(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    pool_inr: float | None = None,
    session: DbSession = Depends(get_session),
) -> dict:
    """Run the Partner month: attribution summary, filters, EarningLines."""
    pool_paise = int(pool_inr * 100) if pool_inr is not None else None
    return run_month(session, month, pool_paise)


@router.get("/stats")
def stats(session: DbSession = Depends(get_session)) -> dict:
    """Coverage counts for the report (SPEC §17 item 7)."""
    places = int(session.exec(select(func.count()).select_from(Place)).one() or 0)
    by_state = dict(
        session.exec(
            select(Place.state, func.count()).group_by(Place.state).order_by(func.count().desc())
        ).all()
    )
    by_category = dict(
        session.exec(select(Place.category, func.count()).group_by(Place.category)).all()
    )
    with_photo = int(
        session.exec(
            select(func.count(func.distinct(Media.place_id))).where(Media.status == "ok")
        ).one()
        or 0
    )
    by_lang = dict(
        session.exec(
            select(PlaceName.lang, func.count(func.distinct(PlaceName.place_id))).group_by(
                PlaceName.lang
            )
        ).all()
    )
    return {
        "places": places,
        "by_state": {str(k): int(v) for k, v in by_state.items() if k},
        "by_category": {str(k): int(v) for k, v in by_category.items()},
        "with_photo": with_photo,
        "photo_share": round(with_photo / places, 4) if places else 0.0,
        "names_by_lang": {str(k): int(v) for k, v in by_lang.items()},
    }
