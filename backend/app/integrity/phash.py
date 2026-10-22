"""Perceptual hashing of photos (SPEC §9.7).

A perceptual hash is a 64-bit fingerprint of what a picture *looks like*. Unlike
a checksum it survives resizing, re-compression and small crops, so it catches
someone downloading a photo from the app (or from the web) and posting it as
their own find.

`imagehash.phash` works on the discrete cosine transform of a 32x32 greyscale
version of the image, keeping the low-frequency corner -- the coarse structure
of light and dark that a human recognises. Two hashes are compared by Hamming
distance (how many of the 64 bits differ):

    <= 8 bits  the same photo    (config: integrity.phash_max_hamming)
    > 8 bits   a different photo

Another user's existing photo at <= 8 is rejected outright. The *same* user
re-posting to the *same* place is skipped silently -- that is a duplicate
upload, not theft.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import imagehash
from PIL import Image

from ..config import cfg

HASH_BITS = 64


def phash_image(img: "Image.Image") -> str:
    """Hex phash of an open Pillow image."""
    return str(imagehash.phash(img))


def phash_file(path: str | Path) -> str:
    """Hex phash of an image file on disk."""
    with Image.open(path) as img:
        return phash_image(img)


def hamming(a: str, b: str) -> int:
    """Bit distance between two hex phashes.

    Returns HASH_BITS (maximum distance, i.e. "nothing like it") when either
    hash is missing or unparseable, so a bad hash can never read as a match.
    """
    if not a or not b:
        return HASH_BITS
    try:
        return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))
    except (ValueError, TypeError):
        return HASH_BITS


def is_match(a: str, b: str, max_hamming: int | None = None) -> bool:
    """Whether two hashes are the same photo under the configured threshold."""
    if max_hamming is None:
        max_hamming = int(cfg("integrity.phash_max_hamming", 8))
    return hamming(a, b) <= max_hamming


@dataclass
class PhashVerdict:
    """What to do with an upload: 'ok', 'reject' or 'skip'."""

    action: str
    message: str = ""
    matched_media_id: int | None = None


def check_upload(
    new_hash: str,
    uploader_id: int | None,
    place_id: int,
    existing: list[dict],
    max_hamming: int | None = None,
) -> PhashVerdict:
    """Decide an upload against stored hashes (SPEC §9.7).

    `existing` items are dicts with keys: id, phash, user_id, place_id. The
    nearest match wins, so the message names the photo actually matched.
    """
    best: tuple[int, dict] | None = None
    for row in existing:
        d = hamming(new_hash, str(row.get("phash") or ""))
        if best is None or d < best[0]:
            best = (d, row)

    if best is None:
        return PhashVerdict("ok")

    threshold = int(cfg("integrity.phash_max_hamming", 8)) if max_hamming is None else max_hamming
    distance, row = best
    if distance > threshold:
        return PhashVerdict("ok")

    same_user = uploader_id is not None and row.get("user_id") == uploader_id
    if same_user and row.get("place_id") == place_id:
        # Their own photo, same place: nothing wrong happened, just nothing new.
        return PhashVerdict("skip", "You have already added this photo here.", row.get("id"))
    return PhashVerdict(
        "reject",
        "This photo is already on Truvel.",
        row.get("id"),
    )
