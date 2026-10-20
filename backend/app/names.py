"""Place-name selection and display (SPEC §7.2).

A place has many names: OSM `name:*` tags, Wikidata labels in 22 languages,
names typed by visitors. Which two lines do we show?

**Source precedence**, best first:
    user with >= 3 votes  ->  osm  ->  wikidata  ->  user (fewer votes)  ->  auto

Visitor names that the community has endorsed beat imported data, because the
people who go there know what it is called. Unendorsed user names rank below
imported data so one person cannot rename a fort. `auto` (Tier-2
transliteration) is last and is shown with a small "auto" tag.

**Display modes**, per the user's `names_mode`:
    en_local    line 1 English,            line 2 regional language
    mine_local  line 1 the user's language, line 2 regional (if a different language)
    en          English only

Never more than 2 lines. Every line carries its own `lang` attribute, and
Perso-Arabic names are returned with `rtl: true` so the frontend can wrap them
in `<bdi dir="rtl">` (AC-4).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import regional_langs

# Perso-Arabic scripts among our languages: these render right-to-left.
RTL_LANGS = {"ur", "ks", "sd"}

SOURCE_RANK = {"osm": 1, "wikidata": 2, "user": 3, "auto": 4}
VOTED_USER_RANK = 0          # user name with >= 3 votes outranks everything
VOTES_FOR_PRECEDENCE = 3


@dataclass
class NameRow:
    """One PlaceName row, as the selector sees it."""

    lang: str
    name: str
    source: str = "user"
    votes: int = 0


@dataclass
class NameLine:
    """One rendered line: the text, its language, and how to lay it out."""

    text: str
    lang: str
    rtl: bool = False
    auto: bool = False


@dataclass
class NameBlock:
    """What the API returns for a place name (consumed by <NameBlock/>)."""

    primary: NameLine
    secondary: NameLine | None = None
    all_langs: list[str] = field(default_factory=list)


def is_rtl(lang: str) -> bool:
    return lang in RTL_LANGS


def source_rank(row: NameRow) -> int:
    """Lower is better. Endorsed user names jump to the front (SPEC §7.2)."""
    if row.source == "user" and row.votes >= VOTES_FOR_PRECEDENCE:
        return VOTED_USER_RANK
    return SOURCE_RANK.get(row.source, 99)


def best_in_lang(rows: list[NameRow], lang: str) -> NameRow | None:
    """The best name for one language, by source precedence then votes."""
    candidates = [r for r in rows if r.lang == lang and r.name.strip()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda r: (source_rank(r), -r.votes, r.name))[0]


def _line(row: NameRow) -> NameLine:
    return NameLine(
        text=row.name,
        lang=row.lang,
        rtl=is_rtl(row.lang),
        auto=(row.source == "auto"),
    )


def regional_lang_for(state: str | None, rows: list[NameRow]) -> str | None:
    """The regional language we actually have a name in, for this state.

    Telangana maps to [te, ur]; if we only hold a Telugu name, that is the
    regional line. If we hold neither, there is no second line -- we never
    invent one.
    """
    for lang in regional_langs(state):
        if lang == "en":
            continue
        if best_in_lang(rows, lang) is not None:
            return lang
    return None


def display(
    rows: list[NameRow],
    state: str | None,
    names_mode: str = "en_local",
    names_lang: str = "en",
) -> NameBlock:
    """Build the one- or two-line name block for a place (SPEC §7.2)."""
    rows = [r for r in rows if (r.name or "").strip()]
    english = best_in_lang(rows, "en")
    regional = regional_lang_for(state, rows)

    # A place with no English name at all still has to render: fall back to any
    # name we hold, preferring the regional one.
    def any_name() -> NameRow | None:
        if regional:
            r = best_in_lang(rows, regional)
            if r:
                return r
        return sorted(rows, key=lambda r: (source_rank(r), -r.votes))[0] if rows else None

    if names_mode == "en":
        head = english or any_name()
        if head is None:
            return NameBlock(NameLine("Unnamed place", "en"))
        return NameBlock(_line(head), None, sorted({r.lang for r in rows}))

    if names_mode == "mine_local":
        mine = best_in_lang(rows, names_lang) or english or any_name()
        if mine is None:
            return NameBlock(NameLine("Unnamed place", "en"))
        second = None
        if regional and regional != mine.lang:
            r = best_in_lang(rows, regional)
            if r and r.name != mine.name:
                second = _line(r)
        return NameBlock(_line(mine), second, sorted({r.lang for r in rows}))

    # en_local (default): English on top, the place's own script underneath.
    head = english or any_name()
    if head is None:
        return NameBlock(NameLine("Unnamed place", "en"))
    second = None
    if regional and regional != head.lang:
        r = best_in_lang(rows, regional)
        if r and r.name != head.name:
            second = _line(r)
    return NameBlock(_line(head), second, sorted({r.lang for r in rows}))


def to_dict(block: NameBlock) -> dict:
    """JSON shape the frontend expects."""

    def line(ln: NameLine | None) -> dict | None:
        if ln is None:
            return None
        return {"text": ln.text, "lang": ln.lang, "rtl": ln.rtl, "auto": ln.auto}

    return {
        "primary": line(block.primary),
        "secondary": line(block.secondary),
        "langs": block.all_langs,
    }


def search_strings(rows: list[NameRow]) -> list[str]:
    """Every name of a place, for the dedupe comparison (SPEC §9.6, AC-7)."""
    return [r.name for r in rows if (r.name or "").strip()]
