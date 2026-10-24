# SECURITY_REVIEW.md — card A1, 23-24 Oct 2026

An independent subagent (PROMPT.md Prompt 8) reviewed the backend with no
visibility into any other conversation about this project — only CLAUDE.md's
invariants, SPEC.md §5, §8.7, §8.8, §8.14, §9.6-9.10, §10, §14, and the backend
source. It found 1 Critical, 3 High, 2 Medium and 1 Low (accepted) finding.
Every Critical/High/Medium is fixed below, each with a test in
`backend/tests/test_security.py`. `pytest -q` is green (238 passed).

---

## 1. CRITICAL — Fragile-place exact coordinates recoverable by trilateration

**Where:** `services.place_payload()` computed `distance_km` from the place's
*true* `lat`/`lng` even when it had just fuzzed the `lat`/`lng` it returned to
~1 km for an unpledged fragile place. `routers/add.py`'s duplicate-candidate
endpoint had the same gap: `distance_m` came from the true coordinates
regardless of redaction. Three `GET /api/places/{id}?lat=&lng=` calls (or
three `POST /api/places/candidates` calls) from three known points gave three
exact distances — enough to trilaterate the true pin without ever pledging,
breaking invariant 5.

**Fix:**
- `services.py`: `distance_km` is now computed from `out_lat`/`out_lng` (the
  value actually returned), never from `place.lat`/`place.lng`.
- `add.py`: `duplicate_candidates` only includes `distance_m` in the response
  when `payload["coords_exact"]` is true.

**Tests:** `test_fragile_place_distance_comes_from_fuzzed_not_true_coordinates`,
`test_duplicate_candidates_hide_exact_distance_for_fragile_unpledged_place`.

---

## 2. HIGH — `/api/touch` trusted the client to assert a video/photo view

**Where:** `routers/interact.py:record_touch` let any logged-in user claim
"I watched creator C's video" via `content_type="video"` with no check that a
genuine, engaged `MediaView` existed, and had no rate limit. The frontend
never actually calls it that way (legitimate video touches are created
server-side in `watch_router.record_view`, straight from a classified,
engaged `MediaView` — see SPEC §9.10), so the branch was pure unverifiable
attack surface: flood touches for a target creator, then make one real
check-in, and walk away with that creator's attribution share and
`kadam.VISIT_CAUSED` for content nobody watched.

**Fix:**
- `record_touch` now only accepts `content_type in ("place", "steps")`;
  `video`/`photo` touches can only be created by the watch-view handler that
  already verified engagement.
- Added `rate_limits.touches_per_hour` (config.yaml, default 60), enforced the
  same way as `checkins_per_hour`/`pulse_per_hour`.
- A repeated call for the same `(user, place, content_type, content_id)`
  inside the attribution lookback window is now a no-op, so one real page
  view can't be replayed into dozens of weighted `Touch` rows.

**Tests:** `test_touch_rejects_video_and_photo_content_types`,
`test_touch_does_not_duplicate_on_repeated_calls`, `test_touch_is_rate_limited`.

**Remaining gap, noted not fixed:** SPEC §9.9 also wants last-mile-steps
touches to require "read for ≥ 10 s," but nothing in the codebase tracks step
read duration server-side — the frontend's 10 s timer is a client-side
courtesy only. Verifying that server-side needs a new dwell-time signal (a
Tier-2-sized feature, not a hardening fix), so for now a `steps` touch is
rate-limited and deduped like a `place` touch but not duration-verified.

---

## 3. HIGH — Viewer coordinates persisted to plaintext logs

**Where:** `/api/deck`, `/api/watch`, `/api/places/{id}`,
`/api/cities/{slug}/places` and `/api/search` all accept the viewer's live
position as `lat`/`lng` query parameters (by design — that's how "near me"
works). Uvicorn's default access logger printed the full request line,
including that query string, to stdout on every one of those requests —
accumulating a plaintext location history even though `Visit`/`Pulse`/`Touch`
correctly never store coordinates (invariant 1 covers the database; a log
file is storage too).

**Fix:** `main.py` disables the `uvicorn.access` logger at import time.

**Test:** `test_uvicorn_access_logger_is_disabled`.

---

## 4. HIGH — Check-in race condition could double-award kadam and attribution

**Where:** `routers/checkin.py:check_in` read "already checked in today?" and
"is this the first-ever visit?" and then, separately, inserted the `Visit`
row and ran awards/attribution — a plain check-then-act with no lock.
FastAPI runs a sync `def` route in a thread pool, so two near-simultaneous
check-ins from the same person for the same place (two tabs, a double-tap, a
scripted retry) could both read "no visit yet" before either committed,
doubling `own_visit` kadam and, worse, running visit attribution twice for
one physical visit.

**Fix:** a per-`(user_id, place_id)` `threading.Lock` now wraps the whole
read-then-write section (`check_in` acquires it, then calls the actual logic
in `_check_in_locked`). This is a single-process, single-SQLite-file app
(CLAUDE.md: no Postgres/Redis), so an in-process lock is sufficient and
needs no schema migration.

**Test:** `test_concurrent_checkins_award_kadam_only_once` (5 threads check in
simultaneously; exactly one wins, exactly one `own_visit` KadamEntry exists).

---

## 5. MEDIUM — Login timing side-channel enabled user enumeration

**Where:** `routers/auth_router.py:login` used
`user is None or not auth.verify_password(...)` — short-circuit evaluation
meant the (deliberately slow, memory-hard) argon2id check only ran when an
account existed. A non-existent identifier returned fast; a real one with a
wrong password was measurably slower, undoing the point of the identical
error message (SPEC §11).

**Fix:** `auth.py` now computes a dummy argon2id hash once at import
(`dummy_hash()`). `login()` always calls `verify_password` — against the
real hash if the account exists, against the dummy hash if it doesn't — so
both paths cost the same.

**Tests:** `test_login_with_nonexistent_identifier_still_calls_verify_password`,
`test_dummy_hash_never_verifies_as_a_real_password`.

---

## 6. MEDIUM — Dev teleport leaked exact fragile coordinates regardless of pledge

**Where:** `routers/dev.py:teleport` returned `place.lat`/`place.lng`
directly for any place, including a fragile, unpledged one. `_guard()` only
checked the `DEV_ALLOW_FAKE_LOCATION` flag — and that flag is exactly the
mode CLAUDE.md's documented demo workflow runs in, so this wasn't a
theoretical edge case.

**Fix:** `teleport()` now applies the same fuzzing `place_payload` uses
(`services.FRAGILE_PRECISION`) when the place is fragile and the caller
hasn't pledged. Pledging first (`POST /api/places/{id}/fragile-pledge`, same
as the real flow) unlocks the exact coordinates for the simulator too — this
is the correct behaviour, not a regression: the dev tool now follows
invariant 5 exactly as the rest of the API does.

**Test:** `test_teleport_hides_fragile_place_before_pledge` (checks both the
fuzzed pre-pledge response and the exact post-pledge one).

---

## 7. LOW — pHash dedupe defeated by simple image transforms (accepted, Tier 1)

A horizontal flip, hard crop, or strong colour shift typically pushes a
stolen photo's Hamming distance past the configured threshold
(`integrity.phash_max_hamming`, default 8), letting it be re-uploaded
undetected. This is an inherent property of perceptual hashing, not a bug in
this implementation, and SPEC already names CLIP embedding similarity
(§9.6/§9.11) as the Tier-2 mitigation. No Tier-1 change made; noted here so
it isn't mistaken for full theft protection in the viva.

---

## Also added (card A1's explicit "Do")

Security headers on every response (`main.py`): `Content-Security-Policy`
(restricted to `'self'` plus `tiles.openfreemap.org`, per invariant 7),
`X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`,
`Permissions-Policy: geolocation=(self)`, `X-Frame-Options: DENY`.
Test: `test_security_headers_present`.
