# PLAN.md — Truvel (v2)

Eight working days, Wed 21 – Wed 28 October 2026. Submit Thursday 29 October.
One phase per Claude Code session. Each phase: Plan Mode → approve → implement →
verify → teach-back (Prompt 5) → commit (Prompt 3).

Legend: **[T1]** must · **[E]** engine/evaluation must · **[T2]** only if time.
Boxes: `[x]` done and verified · `[~]` built but needs real-world input · `[ ]` not started.

**Honest load warning.** v2 is about 40 % bigger than v1 in the same 8 days. It
fits only if each day stays on its phase, and you'll need ~8–9 focused hours a
day. If a day slips by more than half, run Prompt 10 with the SPEC §4 cut order
that evening; don't carry debt into the next day.

## Calendar

| Day | Date | Phases | End-of-day check |
|---|---|---|---|
| 0 | Tue 20 Oct (tonight) | Prompt 1 + Prompt 2; answer Q1–Q6 | SPEC updated with your answers |
| 1 | Wed 21 | P0 Setup (incl. fonts, i18n) · P1 Data: OSM city + Wikidata India + Commons | Places with names in many scripts at `/api/cities/<slug>/places` |
| 2 | Thu 22 | P2 Design system, Explore list, Place page, ranking, names | Explore + Place match the reference |
| 3 | Fri 23 | P3 Accounts, likes, follows, kadam · P4 Nearby deck | Deck swipes on your phone |
| 4 | Sat 24 | P5 Media pipeline, Add (3 flows), Watch feed | Post a video; it plays in Watch |
| 5 | Sun 25 | P6 Check-in, Pulse, Explore map + fog, You/Passport, profiles · **Tier 1 gate** · go out: add 2 places + 2 videos on site | Prompt 6 passes |
| 6 | Mon 26 | P7 Partner engine + Studio · P8 Simulations + demo data | Studio shows simulated earnings; results/ filled |
| 7 | Tue 27 | P9 Polish, reviews, Tier 2 picks | Prompts 7 + 8 issues fixed |
| 8 | Wed 28 | P10 Report, viva, rehearsal · **code freeze 12:00** | You can demo and explain everything |
| — | Thu 29 | Submit | |

Team split (if not solo): backend person P1, P3, P5-backend, P7, P8; frontend person
P2, P4-UI, P5-UI (Add, Watch), P6-UI, Studio UI.

---

## Phase 0 — Setup [T1] (Day 1 morning, ~2 h)
- [x] Repo per CLAUDE.md; `.gitignore` (media, db, data/, env, venv, node_modules).
- [x] Backend: FastAPI `/api/health`, config loader, SQLite engine, pytest.
- [x] Frontend: Vite React TS, Router with Nearby, Watch, Explore, Place, Add, You,
      Settings; proxy `/api` `/media`; basic-ssl behind `--host`.
- [x] `tokens.css` (SPEC §12.2, both themes), `base.css`, `fonts.css` with all
      @fontsource families from CLAUDE.md and one font stack (SPEC §12.3).
- [x] i18next with `en.json`; `format.ts` (en-IN numbers), `<Money>` with Simulated tag.
- [x] Bottom nav: Nearby · Watch · (+) · Explore · You.
- [x] Commit skill (Prompt 3) and first commit.
- **Done when**: screens and nav render in light and dark on laptop and phone; a
  test page shows one word in each of the 23 languages with correct glyphs.

## Phase 1 — Data [T1] (Day 1, ~6 h)
- [x] `models.py`: all SPEC §5 tables; FTS5 over PlaceName.
- [x] `geo.py` haversine + bbox (tests with known distances).
- [x] `seed_osm.py` (SPEC §6.1): Overpass per category, cache, centroids, `name:*`
      → PlaceName, neighbourhoods, idempotent.
- [x] `seed_wikidata.py` (SPEC §6.2): verify class QIDs and the state/UT QIDs in the
      query service first; one query per class; labels in 23 languages; image,
      sitelinks, heritage, state via `P131*`; merge with OSM; idempotent.
- [x] `commons.py` (SPEC §6.3): lazy fetch, licence allowlist, attribution fields,
      local cache, `/api/media/commons/{id}`.
- [x] Fame (SPEC §6.7). Endpoints: `/cities`, `/cities/{slug}/places?sort=near`,
      `/places/{id}`.
- [x] Tests: AC-1, AC-2, AC-3 on saved fixture JSON (never live APIs in tests).
- [x] Fill Measured values: places per state/category, % with photo, % with each
      language's name.
- **Watch**: Wikidata 60 s timeouts → smaller class batches; Commons 429 → back off.

## Phase 2 — Design system, Explore list, Place page, ranking, names [T1] (Day 2)
- [x] `ranking/` Wilson, gems, trending with SPEC §9.1–9.3 tests.
- [x] `names.py` + `lib/names.ts` (SPEC §7.2) + `NameBlock`; tests for 3 modes,
      `lang` attrs, `<bdi>` for RTL.
- [x] Sort endpoint (5 sorts), category filter, verified toggle, search (FTS5, any script).
- [x] Components: PlaceRow, SortTabs, CategoryChip, Stat, SafetyCard, StepList,
      TipNote, LivePill, PulseStrip (static), EmptyState, illustrations.
- [x] Explore List screen; Place page with all SPEC §8.5 sections (actions disabled
      until sign-in); Open in Maps; attribution for OSM/Wikidata/Commons.
- [x] Fragile server rule (AC-15 part) now.
- **Done when**: AC-4 (except Languages screen), AC-5 (list part), AC-6 pass; screenshots
  match the reference (Prompt 7 quick check).

## Phase 3 — Accounts, likes, follows, kadam [T1] (Day 3 morning)
- [x] Auth (argon2id, hashed sessions, cookie flags, `X-Requested-With`).
- [x] Like/save/view; MediaLike; Follow; profiles `/users/{handle}`.
- [x] `kadam.py` (all SPEC §10.1 rules and caps), reports API.
- [x] Settings screen: names mode + language, UI language (English only enabled),
      theme; Languages & cities screen as in the reference.
- [x] Tests: AC-9, AC-14 (rules available so far), AC-4 Languages screen glyph check.

## Phase 4 — Nearby deck [T1] (Day 3 afternoon)
- [x] `deck/thompson.py`, `deck/rank.py` (SPEC §9.4); `/deck`, `/deck/swipe`.
- [x] DeckCard + DeckActions (gestures, buttons, reduced motion, preload, end card,
      radius chips, location fallback, Live pill).
- [x] Tests: AC-10.
- **Done when**: saving waterfalls brings more waterfalls within ~10 swipes on your phone.

## Phase 5 — Media, Add, Watch [T1] (Day 4)
- [x] `media_store.py`: magic-byte checks, Pillow re-encode without EXIF, video
      limits (60 s / 60 MB), posters, Range serving.
- [x] `integrity/phash.py`, `exif.py`, `dedupe.py` (all names, all languages).
- [x] Client EXIF read, resize, video duration + poster.
- [x] (+) sheet; Add a new place (3 steps, duplicate prompt); Add photos/video to a
      place; content rules sheet.
- [x] `watch/rank.py` (SPEC §9.5), `watch/views.py` (engaged/completed from heartbeat,
      §9.10 view rules); `/watch`, `/watch/{id}/view`; Touch recording.
- [x] WatchPlayer + WatchRail + tabs; Go here; saveData path; 20-min nudge.
- [x] Tests: AC-7, AC-11.
- **Done when**: you post a 20 s video from your phone and it appears in Watch.

## Phase 6 — Check-in, Pulse, Map + fog, You [T1] (Day 5)
- [x] `/checkin` (SPEC §8.7), fraud flags, place verification, kadam; dev simulator.
- [x] Pulse endpoint + form + summaries (SPEC §8.8); Live pill everywhere.
- [x] Last-mile: write versions, vote, best by Wilson.
- [x] Explore Map: OpenFreeMap restyle (6 paint overrides), boundary layers hidden,
      pins, clusters, fog (turf), neighbourhood count, bottom sheet.
- [x] You: Passport (stamps, streak, kadam, found, want to go) + public profile.
- [x] Fragile pledge UI.
- [x] Tests: AC-8, AC-12, AC-13, AC-14 (all), AC-15, AC-25.
- **Tier 1 gate (Prompt 6)**: AC-1…AC-15 and AC-25 have automated tests that pass;
  the phone journey still needs walking through once on a real device.
  Original wording: AC-1 to AC-15 and AC-25 pass; journey on the phone:
  deck → save → place → check in (simulator) → Pulse → fog clears → stamp → Watch →
  Go here.
- **Then go outside** (Sat/Sun): add 2 real places and 2 real videos on site; check in
  to 2 seeded places; post 1 Pulse.  ← **still to do, needs you and a phone**

## Phase 7 — Partner engine + Studio [E] (Day 6 morning)
- [x] `partner/attribution.py` (SPEC §9.9), `invalid.py` (§9.10 rules + velocity hold),
      `eligibility.py` (§10.4), `split.py` (§10.3, paise, rounding down).
- [x] `/admin/partner/run?month=`; `/studio`.
- [x] Studio screen: banner, metric cards + sparklines (text values too), checklist,
      top content, audience, "How earnings are split" sheet.
- [x] Tests: AC-16, AC-17, AC-18, AC-19, AC-23.

## Phase 8 — Simulations + demo data [E] (Day 6 afternoon)
- [x] `sim/ranking_sim.py` (SPEC §17 item 1), `bandit_sim.py` (item 2),
      `attribution_sim.py` (item 3), `fraud_sim.py` (item 4). Sims import the real
      functions, never copies.
- [~] pHash robustness (item 5) on your own photos (not committed).
- [x] Coverage table (item 7) from the DB.
- [x] `scripts/demo_data.py` (item 9) then run the Partner month on demo data.
- [x] README results quoting `metrics.json`; Prompt 9 audit.
- [x] Tests: AC-24.

## Phase 9 — Polish, reviews, Tier 2 [T2 + fixes] (Day 7)
- [ ] Prompt 7 design critique on all 9 screens, both themes; fix the top 10.
- [ ] Prompt 8 independent security/privacy/fraud review; fix high + medium.
- [ ] AC-20, AC-21, AC-22 in Playwright.
- [ ] Lighthouse mobile on Nearby and Watch; fix the top 2 issues each.
- [ ] Tier 2, in order, stop at 18:00: Hindi + regional UI (Prompt 14, native-reviewed) → comments
      → golden hour → Weekly Trail → Trails → clans → admin UI → offline → Isolation
      Forest → CLIP → IndicXlit batch (Prompt 13) → Wikivoyage.

## Phase 10 — Report, viva, rehearsal (Day 8) — code freeze 12:00
- [ ] `docs/REPORT.md` (Prompt 11).
- [ ] 3-minute screen recording of the journey (backup for the live demo).
- [ ] Demo rehearsal (Prompt 12).
- [ ] Viva drill with `docs/VIVA.md` (Prompt 5 quiz mode).
- [ ] Final commit, tag `v1.0-submission`.

---

## Risks

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| R1 | Overpass / Wikidata timeouts | Medium | Per-class queries, caching, fixtures for tests |
| R2 | Commons rate limits / odd licences | Medium | ≤ 2 req/s, allowlist, illustration fallback |
| R3 | Geolocation blocked on phone (no HTTPS) | High | basic-ssl; simulator for the viva |
| R4 | Too much scope for 8 days | **High** | Strict daily phases; Prompt 10 cut order the same evening |
| R5 | Video playback/size issues | Medium | Limits, poster first, Range test, MP4 H.264 advice |
| R6 | Indic text renders wrong (missing glyphs, wrong font) | Medium | Phase 0 glyph test page for all 23 languages; `lang` attrs |
| R7 | Wrong place names in some languages (data errors) | Medium | Show source; users add/vote names; report "wrong name" |
| R8 | Map restyle eats time | Medium | 6 paint overrides only; hide boundary layers by id |
| R9 | Attribution bugs credit the wrong creator | Medium | Fixture tests to 1e-9 (AC-16) + simulation |
| R10 | Examiner: "is this AI?" | High | VIVA.md section C: ranking under uncertainty, bandits, attribution, fraud detection, hashing, (CLIP, IndicXlit) |
| R11 | Live demo fails (Wi-Fi) | Medium | Localhost; browse map once to cache tiles; recording backup |
| R12 | Machine-translated UI shipped by mistake | Low | Invariant 11; only `en` enabled in Tier 1 |

## Measured values

Filled from `results/<name>/latest/metrics.json` and the seed scripts' own
summaries. Every figure here is reproducible by re-running the command named.

| What | Value | Phase |
|---|---|---|
| OSM places / neighbourhoods (Hyderabad) | 296 places, 1,408 areas (`seed_osm --city hyderabad`) | P1 |
| OSM places per category | heritage 73, museum 98, park 53, temple 15, lake 11, hills 7, viewpoint 5, other 34 | P1 |
| Wikidata places in India (total) | 16,971 across 34 states/UTs, 26 verified classes | P1 |
| Wikidata top categories | temple 7,787 · hills 2,712 · heritage 2,186 · lake 2,138 · park 998 | P1 |
| Share with a photo (Commons image recorded) | 41.3 % (7,005 of 16,971) | P1 |
| Share with a name, per language | en 99.5 · ta 22.4 · hi 17.3 · bn 15.4 · te 12.4 · ml 11.8 · pa 8.0 · kn 7.5 · or 6.8 · mr 5.0 · gu 4.5 · ur 4.3 · as 2.5 · sa 1.5 · ne 1.1 · mai 1.1 · sat 1.0 · ks 0.7 · sd 0.3 · gom 0.2 · mni 0.1 · **doi 0 · brx 0** (%) | P1 |
| Explore endpoint (17k places, best of 3) | top 68 ms · trending 72 ms · nearest 60 ms | P2 |
| Deck endpoint | 78 ms (SPEC §15 budget: 200 ms) | P4 |
| Watch endpoint | 37 ms | P5 |
| Passport / fog endpoint | 33 ms warm, 68 ms cold (was 660 ms before the grid + cache) | P6 |
| App shell JS | 372 KB raw, **118 KB gzipped** (budget 250 KB); MapLibre and turf lazy | P9 |
| Ranking sim precision@10: raw / ratio / Wilson | 0.042 / 0.356 / **0.452** (200 seeds) | P8 |
| Ranking sim Kendall τ: raw / ratio / Wilson | 0.282 / **0.621** / 0.554 — ratio wins globally, Wilson wins at the top | P8 |
| Bandit sim save rate @30: random / popular / fixed / Thompson | 0.114 / **0.194** / 0.191 / 0.178 (Thompson −8.4 %) | P8 |
| Bandit sim save rate once settled | 0.114 / 0.145 / 0.144 / **0.155** (Thompson +7.0 %) | P8 |
| Attribution sim Spearman ρ: last-touch / linear / time-decay | 0.806 / 0.830 / **0.864** at truth τ = 10 d; time-decay best or near-best across τ = 2…30 d | P8 |
| Fraud sim precision / recall of §9.10 rules | **1.000** / 0.786 (50 seeds) | P8 |
| Fraud share of pool: rules off → on | 0.598 → 0.278, a 53.6 % reduction | P8 |
| pHash detection / false-match rate | 100 % recompress & resize, 98 % brightness, **0 % at a 20 % crop**; false matches **0 of 1,225** | P8 |
| Backend tests | 207 passing, ruff clean | P8 |
| Frontend tests | 26 unit (vitest) + 54 e2e (Playwright, 9 screens × 2 themes) | P9 |
| axe serious/critical issues | **0** across the nine screens, after fixing 2 real WCAG 2.5.3 violations | P9 |
| Outdoor check-in accuracy (m) | *not yet measured — needs the Day-5 trip* | P6 |
| Median upload size after resize (KB) | *not yet measured — needs real photos from a phone* | P5 |
| Watch first-frame time on phone (s) | *not yet measured — needs a real uploaded video* | P5 |
| Lighthouse mobile (Nearby / Watch) | *not yet run* | P9 |


## Ideas parked
- **Sign in with Google.** Built as a plain email + password flow. Google sign-in
  has to be a server-side OAuth redirect (invariant 7 forbids loading Google's
  script in the page), and it needs a free OAuth client ID that only the account
  owner can create in Google Cloud Console. Add `GOOGLE_CLIENT_ID` and
  `GOOGLE_CLIENT_SECRET` to `.env` and the button can be wired to
  `/auth/google` and `/auth/google/callback` in about an hour.
- **Merge large features.** `scripts/merge_duplicates.py` joins records within
  150 m. A 1 km lake whose OSM polygon centre and Wikidata pin are 500 m apart
  (Durgam Cheruvu) and a national park split into two OSM fragments 3 km apart
  survive as duplicates. Fixing it means comparing outlines, not points.

## Progress log
- 2026-10-23 (later) — **State-wide OSM import, corrected to famous places only.**
  `scripts/seed_osm_states.py` finds places OSM knows about that Wikidata's
  sweep missed, one Indian state at a time (an Overpass `area["ISO3166-2"=...]`
  filter, not a boundary we draw -- invariant 12). Its first run, before it had
  a fame filter, added 1,409 places across Goa and Andhra Pradesh; most were
  plain named OSM features (a rock, a gallery with no other record) rather
  than anything "kinda famous", which is not what the catalogue should be.
  `scripts/undo_state_seed.py` removed the 1,043 of those with neither an OSM
  `wikipedia` tag nor a `wikidata` id, keeping the 366 that had one. The script
  now applies that same filter by default, so a future run cannot repeat this.
  The remaining 26 states were not run -- the task turned out to be photos for
  the places already here, not adding more places.
- 2026-10-23 — **More real photographs, everywhere, not just Hyderabad.**
  `scripts/fetch_photos.py` only ever geosearched one city at a time.
  `--all` runs it across every place in the country that has none, in id
  order, at the same throttled rate (2 req/s against the Commons API, nothing
  paid). One run found real, freely-licensed photographs for 1,131 of the
  9,631 places that had none — everywhere: **41.7% → 49.4%** (8,301 of
  16,801). The remaining places are mostly small OSM features (a viewpoint, a
  well) with no photograph on Commons within 250 m; that is an honest gap, not
  a bug, and they keep their category illustration (SPEC §12.6).
  Also fixed: `GET /media/commons/{id}` would 404 forever for a place whose
  photo was credited but never downloaded (a batch run credits far more than
  it has time to cache). It now fetches the bytes once, on the first real
  view, instead of only at credit time.
- 2026-10-22 (night) — **Product pass.**
  - The location simulator now lives only on Nearby (it was on every page,
    including sign-in).
  - **Open in Maps**: Google snaps a pin to the nearest thing it knows, so the
    Salar Jung Museum's pin opened "Metal Ware Gallery". Places with a Wikidata
    item are now sent by name + city; everything else keeps exact coordinates.
  - **Share your trip** became **Ask a friend to check on me** (a message with a
    return time and the Truvel page, no Maps link, no location). The top share
    button shares the Truvel page.
  - **Reports** are grouped into cases in Admin, ranked by how many reporters have
    a verified check-in there; new reasons (wrong name, closed, out of date), an
    optional note, one open report per person per reason, 20 a day.
  - **Duplicates**: the server now refuses a place that is certainly an existing
    one (name agrees in any language *and* the pin is within 150 m), so skipping
    the "Is it one of these?" prompt does not get around it.
  - Watch > Nearby shows nearby places as cards. `docs/MONETISATION.md` explains
    how the app could earn, and why none of it is switched on.
- 2026-10-22 (later) — **@truvel publishes every place; reset and delete built.**
  - `Place.added_by` is `@truvel` for all 16,801 places (and the password is
    `qw12&er34`, 8 characters minimum now). The 50-second bug is avoided by
    design, not by leaving the column empty: `User.official` makes the account a
    publisher — no kadam, no touch credit, not a Partner creator, no Studio
    ranking — and `/me/passport` and `/users/{handle}` count and page "places
    found" instead of loading them all. `/me/passport` 243 ms, `/studio` 65 ms.
  - 3 photo-less OpenStreetMap viewpoints removed; 104 photographed,
    little-known places marked `fame = hidden`, and Hidden gems lists them after
    any place that has earned its spot (no videos exist: Commons has none that
    the app can play). `scripts/publish_as_official.py` does all of it.
  - **Password reset** (`/auth/forgot`, `/auth/reset`, `/forgot`, `/reset`): one
    hour, one use, ends other sessions, same answer for unknown emails. Mail goes
    out through SMTP if `TRUVEL_SMTP_*` is set; otherwise it is written to the
    server log.
  - **Delete your own upload** (`DELETE /media/{id}`, trash button on your own
    photo): removes files and the rows that point at it; kadam stays in the ledger.
- 2026-10-20 — v1 spec, plan, design reference.
- 2026-10-20 — v2: languages, all-India open data, Watch, Pulse, Partner Program, Studio.
- 2026-10-22 — **Renamed to Truvel, and the demo population removed.**
  The app is now *Truvel — Discover Hidden India*. `Pagdandi` survives only in
  `results/**/config.yaml`, which record the config each simulation actually ran
  under and must not be rewritten, and in this log.
  - **One account.** `scripts/official_account.py --reset` deletes every account
    and everything anyone did: 252 users, their likes, views, visits, tips, live
    reports, last-mile directions and earnings, the 44 generated photos and
    videos, and the 4 places that were invented outright. What is left is 16,967
    places from OpenStreetMap and Wikidata, published by `@truvel`, with every
    counter at zero. `demo_data.py` still works, so a populated app is one
    command away for the viva.
  - **Real photographs.** `scripts/fetch_photos.py` credits Commons images in
    batches of 50 (6,996 of them had a filename but no licence, so they could
    not legally be shown and the app was falling back to illustrations), and
    finds new ones by Commons geosearch within 250 m of the pin. Hyderabad went
    from **25.3 % to 57.0 %** photographed; everywhere, 41.6 %. 69 candidates
    were discarded for having no usable licence.
  - **Accounts are email + password** (SPEC §5, §11): NIST SP 800-63B rules —
    8 characters, a blocklist, no forced symbols — argon2id, sign-in by email
    or handle, one error for both failure modes, and a 15-minute lockout after
    8 failures counted per account *and* per address.
  - **Duplicates merged.** Both datasets overlap, so Golconda Fort was three
    records (Wikidata Q1134499, Wikidata Q17986822, an OSM element) and 20 names
    in Hyderabad appeared more than once. `scripts/merge_duplicates.py` applies
    SPEC §9.6 but is stricter than the prompt a person sees: the SPEC's
    `token_set_ratio` scores 100 whenever one name is a subset of the other, so
    "Golconda Fort" and "Golconda Jail" matched. It now also needs a plain
    character ratio of 72 on **English names only** (a shared Tamil village name
    had merged two different temples) and category compatibility (a park beside
    a lake is two places). 16,967 → 16,804 places; the survivor keeps every name,
    photo and bit of engagement the others had. Golconda Fort is one place with
    10 languages and 3 photographs.
  - **A 50-second bug.** Setting `added_by` on all 16,967 imported places made
    `/me/passport` take 50 s and `/studio` 14 s — queries for "places this
    creator found" returned everything — and would have credited `@truvel` as
    the discoverer of every place for Partner payouts. `added_by` means "a person
    found this", so imported places have none; the official account is the
    publisher, and the attribution line already says where each place comes
    from. 50 s → 321 ms.
  - **Watch's empty state was invisible** (1.23:1 contrast): it used the light
    theme's ink on a surface that is dark in both themes. Fixed; axe found it.
  - **Ranking ties** now fall back to Wikidata `sitelinks`, because on a fresh
    install every Wilson bound is nought and the sort did nothing.
  - Fixed while checking: the password field's reveal button sat inside its
    `<label>`, so the input's accessible name was "Password Show"; and the
    Nearby banner read "the centre of Nearby" for anyone without a home city.
  - **Consequences, stated plainly:** Watch is empty (every video was demo
    data, and Commons has photographs, not video); Explore's Top, the Studio,
    the Partner Program and the Passport all show zeros; and "Hidden gems" is
    empty, because a hidden gem is by definition a place a local added and
    nobody has added one yet. All of that is true rather than broken.

- 2026-10-21 — **P0–P8 built in one pass.** Backend (FastAPI + SQLModel + FTS5,
  43 routes), frontend (Vite + React + TS, nine screens matching the design
  reference in both themes), all SPEC §9/§10 algorithms as pure functions with
  207 tests, four simulations, the coverage table, and demo data.
  Seeded 296 OSM places + 1,408 areas for Hyderabad and 16,971 Wikidata places
  across India with names in 21 languages.
  Things the build changed or found, rather than just implementing:
  - **Four Wikidata class QIDs in SPEC §6.2 were wrong** — Q842425 is a chef,
    Q1066288 is "figurine", Q2082441 is a record producer, Q1129447 has no
    English label. Verified replacements are in `config.yaml`, along with four
    classes the SPEC asked Phase 1 to add (Jain temple, palace, hill station,
    ghat). This is what `--verify` is for.
  - **The kadam caps in SPEC §10.1 count events, not kadam** (five Pulse reports
    a day is 15 kadam, not 5). Implemented that way; see `kadam.allowed_amount`.
  - **The fog denominator needed a decision.** Real OSM gives Hyderabad ~1,400
    neighbourhood nodes, so "6 of 1,408" reads as hopeless, which SPEC §8.4
    explicitly does not want. The denominator is now neighbourhoods that have at
    least one place in them (244 for Hyderabad). **Proposed SPEC §8.4 edit —
    needs your sign-off.**
  - **The deck/Watch re-rank was wrong**, in a way only a stress test showed: the
    obvious greedy strands a long run at the end (6 videos from one creator and
    3 from another produced a run of 5). Replaced with a feasibility-checked
    rearrangement in `app/ranking/diversity.py`, with tests.
  - **Two real WCAG 2.5.3 violations** found by axe and fixed.
  - **Passport/fog was 660 ms**; a spatial grid plus a per-seed cache brought it
    to 33 ms warm.
