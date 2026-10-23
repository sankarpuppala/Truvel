# Truvel: project review and the road to a start-up

Reviewed 23 October 2026 on branch `claude/affectionate-bohr-nud480` (head `92885f8`).
This file is the report. The step-by-step plan is in `docs/NEXT_LEVEL_PLAN.md`,
the prompts are in `docs/NEXT_PROMPTS.md`, and `docs/CONTEXT_MAP.md` tells
Claude Code what to read for each kind of task.

---

## 1. Where the project stands

| Area | State | Evidence |
|---|---|---|
| Tier 1 app (Phases 0–6) | **Done** | PLAN.md boxes all `[x]`; 9 screens, light and dark screenshots in `results/screens/` |
| Partner engine + Studio (Phase 7) | **Done** | AC-16..19, AC-23 tests |
| Simulations (Phase 8) | **Done**, with honest numbers | `results/*/latest/metrics.json`, quoted in README |
| Backend tests | **227 passing**, ruff clean (re-run today) | `pytest -q` → 227 passed in 66 s |
| Frontend tests | 26 unit + 54 e2e (from PLAN.md; not re-run today) | PLAN.md "Measured values" |
| Phase 9 (security review, Lighthouse, design critique) | **Not started** | PLAN.md Phase 9 boxes all `[ ]`. AC-20/21/22 tests do exist in `frontend/e2e/` but the box is not ticked |
| Phase 10 (report, recording, rehearsal, tag) | **Not started** | |
| Field measurements (check-in accuracy, upload size, first frame) | **Missing** | "not yet measured" in PLAN.md |

Size: about 9,200 lines of Python in `backend/app`, 10,300 lines of TS/TSX/CSS in
`frontend/src`, 7 simulation scripts.

**Verdict:** for a student project this is unusually complete and unusually
honest: real open data (16,971 Wikidata places, 41 % with a Commons photo),
each algorithm a small cited function with tests, a simulated money engine that
says so on screen, and simulations that report where the chosen method loses
(Thompson sampling is 8 % *worse* than "popular" at 30 swipes). The work left
before 29 October is mostly review, measurement and writing, not features.

---

## 2. Strengths to protect (these are the pitch)

1. **Verified visits, not clicks.** Check-in on site + fraud rules (§9.8) +
   time-decay attribution (§9.9). Fraud sim: precision 1.00, recall 0.79; the
   rules cut fraud's share of the pool from 60 % to 28 %.
2. **Privacy by design.** No coordinates stored anywhere (invariant 1). That is
   a real selling point under India's DPDP Act 2023, not just a viva answer.
3. **India-first languages.** Names in 23 languages with the right fonts and
   `lang`/`<bdi>` handling. Few travel apps do this properly.
4. **Licence hygiene.** OSM / Wikidata / Commons attribution on every item; no
   Google data. This keeps the company clean if it grows.
5. **Evaluation culture.** Every claim in the README traces to a
   `metrics.json`. Investors and examiners both trust that.

---

## 3. Problems found (ranked)

### Must fix before submission (29 Oct)

| # | Problem | Why it matters | Fix (card) |
|---|---|---|---|
| P1 | Phase 9 security/privacy review never ran | Invariants 1, 5, 7 are the core promise; nobody independent has tried to break them | A1 |
| P2 | AC-20, AC-21, AC-22 tests exist (`e2e/screens.spec.ts`, `e2e/accessibility.spec.ts`) but PLAN.md still shows them `[ ]`, and Lighthouse never ran | Unticked boxes read as unfinished work to an examiner | A2 (run, tick, record) |
| P3 | Field values unmeasured (check-in accuracy, upload KB, first-frame) | The examiner's first question will be "does check-in work outdoors?" | A3 (you, on site) |
| P4 | Very long functions: `check_in` 202 lines (`routers/checkin.py:57`), `studio` 186, `get_watch` 173, `measure_creator` 150, `get_deck` 139 | CLAUDE.md says ≤ 40 lines where possible and "explain every line in the viva". A 200-line handler is hard to explain | A5 (behaviour-preserving split, tests first) |
| P5 | `pagdandi-starter.zip` (395 KB) committed; `.gitignore` names the old `truvel-starter.zip` | Its contents duplicate the repo; leftover of the rename | A6 |
| P6 | No CI (`.github/` absent), no commit skill (`.claude/` absent though Prompt 3 created one) | Nothing stops a red push; the commit rule lives only in prose | A6 |
| P7 | Name drift: SPEC title says Truvel but the epigraph explains *Pagdandi*; zip still named pagdandi | Confuses examiners and the brand | A6 (one-line SPEC fix, with approval) |

### Fix before real users (start-up track)

| # | Problem | Fix (card) |
|---|---|---|
| S1 | No schema migrations; SQLite single file | B0: Alembic now, Postgres + PostGIS when hosted |
| S2 | Media on local disk, video not transcoded | B0: object storage + ffmpeg 720p H.264 |
| S3 | Long jobs (Commons fetch, Partner month) run inline or by hand | B0: a scheduled worker |
| S4 | **ODbL share-alike.** If user-added places live in the same table as OSM-derived rows and the result is used publicly, it may count as an ODbL *Derivative Database* that must be offered under ODbL | B0: keep OSM-derived and user-contributed data as separate databases (a *Collective Database*); get a lawyer's view before launch |
| S5 | No content-moderation workflow beyond reports | B0: admin queue UI (already a Tier 2 item) |
| S6 | Duplicate large features (lakes, split parks) survive the 150 m merge | B0 or later: polygon overlap instead of points (PLAN "Ideas parked") |
| S7 | No CSP / security headers on the API and static app | A1 or B0 |

### Claude Code token cost (why sessions feel expensive)

| What happens now | Approx. tokens |
|---|---|
| CLAUDE.md auto-loaded | ~2,300 |
| "Read SPEC.md" at session start (60 KB) | ~15,000 |
| "Read PLAN.md" (26 KB, and the progress log keeps growing) | ~6,500 |
| Opening `docs/design-reference.html` (549 KB, **fonts embedded as base64**) | **~150,000+**, enough to fill most of a session |
| Full `pytest -q` output after every small change | 1–3k each time |

So a session spends about 24k tokens reading before any work, and one careless
look at the design reference costs far more. `docs/CONTEXT_MAP.md` fixes this:
it maps each kind of task to the exact SPEC line ranges and files to read, and
says to look at `results/screens/*.png` instead of the HTML reference. Expected
saving: 60–80 % of start-up reading per session.

---

## 4. What would take it to the next level

### 4.1 Product: sharpen to one loop

Today the app has many surfaces (deck, Watch, map, Pulse, Studio, passport). A
start-up wins on **one loop that repeats every weekend**:

```
See a place (Watch / deck / a WhatsApp share)
  → Go (last-mile steps, Pulse says it's open and safe)
    → Check in on site (fog clears, passport stamp, kadam)
      → Post (photo, Pulse, steps) → credited "Found by" / visits caused
        → Share card to WhatsApp → a friend sees a place …
```

Every feature in the plan below is judged by whether it makes this loop faster
or more frequent. North-star metric: **verified visits caused per week**.
Guardrails: fraud share of visits, D7 retention, % of new places verified.

### 4.2 Ten start-up ideas, ranked by fit and cost

| # | Idea | Why it fits Truvel | Cost |
|---|---|---|---|
| 1 | **WhatsApp share cards** (server-rendered image + deep link for every place, Trail and passport) | India's distribution channel is WhatsApp; today a shared link shows nothing | Low (Pillow already in stack) |
| 2 | **Trails** (creator playlists of 3–6 places with order and time) + **Weekly Trail** | Gives creators a shareable unit; turns a single visit into three | Medium (Tier 2 already) |
| 3 | **City launch as a game: "Clear the fog of Hyderabad" 30-day challenge** with campus clans | Density in one city beats thin coverage of India; Hyderabad has T-Hub and many colleges | Low–medium |
| 4 | **Offline city packs (PWA)** | Hidden places have weak signal; offline is a reason to install | Medium |
| 5 | **Trip check-out timer** ("I'm at X, alert my friend if I'm not out by 6 pm") with no coordinates stored | Safety is the top worry for solo women and families; fits invariant 1 | Low (mailer exists) |
| 6 | **Visit bounties for local businesses**: a homestay or café near a place funds "₹N per verified visit"; shown as *Sponsored*, never in ranking | Monetises the moat (verified visits) directly; cost-per-visit is measurable, unlike ads | Medium; simulated until payouts are legal |
| 7 | **District footfall dashboard for tourism boards** (aggregate, k ≥ 10 suppression, CSV) | MONETISATION.md's first customer; DPDP-friendly because nothing personal is stored | Medium |
| 8 | **Voice last-mile notes in any Indian language**, transcribed in an offline batch with an open model | Locals who know the path often won't type; voice is natural | Medium (batch in Colab) |
| 9 | **Seasonal campaigns** (monsoon waterfalls, winter treks, festival calendar) driven by Pulse | Pulse freshness is a reason to open the app every week | Low |
| 10 | **Local guides marketplace** (verified locals offer walks, commission later) | Natural next revenue after bounties | High; later |

Ideas 1, 3, 5 and 9 cost little and directly feed the loop: do them first.
Ideas 6 and 7 are the business. Idea 10 is a year-two story.

### 4.3 Business model (extends `docs/MONETISATION.md`)

| Stage | Who pays | Product | Proof needed first |
|---|---|---|---|
| 0 (now–3 mo) | Nobody | Free app, one city | 1,000 weekly verified visits in Hyderabad |
| 1 | Tourism board / district (pilot) | Footfall dashboard + featured Trails | Visit counts from stage 0 |
| 2 | Local businesses | Visit bounties (cost per verified visit) | Fraud rate < 5 % on real data |
| 3 | Travellers | Truvel Plus: offline packs, unlimited Trails | Offline used by > 20 % of actives |
| 4 | Creators earn real share | Pool from stages 1–2, split by `partner.run_month()` | Registered company, KYC, TDS, payments partner |

Never sold: ranking, individual data (there is none), fragile-place pins.

### 4.4 Go-to-market in one city

1. **Supply first (weeks 1–4):** 30 local creators and 3 college clubs in
   Hyderabad add 300 verified hidden places with last-mile steps. Reward:
   "Found by" credit, kadam, leaderboard, Studio shows simulated earnings.
2. **Demand (weeks 5–8):** "Clear the fog" challenge, share cards on WhatsApp
   groups, creators cross-post Shorts/Reels with a Truvel link.
3. **Prove (weeks 9–12):** publish a public "Hidden Hyderabad" footfall report
   (aggregate only); use it to pitch Telangana Tourism or a district office.
4. **Support to apply for (all free):** DPIIT Startup India recognition, T-Hub
   (Hyderabad) programmes, college incubator. Check each programme's current
   terms before applying.

### 4.5 Engineering to grow (zero or near-zero cost)

| Need | Choice | Notes |
|---|---|---|
| Hosting | One free-tier cloud VM (for example an "always free" ARM VM) + a free tunnel/CDN in front | Check current free-tier terms; keep a nightly DB backup off the box |
| Database | SQLite → Postgres + PostGIS at ~1k daily users | Alembic migrations first so the switch is a config change |
| Media | Free-tier object storage with free egress; ffmpeg to 720p H.264 + poster | Keep EXIF stripping on the server (invariant 2) |
| Jobs | One worker process with a schedule (Commons fetch, Partner month, Pulse expiry) | No Redis needed at this size |
| CI | GitHub Actions: ruff, pytest, tsc, vitest, Playwright smoke | Free for public repos; minutes quota for private |
| Errors | Backend-only error logging (self-hosted), never logging request bodies with lat/lng | Invariant 7 forbids third-party scripts in the page |
| Security | CSP, security headers, upload size limits at the proxy, moderation queue | |

---

## 5. Recommended order

1. **Now → 28 Oct:** Track A in `docs/NEXT_LEVEL_PLAN.md` (A1–A7). No new
   features; the Tier 1 gate rule in CLAUDE.md still applies.
2. **29 Oct:** submit, tag `v1.0-submission`.
3. **November:** B0 foundations, then B1 share cards and B2 Trails.
4. **December–January:** B3 city challenge, B4 safety timer, B5 Hindi + Telugu
   UI with native review. Launch publicly in Hyderabad.
5. **After 1,000 weekly verified visits:** B6 bounties, B7 board dashboard.
   B8 real payouts only after real revenue and legal setup.

Every Track B card starts by proposing the SPEC.md change and waiting for
approval, as CLAUDE.md requires ("Fix the spec, not the code").
