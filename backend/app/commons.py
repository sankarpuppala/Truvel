"""Wikimedia Commons photos, fetched and cached by us (SPEC §6.3).

Wikidata gives us an image *filename* (property P18); Commons gives us the
picture and, crucially, who took it and under what licence. Three rules:

1. **Licence allowlist.** CC0, Public domain, CC BY and CC BY-SA only. Anything
   else is not stored and the place falls back to its category illustration --
   "no licence, no photo" is the only safe default (AC-3).
2. **Attribution is stored with the file**, never derived later: author,
   licence name, licence URL and the file-page URL. Every rendered photo shows
   "Photo: <author> - <licence> - Wikimedia Commons", linked to the file page
   (CLAUDE.md invariant 6).
3. **Served from our own origin.** The frontend makes no third-party requests
   (invariant 7), so we fetch once, cache under `data/commons/`, and serve the
   bytes ourselves at `/api/media/commons/{id}`.

Politeness: at most 2 requests per second and a descriptive User-Agent, as the
Wikimedia API terms ask.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import DATA_DIR, cfg

API_URL = "https://commons.wikimedia.org/w/api.php"
FILE_PAGE = "https://commons.wikimedia.org/wiki/File:"
_last_request_at = 0.0


@dataclass
class CommonsPhoto:
    """One Commons image, ready to become a Media row."""

    filename: str
    url: str
    width: int
    height: int
    author: str
    licence: str
    licence_url: str
    file_page: str
    cached_path: str = ""


def cache_dir() -> Path:
    path = DATA_DIR / "commons"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _strip_html(text: str) -> str:
    """Commons `Artist` is HTML (often a link). We want the readable name."""
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    return " ".join(no_tags.split()).strip()


def licence_allowed(licence_short: str) -> bool:
    """Whether a licence string is on the allowlist (SPEC §6.3).

    Matched as a prefix so "CC BY-SA 4.0" and "CC BY 2.0" pass under the
    "CC BY-SA"/"CC BY" entries, while "CC BY-NC" does not -- non-commercial and
    no-derivatives licences are deliberately excluded.
    """
    allow = [str(a).casefold() for a in (cfg("commons.licence_allowlist") or [])]
    value = (licence_short or "").strip().casefold()
    if not value:
        return False
    for ok in allow:
        if value == ok or value.startswith(ok + " ") or value.startswith(ok + "-0"):
            return True
        if ok == "public domain" and value.startswith("public domain"):
            return True
        if ok == "cc0" and value.startswith("cc0"):
            return True
    return False


def _throttle(max_per_second: float) -> None:
    """Keep to the configured request rate across the whole process."""
    global _last_request_at
    min_gap = 1.0 / max(0.1, max_per_second)
    wait = min_gap - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def parse_imageinfo(payload: dict, filename: str) -> CommonsPhoto | None:
    """Turn an API response into a CommonsPhoto, or None if unusable.

    Separated from the HTTP call so the AC-3 test can run on saved fixtures
    rather than the live API (PLAN.md: never live APIs in tests).
    """
    pages = (payload.get("query") or {}).get("pages") or {}
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        meta = info.get("extmetadata") or {}

        def field(key: str) -> str:
            return str((meta.get(key) or {}).get("value") or "")

        licence = field("LicenseShortName")
        if not licence_allowed(licence):
            return None

        return CommonsPhoto(
            filename=filename,
            url=info.get("thumburl") or info.get("url") or "",
            width=int(info.get("thumbwidth") or info.get("width") or 0),
            height=int(info.get("thumbheight") or info.get("height") or 0),
            author=_strip_html(field("Artist")) or "Unknown author",
            licence=licence,
            licence_url=field("LicenseUrl"),
            file_page=info.get("descriptionurl") or (FILE_PAGE + filename.replace(" ", "_")),
        )
    return None


def fetch_metadata(filename: str, client: httpx.Client | None = None) -> CommonsPhoto | None:
    """Ask Commons for a thumbnail URL plus licence metadata."""
    width = int(cfg("commons.thumb_width", 1200))
    params = {
        "action": "query",
        "format": "json",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size",
        "iiurlwidth": str(width),
    }
    headers = {"User-Agent": str(cfg("wikidata.user_agent", "Pagdandi/1.0"))}
    _throttle(float(cfg("commons.max_requests_per_second", 2)))

    own_client = client is None
    client = client or httpx.Client(timeout=30.0, headers=headers)
    try:
        response = client.get(API_URL, params=params, headers=headers)
        response.raise_for_status()
        return parse_imageinfo(response.json(), filename)
    finally:
        if own_client:
            client.close()


def cache_bytes(filename: str, data: bytes) -> str:
    """Write image bytes into the local cache; returns the cache file name."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:120]
    path = cache_dir() / safe
    path.write_bytes(data)
    return safe


def cached_path(filename: str) -> Path | None:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:120]
    path = cache_dir() / safe
    return path if path.exists() else None


def fetch_and_cache(filename: str, client: httpx.Client | None = None) -> CommonsPhoto | None:
    """Full flow: metadata, licence check, download, cache. None if refused."""
    photo = fetch_metadata(filename, client)
    if photo is None or not photo.url:
        return None

    existing = cached_path(filename)
    if existing is not None:
        photo.cached_path = existing.name
        return photo

    headers = {"User-Agent": str(cfg("wikidata.user_agent", "Pagdandi/1.0"))}
    _throttle(float(cfg("commons.max_requests_per_second", 2)))
    own_client = client is None
    client = client or httpx.Client(timeout=60.0, headers=headers, follow_redirects=True)
    try:
        response = client.get(photo.url, headers=headers)
        response.raise_for_status()
        photo.cached_path = cache_bytes(filename, response.content)
        return photo
    finally:
        if own_client:
            client.close()


def attribution_text(author: str, licence: str) -> str:
    """The line shown under every Commons photo (CLAUDE.md invariant 6)."""
    return f"Photo: {author} - {licence} - Wikimedia Commons"


def resolve_media(session, media) -> bool:  # noqa: ANN001
    """Make sure a Commons Media row has its credit, fetching it once if needed.

    Returns True when the photo is usable. The row is updated in place with the
    author, licence and file-page link (invariant 6), so every later read shows
    the attribution without another network call. A photo whose licence is not
    on the allowlist is hidden and never served: the place falls back to its
    category illustration (SPEC §6.3).
    """
    if media.licence and media.attribution:
        return True
    try:
        photo = fetch_and_cache(media.path_display)
    except Exception:  # noqa: BLE001 - offline or rate-limited: try again later
        return False
    if photo is None:
        media.status = "hidden"
        session.add(media)
        session.commit()
        return False
    media.licence = photo.licence
    media.attribution = attribution_text(photo.author, photo.licence)
    media.source_url = photo.file_page
    session.add(media)
    session.commit()
    return True
