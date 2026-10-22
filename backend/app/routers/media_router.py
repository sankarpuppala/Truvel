"""Serving media: uploads with HTTP Range, and cached Commons thumbnails.

Range support is not optional: iOS Safari will not play a video from a server
that answers a ranged request with the whole file, so video seeking needs real
206 responses (SPEC §11, tested).

Commons photos are served from our own origin so the frontend never talks to a
third party (CLAUDE.md invariant 7). The licence was already checked when the
file was cached (SPEC §6.3).
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session as DbSession

from .. import commons, media_store
from ..db import get_session
from ..errors import not_found
from ..models import Media

router = APIRouter(tags=["media"])

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")
CHUNK = 64 * 1024

CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


def content_type_for(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def ranged_response(path: Path, request: Request) -> Response:
    """Serve a file, honouring a Range header with a real 206 (SPEC §11)."""
    size = path.stat().st_size
    media_type = content_type_for(path)
    range_header = request.headers.get("range")

    if not range_header:
        return FileResponse(
            path,
            media_type=media_type,
            headers={"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=86400"},
        )

    match = RANGE_RE.match(range_header)
    if not match:
        return FileResponse(path, media_type=media_type, headers={"Accept-Ranges": "bytes"})

    start_s, end_s = match.groups()
    if start_s == "":
        # "bytes=-500" means the last 500 bytes.
        length = int(end_s or 0)
        start = max(0, size - length)
        end = size - 1
    else:
        start = int(start_s)
        end = int(end_s) if end_s else size - 1
    start = max(0, min(start, size - 1))
    end = max(start, min(end, size - 1))
    length = end - start + 1

    def stream():
        with path.open("rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        stream(),
        status_code=206,
        media_type=media_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get("/media/commons/{media_id}")
def commons_photo(
    media_id: int,
    request: Request,
    session: DbSession = Depends(get_session),
) -> Response:
    """Serve a cached Commons thumbnail from our own origin (SPEC §6.3)."""
    media = session.get(Media, media_id)
    if media is None or media.source != "commons" or media.status != "ok":
        raise not_found("No such photo.", "no_media")

    # Credit first: this also hides the photo if its licence is not allowed.
    if not commons.resolve_media(session, media):
        raise not_found("That photo is not available.", "no_photo")
    cached = commons.cached_path(media.path_display)
    if cached is None:
        # Already credited but never downloaded (a batch run can credit many
        # more photos than it has time to cache) -- fetch the bytes now, once,
        # so the place is not stuck showing its illustration forever.
        try:
            photo = commons.fetch_and_cache(media.path_display)
        except Exception:  # noqa: BLE001 - offline or rate-limited: try again later
            photo = None
        if photo is None or photo.cached_path is None:
            raise not_found("That photo is not available.", "no_photo")
        cached = commons.cache_dir() / photo.cached_path

    response = ranged_response(cached, request)
    # The attribution travels with the bytes, so it cannot be lost downstream.
    response.headers["X-Attribution"] = media.attribution or ""
    response.headers["X-Licence"] = media.licence or ""
    return response


@router.get("/media/file/{path:path}")
def uploaded_file(path: str, request: Request) -> Response:
    """Serve an uploaded photo or video with Range support."""
    target = media_store.absolute(path)
    if not target.exists() or not target.is_file():
        raise not_found("No such file.", "no_file")
    return ranged_response(target, request)
