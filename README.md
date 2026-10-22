# Truvel — Discover Hidden India

> Every city has places the map doesn't know. The dashed footpath through the
> logo is the one locals walk; *pagdandi*, the word the project was named for
> before it was Truvel, is still what the whole design is built around.

A travel + social + creator web app for India. People discover places — famous
ones from OpenStreetMap and Wikidata with Wikimedia Commons photos, hidden ones
added by people who were physically there — see names in their own language and
the local script, swipe a deck of places near them, watch short videos, read
live conditions, check in on site to clear the fog on their city map, and earn
**kadam** (points). Creators get a Studio and a Partner Program that splits a
revenue pool mostly by **visits they caused**.

**No real money moves in this version.** The pool is a fixed figure from
`config.yaml`, every rupee on screen carries a *Simulated* label, and the Studio
banner cannot be dismissed.

`SPEC.md` is the source of truth. `docs/design-reference.html` is the visual one
(nine screens, both themes). `PLAN.md` tracks the phases.

---

## Running it

Two terminals. Python 3.12 and Node 20+, no Docker, no Postgres, no paid service.

```powershell
# terminal 1 — backend
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```powershell
# terminal 2 — frontend
cd frontend
npm install
npm run dev                  # http://localhost:5173
npm run dev -- --host        # your phone, same Wi-Fi: https://<laptop-ip>:5173
```

### What is in the database

Everything, and only what came from a source that can be named:

```powershell
python -m scripts.seed_osm --city hyderabad       # ~300 places, 1,400 areas
python -m scripts.seed_wikidata --verify          # check the class QIDs first
python -m scripts.seed_wikidata                   # ~17,000 places across India
python -m scripts.fetch_photos --city hyderabad --resolve-all
python -m scripts.official_account --reset        # one account, zero engagement
```

There is **one account**, `@truvel`, and every place is published by it. Nothing
has been liked, visited or watched, because nobody has used the app yet. That is
the honest state of a product before launch, and it is what the last command
guarantees: it deletes every account, every like, view, visit, tip, live report
and last-mile direction, and every place that was invented rather than imported.

It prints a generated password once. Write it down — it is stored as an argon2id
hash and cannot be read back. Change `hello@truvel.app` to an address you own.

The copy of the database in this repository uses
`marigold-footpath-granite-2026`, which the end-to-end tests also use
(`TRUVEL_PASSWORD` overrides it). **It is a local development credential and is
in version control: change it before this is reachable by anyone else.**

**To get a populated app back** — for a demo, or to see the Studio and the
Partner Program with numbers in them:

```powershell
python -m scripts.demo_data --reset --viewers 240 --month 2026-10
```

That is invented data and says so on every screen it touches. `--reset` rebuilds
the schema, so it removes the official account too; re-run `official_account`
afterwards if you want it back.

To demonstrate check-in indoors, start the server with the location simulator
and build the frontend with the dev tools — **both** are required, and a
production build has no teleport UI at all:

```powershell
$env:DEV_ALLOW_FAKE_LOCATION=1   # before uvicorn
# frontend/.env.development.local:  VITE_DEV_TOOLS=1
```

Visits made that way are stored `simulated = true`, shown with a **SIM** badge,
and excluded from metrics, attribution and earnings.

---

## Checking it

```powershell
cd backend  && pytest -q                 # 207 tests
cd backend  && ruff check app scripts tests
cd frontend && npm run test              # 26 unit tests
cd frontend && npx playwright test       # 54 tests: 9 screens x 2 themes, axe, privacy
```

Playwright writes screenshots of all nine screens in both themes to
`results/screens/`.

---

## What the measurements say

Every number below is quoted from `results/<name>/latest/metrics.json`, written
by the simulations in `sim/`. Each simulation imports the app's own functions —
never a copy — and records its config, seeds and assumptions alongside the
result. **These are simulations under stated assumptions, not user studies.**

```powershell
python sim/ranking_sim.py --seeds 200
python sim/bandit_sim.py --seeds 50
python sim/attribution_sim.py --seeds 100
python sim/fraud_sim.py --seeds 50
python sim/phash_sim.py --photos "C:/path/to/50/of/your/photos"
python sim/coverage.py --markdown
```

### Ranking: Wilson's lower bound (SPEC §9.1) — 200 seeds

| method | precision@10 | mean true like rate of the top 10 | Kendall τ |
|---|---:|---:|---:|
| raw likes | 0.042 | 0.382 | 0.282 |
| like ratio | 0.356 | 0.592 | **0.621** |
| **Wilson lower bound** | **0.452** | **0.651** | 0.554 |

Wilson puts the genuinely best places on top: precision@10 of 0.452 against
0.356 for the raw ratio (95 % CI [0.433, 0.471] vs [0.337, 0.375] — the
intervals do not overlap). The honest wrinkle is the last column: the raw ratio
wins on *global* rank correlation, because Wilson deliberately shrinks
small-sample places towards zero. That costs ordering accuracy deep in the tail
and buys accuracy at the top, which is the only part of the list anyone reads.

### Thompson sampling for the deck (SPEC §9.4) — 50 seeds, 300 users each

| strategy | save rate, first 30 swipes | save rate once settled |
|---|---:|---:|
| random | 0.114 | 0.114 |
| popularity only | **0.194** | 0.145 |
| fixed category weights | 0.191 | 0.144 |
| **Thompson sampling** | 0.178 | **0.155** |

Exploration costs before it pays. Over the first 30 swipes Thompson is **8.4 %
worse** than ranking by popularity alone; once it has learned, it is **7.0 %
better**. Both are real, and reporting only the second would be dishonest. The
crossover is why the deck uses a Beta prior per category rather than a fixed
weight: a user who comes back is better served, and a user who does not has lost
roughly one save in thirty.

### Visit attribution (SPEC §9.9) — 100 seeds

Spearman ρ between credited visits and the ground truth, as the truth's own
decay constant is swept (the rule is never told it):

| truth decay → | 2 d | 4 d | 7 d | 10 d | 14 d | 21 d | 30 d |
|---|---:|---:|---:|---:|---:|---:|---:|
| last touch | **0.93** | 0.85 | 0.77 | 0.84 | 0.82 | 0.79 | 0.80 |
| linear | 0.74 | 0.80 | 0.82 | 0.83 | 0.87 | 0.87 | **0.87** |
| **time decay (§9.9)** | 0.91 | **0.88** | **0.85** | **0.88** | **0.88** | **0.88** | **0.88** |

This is the argument for the rule the Partner Program divides money with.
Last-touch wins when influence really does decay fast; linear wins when it
barely decays. Time-decay is almost never the single best — and is never far
from it, at any decay. We do not know how real influence decays, so the robust
choice is the right one. At the headline setting (10 days) it also leads
outright: ρ = 0.864 [0.846, 0.881] against 0.806 for last-touch and 0.830 for
linear.

### Invalid traffic (SPEC §9.10) — 50 seeds

| | |
|---|---:|
| precision over individual views | **1.000** |
| recall | 0.786 |
| share of the pool taken by fraud, rules **off** | 0.598 |
| share of the pool taken by fraud, rules **on** | 0.278 |

Precision is 1.000 — in 50 runs the rules never flagged an honest view, which
matters more than recall here, because a false positive takes money from a real
creator. The rules remove **53.6 %** of what fraud would otherwise have earned.
They do not end it: a quarter of the pool still goes to fraudsters when scoring
is views-only. That is the measured case for weighting a visit 25× a view —
a visit needs a body in a place.

### pHash robustness (SPEC §9.7)

With the 8-bit threshold, on 50 images:

| transform | still recognised |
|---|---:|
| re-compress to JPEG q55 | 100 % |
| resize to 50 % | 100 % |
| contrast +30 % | 100 % |
| brightness +25 % | 98 % |
| watermark | 46 % |
| rotate 3° | 36 % |
| crop 5 % | 32 % |
| screenshot frame | 16 % |
| crop 20 % | 0 % |

False-match rate **0.0000 %** (0 of 1,225 different-photo pairs; the mean
distance between two different photos is 31.5 bits, four times the threshold).
So the hash is extremely unlikely to accuse anyone wrongly, and it reliably
catches the lazy copy — re-upload, re-compress, resize. **It does not survive
cropping**, which is the honest limitation and exactly what the Tier-2 CLIP
embeddings in SPEC §9.11 would address.

> Run this with your own photographs (`--photos`). The numbers above come from
> generated stand-in images, which have sharper geometric structure than
> photographs and are a weaker test. The harness says so in its own output.

### Data coverage (SPEC §17 item 7)

**16,967 places** across **34 states and union territories**. **7,063 of them
(41.6 %) have a real photograph**, and in Hyderabad — the city seeded in depth —
**245 of 430 (57 %)** do.

Every one of those photographs is a Wikimedia Commons file under CC0, public
domain, CC BY or CC BY-SA, shown with its author, its licence and a link to its
file page. 69 candidates were thrown away for having no usable licence. Two
sources feed this: Wikidata's own `P18` image, and a Commons **geosearch** within
250 m of the pin, which is how a temple with no Wikidata entry still gets a
picture of itself. A photo from further away is likely to be of something else,
so there is no photo rather than a wrong one.

The remaining places show their category illustration (SPEC §12.6), which is the
designed behaviour and not a gap: for a great many Indian places no freely
licensed photograph exists, and inventing one is not an option.

Names per language, from OpenStreetMap `name:*` tags and Wikidata labels:

| | | | |
|---|---:|---|---:|
| English | 99.5 % | Gujarati | 4.5 % |
| Tamil | 22.4 % | Urdu | 4.3 % |
| Hindi | 17.3 % | Assamese | 2.5 % |
| Bengali | 15.4 % | Sanskrit | 1.5 % |
| Telugu | 12.4 % | Nepali | 1.1 % |
| Malayalam | 11.8 % | Maithili | 1.1 % |
| Punjabi | 8.0 % | Santali | 1.0 % |
| Kannada | 7.5 % | Kashmiri | 0.7 % |
| Odia | 6.8 % | Sindhi | 0.3 % |
| Marathi | 5.0 % | Konkani | 0.2 % |
| | | Manipuri | 0.1 % |
| | | **Dogri, Bodo** | **0 %** |

The weak end of that table is the point of printing it. Two scheduled languages
have no place names at all in the open data, and five more are under 1 %. The
app renders all 23 correctly — the Languages screen is the glyph test — but
*having* a name is a data problem, not a rendering one.

Full table: `results/coverage/latest/coverage.md`.

---

## How it is built

```
backend/app/
  ranking/   wilson.py gems.py trending.py diversity.py    SPEC §9.1–9.3
  deck/      rank.py thompson.py                           SPEC §9.4
  watch/     rank.py views.py                              SPEC §9.5, §9.10
  integrity/ dedupe.py phash.py exif.py fraud.py           SPEC §9.6–9.8
  partner/   attribution.py invalid.py split.py
             eligibility.py run.py                         SPEC §9.9, §10
  kadam.py   the points ledger                             SPEC §10.1
  names.py   which name to show, in which script           SPEC §7.2
frontend/src/
  styles/    tokens.css + components.css, lifted from the design reference
  screens/   the nine screens
  components/
sim/         the simulations above
results/     metrics.json, figures and screenshots
```

Each SPEC §9/§10 algorithm is a small pure function with a docstring that says
what it does and cites its section, and a test named after the acceptance
criterion it satisfies (`test_ac16_shares_always_sum_to_one`).

### The rules the code will not break

1. **Signing in follows NIST SP 800-63B, not folklore.** Passwords are at least
   10 characters, checked against a blocklist of the most common choices, and
   refused if they contain your own name or email — no forced symbols, which
   only produce `Password1!`. They are hashed with argon2id. Sign-in takes an
   email or a handle and gives one error for both a wrong address and a wrong
   password, so it cannot be used to find out who has an account. Eight failures
   lock an account *and* an address out for fifteen minutes, the right password
   included, so a correct guess at the end of a run of wrong ones is no use.
2. **A user's coordinates are never stored.** Check-in sends one position; the
   server turns it into a distance and an accuracy and discards the rest.
   `Visit`, `Pulse` and `Touch` have no coordinate columns, and a test asserts
   that against the table definitions.
3. **Stored photos carry no EXIF** — every image is re-encoded, never copied.
4. **Kadam and earnings exist only as ledger rows.** There is no balance column
   to drift; a balance is `sum(KadamEntry.delta)`.
5. **Fragile places** never return exact coordinates or last-mile directions
   before the user saves and pledges — enforced server-side, tested through the
   API rather than the UI.
6. **Attribution is kept**: OpenStreetMap (ODbL), Wikidata (CC0), Commons
   (author + licence + link per photo, allowlisted licences only), OpenFreeMap.
7. **The frontend talks to no third party** except `tiles.openfreemap.org`.
   Commons photos are proxied and cached by our own server. A Playwright test
   watches every request and fails on anything else.
8. **Maps of India hide international boundary layers** and never draw state or
   country borders (SPEC §14).
9. **The safety card is never hidden**, always shows 112, and nothing in the
   ranking rewards risky content.
10. **A UI language ships only after a native speaker has reviewed it.** English
   is the only one switched on; Hindi and Telugu are listed as *in review* and
   cannot be selected.
11. **Every rupee carries a Simulated label**, checked by a DOM test over the
    whole Studio.

---

## Licences and sources

- Places and geometry from **OpenStreetMap**, © OpenStreetMap contributors, ODbL.
- Famous places from **Wikidata**, CC0 — no attribution required; credited anyway.
- Photos from **Wikimedia Commons**, CC0 / public domain / CC BY / CC BY-SA only,
  each shown with its author, licence and a link to the file page.
- Map tiles from **OpenFreeMap**.
- Nothing is taken from Google Maps. The only Google used is the free
  "Open in Maps" directions link (SPEC §6.6).
- Fonts: Rozha One, Mukta, Kalam, the Anek family and Noto, self-hosted through
  @fontsource with `unicode-range`, so a phone downloads only the scripts on
  screen.
