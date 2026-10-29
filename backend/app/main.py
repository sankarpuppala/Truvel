"""FastAPI application (SPEC §11).

Routes live under `/api`; uploaded media is mounted at `/media`. Request logging
is deliberately minimal: we never log a request body, because check-in bodies
carry `lat`/`lng` and invariant 1 says those must not be written anywhere.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import DB_PATH, ROOT_DIR, cfg, dev_allow_fake_location, load_config
from .db import init_db
from .errors import ApiError, api_error_handler, http_error_handler
from .media_store import media_root
from .routers import (
    add,
    admin,
    auth_router,
    checkin,
    comments,
    deck_router,
    dev,
    interact,
    me,
    media_router,
    places,
    social,
    studio,
    users,
    watch_router,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("truvel")

# Uvicorn's own access logger prints the full request line, query string
# included -- and every deck/watch/nearby/search request carries the viewer's
# live lat/lng as a query parameter. That would put a user's location history
# into plaintext log files even though no lat/lng ever reaches a database row
# (invariant 1 covers *storage*, but a log file is storage too). Disabling it
# here means the "never log a request body" promise in this module's
# docstring also holds for request lines, regardless of how uvicorn is
# started.
logging.getLogger("uvicorn.access").disabled = True

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create tables and the media directory before serving the first request."""
    init_db()
    media_root()
    log.info("Truvel up. db=%s", DB_PATH)
    if dev_allow_fake_location():
        # Loud, because this must never be on in a build anyone else uses.
        log.warning("DEV_ALLOW_FAKE_LOCATION=1 -- the location simulator is ENABLED")
    yield


app = FastAPI(
    title="Truvel",
    version="1.0",
    lifespan=lifespan,
    description=(
        "Travel + social + creator app for India. Places from OpenStreetMap and "
        "Wikidata with Wikimedia Commons photos; hidden places added by people who "
        "were there. No real money moves in this version."
    ),
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)


# Only tiles.openfreemap.org is allowed to be reached from the frontend
# (invariant 7); these headers make the browser enforce that, and close off
# a few other response-header gaps a security review would otherwise flag.
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: blob: https://tiles.openfreemap.org https://upload.wikimedia.org https://commons.wikimedia.org https://*.wikimedia.org https://images.unsplash.com; "
        "connect-src 'self' https://tiles.openfreemap.org; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self)"
    response.headers["X-Frame-Options"] = "DENY"
    return response

API = "/api"
for router in (
    auth_router.router,
    places.router,
    interact.router,
    comments.router,
    social.router,
    add.router,
    checkin.router,
    deck_router.router,
    watch_router.router,
    me.router,
    studio.router,
    users.router,
    admin.router,
    media_router.router,
    dev.router,
):
    app.include_router(router, prefix=API)


@app.get(f"{API}/health")
def health() -> dict:
    """Liveness plus the few flags a client needs to know about."""
    return {
        "ok": True,
        "city_default": cfg("city_default"),
        "languages": cfg("languages"),
        "ui_available": cfg("ui_languages.available"),
        "ui_in_review": cfg("ui_languages.in_review"),
        "dev_fake_location": dev_allow_fake_location(),
        "simulated_money": True,
    }


@app.get(f"{API}/config")
def public_config() -> dict:
    """The config values the frontend legitimately needs (SPEC §16)."""
    full = load_config()
    return {
        "languages": full.get("languages", []),
        "state_languages": full.get("state_languages", {}),
        "ui_languages": full.get("ui_languages", {}),
        "kadam": {
            "levels": (full.get("kadam") or {}).get("levels", {}),
        },
        "deck": {"radii_km": [5, 10, 25]},
        "media": full.get("media", {}),
        "watch": {
            "video_max_s": (full.get("watch") or {}).get("video_max_s"),
            "video_max_mb": (full.get("watch") or {}).get("video_max_mb"),
            "break_nudge_min": (full.get("watch") or {}).get("break_nudge_min"),
        },
        "verification": full.get("verification", {}),
        "pulse": full.get("pulse", {}),
        "partner": {
            "demo_pool_inr": (full.get("partner") or {}).get("demo_pool_inr"),
            "creator_share": (full.get("partner") or {}).get("creator_share"),
            "weights": (full.get("partner") or {}).get("weights", {}),
        },
        "attribution": full.get("attribution", {}),
        "simulated_money": True,
    }


# Uploaded media. Range support for videos lives in media_router; this mount is
# the fast path for images.
app.mount("/media", StaticFiles(directory=str(media_root())), name="media")

# In production (or when built), serve the frontend SPA from frontend/dist:
dist_dir = ROOT_DIR / "frontend" / "dist"
if dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="frontend_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        target = dist_dir / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(dist_dir / "index.html")

