"""Duplicate place detection (SPEC §9.6).

Two people standing on the same rock will type two different names for it:
"Khajaguda Rocks", "Khajaguda hillock", "ఖాజాగూడ గుట్టలు". The check runs when
the pin is placed and again on submit, over places within 300 m.

A candidate is a likely duplicate if:
    distance <= 300 m and name_sim >= 80
 or distance <= 100 m and same category

`name_sim` compares the new name against **every** name of the candidate, in
every language, and takes the best match (AC-7). Before comparing we normalise:
lowercase, strip punctuation, and drop generic words from the per-language list
in config -- otherwise "Durgam Cheruvu" and "Khajaguda Cheruvu" score highly on
the shared word "cheruvu" (lake) alone.

The user always decides. We show up to 3 candidates and ask "Is it one of
these?" -- we never silently merge, because a wrong merge loses someone's find.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

from ..config import cfg
from ..geo import haversine_m


@dataclass
class DupeCandidate:
    """A nearby place and why we think it might be the same one."""

    place_id: int
    distance_m: float
    name_sim: int
    same_category: bool
    reason: str
    names: list[str]


def _strip_punctuation(text: str) -> str:
    """Drop punctuation and symbols but keep letters, digits and marks.

    Unicode categories rather than a regex of ASCII punctuation, so Devanagari
    danda and Indic viramas are handled correctly: a virama is a mark (Mn) and
    must survive, a danda is punctuation (Po) and must go.
    """
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith(("L", "N", "M")):
            out.append(ch)
        else:
            out.append(" ")
    return "".join(out)


def generic_words() -> set[str]:
    """Every generic word from every language in config, as one set.

    One flat set rather than per-language lists because we do not know which
    language the typed name is in -- someone may type a Telugu word in Latin
    script ("cheruvu"), which is exactly the case that needs stripping.
    """
    table = cfg("dedupe.generic_words", {}) or {}
    words: set[str] = set()
    for langs in table.values():
        for w in langs or []:
            words.add(str(w).casefold())
    return words


def normalise(name: str, drop_generic: bool = True) -> str:
    """Lowercase, strip punctuation, drop generic words (SPEC §9.6)."""
    text = unicodedata.normalize("NFC", name or "")
    text = _strip_punctuation(text).casefold()
    tokens = [t for t in text.split() if t]
    if drop_generic:
        generic = generic_words()
        kept = [t for t in tokens if t not in generic]
        # If the name was *only* generic words ("The Lake"), keep them: an empty
        # string would match everything.
        tokens = kept or tokens
    return " ".join(tokens)


def name_similarity(new_name: str, candidate_names: list[str]) -> int:
    """Best token_set_ratio between the new name and any name of the candidate.

    `token_set_ratio` ignores word order and duplication, so "Fort Golconda"
    matches "Golconda Fort" at 100. Returns 0..100.
    """
    a = normalise(new_name)
    if not a:
        return 0
    best = 0
    for other in candidate_names:
        b = normalise(other)
        if not b:
            continue
        best = max(best, int(round(fuzz.token_set_ratio(a, b))))
    return best


def find_duplicates(
    new_lat: float,
    new_lng: float,
    new_name: str,
    new_category: str,
    nearby: list[dict],
    limit: int = 3,
) -> list[DupeCandidate]:
    """Rank likely duplicates among `nearby` places, closest/strongest first.

    `nearby` items are dicts with keys: id, lat, lng, category, names (list[str]).
    Only places that trip one of the two rules are returned.
    """
    radius_m = float(cfg("dedupe.radius_m", 300))
    sim_min = int(cfg("dedupe.name_sim_min", 80))
    cat_radius_m = float(cfg("dedupe.same_category_radius_m", 100))

    out: list[DupeCandidate] = []
    for place in nearby:
        dist = haversine_m(new_lat, new_lng, float(place["lat"]), float(place["lng"]))
        if dist > radius_m:
            continue
        names = list(place.get("names") or [])
        sim = name_similarity(new_name, names)
        same_cat = str(place.get("category") or "") == str(new_category or "")

        if sim >= sim_min:
            reason = f"{sim}% name match"
        elif same_cat and dist <= cat_radius_m:
            reason = "same category"
        else:
            continue

        out.append(
            DupeCandidate(
                place_id=int(place["id"]),
                distance_m=dist,
                name_sim=sim,
                same_category=same_cat,
                reason=reason,
                names=names,
            )
        )

    # Strongest name match first, then nearest: the one they most likely meant.
    out.sort(key=lambda c: (-c.name_sim, c.distance_m))
    return out[:limit]
