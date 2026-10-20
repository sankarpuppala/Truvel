"""Wikimedia Commons licence handling (SPEC §6.3, AC-3).

These run entirely on saved fixtures -- PLAN.md is explicit that tests never
touch live APIs. The fixtures are the shape the Commons API really returns,
trimmed to the fields we read.
"""
from __future__ import annotations

from app.commons import (
    attribution_text,
    licence_allowed,
    parse_imageinfo,
)


def fixture(licence: str, *, artist: str = '<a href="/wiki/User:Someone">A. Photographer</a>') -> dict:
    """A Commons `imageinfo` response with a given licence."""
    return {
        "query": {
            "pages": {
                "12345": {
                    "title": "File:Golconda Fort.jpg",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/.../Golconda_Fort.jpg",
                            "thumburl": "https://upload.wikimedia.org/.../1200px-Golconda_Fort.jpg",
                            "thumbwidth": 1200,
                            "thumbheight": 800,
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Golconda_Fort.jpg",
                            "extmetadata": {
                                "Artist": {"value": artist},
                                "LicenseShortName": {"value": licence},
                                "LicenseUrl": {
                                    "value": "https://creativecommons.org/licenses/by-sa/4.0"
                                },
                            },
                        }
                    ],
                }
            }
        }
    }


# --- AC-3: the allowlist -------------------------------------------------- #

def test_ac3_allowed_licences_pass():
    for licence in (
        "CC0",
        "CC0 1.0",
        "Public domain",
        "Public domain in the United States",
        "CC BY 2.0",
        "CC BY 4.0",
        "CC BY-SA 3.0",
        "CC BY-SA 4.0",
    ):
        assert licence_allowed(licence) is True, licence


def test_ac3_non_commercial_and_no_derivatives_are_refused():
    """These are the ones that look close but are not usable here."""
    for licence in ("CC BY-NC 4.0", "CC BY-NC-SA 3.0", "CC BY-ND 4.0", "Fair use", "All rights reserved", ""):
        assert licence_allowed(licence) is False, licence


def test_ac3_a_photo_with_an_allowed_licence_is_parsed():
    photo = parse_imageinfo(fixture("CC BY-SA 4.0"), "Golconda Fort.jpg")
    assert photo is not None
    assert photo.licence == "CC BY-SA 4.0"
    assert photo.author == "A. Photographer"          # HTML stripped
    assert photo.width == 1200
    assert photo.url.endswith("1200px-Golconda_Fort.jpg")
    assert photo.file_page == "https://commons.wikimedia.org/wiki/File:Golconda_Fort.jpg"


def test_ac3_a_photo_with_a_refused_licence_is_not_stored():
    """The place falls back to its category illustration instead."""
    assert parse_imageinfo(fixture("CC BY-NC 4.0"), "Somewhere.jpg") is None
    assert parse_imageinfo(fixture("All rights reserved"), "Somewhere.jpg") is None


def test_ac3_missing_imageinfo_is_handled():
    assert parse_imageinfo({"query": {"pages": {"-1": {"title": "File:None"}}}}, "None.jpg") is None
    assert parse_imageinfo({}, "None.jpg") is None


def test_ac3_author_falls_back_when_absent():
    photo = parse_imageinfo(fixture("CC0", artist=""), "Golconda Fort.jpg")
    assert photo is not None
    assert photo.author == "Unknown author"


def test_ac3_html_in_the_artist_field_is_stripped():
    photo = parse_imageinfo(
        fixture("CC BY 4.0", artist='<a href="//commons.wikimedia.org/wiki/User:X" title="X">Ravi K</a>'),
        "Golconda Fort.jpg",
    )
    assert photo is not None
    assert photo.author == "Ravi K"
    assert "<" not in photo.author


def test_ac3_attribution_line_names_author_licence_and_source():
    """Invariant 6: every Commons photo shows all three."""
    line = attribution_text("A. Photographer", "CC BY-SA 4.0")
    assert "A. Photographer" in line
    assert "CC BY-SA 4.0" in line
    assert "Wikimedia Commons" in line


def test_ac3_stored_media_row_carries_its_attribution(session):
    """A Commons photo in the database must never lose its credit."""
    from app.models import Media, Place
    from app.services import media_payload

    place = Place(lat=17.38, lng=78.40, category="fort_heritage", source="wikidata")
    session.add(place)
    session.commit()
    session.refresh(place)

    photo = parse_imageinfo(fixture("CC BY-SA 4.0"), "Golconda Fort.jpg")
    assert photo is not None
    media = Media(
        place_id=int(place.id),
        kind="photo",
        path_display=photo.filename,
        caption="Golconda Fort",
        source="commons",
        licence=photo.licence,
        attribution=attribution_text(photo.author, photo.licence),
        source_url=photo.file_page,
    )
    session.add(media)
    session.commit()
    session.refresh(media)

    payload = media_payload(media)
    assert payload["source"] == "commons"
    assert "A. Photographer" in payload["attribution"]
    assert "CC BY-SA 4.0" in payload["licence"]
    assert payload["source_url"].startswith("https://commons.wikimedia.org/wiki/File:")
    # Served from our own origin, never hot-linked (invariant 7).
    assert payload["url"].startswith("/api/media/commons/")
