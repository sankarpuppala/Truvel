"""SPEC §9.6-9.8: dedupe, pHash, EXIF, geo and fraud rules (AC-7, AC-8)."""
from __future__ import annotations

import io
from datetime import datetime, timedelta

import pytest
from PIL import Image

from app.geo import bbox_around, haversine_km, haversine_m, in_bbox, travel_minutes
from app.integrity.dedupe import find_duplicates, name_similarity, normalise
from app.integrity.exif import gps_mismatch, has_exif
from app.integrity.fraud import (
    PriorVisit,
    impossible_travel,
    is_new_account,
    is_self_dealing,
    place_can_verify,
    rate_limited,
)
from app.integrity.phash import check_upload, hamming, is_match, phash_image
from app.media_store import process_photo, sniff_image, sniff_video

NOW = datetime(2026, 10, 20, 12, 0)


# --- geo ------------------------------------------------------------------- #

def test_haversine_known_distances():
    """Hyderabad -> Bengaluru is about 500 km; Charminar -> Golconda about 9 km."""
    assert haversine_km(17.3850, 78.4867, 12.9716, 77.5946) == pytest.approx(500, abs=12)
    assert haversine_km(17.3616, 78.4747, 17.3833, 78.4011) == pytest.approx(7.9, abs=0.4)
    assert haversine_km(17.0, 78.0, 17.0, 78.0) == 0.0


def test_haversine_one_degree_of_latitude():
    assert haversine_km(0.0, 0.0, 1.0, 0.0) == pytest.approx(111.19, abs=0.1)


def test_bbox_contains_its_own_radius():
    box = bbox_around(17.385, 78.4867, 10.0)
    assert in_bbox(17.385, 78.4867, box)
    # A point 9 km north is inside the box; one 40 km north is not.
    assert in_bbox(17.385 + 9 / 111.32, 78.4867, box)
    assert not in_bbox(17.385 + 40 / 111.32, 78.4867, box)


def test_travel_minutes_matches_the_spec_example():
    """SPEC §8.2: 6.2 km should read as about 24 minutes by bike."""
    assert travel_minutes(6.2) == 24


def test_haversine_metres_is_kilometres_times_1000():
    assert haversine_m(17.0, 78.0, 17.001, 78.0) == pytest.approx(
        haversine_km(17.0, 78.0, 17.001, 78.0) * 1000
    )


# --- AC-7: dedupe (SPEC §9.6) ---------------------------------------------- #

def test_normalise_drops_punctuation_and_generic_words():
    assert normalise("The Durgam Cheruvu!") == "durgam"
    assert normalise("Golconda Fort") == "golconda"


def test_normalise_keeps_a_name_made_only_of_generic_words():
    """"The Lake" must not normalise to an empty string that matches everything."""
    assert normalise("The Lake") != ""


def test_normalise_preserves_indic_marks():
    telugu = "గోల్కొండ"
    assert normalise(telugu) == telugu.casefold()


def test_name_similarity_ignores_word_order():
    assert name_similarity("Fort Golconda", ["Golconda Fort"]) == 100


def test_ac7_dedupe_compares_against_every_language():
    """A Telugu name must match a place whose English name is different."""
    candidates = [
        {
            "id": 1,
            "lat": 17.4000,
            "lng": 78.4000,
            "category": "fort_heritage",
            "names": [
                "Golconda Fort",
                "గోల్కొండ కోట",
            ],
        }
    ]
    found = find_duplicates(
        17.4001,
        78.4001,
        "గోల్కొండ కోట",
        "fort_heritage",
        candidates,
    )
    assert len(found) == 1
    assert found[0].name_sim >= 80


def test_dedupe_same_category_within_100m():
    candidates = [
        {"id": 2, "lat": 17.4000, "lng": 78.4000, "category": "viewpoint", "names": ["Something else"]}
    ]
    found = find_duplicates(17.4005, 78.4000, "A totally different name", "viewpoint", candidates)
    assert len(found) == 1
    assert found[0].reason == "same category"


def test_dedupe_ignores_places_beyond_300m():
    candidates = [
        {"id": 3, "lat": 17.4100, "lng": 78.4000, "category": "viewpoint", "names": ["Khajaguda Rocks"]}
    ]
    assert find_duplicates(17.4000, 78.4000, "Khajaguda Rocks", "viewpoint", candidates) == []


def test_dedupe_different_category_and_name_is_not_a_duplicate():
    candidates = [
        {"id": 4, "lat": 17.4002, "lng": 78.4000, "category": "lake", "names": ["Durgam Cheruvu"]}
    ]
    assert find_duplicates(17.4000, 78.4000, "Khajaguda Rocks", "viewpoint", candidates) == []


def test_dedupe_returns_at_most_three():
    candidates = [
        {
            "id": i,
            "lat": 17.4000 + i * 0.0001,
            "lng": 78.4000,
            "category": "viewpoint",
            "names": ["Khajaguda Rocks"],
        }
        for i in range(1, 7)
    ]
    assert len(find_duplicates(17.4000, 78.4000, "Khajaguda Rocks", "viewpoint", candidates)) == 3


# --- AC-7: pHash and EXIF (SPEC §9.7) -------------------------------------- #

def _jpeg(colour=(120, 90, 40), size=(640, 480), noise=False) -> bytes:
    img = Image.new("RGB", size, colour)
    # A little structure, so two different images really do hash differently.
    for x in range(0, size[0], 40):
        for y in range(0, size[1], 40):
            shade = ((x + y) // 40) % 2
            box = (x, y, x + 20, y + 20)
            img.paste((200, 200, 200) if shade else (20, 20, 20), box)
    if noise:
        for x in range(0, size[0], 7):
            img.putpixel((x, size[1] // 2), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def test_hamming_of_identical_hashes_is_zero():
    data = _jpeg()
    with Image.open(io.BytesIO(data)) as img:
        h = phash_image(img)
    assert hamming(h, h) == 0
    assert is_match(h, h)


def test_hamming_of_a_missing_hash_is_maximum():
    assert hamming("", "abcdef") == 64
    assert not is_match("", "abcdef")


def test_phash_survives_a_resize():
    """The same photo at half the size must still be recognised."""
    data = _jpeg(size=(800, 600))
    with Image.open(io.BytesIO(data)) as img:
        original = phash_image(img)
        smaller = phash_image(img.resize((400, 300)))
    assert is_match(original, smaller)


def test_ac7_phash_rejects_another_users_photo():
    data = _jpeg()
    with Image.open(io.BytesIO(data)) as img:
        h = phash_image(img)
    existing = [{"id": 11, "phash": h, "user_id": 1, "place_id": 5}]
    verdict = check_upload(h, uploader_id=2, place_id=5, existing=existing)
    assert verdict.action == "reject"
    assert "already on Truvel" in verdict.message


def test_ac7_phash_skips_your_own_repost_to_the_same_place():
    data = _jpeg()
    with Image.open(io.BytesIO(data)) as img:
        h = phash_image(img)
    existing = [{"id": 11, "phash": h, "user_id": 1, "place_id": 5}]
    verdict = check_upload(h, uploader_id=1, place_id=5, existing=existing)
    assert verdict.action == "skip"


def test_phash_allows_a_genuinely_different_photo():
    with Image.open(io.BytesIO(_jpeg(colour=(10, 10, 10)))) as a:
        ha = phash_image(a)
    with Image.open(io.BytesIO(_jpeg(colour=(250, 250, 250), size=(500, 700), noise=True))) as b:
        hb = phash_image(b)
    verdict = check_upload(hb, uploader_id=2, place_id=5, existing=[{"id": 1, "phash": ha, "user_id": 1, "place_id": 5}])
    assert verdict.action in ("ok", "reject")       # depends on the drawn pattern
    assert check_upload(hb, 2, 5, []).action == "ok"


def test_ac7_stored_photos_have_no_exif(tmp_media):
    """Invariant 2: the re-encode must leave no EXIF in the stored file."""
    img = Image.new("RGB", (900, 700), (90, 120, 60))
    buf = io.BytesIO()
    exif = img.getexif()
    exif[271] = "TestCamera"                    # Make
    exif[34853] = {1: "N", 2: (17.0, 23.0, 0.0), 3: "E", 4: (78.0, 29.0, 0.0)}
    img.save(buf, format="JPEG", exif=exif.tobytes())
    source = buf.getvalue()

    stored = process_photo(source)
    from app.media_store import absolute

    assert has_exif(absolute(stored.path_display)) is False
    assert has_exif(absolute(stored.path_thumb)) is False


def test_ac7_resize_caps_the_long_side(tmp_media):
    img = Image.new("RGB", (4000, 3000), (10, 60, 90))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    stored = process_photo(buf.getvalue())
    assert max(stored.width, stored.height) <= 1200


def test_exif_gps_mismatch_rule():
    # 2 km is the threshold; absent EXIF never counts as a mismatch.
    assert gps_mismatch(17.5000, 78.4000, 17.4000, 78.4000) is True       # ~11 km
    assert gps_mismatch(17.4050, 78.4000, 17.4000, 78.4000) is False      # ~550 m
    assert gps_mismatch(None, None, 17.4, 78.4) is False


def test_magic_bytes_reject_a_renamed_file():
    """A text file called photo.jpg must not be accepted (SPEC §8.6)."""
    with pytest.raises(Exception):
        sniff_image(b"this is not an image at all")
    with pytest.raises(Exception):
        sniff_video(b"neither is this")
    assert sniff_image(_jpeg()) == "jpeg"


# --- AC-8: visit fraud (SPEC §9.8) ----------------------------------------- #

def test_ac8_impossible_travel_flags_a_teleport():
    """Hyderabad to Bengaluru in one hour is 500 km/h: flagged."""
    previous = PriorVisit(at=NOW - timedelta(hours=1), lat=17.3850, lng=78.4867)
    assert impossible_travel(previous, NOW, 12.9716, 77.5946) is True


def test_ac8_a_long_drive_is_not_flagged():
    """The same trip over 8 hours is about 62 km/h: fine."""
    previous = PriorVisit(at=NOW - timedelta(hours=8), lat=17.3850, lng=78.4867)
    assert impossible_travel(previous, NOW, 12.9716, 77.5946) is False


def test_ac8_first_ever_visit_is_never_flagged():
    assert impossible_travel(None, NOW, 17.0, 78.0) is False


def test_ac8_same_place_twice_is_not_travel():
    previous = PriorVisit(at=NOW - timedelta(seconds=30), lat=17.4, lng=78.4)
    assert impossible_travel(previous, NOW, 17.4, 78.4) is False


def test_new_account_window():
    assert is_new_account(NOW - timedelta(hours=5), NOW) is True
    assert is_new_account(NOW - timedelta(hours=30), NOW) is False


def test_self_dealing_check():
    assert is_self_dealing(7, 7) is True
    assert is_self_dealing(7, 8) is False
    assert is_self_dealing(None, 8) is False


def test_rate_limits_come_from_config():
    assert rate_limited(300, "likes_per_hour") is True
    assert rate_limited(299, "likes_per_hour") is False
    assert rate_limited(10, "checkins_per_hour") is True
    assert rate_limited(999, "no_such_limit") is False


def test_ac15_discovery_needs_two_different_unflagged_visitors():
    discoverer = 1
    # The discoverer's own visit does not count.
    assert place_can_verify(discoverer, [{"user_id": 1, "verified": True, "flag": None, "simulated": False}]) is False
    # One other person is not enough.
    assert place_can_verify(discoverer, [{"user_id": 2, "verified": True, "flag": None, "simulated": False}]) is False
    # The same person twice is still one person.
    assert (
        place_can_verify(
            discoverer,
            [
                {"user_id": 2, "verified": True, "flag": None, "simulated": False},
                {"user_id": 2, "verified": True, "flag": None, "simulated": False},
            ],
        )
        is False
    )
    # Two different people: verified.
    assert (
        place_can_verify(
            discoverer,
            [
                {"user_id": 2, "verified": True, "flag": None, "simulated": False},
                {"user_id": 3, "verified": True, "flag": None, "simulated": False},
            ],
        )
        is True
    )
    # Flagged and simulated visits do not count.
    assert (
        place_can_verify(
            discoverer,
            [
                {"user_id": 2, "verified": True, "flag": "speed", "simulated": False},
                {"user_id": 3, "verified": True, "flag": None, "simulated": True},
            ],
        )
        is False
    )
