# CONTEXT_MAP.md — read only what the task needs

SPEC.md is ~15k tokens, PLAN.md ~6.5k, and `docs/design-reference.html` is
549 KB (fonts embedded as base64, ~150k tokens). Don't read any of them whole.
Read the line ranges below with `sed -n 'A,Bp' SPEC.md` or the Read tool's
offset/limit. Line numbers are as of 23 Oct 2026; if a heading has moved,
`grep -n '^### 9.4' SPEC.md` finds it.

## Never open
- `docs/design-reference.html` — look at `results/screens/{light,dark}/<n>-<screen>.png` (e.g. `5-place.png`)
  (390 × 844) or `results/screens/laptop-*/` instead.
- `frontend/package-lock.json`, `results/*/<timestamp>/` (use `latest/`).
- `pagdandi-starter.zip`.

## SPEC.md sections (line ranges)

| § | Topic | Lines |
|---|---|---|
| 1–3 | Goal, users, moat | 20–85 |
| 4 | Tiers, cut order | 86–101 |
| 5 | Data model | 102–168 |
| 6 | Data sources (OSM 171, Wikidata 192, Commons 214, Google ban 232, fame 241) | 169–247 |
| 7 | Languages, names display (7.2 at 282), search 315 | 248–321 |
| 8.1–8.4 | Nav, Nearby, Watch, Explore | 322–371 |
| 8.5–8.6 | Place page, Add | 372–414 |
| 8.7–8.8 | Check-in, Pulse | 415–447 |
| 8.9–8.11 | You, Studio, Social | 448–476 |
| 8.12–8.14 | Tier 2 extras, moderation, safety + fragile | 477–509 |
| 9.1–9.5 | Wilson, gems, trending, deck, Watch rank | 510–561 |
| 9.6–9.8 | Dedupe, photo integrity, fraud rules | 562–596 |
| 9.9–9.12 | Attribution, engaged views, CLIP, xlit | 597–638 |
| 10 | Kadam, pool, split, eligibility | 639–701 |
| 11 | API | 702–763 |
| 12 | Design system (tokens 776, type 794, components 810) | 764–843 |
| 13–15 | Accessibility, privacy/licences, performance | 844–881 |
| 16 | Config | 882–1005 |
| 17 | Evaluation | 1006–1037 |
| 18 | Acceptance criteria AC-1..25 | 1038–1097 |
| 19–20 | Decisions, open questions | 1098–1130 |

## By kind of task

| Task | Read | Code entry points |
|---|---|---|
| Check-in / verification / fraud | §8.7, §9.8, invariants 1, 3, 8 | `routers/checkin.py`, `integrity/fraud.py`, `kadam.py` |
| Ranking / Explore sorts | §9.1–9.3, §8.4 | `ranking/*.py`, `routers/places.py:_rank_places` |
| Deck | §8.2, §9.4 | `deck/*.py`, `routers/deck_router.py` |
| Watch | §8.3, §9.5, §9.10 | `watch/*.py`, `routers/watch_router.py`, `components/WatchPlayer.tsx` |
| Uploads / media | §8.6, §9.6–9.7, invariant 2 | `media_store.py`, `routers/add.py`, `integrity/` |
| Partner / Studio / money | §10, invariants 4, 13 | `partner/*.py`, `routers/studio.py`, `components/StudioParts.tsx` |
| Names / languages | §7, invariants 10–11 | `names.py`, `components/NameBlock.tsx`, `lib/languages.ts` |
| Auth / accounts | §5 User/Session, §14 | `auth.py`, `routers/auth_router.py`, `mailer.py` |
| Map / fog | §8.4, §14 (borders) | `components/FogMap.tsx`, `styles/map.css`, `routers/me.py:passport` |
| UI look | §12.2–12.5 only | `styles/tokens.css`, the matching PNG in `results/screens/` |
| Seeding data | §6 | `scripts/seed_*.py` (never run live APIs in tests) |
| Any Track B card | its card in `docs/NEXT_LEVEL_PLAN.md`, then only the § it names | — |

PLAN.md: read only the phase you are on (`grep -n '^## Phase' PLAN.md`) and the
last 20 lines of "Progress log". Never the whole file.

## Cheap habits
- Search before reading: `grep -n` / Grep with a narrow path, then read ±30 lines.
- Run one test file while working (`pytest tests/test_x.py -q`); the full suite
  (~66 s, 227 tests) once before commit. Pipe long output through `tail -20`.
- One card per session; start a new session instead of continuing a long one.
- Use a subagent only for broad sweeps or the independent review (A1); it keeps
  file dumps out of the main session.
- Append to PLAN.md "Progress log" in one or two lines, not paragraphs; move
  entries older than a week to `docs/LOG.md`.
