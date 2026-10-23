# CLAUDE.md — Truvel

Project memory. Read this, then `docs/CONTEXT_MAP.md`, then only the SPEC.md line
ranges and the PLAN.md phase (or `docs/NEXT_LEVEL_PLAN.md` card) your task needs,
before touching any file. Never open `docs/design-reference.html` (549 KB of
embedded fonts); use the PNGs in `results/screens/`.

## What this is

A travel + social + creator web app for India. People discover places (famous ones
from OpenStreetMap and Wikidata with Commons photos; hidden ones added by people
who were physically there), see names in their language and the local script,
swipe a deck of places near them, watch short videos of places, read live
conditions (Pulse) and last-mile directions, check in on site to clear the fog on
their city map, and earn **kadam** (points). Creators get a Studio and a Partner
Program that splits a revenue pool mostly by **visits they caused**; in this
version the pool is simulated and labelled so.

`SPEC.md` = what to build. `docs/design-reference.html` = how it looks (9 screens).
This file = how we work.

**Deadline: submit 29 October 2026.** Tier 1 app by end of Day 5 (Sun 25 Oct);
Partner engine + evaluation by Day 6. No Tier 2 work before the Tier 1 gate passes.

## Hard constraints

- **Zero budget.** No paid API, service, dataset or hosting. No Google Places,
  Google Maps JS API, or any data copied from Google Maps (SPEC §6.6). Maps:
  MapLibre + OpenFreeMap. Directions: the plain Google Maps URL link only.
- **Windows laptop.** Python 3.12, Node 20+. No Docker, Postgres or Redis. SQLite
  file DB, media on local disk. Heavy ML (IndicXlit, CLIP) runs in Colab/Kaggle as
  batches or is Tier 2.
- **No real money.** Kadam are points. The Partner Program uses
  `partner.demo_pool_inr`; every ₹ figure is labelled **Simulated**.
- **The student must explain every line in the viva.** Simple readable code; each
  SPEC §9/§10 algorithm is a small pure function with a plain-English docstring
  citing its SPEC section. No new library beyond the stack below without asking.

## Invariants — never break these

1. **Never store a user's coordinates.** Check-in, Pulse, deck, Watch and search use
   location for that request only. `Visit`, `Pulse`, `Touch` have no lat/lng
   columns. Never log request bodies containing `lat`/`lng`.
2. **Stored media has no EXIF.** The server re-encodes every photo and poster.
3. **Verification rules are law** (SPEC §8.7, §9.8). No shortcut that pays kadam or
   earnings.
4. **Ledgers only.** Kadam changes only via `kadam.award()` / `kadam.reverse()`;
   earnings only via `partner.run_month()` writing `EarningLine`s. Never update a
   balance directly.
5. **Fragile places**: the API never returns exact coordinates or last-mile steps
   before the pledge. Enforced on the server.
6. **Attribution and licences**: OSM (ODbL), Wikidata (credited), Commons (author +
   licence + link on every photo, allowlisted licences only), OpenFreeMap. Never
   remove attribution to tidy a design.
7. **No third-party calls from the frontend** except `tiles.openfreemap.org`.
   Commons images are proxied and cached by our server. Fonts self-hosted via
   @fontsource. No analytics.
8. **Dev location simulator only in dev** (`VITE_DEV_TOOLS=1` and
   `DEV_ALLOW_FAKE_LOCATION=1`); simulated visits never reach metrics, attribution
   or earnings.
9. **Safety card never hidden or collapsed.** Nothing rewards risky content.
10. **Accessibility**: every gesture has a button; SPEC §12.2 tokens only; reduced
    motion honoured; `lang` on every place name; RTL names in `<bdi>`.
11. **No unreviewed translations presented as reviewed.** UI languages ship only
    after a native speaker reviews them; machine drafts stay behind "Beta".
12. **Maps of India**: international boundary layers hidden; never draw state or
    country borders (SPEC §14).
13. **Money honesty**: every element that shows ₹ carries a Simulated label; the
    Studio banner is always present (AC-23).

## Stack

- **Backend**: FastAPI, SQLModel (SQLite + FTS5), Pydantic v2, argon2-cffi, Pillow,
  imagehash, rapidfuzz, PyYAML, httpx (seed scripts and
  Commons proxy), numpy, pytest. Tier 2: scikit-learn (Isolation Forest),
  indic-transliteration, open_clip_torch + torch CPU.
- **Frontend**: Vite + React 18 + TypeScript, React Router, i18next + react-i18next,
  MapLibre GL, @turf/turf, exifr, @use-gesture/react, Vitest, Playwright +
  @axe-core/playwright. Tier 2: suncalc, vite-plugin-pwa.
- **Fonts** (@fontsource, self-hosted, `unicode-range`): rozha-one, mukta (Latin +
  Devanagari), kalam, anek-bangla, anek-gujarati, anek-gurmukhi, anek-odia,
  anek-telugu, anek-tamil, anek-kannada, anek-malayalam, noto-nastaliq-urdu,
  noto-naskh-arabic, noto-sans-ol-chiki, noto-sans-meetei-mayek.
- **Styling**: plain CSS with SPEC §12.2 tokens in `frontend/src/styles/tokens.css`.
  No Tailwind, no component library.

## Repository layout

```
truvel/
  CLAUDE.md  SPEC.md  PLAN.md  PROMPT.md  README.md  config.yaml
  docs/  design-reference.html  VIVA.md  REPORT.md (Phase 9)
  backend/
    app/
      main.py  config.py  db.py  models.py  auth.py  errors.py  geo.py
      routers/       auth, places, names, deck, watch, media, pulse, me, studio,
                     users, admin, dev
      ranking/       wilson.py gems.py trending.py            (SPEC §9.1–9.3)
      deck/          rank.py thompson.py                      (SPEC §9.4)
      watch/         rank.py views.py                         (SPEC §9.5, §9.10)
      integrity/     dedupe.py phash.py exif.py fraud.py      (SPEC §9.6–9.8)
      partner/       attribution.py invalid.py split.py eligibility.py  (SPEC §9.9–9.10, §10)
      names.py       display rules (SPEC §7.2)
      kadam.py       ledger (SPEC §10.1)
      media_store.py commons.py
    scripts/  seed_osm.py  seed_wikidata.py  demo_data.py
    tests/  requirements.txt  media/ (gitignored)
  frontend/
    src/
      styles/ tokens.css base.css fonts.css
      i18n/   en.json (+ reviewed languages later)
      components/   SPEC §12.5 names
      screens/      Nearby Watch Explore Place Add You(Passport, Studio) Settings Admin
      lib/          api.ts geo.ts fog.ts exif.ts resize.ts names.ts format.ts
      illustrations/
    e2e/
  sim/  ranking_sim.py bandit_sim.py attribution_sim.py fraud_sim.py
  notebooks/  indicxlit_batch.ipynb (Tier 2, runs in Colab)
  results/
  data/  osm/ wikidata/ commons/   (gitignored)
```

## Commands (Windows PowerShell)

```powershell
# backend
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m scripts.seed_osm --city hyderabad
python -m scripts.seed_wikidata
uvicorn app.main:app --reload --port 8000
pytest -q

# frontend (second terminal)
cd frontend
npm install
npm run dev                  # http://localhost:5173 (proxies /api, /media)
npm run dev -- --host        # phone on same Wi-Fi: https://<laptop-ip>:5173
npm run test
npx playwright test

# simulations
python sim/ranking_sim.py --seeds 200
python sim/bandit_sim.py --seeds 50
python sim/attribution_sim.py --seeds 100
python sim/fraud_sim.py --seeds 50
```
Demo mode: `$env:DEV_ALLOW_FAKE_LOCATION=1` before uvicorn; `VITE_DEV_TOOLS=1` in
`frontend/.env.development.local`.

## How we work (spec-driven)

1. One phase per session. Start in **Plan Mode**: read SPEC sections + the phase in
   PLAN.md; list files to touch and tests to write; wait for approval.
2. Implement only that phase. Tests first for SPEC §9 and §10 logic.
3. Verify: `pytest -q`, `npm run test`; UI phases: Playwright screenshots at
   390 × 844, light and dark, compared with the matching reference screen.
4. Update PLAN.md (tick tasks, Measured values, Progress log).
5. **Teach-back** (PROMPT.md Prompt 5): explain what was built in plain English, then
   3 viva questions with answers appended to `docs/VIVA.md`.
6. Commit with the commit skill (Prompt 3).

**Fix the spec, not the code.** If SPEC is wrong or unclear, stop, propose the
SPEC.md change, wait. Blocked > 20 minutes → stop and report what you tried; the
deadline beats perfection, so propose the simpler version.

## Conventions

- Python: type hints, ruff, functions ≤ 40 lines where possible, constants from
  `config.yaml`. Money as integer paise.
- TypeScript strict, no `any`; PascalCase component files.
- CSS: tokens only; both themes via `prefers-color-scheme` + `[data-theme]`.
- Names always rendered through `NameBlock` / `names.ts` (SPEC §7.2), never by
  reading `name` directly.
- Numbers via `format.ts` (`en-IN` grouping); every ₹ through `<Money>` which adds
  the Simulated tag.
- Tests named after ACs: `test_ac16_attribution_shares_sum_to_one`.

## Git

- Commit after each phase: `phase N: <what>`, body lists ACs touched.
- Never commit: `backend/media/`, `*.db`, `data/`, `.env*`, `.venv/`,
  `node_modules/`, uploaded photos/videos, Commons cache.
- Commit: `results/**/metrics.json` + figures, `docs/`.

## Don'ts

- Don't add features not in SPEC; park them in PLAN.md "Ideas parked".
- Don't bypass verification for a demo; use the dev simulator.
- Don't copy anything from Google Maps, even "just for testing".
- Don't write that the app "pays" users, "verifies identity", is "100 % safe", or
  that a translation is reviewed when it isn't.
