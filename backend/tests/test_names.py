"""SPEC §7.2 name display rules (AC-4)."""
from __future__ import annotations

from app.names import NameRow, display, is_rtl, source_rank, to_dict

# Golconda Fort: English from OSM, Telugu from Wikidata, Urdu too (Telangana's
# second regional language), plus a Tamil label for `mine_local`.
GOLCONDA = [
    NameRow(lang="en", name="Golconda Fort", source="osm"),
    NameRow(lang="te", name="గోల్కొండ కోట", source="wikidata"),
    NameRow(lang="ur", name="گولکندہ قلعہ", source="wikidata"),
    NameRow(lang="ta", name="கோல்கொண்டா கோட்டை", source="wikidata"),
]


def test_ac4_en_local_is_english_then_regional_script():
    block = display(GOLCONDA, "Telangana", "en_local")
    assert block.primary.text == "Golconda Fort"
    assert block.primary.lang == "en"
    assert block.secondary is not None
    assert block.secondary.lang == "te"              # Telangana -> te first
    assert block.secondary.rtl is False


def test_ac4_mine_local_puts_my_language_first():
    block = display(GOLCONDA, "Telangana", "mine_local", "ta")
    assert block.primary.lang == "ta"
    assert block.secondary is not None
    assert block.secondary.lang == "te"


def test_ac4_en_only_has_one_line():
    block = display(GOLCONDA, "Telangana", "en")
    assert block.primary.text == "Golconda Fort"
    assert block.secondary is None


def test_ac4_never_more_than_two_lines():
    for mode in ("en_local", "mine_local", "en"):
        block = display(GOLCONDA, "Telangana", mode, "ta")
        lines = [block.primary] + ([block.secondary] if block.secondary else [])
        assert len(lines) <= 2


def test_ac4_urdu_name_is_marked_rtl():
    """An Urdu name must be flagged so the frontend can wrap it in <bdi>."""
    assert is_rtl("ur") and is_rtl("ks") and is_rtl("sd")
    assert not is_rtl("te")
    # Kashmir's regional languages are [ur, ks], so the second line is RTL.
    block = display(
        [
            NameRow(lang="en", name="Dal Lake", source="osm"),
            NameRow(lang="ur", name="دل جھیل", source="wikidata"),
        ],
        "Jammu and Kashmir",
        "en_local",
    )
    assert block.secondary is not None
    assert block.secondary.lang == "ur"
    assert block.secondary.rtl is True


def test_mine_local_falls_back_to_english_when_my_language_is_missing():
    block = display(GOLCONDA, "Telangana", "mine_local", "mni")
    assert block.primary.lang == "en"


def test_source_precedence_user_with_three_votes_wins():
    """SPEC §7.2: an endorsed visitor name beats imported data."""
    rows = [
        NameRow(lang="en", name="From OSM", source="osm"),
        NameRow(lang="en", name="Locals call it this", source="user", votes=3),
    ]
    block = display(rows, "Telangana", "en")
    assert block.primary.text == "Locals call it this"


def test_source_precedence_unvoted_user_name_loses_to_osm():
    """One person must not be able to rename a fort."""
    rows = [
        NameRow(lang="en", name="From OSM", source="osm"),
        NameRow(lang="en", name="My own idea", source="user", votes=0),
    ]
    block = display(rows, "Telangana", "en")
    assert block.primary.text == "From OSM"


def test_source_rank_order():
    assert source_rank(NameRow("en", "x", "user", votes=3)) < source_rank(
        NameRow("en", "x", "osm")
    )
    assert source_rank(NameRow("en", "x", "osm")) < source_rank(
        NameRow("en", "x", "wikidata")
    )
    assert source_rank(NameRow("en", "x", "wikidata")) < source_rank(
        NameRow("en", "x", "user", votes=0)
    )
    assert source_rank(NameRow("en", "x", "user", votes=0)) < source_rank(
        NameRow("en", "x", "auto")
    )


def test_auto_names_are_tagged():
    rows = [NameRow(lang="te", name="అటో", source="auto")]
    block = display(rows, "Telangana", "en_local")
    assert block.primary.auto is True


def test_no_second_line_when_we_have_no_regional_name():
    rows = [NameRow(lang="en", name="Only English", source="osm")]
    block = display(rows, "Telangana", "en_local")
    assert block.secondary is None


def test_payload_shape():
    payload = to_dict(display(GOLCONDA, "Telangana", "en_local"))
    assert set(payload) == {"primary", "secondary", "langs"}
    assert set(payload["primary"]) == {"text", "lang", "rtl", "auto"}
    assert "te" in payload["langs"] and "ur" in payload["langs"]


def test_unnamed_place_still_renders():
    block = display([], None, "en_local")
    assert block.primary.text == "Unnamed place"
