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
