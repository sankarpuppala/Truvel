"""Storing uploaded photos and videos (SPEC §8.6, §9.7, CLAUDE.md invariant 2).

Every stored photo is **re-encoded** with Pillow: we decode the pixels and write
a fresh JPEG. That is what guarantees no stored file carries EXIF -- we never
copy the original bytes, so there is nothing for location data to hide in. Two
sizes are written, 1200 px display and 400 px thumbnail (SPEC §15).

Uploads are checked by **magic bytes**, not by the filename or the
`Content-Type` header, both of which the client controls. Videos are not
transcoded (no budget, no time -- SPEC §19 D14); they are limited to 60 s and
60 MB instead, and the client supplies a poster frame which we re-encode like
any other photo.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

from .config import MEDIA_DIR, cfg
from .errors import bad_request
from .integrity.phash import phash_image
from .models import utcnow

# Magic bytes we accept. The video containers are checked for the ISO-BMFF
# 'ftyp' box at offset 4, which is what an MP4/MOV actually starts with.
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEBP_MAGIC = (b"RIFF", b"WEBP")
MP4_BRANDS = {b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"mmp4", b"M4V ", b"qt  "}
WEBM_MAGIC = b"\x1a\x45\xdf\xa3"


@dataclass
class StoredPhoto:
    """Where a processed photo landed, and what it looks like."""

    path_display: str
    path_thumb: str
    width: int
    height: int
    phash: str


@dataclass
class StoredVideo:
    path_display: str
    path_poster: str
    path_thumb: str
    duration_s: float
    phash: str


def media_root() -> Path:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    return MEDIA_DIR


def _dated_dir(kind: str, now: datetime | None = None) -> Path:
    """media/<kind>/YYYY/MM/ -- keeps directories small as the DB grows."""
    now = now or utcnow()
    path = media_root() / kind / f"{now:%Y}" / f"{now:%m}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _token() -> str:
    """An unguessable filename: media URLs should not be enumerable."""
    return secrets.token_hex(12)


def sniff_image(data: bytes) -> str:
    """Image format from magic bytes, or raise. Never trusts the filename."""
    if data.startswith(JPEG_MAGIC):
        return "jpeg"
    if data.startswith(PNG_MAGIC):
        return "png"
    if data[:4] == WEBP_MAGIC[0] and data[8:12] == WEBP_MAGIC[1]:
        return "webp"
    raise bad_request("That file is not a JPEG, PNG or WebP image.", "bad_image")


def sniff_video(data: bytes) -> str:
    """Video container from magic bytes, or raise."""
    if data.startswith(WEBM_MAGIC):
        return "webm"
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in MP4_BRANDS:
        return "mp4"
    raise bad_request("That file is not an MP4 or WebM video.", "bad_video")


def _open_clean(data: bytes) -> Image.Image:
    """Decode to RGB pixels, honouring the EXIF rotation then discarding it.

    `exif_transpose` applies the orientation tag so a portrait photo is not
    stored sideways; after that the tag has done its job and the pixels are all
    we keep.
    """
    import io

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img


def _save_jpeg(img: Image.Image, path: Path, quality: int) -> None:
    """Write a JPEG with no EXIF, no ICC profile and no comment block."""
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    clean.save(path, format="JPEG", quality=quality, optimize=True, progressive=True)


def process_photo(data: bytes, now: datetime | None = None) -> StoredPhoto:
    """Re-encode an uploaded photo into display and thumb sizes.

    Raises if the bytes are not a supported image. The returned paths are
    relative to the media root, which is what goes in the database.
    """
    sniff_image(data)
    max_bytes = int(cfg("media.photo_long_side", 2048))  # guard against absurd input
    img = _open_clean(data)
    if max(img.size) > 12000 or max_bytes <= 0:
        raise bad_request("That image is too large to process.", "image_too_large")

    display_side = int(cfg("media.display_long_side", 1200))
    thumb_side = int(cfg("media.thumb_long_side", 400))
    quality = int(cfg("media.jpeg_quality", 85))

    out_dir = _dated_dir("photos", now)
    name = _token()

    display = img.copy()
    display.thumbnail((display_side, display_side), Image.LANCZOS)
    display_path = out_dir / f"{name}.jpg"
    _save_jpeg(display, display_path, quality)

    thumb = img.copy()
    thumb.thumbnail((thumb_side, thumb_side), Image.LANCZOS)
    thumb_path = out_dir / f"{name}_t.jpg"
    _save_jpeg(thumb, thumb_path, quality)

    return StoredPhoto(
        path_display=str(display_path.relative_to(media_root())).replace("\\", "/"),
        path_thumb=str(thumb_path.relative_to(media_root())).replace("\\", "/"),
        width=display.width,
        height=display.height,
        phash=phash_image(display),
    )


def check_video_limits(size_bytes: int, duration_s: float) -> None:
    """60 s and 60 MB from config (SPEC §8.6). No transcoding, so hard limits."""
    max_s = float(cfg("watch.video_max_s", 60))
    max_mb = float(cfg("watch.video_max_mb", 60))
    if duration_s > max_s + 0.5:
        raise bad_request(
            f"Videos can be up to {int(max_s)} seconds. Trim it and try again.",
            "video_too_long",
        )
    if size_bytes > max_mb * 1024 * 1024:
        raise bad_request(
            f"Videos can be up to {int(max_mb)} MB.", "video_too_large"
        )


def process_video(
    data: bytes,
    poster: bytes,
    duration_s: float,
    now: datetime | None = None,
) -> StoredVideo:
    """Store a video as-is, plus a re-encoded poster and thumbnail.

    The video bytes are stored unchanged -- we cannot strip metadata from a
    container without ffmpeg, which is out of scope -- but the poster is
    re-encoded, and the poster is what is ever rendered as an image.
    """
    ext = sniff_video(data)
    check_video_limits(len(data), duration_s)
    sniff_image(poster)

    out_dir = _dated_dir("videos", now)
    name = _token()
    video_path = out_dir / f"{name}.{ext}"
    video_path.write_bytes(data)

    stored_poster = process_photo(poster, now)

    return StoredVideo(
        path_display=str(video_path.relative_to(media_root())).replace("\\", "/"),
        path_poster=stored_poster.path_display,
        path_thumb=stored_poster.path_thumb,
        duration_s=float(duration_s),
        phash=stored_poster.phash,
    )


def absolute(path_rel: str) -> Path:
    """Resolve a stored relative path, refusing anything outside the media root.

    Path traversal guard: a database row should never be able to serve
    `../../etc/passwd`, even if something upstream is wrong.
    """
    root = media_root().resolve()
    target = (root / path_rel).resolve()
    if not str(target).startswith(str(root)):
        raise bad_request("Bad media path.", "bad_path")
    return target
