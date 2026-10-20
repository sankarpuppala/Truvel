"""EXIF GPS cross-check, and the promise that stored files carry no EXIF.

Two separate jobs (SPEC §9.7):

1. **Cross-check.** The client reads EXIF GPS with exifr *before* resizing and
   sends the coordinates with the upload. If they are more than 2 km from the
   pin, we warn the user and flag the media `gps_mismatch` for review. Missing
   EXIF is completely normal -- Android's photo picker strips location before
   the file ever reaches the browser -- so it is never required and never
   penalised.

2. **Stripping.** Every stored photo is re-encoded by `media_store`, which
   writes pixels only. That is what guarantees invariant 2; this module just
   provides the verifier used by the test (AC-7).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from ..config import cfg
from ..geo import haversine_km

GPS_MISMATCH = "gps_mismatch"


def gps_mismatch(
    exif_lat: float | None,
    exif_lng: float | None,
    pin_lat: float,
    pin_lng: float,
    max_km: float | None = None,
) -> bool:
    """True when the photo's own GPS is implausibly far from the pin.

    Absent EXIF returns False: we cannot conclude anything from a photo that
    does not say where it was taken.
    """
    if exif_lat is None or exif_lng is None:
        return False
    if max_km is None:
        max_km = float(cfg("integrity.exif_mismatch_km", 2))
    return haversine_km(exif_lat, exif_lng, pin_lat, pin_lng) > max_km


def has_exif(path: str | Path) -> bool:
    """Whether a stored file still carries EXIF. Used by the AC-7 test.

    Checks both the parsed EXIF block and the raw `exif` bytes, because Pillow
    can report an empty dict while the segment is still in the file.
    """
    with Image.open(path) as img:
        exif = img.getexif()
        if exif is not None and len(dict(exif)) > 0:
            return True
        raw = img.info.get("exif")
        return bool(raw)


def gps_from_exif(exif: dict) -> tuple[float | None, float | None]:
    """Decode EXIF GPS to signed decimal degrees, or (None, None).

    Mostly for tests and for the seed tooling; in the app the client has
    already decoded this with exifr. EXIF stores degrees/minutes/seconds plus a
    N/S/E/W reference, which is why this is not a one-liner.
    """
    gps = exif.get("GPSInfo") or exif.get(34853) or {}
    if not gps:
        return (None, None)

    def to_deg(value) -> float | None:  # noqa: ANN001
        try:
            d, m, s = (float(x) for x in value)
        except (TypeError, ValueError):
            return None
        return d + m / 60.0 + s / 3600.0

    lat = to_deg(gps.get("GPSLatitude") or gps.get(2))
    lng = to_deg(gps.get("GPSLongitude") or gps.get(4))
    if lat is None or lng is None:
        return (None, None)
    if str(gps.get("GPSLatitudeRef") or gps.get(1) or "N").upper().startswith("S"):
        lat = -lat
    if str(gps.get("GPSLongitudeRef") or gps.get(3) or "E").upper().startswith("W"):
        lng = -lng
    return (lat, lng)
