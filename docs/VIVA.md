# VIVA.md — Pagdandi (v2)

The questions an examiner is most likely to ask, with plain-English answers.
Learn the **bold line** first; the rest is backup. Prompt 5 appends 3 questions per
phase under "Phase notes". Before the viva, check every answer against the final
code and fill the [numbers].

---

## A. The idea

**1. What is your project, in one sentence?**
**A travel, social and creator app for India where people discover places to visit,
including hidden ones that aren't on Google Maps, in their own language, and
creators are rewarded mainly for the visits they cause.**

**2. Isn't this just Google Maps, Instagram or YouTube?**
**Each feature exists somewhere; the combination doesn't.** Google Local Guides
rewards reviewing places already on Maps. YouTube and Instagram reward views, which
favour entertainment. Tripoto and Explurger are travel social apps built around
trip posts. Pagdandi has verified, unmapped places with last-mile directions and
live conditions, and its creator rewards are tied to real visits.

**3. What makes people come back?**
**Things that pull them outside:** the deck of nearby places, short videos with a
"Go here" button, live conditions, a fog map they clear by visiting, passport
stamps, a weekly (not daily) streak, and credit when someone visits a place they
found. The deck ends, and Watch nudges you after 20 minutes. We build a habit of
going out, not of scrolling.

**4. What's your moat? Couldn't Google copy you?**
**Google could copy any feature; it's harder to copy the data and the incentives.**
Verified unmapped places, last-mile steps and live Pulse get better with every
visitor in each city (a network effect). Paying creators for visits caused draws
useful content. All 22 scheduled languages from day one, and privacy (we never store
where users are), build trust.

## B. Money

**5. How do creators earn? Is it like YouTube?**
**Similar idea, different measure.** YouTube shares 55 % of ad revenue on long-form
videos (45 % on Shorts) with Partner Program members. We use the same 55 % creator
pool, but split it by a score where **one visit caused counts as much as 25 engaged
views**, plus small amounts for helpful directions and confirmed live reports.

**6. Does your app pay real money?**
**No. The pool is a simulated number from config, and every ₹ on screen says
"Simulated".** Real payouts need revenue, identity and bank verification, tax
deduction and a payment partner. That's the roadmap; the engine and the maths
are built and tested.

**7. Where would the money come from?**
**Local businesses near places ("Food & stay nearby", paying per verified visit),
clearly labelled sponsored cards (at most 1 in 15), sponsored trails from tourism
boards, and an optional Plus subscription.**

**8. Why not pay per like, as originally planned?**
**Likes are cheap to fake and reward looks, not usefulness.** Paying per like
invites bought likes, stolen photos and dangerous stunts. A visit means someone
physically went there, which is much harder to fake and is the outcome the app is
for.

**9. Who is eligible to earn?**
**Accounts 30+ days old with no strikes, 10+ pieces of verified content, and in the
last 90 days either 300 visits caused or 1,00,000 engaged views.** The thresholds
stop fake accounts from farming small amounts.

## C. Data and languages

**10. Where does your place data come from? Did you copy Google Maps?**
**No. Famous places across India come from Wikidata (CC0), photos from Wikimedia
Commons (free licences with attribution), and one city in depth from OpenStreetMap
(ODbL).** Copying Google Maps would break its terms and the photographers'
copyright. Google's Places API terms also forbid using its content with a non-Google
map and limit how long coordinates can be stored, and it's paid beyond free limits.
We only use the free "Open in Google Maps" link for directions.

**11. How do you get photos?**
**From each Wikidata item's image on Commons, fetched once, cached on our server,
and shown with author and licence.** We accept only CC0, public domain, CC BY and
CC BY-SA. Users add their own photos for hidden places.

**12. How do you support all Indian languages?**
**Place names come in all 22 scheduled languages + English** from OpenStreetMap's
`name:xx` tags, Wikidata labels, and users with a verified visit who add a name in
their language. Each place shows English (or your language) plus the regional
language's name in its script. Fonts are self-hosted per script and only download
when that script appears.

**13. What if a place has no name in my language?**
**We show English and the regional name.** As Tier 2 we run AI4Bharat's IndicXlit
(an open MIT-licensed transliteration model for 21 languages) in Colab and import
its output tagged "auto". It doesn't cover Dogri or Santali.

**14. Is the whole app translated into 22 languages?**
**Not yet. Place names are; the interface is English first, then Hindi and one
regional language reviewed by native speakers.** We don't ship machine-translated
UI as if it were reviewed. Bad translations damage trust more than English does.

**15. Why do you hide country borders on the map?**
**India has strict rules on how its external boundaries are depicted, and free map
data may not match the official depiction.** We don't need borders, so we hide those
layers and take states from Wikidata's administrative hierarchy instead.

**16. What do you store about users' location?**
**Nothing.** At check-in the phone sends its position once; the server keeps only
the distance to the place and the GPS accuracy, then discards the coordinates.

## D. Algorithms (the data science / AI part)

**17. How do you rank places? Why not sort by likes?**
**By the Wilson lower bound of likes ÷ viewers.** Raw likes favour old places; a raw
ratio favours 1 like out of 1 viewer. The Wilson lower bound is the cautious end of a
95 % confidence interval for the true like rate. Example: 1/1 → 0.21, 8/10 → 0.49,
80/100 → 0.71.

**18. Formula?**
With p̂ = k/n, z = 1.96: `(p̂ + z²/2n − z·√(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n)`.

**19. How does the deck learn what I like?**
**Thompson sampling, a multi-armed bandit method.** Each category has a Beta(α, β)
distribution starting at Beta(1,1). Save → α+1, skip → β+1. For each deck we draw a
random value per category and use it as your taste score. Liked categories rise;
rarely seen ones still get tried sometimes. It needs no training data and is
explainable.

**20. How is Watch ranked?**
**35 % quality (Wilson of completions over engaged views), 20 % closeness, 20 % your
taste (same Thompson sampling), 15 % freshness, 10 % following,** with no more than 2
videos in a row from one creator.

**21. What is an "engaged view"?**
**At least 3 seconds watched (or half of a very short video).** A completion is 90 %.
Views by the creator, by accounts under 24 hours old, or repeats by the same user
within 24 hours don't count.

**22. How do you decide which creator "caused" a visit?**
**Time-decay attribution.** When someone visits a place for the first time, we look at
what they engaged with about that place in the previous 30 days: the place page
(credit to the discoverer), videos, last-mile steps. Each touch gets weight
2^(−age in days / 7), so a video seen yesterday counts more than one seen 3 weeks
ago. Weights are normalised so the visit's credit sums to 1 and is split between
creators.

**23. Why time-decay and not last-touch?**
**Last-touch gives everything to the final thing seen; linear ignores timing.** We
compared all three in a simulation with known true influence, measuring which
recovers it best. [Fill in: Spearman ρ for each.]

**24. How do you catch fake views?**
**Rules plus a spike detector.** On top of the view rules, if an item's views in one
hour exceed its 7-day hourly mean by 4 standard deviations (and are over 50), the
excess is held out of earnings for review. Tier 2 adds an Isolation Forest, an
unsupervised anomaly detector, over daily creator features.

**25. How do you detect duplicate places?**
**Distance plus fuzzy name matching across all languages.** Within 300 m and ≥ 80 %
name similarity to any of the candidate's names (after removing generic words like
"lake", "cheruvu", "talab"), or within 100 m and the same category. The user decides.

**26. Stolen photos?**
**Perceptual hashing:** a 64-bit fingerprint of how an image looks. Copies that have
been resized or recompressed stay within 8 bits, so we reject another user's photo.
It can't catch photos we've never seen.

**27. How do you know someone really visited?**
**Geolocation at check-in: within 150 m with accuracy ≤ 100 m,** plus an
impossible-travel check (> 120 km/h between check-ins). GPS can be spoofed by a
determined user; we raise the cost of cheating rather than claiming it's impossible.

**28. What is Pulse?**
**Live conditions posted only by people who checked in there in the last 2 hours:**
water flowing/dry, crowd, path, open/closed. Live for 6 hours, recent for 48. If
recent reports disagree, we show the majority and say "mixed reports".

## E. Evaluation

**29. How did you evaluate all this without real users?**
**Simulations with known ground truth, each over many random seeds with 95 %
confidence intervals,** plus a coverage table from the real data and the acceptance
tests. Simulations show the methods work under stated assumptions; they don't prove
real users behave that way. A user study is future work.

**30. Results?**
- Ranking: Wilson precision@10 [__] vs raw likes [__].
- Bandit: Thompson save rate @30 [__] vs random [__].
- Attribution: time-decay ρ [__] vs last-touch [__] vs linear [__].
- Fraud rules: precision [__], recall [__].
- pHash: detection [__ %], false matches [__ %].
- Coverage: [__] places in India, [__ %] with photos, names in [__] languages.

## F. Engineering

**31. Architecture?**
**React web app → FastAPI (Python) → SQLite, with media on disk.** Seed scripts pull
from OpenStreetMap and Wikidata; the server proxies and caches Commons photos. Maps
use MapLibre with free OpenFreeMap tiles. It all runs on a laptop; the phone connects
over HTTPS on the same Wi-Fi.

**32. Why a web app?**
**Zero budget, one codebase, installable from the browser.** The Play Store needs a
paid developer account.

**33. How does the fog work?**
**A semi-transparent layer over the city with 1 km holes around each verified visit**
(circles merged and subtracted with Turf.js). Progress is counted in neighbourhoods:
each visit belongs to the nearest neighbourhood point, which is the same as asking
which Voronoi cell it falls in.

**34. Limitations and next steps?**
**Simulations not user studies; one deep city; spoofable GPS; simulated money; UI not
yet translated.** Next: a user study with classmates, the real revenue sources,
reviewed UI languages, CLIP photo checks, voice stories in Indian languages, more
cities.

## Push questions
- *"Is this AI?"* → Applied data science inside a product: ranking under uncertainty
  (Wilson), online learning (Thompson bandit), attribution modelling (time-decay vs
  baselines), anomaly detection (spike rule; Isolation Forest), similarity (fuzzy
  names, perceptual hashes, CLIP), neural transliteration (IndicXlit), all evaluated
  by simulation with confidence intervals.
- *"Isn't paying for visits gameable?"* → Visits need physical presence; attribution
  ignores self-touches, new accounts and flagged visits; eligibility thresholds; spike
  holds; reversals on removal. It's harder to game than views, not impossible.
- *"Dangerous places?"* → Safety card always open, edge warnings, no boost for risky
  videos, fragile places hidden until a pledge, 112 shown.
- *"Did you write the code?"* → Built with Claude Code using spec-driven development.
  I wrote and approved the spec and every phase plan, reviewed and tested each phase,
  and can explain every algorithm (`wilson.py`, `thompson.py`, `attribution.py`,
  `split.py` line by line).

## Phase notes

### Build pass, 21 Oct 2026 — phases 0 to 8

**What was built, in plain English.** A FastAPI backend with 43 routes over a
SQLite database, and a React frontend of nine screens that match
`docs/design-reference.html` in both light and dark. Every algorithm in SPEC §9
and §10 is a small pure function with its own tests. The data is real: 296
places and 1,408 neighbourhoods for Hyderabad from OpenStreetMap, and 16,971
famous places across all 34 states and union territories from Wikidata, with
names in 21 of the 22 scheduled languages. Four simulations measure the design
choices, and the README quotes their `metrics.json` exactly.

---

**Q1. Your ranking simulation says the plain like-ratio beats Wilson on Kendall
τ (0.621 vs 0.554). So why did you use Wilson?**

**Because τ measures the wrong thing for this product, and precision@10
measures the right one — and Wilson wins there, 0.452 against 0.356.**

Kendall τ scores the ordering of all 500 places, including the hundreds nobody
will ever scroll to. Wilson deliberately shrinks a place seen by six people
towards zero, because six people is not evidence. That shrinkage misorders the
long tail, which costs τ. At the top of the list — the only part a user reads —
that same shrinkage is exactly what stops a place with 2 likes from 2 viewers
outranking one with 1,600 from 2,000. The mean *true* like rate of the top ten
is 0.651 under Wilson against 0.592 under the ratio, so a user served by Wilson
genuinely has a better time. I report both numbers because reporting only the
flattering one would be dishonest.

---

**Q2. Your own bandit simulation shows Thompson sampling is 8.4 % *worse* than
just ranking by popularity over the first 30 swipes. Why ship it?**

**Because the same simulation shows it is 7.0 % better once it has learned, and
the deck is for people who come back.**

Over the first 30 swipes Thompson is still drawing from a uniform Beta(1,1)
prior for eight categories — it is spending swipes finding out what you like,
and that costs about one save in thirty. By the settled window (the last 30 of
150) it has a real belief per category and beats popularity 0.155 to 0.145.
The crossover is the whole story of exploration versus exploitation, and it is
the honest argument: if the app were a one-visit kiosk, popularity would be the
right choice. It is not — a weekly streak and a passport are the product — so
paying a small early cost for a better long-run feed is the correct trade. If I
wanted the best of both, the next step is seeding the prior from the
population's average taste rather than a uniform one, which the simulation
already has as its "fixed weights" baseline.

---

**Q3. Your fraud rules have recall of 0.786. A quarter of the fraudulent views
get through. Isn't that a failure?**

**Recall is the wrong headline. Precision is 1.000, and the number that matters
is that fraud's share of the pool drops from 0.598 to 0.278.**

Three points. First, precision 1.000 over 50 runs means the rules never once
flagged an honest view — and a false positive here takes money from a real
creator, which is worse than letting a bot view through. Second, the rules
remove 53.6 % of what fraud would have earned, which is the figure that
actually describes the defence. Third, and most importantly, the simulation
scores on **views only**, to isolate the view rules. The real defence is that a
visit is worth 25 views in `partner.weights`, and a visit needs a person
standing in a place with GPS accuracy under 100 m, no impossible travel, and
two independent confirmations before a new place even counts. The honest
conclusion, which the simulation's own assumptions state, is that these rules
raise the cost of fraud; they do not end it. A patient attacker with aged
accounts viewing once each at human pace would evade all four.

---

**Q4. You found bugs in your own spec. Which, and how?**

Four, and each was found by a different kind of check:

1. **Four Wikidata QIDs were wrong.** SPEC §6.2 lists classes to seed and says
   "Phase 1 verifies each QID in the query service". Doing that showed Q842425
   is the chef Rau Le Creuset, not a gurdwara; Q1066288 is "figurine", not a
   stepwell; Q2082441 is the record producer Keith Olsen, not a ghat. Had I
   skipped the check, the seed would have quietly returned nothing for those
   classes and I would have concluded India has no stepwells.
2. **The kadam caps were ambiguous.** "pulse +3, 5 per day" reads as five
   reports a day (15 kadam), not five kadam. The table makes sense only on the
   first reading — `visit_caused +10, 20 per place per day` would otherwise cap
   at two visits. Implemented as event counts, documented in `kadam.py`.
3. **The deck's diversity re-rank was broken.** The obvious greedy — "take the
   best card that does not extend the run" — strands a long run at the end: six
   videos from one creator and three from another came out as a run of five. I
   only found it because I wrote a test that stressed the tail rather than the
   head. The fix (`app/ranking/diversity.py`) follows the ranking except where
   doing so would make the remainder impossible to arrange, which has a closed
   form: `largest_group <= k * (total - largest_group + 1)`.
4. **The fog denominator did not survive real data.** SPEC §8.4 wants a number
   that "feels reachable" and illustrates it with "12 of 87 neighbourhoods".
   Real OSM gives Hyderabad about 1,400 nodes tagged suburb or neighbourhood,
   mostly residential colonies, so the honest count read "6 of 1,408 (0 %)". I
   changed the denominator to neighbourhoods that contain at least one place —
   244 for Hyderabad — because an area with nowhere to go is not somewhere the
   app can send you. **This is a SPEC change and needs sign-off**; it is
   flagged in PLAN.md rather than slipped in.

---

**Q5. Why is time-decay attribution the right rule, when your own sweep shows
last-touch beats it at a 2-day decay and linear beats it at 30?**

**Because we do not know how real influence decays, and time-decay is the only
one of the three that is never far from best at any decay.**

The sweep is the argument. Across ground-truth decay constants from 2 to 30
days, last-touch ranges 0.77–0.93 and linear 0.74–0.87, while time-decay stays
between 0.85 and 0.91. Last-touch is excellent when recency is everything and
poor otherwise; linear is the reverse. Choosing either is a bet on a parameter
nobody has measured. Time-decay costs a little in both extremes and never
collapses — and since this rule divides money between real people, robustness
to being wrong about the world matters more than winning the best case. The
half-life is a config value (`attribution.half_life_days`), so it can be tuned
if real data ever tells us what the decay actually is.

---

**Q6. What is *not* done, and what would you do next?**

Not done, honestly:
- The things needing a body outdoors: real check-in accuracy, a real uploaded
  video's first-frame time, median upload size from a phone, and the two real
  places and two real videos PLAN.md asks for on 24–25 Oct.
- pHash robustness is measured on generated stand-in images, not the 50 real
  photographs SPEC §17 item 5 asks for. The harness takes `--photos`.
- Lighthouse has not been run.
- All of Tier 2 (comments, golden hour, Trails, clans, offline, CLIP,
  Isolation Forest, IndicXlit, Wikivoyage) and the Hindi/Telugu UI, which by
  invariant 11 cannot ship until a native speaker reviews it.

Next, in order: the outdoor trip (it unblocks four measurements), then the real
pHash run, then CLIP embeddings — because the pHash result shows cropping
defeats the hash completely (0 % detection at a 20 % crop), and CLIP cosine
similarity is the documented Tier-2 answer to exactly that.
