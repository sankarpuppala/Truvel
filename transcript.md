# Conversation transcript — Truvel (Pagdandi) build session

This is a condensed, chronological record of the Claude Code session used to
build and fix Truvel. Each entry pairs the user's request with a summary of
what was done in response. Full tool-call detail (file reads, exact diffs,
intermediate test runs) is in the project's git history (`git log`); this
transcript captures the *decisions and reasoning*, which is what the diffs
alone don't show.

---

## 1. Official account, password policy, data cleanup

**User:** Asked to create the official `@truvel` account with a specific
password, make it the publisher of every existing place, keep only
photographed viewpoints, populate Hidden Gems honestly, lower the minimum
password length to 8, and build password reset and delete-your-own-upload.

**What happened:**
- Set the `@truvel` account's password and lowered `MIN_PASSWORD` to 8
  everywhere (backend validation, frontend copy, SPEC, README).
- Set `Place.added_by` to the official account for all ~16,800 places, but
  first added a `User.official` flag so the account never earns kadam, is
  never credited with a visit, and is excluded from the Partner Program and
  Studio rankings (an earlier attempt at this had caused a 50-second page
  load and false creator credit — fixed properly this time with grouped
  queries instead of per-place loops).
- Removed the 3 OpenStreetMap viewpoints that had no photo at all; kept the
  rest.
- Marked 104 photographed, little-known places as `fame = hidden` so Hidden
  Gems had honest content before anyone had visited anything.
- Built `POST /auth/forgot` / `POST /auth/reset` (one-hour, one-use link,
  generic response so it can't be used to find out who has an account; mail
  goes out via SMTP if configured, else logged).
- Built `DELETE /media/{id}` for your own upload (owner or admin only;
  Commons photos can't be deleted since they aren't ours).
- Full test suites green; committed in stages.

---

## 2. Product pass: simulator placement, Maps link accuracy, safety messaging

**User:** Pointed out (with screenshots) that the dev location simulator was
showing on every page including sign-in; that "Open in Maps" was opening the
wrong exact spot inside a large site (Salar Jung Museum opened "Metal Ware
Gallery"); questioned what "Share your trip" was actually for since it
duplicated the Maps link; asked how flagged reports get collected usefully;
asked how duplicate places from different users get avoided; asked for Watch's
"Nearby" tab to be plain cards; and asked about monetisation.

**What happened:**
- Moved the dev location simulator so it only renders on the Nearby screen,
  not globally.
- Fixed the Maps link: a place with a Wikidata item (i.e. a real, notable
  place) is now sent to Google Maps by name + city instead of raw
  coordinates, since Google snaps a bare pin to the nearest indexed thing —
  which inside a museum can be the wrong room.
- Replaced "Share your trip" with "Ask a friend to check on me": a message
  with a return-by time and the place's Truvel link, deliberately carrying no
  location (invariant 1). The top share button now shares the place page
  itself.
- Built a grouped report-review view in Admin: reports are grouped by target
  rather than listed individually, and a reporter who has a verified
  check-in at the place is weighted higher than a stranger's report.
- Added server-side duplicate rejection: a new place is refused outright if
  an existing place within 150 m has a near-identical name in any language
  (previously this was only a client-side nudge).
- Rebuilt Watch's "Nearby" tab as a plain card list instead of autoplaying
  video.
- Wrote up monetisation options in `docs/MONETISATION.md` rather than
  building anything (no SPEC basis to add a feature unasked).

---

## 3. Finding more photos for existing places

**User:** Asked to check for photo-less places and fill them in by finding
images online.

**What happened:**
- Extended `scripts/fetch_photos.py` so it can geosearch Wikimedia Commons
  for *every* place missing a photo across the whole database, not just one
  city at a time, using the same 250 m match radius (a photo further away
  risks being of the wrong thing).
- Ran it: coverage went from roughly a quarter to just over 40%, in several
  passes as more cities and states were added later in the session (final
  figure below).
- Fixed a related bug while in that code: a place whose Commons photo had
  been *credited* but never actually downloaded would 404 forever; the route
  now fetches the bytes on first real view instead of only at credit time.

---

## 4. "Use 28 subagents" — scope correction

**User:** Asked to use 28 subagents, one per state, to find new places first
and then photos for them, and asked why language codes in the "add a name"
picker were two letters.

**What happened:**
- Explained why 28 *parallel* subagents hitting Overpass/Wikidata — free,
  shared services — wasn't the right move: the bottleneck is the shared rate
  limit, not the number of callers, and hammering it risked losing access
  entirely. Built `scripts/seed_osm_states.py` instead: the same per-category
  Overpass sweep as the existing city seeder, run **one state at a time, one
  query at a time**, with the existing mirror-and-retry logic.
- Tested on Goa, then ran the full 28-state pass in the background.
- Answered the language-code question: they're ISO 639-1 codes (`kn`,
  `te`, ...), the standard tag for the HTML `lang` attribute, i18next and
  font selection. The dropdown was showing the raw code instead of
  "Kannada (ಕನ್ನಡ)" — pulled the existing language-name table (already built
  for Settings) into a shared module and used it there too.

---

## 5. "Only add famous places, the task is photos not new places"

**User:** Said the state-seeding run should only keep places that are "kinda
famous", and that the real priority is photos, not adding more places.

**What happened:**
- Stopped the 28-state run (it had only reached Goa and Andhra Pradesh,
  adding 1,409 places).
- Removed the 1,043 of those with no Wikipedia tag and no Wikidata id — i.e.
  no real notability signal, just a plain OSM name. Kept the 366 that had
  one.
- Changed `seed_osm_states.py`'s default behaviour to apply that same filter
  automatically, so a future run can't repeat the mistake. Did not continue
  seeding the other 26 states, since the user had just said that wasn't the
  priority.
- Went back to the photo-fetch pass instead.

---

## 6. Search only matching literal place names

**User:** Pointed out that searching "Goa" only returned places with "Goa"
literally in their name, not a way to browse the state; asked for the same
for towns/cities, not just large cities.

**What happened:**
- Added `GET /states/{slug}/places` and `GET /localities/{slug}/places`,
  mirroring the existing `GET /cities/{slug}/places` (same sorts, pagination,
  payload shape) but scoped by a place's `state` or new `locality` column
  instead of a seeded `City` row.
- Added a `locality` column to `Place`, backfilled from Wikidata's nearest
  P131 step (usually the actual town, e.g. "Tirupati") by re-running the
  Wikidata seeder with an extended query.
- `/search` now also matches state and locality names and offers them as
  places to browse, before falling back to literal place-name matches.
- Caught and fixed a data-quality side effect: 123 places had backfilled to
  locality = "India" itself (a very sparsely-tagged item's one-hop P131
  landing on the country); cleared those and filtered the case going
  forward.
- Place pages now show the nearest town/district instead of falling back
  straight to the state when there's no seeded-city neighbourhood data,
  since most of the database is outside the handful of deeply-seeded cities.

---

## 7. Search losing its scope; Nearby always saying "Hyderabad"; the deck's radius

**User:** Reported that typing in Explore's search box while browsing a city
replaced the whole list with results from anywhere in India; that the Nearby
header always said "Hyderabad" and never changed; and that widening the
deck's search radius revealed places only 3–4 km away that should already
have been inside a smaller radius.

**What happened:**
- Found that Explore's search box was calling the *global* search endpoint
  and swapping it in for the current city/state/town's list on every
  keystroke. Changed it to filter the current scope's own list instead
  (the scoped endpoints already accepted a `q` parameter); the global search
  still runs, but only to offer "browse somewhere else".
- Found that "Hyderabad" at the top of Nearby was always the user's *saved
  home city*, never their live position. Added `GET /here?lat=&lng=`
  (seeded city if inside one, else the nearest place's locality/area, else
  its state) and wired Nearby's header to it.
- Investigated the radius complaint by reading the deck code directly: the
  candidate query and the haversine radius filter were both already correct
  — a 3–4 km place was always a valid candidate. The real bug was that only
  the top 30 of the *ranked* list was ever shown, and reloading at the same
  radius re-drew the ranking's random (Thompson-sampling) component from
  scratch each time, so a place that scored just outside the top 30 could
  lose on every redraw and never be shown however many times the radius was
  "widened" back over it. Fixed by seeding the ranking once per day instead
  of once per request, and using the request counter to page through that
  one stable order — so continued swiping at a fixed radius eventually
  reaches every candidate in it. The end-of-deck message is now honest about
  whether there's more to see, with a "Keep swiping" option when there is.
- Also seeded 9 more real cities (Chennai, Bengaluru, Kochi, Mumbai,
  Kolkata, Ahmedabad, Amritsar, Bhubaneswar, Guwahati) via the existing OSM
  city seeder, since Settings' "Your city" picker had scripts/labels ready
  for them but only Hyderabad had ever actually been seeded — otherwise
  nothing could ever be picked but Hyderabad. Ran the duplicate-merge script
  afterwards since the new OSM data overlapped with existing Wikidata
  entries for the same landmarks.

---

## 8. "Add a place" photo upload failing

**User:** Reported that uploading a photo on the "Add a new place" page
showed "something went wrong".

**What happened:**
- Traced it to the API log: a foreign-key violation on the `media` table.
  "Add a place" uploads its photos in step 1, before the place itself
  exists, using `place_id = 0` as a placeholder — but 0 isn't a real place,
  and SQLite was correctly rejecting the insert. No test had ever exercised
  this path, so it's unclear it had ever worked.
- Made `Media.place_id` genuinely nullable (NULL while unattached, never the
  constraint-violating 0). Since SQLite has no `ALTER COLUMN` to drop a
  `NOT NULL`, wrote a one-time table rebuild in `init_db()`: rename, recreate
  from the current model, copy every row across, drop the old table —
  checked it was idempotent and preserved all existing rows before trusting
  it against the real database.
- Verified the fix against the live, running server: uploaded a photo with
  no place yet, created the place, confirmed the photo attached. Added two
  regression tests.

---

## 9. Status checks

**User:** Asked more than once whether background jobs were still running.

**What happened:** Checked the actual job output files and, once, the live
process list, and reported plainly what had finished, what hadn't, and in
one case what a long stretch of "0 photos found" meant (a cluster of remote
Himalayan coordinates with genuinely no nearby Commons photos — verified
directly against the Commons API rather than assumed).

---

## 10. Final photo coverage question

**User:** Asked whether all ~16k places now had images.

**What happened:** Checked the database directly and reported the true
number: 8,339 of 18,320 places (45.5%) have a credited photo. The rest keep
their category illustration — mostly small, remote OpenStreetMap features
with no close-up photo on Commons at all, which is a genuine limit of the
free data source rather than something retrying would fix.

---

## 11. Card A6 — repo hygiene, CI workflow, commit skill

**User:** Asked to run "card A1" by name before the `/card` skill had been
discovered; once the skill turned up (`.claude/skills/card/SKILL.md`), picked
up the actual next card in order, A6, from `docs/NEXT_LEVEL_PLAN.md`.

**What happened:**
- Removed the tracked `pagdandi-starter.zip` (394 KB; its contents were
  already unpacked into the repo from the earlier Truvel rename) and widened
  `.gitignore`'s rule from the one literal filename `truvel-starter.zip` to
  `*-starter.zip` so this can't recur under either name.
- Dropped a stale line from the SPEC.md epigraph — "Working name; check it
  first (Q1)" — now that the name was settled to Truvel everywhere else in
  the codebase; proposed this as an explicit diff and waited for approval
  first, since a SPEC change is one of the card skill's "stop and show the
  plan" triggers.
- Added `.github/workflows/ci.yml`: ruff + pytest on Python 3.12, `npm ci` +
  lint (`tsc --noEmit`) + `npm run test` on Node 20. Deliberately no
  Playwright yet — it needs seeded data CI doesn't have.
- Recreated `.claude/skills/commit/SKILL.md` per PROMPT.md Prompt 3 (run
  tests, refuse anything on the "Never commit" list, write a
  `phase N:`/`card ID:` message, print the short hash).
- Backend (227 tests) and frontend (26 tests) green locally; pushed the
  branch on request so GitHub Actions could actually run the new workflow
  (confirming it went green was left to the user — no `gh` CLI or repo API
  access from this session).
- Ticked A6 in `docs/NEXT_LEVEL_PLAN.md`, logged in `PLAN.md`, 3 viva Q&A
  appended to `docs/VIVA.md`.

---

## 12. Card A1 — security, privacy and fraud review

**User:** Asked to run card A1 (security, privacy and fraud review) once A6
was done.

**What happened:**
- Per the card and PROMPT.md Prompt 8, launched an independent background
  subagent with *no* visibility into this conversation — given only
  CLAUDE.md's invariants, the named SPEC sections, and the backend source —
  to hunt for ways to leak a user's location, get kadam/earnings without a
  real visit, see a fragile place's pin before pledging, smuggle a bad
  upload past pHash, show an unlabelled ₹ figure, or break auth.
- It came back with 1 Critical, 3 High, 2 Medium and 1 accepted Low finding.
  Traced each to exact code, proposed concrete minimal fixes (no SPEC
  change needed — these were enforcement bugs against rules already
  written down), and waited for approval before touching ~10 files.
- Fixed, each with a new test in `backend/tests/test_security.py`:
  - **Critical** — `place_payload`'s `distance_km` (and the duplicate-places
    endpoint's `distance_m`) were computed from a fragile place's *true*
    coordinates even when the returned `lat`/`lng` had been fuzzed to ~1 km;
    three distance readings from three known points could trilaterate the
    exact pin without ever pledging. Fixed by deriving distance from the
    same (possibly fuzzed) coordinates actually returned.
  - **High** — `/api/touch` trusted a client-asserted `video`/`photo`
    content_type with no check that anyone had actually watched anything,
    letting an account flood fabricated touches for a creator right before
    a real check-in and walk off with that creator's attribution/kadam.
    The legitimate path already existed server-side in the watch-view
    handler (created only from a genuinely engaged `MediaView`), so the
    fix was to delete the unverifiable branch entirely, add an hourly rate
    limit, and dedupe repeated place/steps touches.
  - **High** — Uvicorn's default access logger printed every deck/watch/
    search request's full query string, including the viewer's live
    `lat`/`lng`, to plaintext logs — technically outside invariant 1's
    "never store coordinates" (no DB column was ever touched) but against
    its spirit. Disabled `uvicorn.access` at import time.
  - **High** — `check_in`'s "already visited today?"/"first ever visit?"
    checks were a plain read-then-write with no lock; since FastAPI runs a
    sync route in a thread pool, two near-simultaneous check-ins could both
    pass the checks before either committed, double-awarding kadam and
    running attribution twice for one physical visit. Fixed with a
    per-`(user_id, place_id)` `threading.Lock` around the whole section —
    sufficient because this is a single-process, single-SQLite-file app by
    design (no Postgres/Redis). A 5-thread concurrent test proved the bug
    and then proved the fix.
  - **Medium** — `login()`'s `user is None or not verify_password(...)`
    short-circuited the (deliberately slow) argon2id check whenever no
    account matched, making a non-existent identifier measurably faster
    than a wrong password on a real one — a timing side-channel defeating
    the endpoint's otherwise-identical error message. Fixed with a
    precomputed dummy hash checked on every login attempt regardless.
  - **Medium** — the dev `/teleport` endpoint (used for the viva demo) handed
    back a fragile place's exact coordinates with no pledge check at all.
    Fixed to apply the same ~1 km fuzzing `place_payload` uses until the
    caller pledges — matching, not weakening, the real API's behaviour.
  - **Low, accepted, not fixed** — pHash dedupe can be defeated by a simple
    flip/crop/colour-shift; this is inherent to perceptual hashing and
    already slated for the Tier-2 CLIP-embedding mitigation in SPEC.
- Also added the security headers the card asked for (CSP scoped to
  `tiles.openfreemap.org` per invariant 7, `X-Content-Type-Options`,
  `Referrer-Policy`, `Permissions-Policy`, `X-Frame-Options`).
- Wrote up every finding and fix in `docs/SECURITY_REVIEW.md`. Full suite:
  238 backend tests, 26 frontend tests, all green. Left several unrelated,
  pre-existing uncommitted changes (stray frontend edits, regenerated
  Playwright screenshots) untouched rather than folding them into this
  commit.
- Ticked A1, logged in `PLAN.md`, 3 viva Q&A appended to `docs/VIVA.md`.

---

## 13. Card A2 — tick what's already verified; Lighthouse

**User:** Asked to run card A2 via the `/card` skill.

**What happened:**
- The card's premise checked out: `npx playwright test` was green (70
  passed across both themes), so AC-20/21/22 in `PLAN.md` Phase 9 got
  ticked.
- Built the production bundle (`npm run build`) and ran Lighthouse's mobile
  profile against it (via `npm run preview`) for Nearby (`/`) and Watch
  (`/watch`), per the card's instruction — first result: Performance
  72/84, Accessibility 98/100, Best Practices 92/92, SEO 92/91.
- Fixed the top real findings rather than chasing every audit line
  (console 401s from Lighthouse's own unauthenticated probe, and the
  `geolocation-on-start` flag on screens that genuinely need location on
  mount for their core feature, were both judged not real bugs):
  1. The deck's lead photo is the LCP element on both screens but had no
     `fetchPriority` hint and was competing with a 1.3 MB of map/geometry
     JS for bandwidth. Added `fetchPriority="high"` to `DeckCard`'s front
     card only (not the peeking back card, which isn't render-critical).
  2. Neither screen had a `<main>` landmark (axe `landmark-one-main`).
     `App.tsx` now wraps the routed screen in one, kept outside
     `<BottomNav>` since persistent chrome isn't page content — Nearby's
     accessibility score went 98 → 100.
  3. The real culprit behind Nearby's especially bad LCP: Vite was
     emitting an unconditional `<link rel="modulepreload">` for the
     `turf` chunk into the single shared `index.html`, so *every* route —
     including Nearby, which never touches `@turf/turf` (only the
     fog-of-war map screen does) — paid for downloading it before first
     paint. Added `build.modulePreload.resolveDependencies` to
     `vite.config.ts` to drop the `maplibre` and `turf` chunks from the
     preload list.
- Rebuilt and re-ran Lighthouse to confirm: Watch's Performance rose
  84 → 90 and its LCP score 0.53 → 0.69-0.73. Nearby's Performance stayed
  low (~66) — diagnosed as an inherent SPA limitation (the deck photo's
  URL isn't known until the JS bundle parses and `/api/deck` returns, so
  Lighthouse's simulated-throttling model scores the resulting
  `resourceLoadDelay` harshly) that would need server-rendering the first
  card to fix properly; noted as out of scope for the zero-budget,
  no-SSR stack rather than pursued further.
- Backend `pytest -q` (238 passed), frontend `npm run test` (26 passed)
  and `tsc --noEmit` all green before committing. Ticked A2 in
  `docs/NEXT_LEVEL_PLAN.md`, recorded the Lighthouse scores in `PLAN.md`'s
  "Measured values" table and logged the session in its progress log.

---

## 14. Merging the two branches into one

**User:** Asked to merge all branches into a single branch.

**What happened:**
- Only two branches existed: `master` and the working branch
  `claude/affectionate-bohr-nud480`. They had diverged — the working
  branch was 5 commits ahead (cards A6, A1, A2) and 4 commits behind
  (search-scope fixes, the Nearby location/deck-paging fix, the
  "Add a place" photo-upload fix, and 9 more cities seeded on master).
- Asked which branch should end up holding everything; the user picked
  merging into `master`.
- `git checkout master`, then `git merge claude/affectionate-bohr-nud480`.
  Only `PLAN.md` conflicted (both branches had appended different dated
  entries to its progress log); every code file merged cleanly. Resolved
  by interleaving the two branches' entries in chronological order (by
  the dates and same-day "later/later still/even later/latest" labels
  already used in the log), rather than picking one side — both commit
  histories' narratives are preserved.
- Committed the merge.

---

## Where things stand

- One official account (`@truvel`), publisher of every imported place,
  excluded from kadam/Partner earnings.
- 10 real, deeply-seeded cities; state- and town-level browsing for
  everywhere else via `locality`/`state`.
- 18,320 places after duplicate merging; 45.5% have a real, credited photo.
- Password reset, delete-your-own-upload, grouped report review, and
  server-side duplicate rejection are all live and tested.
- The Nearby deck shows a live position-based location, pages through its
  full ranked candidate list instead of silently dropping places past the
  first 30, and is honest about whether there's more to see.
- "Add a place" photo upload works end-to-end again.
- CI runs ruff + pytest and npm lint/test on every push
  (`.github/workflows/ci.yml`); the starter-archive cruft is gone; a
  `commit` skill enforces the "never commit media/db/env/venv/node_modules"
  rule before every commit.
- An independent security review closed one Critical and three High findings
  (fragile-place trilateration, unverified attribution touches, logged
  viewer coordinates, a check-in double-award race) plus two Medium ones
  (login timing enumeration, a leaky dev teleport), with a test for each in
  `backend/tests/test_security.py` and the full writeup in
  `docs/SECURITY_REVIEW.md`. Security headers (CSP, etc.) are on every
  response.
- AC-20/21/22 Playwright suite (70 cases, both themes) confirmed green and
  ticked; Lighthouse mobile measured on the production build — Nearby/Watch
  Performance 66/90, Accessibility 100/100 — with the deck's LCP photo now
  fetch-prioritised, a `<main>` landmark on every screen, and the unneeded
  `maplibre`/`turf` preload hints dropped from the shared `index.html`.
- `master` and the working branch have been merged into one history on
  `master`; no branches remain diverged.
- Next up per `docs/NEXT_LEVEL_PLAN.md`'s stated order: card A5 (split the
  long handlers, behaviour-preserving).
