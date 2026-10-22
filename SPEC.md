# SPEC.md — Truvel (v2)

> *Truvel* (पगडंडी): the narrow footpath that isn't on the map, the one locals
> walk. Working name; check it first (Q1).

This is the source of truth. If code and this file disagree, the code is wrong,
or this file gets updated first and then the code (CLAUDE.md, "Fix the spec, not
the code").

**Deadline: submit 29 October 2026.** The Tier 1 app must be finished and
verified by the end of Day 5 (Sun 25 Oct), the Partner Program engine and
evaluation by Day 6. Everything else is optional or roadmap (§4).

v2 changes: all Indian languages (§7), all-India open data with photos (§6),
Watch feed (§8.3), live Pulse reports (§8.8), creator Partner Program modelled on
YouTube's revenue sharing (§10), Creator Studio (§8.10), new navigation (§8.1).

---

## 1. Goal

A travel + social + creator app for India: discover places to visit, from the
famous to the ones only locals know, and get paid (in a later version) for
helping other people go.

You can:
- Search any Indian city and see its places ranked by how much people liked them,
  with names in your language and the local script.
- Swipe a deck of places near you, or watch short videos of places, each with
  a "Go here" button.
- Open a place to see photos, live conditions ("waterfall flowing, quiet, 2 h
  ago"), what to do, when to go, safety, and **last-mile steps** written by people
  who went.
- Add a place that isn't in the app, or post photos and videos of one. You get
  permanent "Found by" credit, earn **kadam** (points), and as a Partner you'd
  earn a share of revenue based mostly on **how many people actually visit
  because of you**.
- Check in on site to clear the fog on your city map and stamp your passport.

Pitch: *Every city has places Google Maps doesn't know. Truvel is where locals
share them, creators get rewarded for them, and you find them.*

### Not the goal
- Not booking, hotels or tickets.
- Not a general social network: no DMs, no posts that aren't about a place.
- No real money moves in this version. The revenue engine runs on a simulated
  pool and says so on screen (§10.5).

---

## 2. Users

| User | Wants | Truvel gives |
|---|---|---|
| **Weekend explorer** (student, young professional) | Something new within 20–30 km, cheap | Nearby deck, Watch, golden hour, Pulse |
| **Local who knows spots** | Recognition | "Found by", kadam, Local Legend level |
| **Travel creator** | An audience and income | Watch feed, Studio, Partner Program paying for real visits |
| **Visitor new to a city** | Beyond the top 10 list, in their own language | Ranked lists, names in their language, last-mile steps, offline saved places |
| **Cautious traveller** (incl. women travelling alone, families, wheelchair users) | Is it safe and accessible? | Safety & access card, Pulse, accessibility fields |

---

## 3. Landscape and moat

Checked October 2026.

| Existing | What it does | Where Truvel differs |
|---|---|---|
| Google Maps / Local Guides | Points and levels for reviewing places already on Maps | Doesn't find unmapped places; no last-mile steps; no creator income |
| YouTube / Instagram | Creators earn from views (YouTube shares 55 % of ad revenue on long-form and 45 % on Shorts with Partner Program members) | Views reward entertainment, not usefulness; no structure (directions, safety, live conditions) |
| Tripoto | Travel stories; editor-approved posts earn credits (₹4 each) redeemable only on Tripoto packages | Stories, not a verified, ranked, live map of a city |
| Explurger | Indian travel social app with check-ins, points, achievements | Social feed of trips; no verified-visit economy, last-mile steps, fog map or live Pulse |
| Atlas Obscura | User-submitted unusual places, editor-reviewed | Curiosities for tourists; thin everyday coverage in Indian cities |

**Moat (why it could win, honestly):** no app can stop competition; Google could
copy any one feature. What's hard to copy:
1. **Data nobody else has**: verified unmapped places, last-mile steps, live Pulse.
   Each city's data gets better with every visitor (network effect per city).
2. **Money for usefulness**: creators earn from *visits caused*, so the best
   creators bring the best places, not just the best-looking ones.
3. **India-first languages**: every place name in 22 languages and their scripts.
4. **Trust**: verified on site, safety-first, privacy (we never store where users are).

---

## 4. Scope tiers and roadmap

| Tier | Contents | By |
|---|---|---|
| **1 — app (must)** | One city seeded deep from OSM + all-India famous places from Wikidata with Commons photos; place names in all scheduled languages with correct fonts; Explore list + map with fog; Place page with Pulse, last-mile steps, safety & accessibility; accounts, likes, saves, follows; Add place / photos / videos with pHash, dedupe, on-site verification; check-in + dev simulator; Pulse reports; Nearby deck (Thompson sampling); Watch feed; You: passport, kadam, streak; creator profiles; fragile-place rules; design system both themes; English UI with i18n framework | Day 5 (Sun 25 Oct) |
| **1 — engine & evaluation (must)** | Partner Program engine: engaged views, time-decay visit attribution, invalid-traffic rules, simulated pool split, eligibility; Creator Studio; simulations (ranking, bandit, attribution, fraud); pHash robustness; demo data | Day 6 (Mon 26 Oct) |
| **2 — if time** | UI in Hindi + your regional language (native-reviewed); comments; golden hour; Weekly Trail; Trails (playlists); campus clans; admin queue UI; offline saved places (PWA); CLIP auto-tags + image dedupe; Isolation Forest fraud check; IndicXlit names (Colab batch); Wikivoyage listings | Day 7 (Tue 27 Oct) |
| **3 — roadmap (document only)** | Real payouts (KYC, TDS, payment partner); local-business placements and sponsored Trails; Truvel Plus; UPI tips; RTL UI for Urdu/Kashmiri/Sindhi; remaining UI languages with native review; voice stories with Indic speech recognition; day planner and group vote; festival calendar; trip-safety check-out timer; push notifications; video transcoding; native apps | not built |

Cut order if behind (first cut first): Wikivoyage → IndicXlit → CLIP → Isolation
Forest → offline → admin UI → clans → Trails → Weekly Trail → golden hour →
comments → UI translations. **Never cut**: tests for §9 and §10, verification
rules, licence attribution, the "Simulated" labels.

---

## 5. Data model

SQLite via SQLModel. Timestamps UTC in the DB, shown in IST. Money as integer
paise.

```
User          id, username (a-z0-9_ 3–20, unique), email (lowercase, unique),
              password_hash (argon2id), official (bool — the app's own account),
              display_name, bio (≤ 160), avatar_media_id, created_at,
              role ('user'|'admin'), strikes, demo (bool),
              names_mode ('en_local'|'mine_local'|'en'), names_lang (ISO 639),
              ui_lang, home_city_id

City          id, slug, name_en, state, bbox, centre_lat, centre_lng, regional_langs (JSON)
Neighbourhood id, city_id, name, lat, lng

Place         id, city_id (nullable for all-India items outside seeded cities),
              state, lat, lng, radius_m (default 150), category, tags (JSON),
              source ('osm'|'wikidata'|'community'), osm_type, osm_id, wikidata,
              sitelinks (int), fame ('famous'|'known'|'hidden'),
              status ('verified'|'unverified'|'hidden'), fragile, added_by,
              added_remotely, description (≤ 600), best_time (JSON),
              entry_fee_text, timings_text,
              access (JSON: road, walk_min_from_road, nearest_transit_text, parking),
              accessibility (JSON: wheelchair 'yes'|'partly'|'no'|'unknown',
                             steps_count_text, toilets, drinking_water, shade, food_nearby),
              safety (JSON §8.14), activities (JSON), created_at, updated_at

PlaceName     place_id, lang (ISO 639-1/-3: en, hi, te, ta, kn, ml, mr, bn, gu, pa,
              or, as, ur, ks, sd, gom, mai, doi, brx, ne, sa, sat, mni),
              name, source ('osm'|'wikidata'|'user'|'auto'), votes   # unique (place, lang, source)

Media         id, place_id, user_id (nullable for commons), kind ('photo'|'video'),
              path_display, path_thumb, path_poster, width, height, duration_s,
              phash, caption (alt text), lang (caption language),
              source ('upload'|'commons'), licence, attribution, source_url,
              status ('ok'|'hidden'), created_at

LastMileStep  id, place_id, author_id, version_group (uuid), order, text (≤ 140), media_id
LastMileVote  user_id, version_group, helpful (bool)        # one per user per version
Like(user, place) · Save(user, place) · View(user, place, first_seen_at)
Follow        follower_id, creator_id, created_at
MediaLike     user_id, media_id
MediaView     id, user_id, media_id, started_at, watched_s, completed (bool),
              engaged (bool), invalid_reason (nullable)   # §9.10
Swipe         user_id, place_id, action, at
CategoryPref  user_id, category, alpha, beta
Visit         id, user_id, place_id, at, distance_m, accuracy_m, verified, flag,
              simulated                       # never raw coordinates
Pulse         id, place_id, user_id, at, water, crowd, path, open, note (≤ 80),
              media_id, visit_id               # §8.8
Touch         user_id, place_id, creator_id, content_type ('place'|'video'|'photo'|'steps'),
              content_id, at                   # engagement used for attribution §9.9
Attribution   visit_id, creator_id, share (float 0–1)
KadamEntry    id, user_id, delta, reason, ref_type, ref_id, at
EarningPeriod id, month, pool_paise, simulated (bool), status
EarningLine   period_id, creator_id, score, share, amount_paise, eligible (bool)
Report        id, reporter_id, target_type, target_id, reason, note, status, at
Session       id (hashed), user_id, created_at, expires_at
```

Invariants (tested): `likes ≤ viewers`; no self-likes/visits/attribution;
kadam and earnings only via ledgers; `Σ Attribution.share = 1` per attributed
visit; `Visit` and `Pulse` have no coordinate columns.

---

## 6. Data sources

### 6.1 OpenStreetMap — deep, one city (Tier 1)
`python -m scripts.seed_osm --city <slug>`: Overpass queries within the city
bbox for the category tags below, named features only, `out center` for
ways/relations, cached to `data/osm/` (gitignored). ODbL: show "© OpenStreetMap
contributors" on maps and seeded places. Also import `place=suburb|neighbourhood`
nodes, and every `name:<lang>` tag into `PlaceName` (source `osm`).

| Category | OSM tags |
|---|---|
| `viewpoint` | tourism=viewpoint |
| `waterfall` | waterway=waterfall, natural=waterfall |
| `lake` | natural=water + water=lake/reservoir **and** (tourism=* or wikidata) |
| `hill_trek` | natural=peak, named natural=rock |
| `fort_heritage` | historic=fort/castle/ruins/monument/archaeological_site/tomb |
| `temple_sacred` | amenity=place_of_worship **only with** tourism=attraction or wikidata |
| `park_garden` | leisure=park/garden/nature_reserve **with** area ≥ 2 ha or wikidata |
| `museum_art` | tourism=museum/gallery/artwork |
| `market_street` | tourism=attraction + (amenity=marketplace or highway=pedestrian) |
| `beach_river` | natural=beach, ghats (man_made=ghat or tourism on riverbanks) |
| `other` | tourism=attraction not matched above |

### 6.2 Wikidata — famous places across all of India (Tier 1)
`python -m scripts.seed_wikidata`: SPARQL on query.wikidata.org (licence **CC0**,
no attribution required, but we credit it). Items with country India (`P17 wd:Q668`),
coordinates (`P625`), and instance of (`P31`) one of the classes in config. Start
with: tourist attraction Q570116, museum Q33506, waterfall Q34038, lake Q23397,
mountain Q8502, beach Q40080, park Q22698, national park Q46169, nature reserve
Q179049, garden Q1107656, castle Q23413, fortification Q57821, temple Q44539,
monument Q4989906, archaeological site Q839954, cave Q35509. **Phase 1 verifies
each QID in the query service and adds missing classes** (Hindu temple, mosque,
church, gurdwara, stepwell, ghat, dargah, step-well, palace…). One query per
class to stay under the 60 s timeout; send a descriptive User-Agent.

Fetch per item: labels in `en` + all 22 language codes (§7.1) → `PlaceName`
(source `wikidata`); `P18` image filename; sitelink count; Wikivoyage sitelink;
`P1435` heritage designation; and the **state**: follow `P131*` (located in the
administrative entity, any depth) to an item that is a state or union territory of
India (QIDs verified in Phase 1). Merge with OSM by `wikidata` tag, else by §9.6
dedupe rules. OSM-seeded places take the state of their configured city. No
boundary files are needed.

Report the counts in PLAN.md "Measured values". Don't guess them.

### 6.3 Wikimedia Commons — photos (Tier 1)
For places with a `P18` image: on first view, the server fetches a 1200 px
thumbnail via the Commons API (`prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=1200`),
stores it locally with `Artist`, `LicenseShortName`, `LicenseUrl` and the file
page URL, and serves it from our own origin. Licence allowlist: CC0, Public
domain, CC BY (any version), CC BY-SA (any version). Anything else: don't store,
use the illustration. Every Commons photo shows "Photo: <author> · <licence> ·
Wikimedia Commons" linked to the file page. Rate: ≤ 2 requests/second.

### 6.4 Wikivoyage (Tier 2)
"See"/"Do" listings for Indian destinations from the dump: description, hours,
price. **CC BY-SA 4.0**: show "From Wikivoyage, CC BY-SA" with a link, and keep
any edited text under the same licence.

### 6.5 Government open data (Tier 3)
ASI centrally protected monuments and state tourism lists from data.gov.in under
the Government Open Data Licence – India. Check each dataset's terms first.

### 6.6 Google Maps: not a data source
We do **not** copy places, photos, reviews or ratings from Google Maps:
- Scraping is against Google's terms, and the photos and reviews belong to their
  authors.
- Google's Places API terms (checked Oct 2026) forbid using Places content with a
  non-Google map, allow caching coordinates for 30 days at most, and the API is
  paid beyond free usage limits.
Allowed and used: the free "Open in Google Maps" directions link (§8.5).

### 6.7 Fame (input to Hidden gems §9.2)
- `famous`: Wikidata sitelinks ≥ 15 (config), or OSM item with a Wikipedia link.
- `known`: in OSM or Wikidata otherwise.
- `hidden`: community-added and not in OSM/Wikidata at add time.

---

## 7. Languages and scripts

### 7.1 Supported languages
All 22 languages of the Eighth Schedule plus English.

| Code | Language | Autonym | Script | Font |
|---|---|---|---|---|
| en | English | English | Latin | Mukta |
| hi | Hindi | हिन्दी | Devanagari | Mukta |
| mr | Marathi | मराठी | Devanagari | Mukta |
| ne | Nepali | नेपाली | Devanagari | Mukta |
| sa | Sanskrit | संस्कृतम् | Devanagari | Mukta |
| gom | Konkani | कोंकणी | Devanagari | Mukta |
| mai | Maithili | मैथिली | Devanagari | Mukta |
| doi | Dogri | डोगरी | Devanagari | Mukta |
| brx | Bodo | बर’ | Devanagari | Mukta |
| bn | Bengali | বাংলা | Bengali | Anek Bangla |
| as | Assamese | অসমীয়া | Bengali–Assamese | Anek Bangla |
| gu | Gujarati | ગુજરાતી | Gujarati | Anek Gujarati |
| pa | Punjabi | ਪੰਜਾਬੀ | Gurmukhi | Anek Gurmukhi |
| or | Odia | ଓଡ଼ିଆ | Odia | Anek Odia |
| te | Telugu | తెలుగు | Telugu | Anek Telugu |
| ta | Tamil | தமிழ் | Tamil | Anek Tamil |
| kn | Kannada | ಕನ್ನಡ | Kannada | Anek Kannada |
| ml | Malayalam | മലയാളം | Malayalam | Anek Malayalam |
| ur | Urdu | اردو | Perso-Arabic (Nastaliq) | Noto Nastaliq Urdu |
| ks | Kashmiri | كٲشُر | Perso-Arabic | Noto Nastaliq Urdu |
| sd | Sindhi | سنڌي | Perso-Arabic (Naskh) | Noto Naskh Arabic |
| sat | Santali | ᱥᱟᱱᱛᱟᱲᱤ | Ol Chiki | Noto Sans Ol Chiki |
| mni | Manipuri | ꯃꯤꯇꯩꯂꯣꯟ | Meetei Mayek | Noto Sans Meetei Mayek |

Fonts are self-hosted via @fontsource with `unicode-range`, so a phone only
downloads a script's font when that script appears on screen.

### 7.2 Place names: sources and display
Sources, best first: `user` names with ≥ 3 votes → `osm` → `wikidata` → `user`
(fewer votes) → `auto` (Tier 2 transliteration, §9.12, shown with a small "auto"
tag).

Every place has a **regional language**: from `state` via the config map
(Telangana → te, ur · Tamil Nadu → ta · Kerala → ml · Karnataka → kn · Maharashtra
→ mr · Gujarat → gu · Punjab → pa · Odisha → or · West Bengal → bn · Assam → as ·
Manipur → mni · J&K → ur, ks · Goa → gom · Bihar → hi, mai · Jharkhand → hi, sat ·
Sikkim → ne · …; full table in config).

Display per user setting `names_mode`:
- `en_local` (default): line 1 English; line 2 regional-language name.
- `mine_local`: line 1 in `names_lang` (fall back to English); line 2 regional
  name if different from line 1's language.
- `en`: English only.
Never more than 2 lines. Every name element has the right `lang` attribute, and
Perso-Arabic names are wrapped in `<bdi dir="rtl">`.

Anyone with a verified visit can **add a name in their language** for a place
(moderated; others vote it up).

### 7.3 UI language
- i18next; strings in `frontend/src/i18n/<code>.json`; English complete in Tier 1.
- Tier 2: Hindi and your regional language, **reviewed by a native speaker**
  before they're enabled.
- Machine-drafted translations may exist only behind a "Beta" label and are never
  presented as reviewed (CLAUDE.md invariant 11).
- Numbers use Indian grouping (`Intl.NumberFormat('en-IN')`: 1,00,000); distances km;
  dates "20 Oct 2026".
- Full right-to-left UI for Urdu/Kashmiri/Sindhi is Tier 3; names render RTL
  correctly from Tier 1.

### 7.4 Search across scripts
Search covers all `PlaceName` rows (FTS5). Tier 2: also index a Latin
romanisation of each Indic name (indic-transliteration library), so "golkonda",
"Golconda" and "గోల్కొండ" all find the fort.

---

## 8. Features

### 8.1 Navigation
Bottom bar: **Nearby · Watch · (+) · Explore · You**. App opens on Nearby.
- (+) opens a sheet: *A new place* · *Photos or a video of a place* · *How is it
  right now?* (Pulse; on-site only).
- Explore has a **List | Map** switch.
- You has **Passport | Studio**, with Settings (languages, theme, account) behind
  a gear.

### 8.2 Nearby (the deck)
- Full-bleed stacked cards, one at a time, next card peeking below.
- **Swipe right = Save** ("Want to go"), **left = Skip**, **tap or swipe up = Open**.
  Three buttons under the card do the same (required, §13).
- Radius chips 5 / 10 / 25 km (default 10). Ranking §9.4.
- **The deck ends**: after the last candidate, an end card: "That's everything
  within 10 km. Widen to 25 km, or go see one you saved?" No infinite feed.
- Location denied → use the city centre and say so.
Card shows: photo/muted video, name (per §7.2), distance and time
(`haversine × 1.3 ÷ 20 km/h`, e.g. 6.2 km → ~24 min by bike), category, ♥ count,
"Found by", the best local tip (Kalam), and a **Live** pill if a Pulse is ≤ 6 h old.

### 8.3 Watch
- Full-screen vertical videos (and photo sets) of places. Tabs: **For you ·
  Nearby · Following**.
- Overlay: creator (avatar, handle, Follow), place name (§7.2), area and
  distance, caption (with its language), Live pill, and a **Go here** button that
  opens the place.
- Right rail: ♥ like, comments (Tier 2), ☆ save place, ↗ share.
- Muted autoplay, tap for sound; `navigator.connection.saveData` → poster + tap to
  play.
- Ranking §9.5. Swipe up/down for next/previous; arrow keys and buttons too.
- After 20 minutes of watching in one session, a dismissible card: "You've
  watched 20 min. *Sunset ridge* (saved) is 3 km away and the sun sets at 5:52."
  The habit we build is going out.
- View tracking per §9.10 (engaged view, completion).

### 8.4 Explore
**List**: search (cities, areas, places, any script); city header with names;
sort tabs **Top · Most liked · Hidden gems · Trending · Nearest** (§9.1–9.3);
ⓘ line explaining Top; category chips; "Verified only" toggle; rows with
thumbnail, names, category · area, ♥, visits this month, distance, badges (Hidden
gem, Trending, Live).
**Map**: MapLibre with OpenFreeMap tiles restyled to our tokens; **international
boundary layers hidden** (§14); pins by category, clusters; zooming out shows
all-India famous places. **Fog**: your verified visits clear 1 km circles (turf
union, subtract from the city bbox; dashed marigold rim); headline "12 of 87
neighbourhoods explored" (nearest neighbourhood node = Voronoi membership). Bottom
sheet lists places in view.

### 8.5 Place page
1. Media carousel (uploads + Commons, with attribution), counter, video count.
2. Names (§7.2) with "Add a name in your language"; category · area.
3. Like, Save, Share, Report.
4. **Pulse strip** (§8.8) if any report ≤ 48 h old.
5. Stats: verified visits, this month, Found by / From OpenStreetMap / From Wikidata.
6. Unverified banner if applicable.
7. Description; What to do chips.
8. When to go.
9. Getting there: **Open in Maps** (`https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>`),
   OpenStreetMap link, access rows, **Last-mile steps** (best version by Wilson
   score of helpful votes; other versions; helpful 👍/👎).
10. **Safety & access** card (§8.14), always open.
11. **Accessibility**: wheelchair, steps, toilets, water, shade, food nearby.
12. Fees & timings.
13. Videos of this place (horizontal strip → Watch).
14. Nearby places.
15. Attribution footer.
Pinned bottom bar: distance + **Check in** (enabled within radius).

### 8.6 Add
Three entry points from (+):
- **A new place**, three steps on a dashed progress path:
  1. *Photos & videos*: 1–10 photos, up to 2 videos; each needs a caption (alt text,
     prefilled "Photo of <name> by <user>").
  2. *Pin & verify*: map centred on you, pin draggable ≤ 300 m. Within 300 m with
     accuracy ≤ 100 m → "You're here · on-site add". Otherwise "Adding from
     elsewhere: stays Unverified until 2 people check in". **Duplicate check**
     (§9.6) runs as the pin moves: "Is it one of these?" → "Yes, add my photos
     there" / "No, it's a different place".
  3. *Details*: name (+ names in any language), category, description, what to do,
     best time, access, accessibility, all safety questions (yes / no / don't
     know), fees/timings, optional first last-mile steps, "This place is fragile".
  Submit → `unverified`: "You'll get 50 kadam when 2 people confirm it." Content
  rules shown before the first add: no private property or trespassing, no homes,
  strangers' faces not the subject, no stunts at edges.
- **Photos or a video of a place**: pick place (nearest first), upload. Videos
  ≤ 60 s, ≤ 60 MB, vertical recommended; caption ≤ 150 chars with language picker;
  on-site uploads get a "Shot here" badge.
- **How is it right now?**: Pulse form (§8.8).
Client: EXIF read (exifr) before resizing photos to ≤ 2048 px JPEG q0.82; video
duration check and poster frame at 1 s.

### 8.7 Check-in and verification
- "Check in" calls `navigator.geolocation.getCurrentPosition({enableHighAccuracy:
  true, timeout: 15000, maximumAge: 0})` once and sends `{lat, lng, accuracy}`. The
  server stores only `distance_m`, `accuracy_m`, `verified`, `flag`; coordinates are
  discarded after the request and never logged.
- Verified when `distance_m ≤ max(place.radius_m, 150)` and `accuracy_m ≤ 100`.
  Poor accuracy → "Your phone isn't sure where you are (±240 m). Step into open sky
  and try again." Too far → "You're 1.4 km away. Check in when you get there."
- One verified visit per user per place per day; only the first ever earns kadam.
- Impossible travel (§9.8) flags a visit: no kadam, no place verification, no
  attribution.
- Geolocation needs HTTPS: `localhost` on the laptop; the phone uses the dev
  certificate (`@vitejs/plugin-basic-ssl`).
- **Dev location simulator** (viva demo only): shown only when the frontend is
  built with `VITE_DEV_TOOLS=1` **and** the server runs with
  `DEV_ALLOW_FAKE_LOCATION=1`. Visits are `simulated=true`, show "SIM", and are
  excluded from metrics, attribution and earnings.
After a successful check-in: stamp animation, fog clears, then a one-tap Pulse prompt.

### 8.8 Pulse (live conditions)
- Only from users with a verified (not simulated, unflagged) visit to that place
  within the last 2 hours.
- Fields (each optional): `water` flowing / low / dry (water categories only);
  `crowd` quiet / busy / packed; `path` dry / muddy / flooded / closed; `open`
  yes / closed today; `note` ≤ 80 chars; one photo.
- Freshness: **Live** ≤ 6 h, **Recent** ≤ 48 h, hidden after 7 days.
- Summary per field = latest report, unless ≥ 2 reports in the last 6 h disagree →
  majority with "mixed reports".
- Shown on the deck card (Live pill), the Watch overlay, Explore rows (Live badge)
  and the Place strip.
- +3 kadam per Pulse (max 5 per day). Pulse photos count as content for the
  Partner Program.

### 8.9 You — Passport and profile
Passport:
- Header: name, level, kadam balance, progress to next level (dashed trail bar).
- Cards: **weekly streak** (weeks in a row with ≥ 1 verified visit; one automatic
  "rain check" per calendar month), places found (+ visits caused), stamps (+
  neighbourhoods explored).
- Tabs: **Stamps** (one per first verified visit, coloured by category, dated,
  slightly rotated like ink; an empty "Next stamp" outline), **Found by me**,
  **Want to go** (saved, nearest first), **Kadam** (ledger with reasons).
Public creator profile: avatar, bio, followers, places found, videos grid, visits
caused (lifetime), Partner badge.

### 8.10 Creator Studio
- Period: 7 / 28 / 90 days.
- Banner (always, this version): "Simulated earnings — no real money is paid in
  this version."
- Metric cards with 28-day sparkline: **Engaged views**, **Watch time (h)**,
  **Visits caused** (1 decimal; fractional attribution §9.9), **Estimated
  earnings** (₹, labelled Simulated).
- **Partner Program progress** (§10.4) as a checklist with progress bars.
- **Top content** table: item, engaged views, average % watched, visits caused.
- **Audience**: top cities and the languages viewers use.
- "How earnings are split" sheet explaining §10.3 in plain words.

### 8.11 Social
Tier 1: follow/unfollow, Following tab, creator profiles, share links.
Tier 2: comments on videos and places (≤ 300 chars; report; 3 reports from verified
users auto-hide pending review; keyword filter list in config).

### 8.12 Golden hour, Weekly Trail, Trails, Clans (Tier 2)
- Golden hour (suncalc): banner on Nearby and Watch, filters to `sunset`/`sunrise` places.
- Weekly Trail: 3 places per city each Monday (top unvisited, best hidden gem, best
  new); all 3 → stamp + 50 kadam.
- Trails: user-made ordered lists ("Monsoon falls near Hyderabad"); "Do this trail"
  → stamp when all visited.
- Clans: join your college; clan leaderboard by neighbourhoods explored per month.

### 8.13 Moderation and reports
- Report reasons: wrong location, private property, unsafe, offensive, stolen photo,
  photo of me, spam, duplicate, other.
- 3 reports from different users with verified visits auto-hide a photo, video,
  step version or comment pending review; "photo of me" hides immediately.
  Places are never auto-hidden; they go to the admin queue.
- Admin (`/admin`, Tier 2 UI; API Tier 1): approve, hide, merge duplicates (moves
  media, likes, visits, names to the target), strikes (3 → can't post).
- Removed content reverses the kadam **and** earnings it produced.

### 8.14 Safety, access and fragile places
Every place answers (yes / no / don't know), shown as a card with icons and words:
`steep_edge` (cliffs, drops), `water_danger` ("No swimming"), `slippery_in_monsoon`,
`no_mobile_signal`, `isolated` ("Better in a group"), `wildlife`, `permit_needed`,
`sacred` (dress/footwear rules), `women_safety_note` (moderated free text).
The card always shows India's emergency number **112** and "Share your trip"
(copies the place name + Maps link to send to a friend). `steep_edge` places say
"Stay back from the edge. No photo is worth it." Nothing rewards risky content:
videos of `steep_edge`/`water_danger` places get no Watch boost and a safety
overlay. **Fragile places** show only the
area until the user saves and pledges; excluded from Trending, Watch "For you" and
Weekly Trail; videos of fragile places blur the location line.

---

## 9. Algorithms

Pure functions in `backend/app/{ranking,deck,watch,integrity,partner}/` with unit
tests. Constants in `config.yaml` (§16).

### 9.1 Top: Wilson lower bound
For `k` likes from `n` distinct viewers, `p̂ = k/n`, `z = 1.96`:
```
wilson_lb(k, n) = 0                                                   if n = 0
                = ( p̂ + z²/(2n) − z·√( p̂(1−p̂)/n + z²/(4n²) ) ) / (1 + z²/n)
```
Test values: `(0,0)=0`, `(1,1)≈0.2065`, `(80,100)≈0.7112`, `(8,10)≈0.4902`.

### 9.2 Hidden gems
`gem = wilson_lb(likes, viewers) × {hidden 1.0, known 0.7, famous 0.3}[fame]`;
verified, non-fragile, ≥ 1 verified visit.

### 9.3 Trending
`Σ w · 2^(−age_days/7)` over likes (w = 1), verified visits (w = 3) and Pulse
reports (w = 1) in the last 30 days.

### 9.4 Nearby deck: score + Thompson sampling
Candidates: verified places (plus unverified within 5 km, marked) within radius R,
excluding places the user saved, visited, or swiped in the last 14 days.
```
q      = percentile rank of wilson_lb among candidates            ∈ [0,1]
prox   = exp(−d_km / 4)
pref   = θ_c,  θ_c ~ Beta(α_c, β_c), one draw per category per request
fresh  = 1 if added ≤ 14 days ago or viewers < 10, else 0
score  = 0.40·q + 0.25·prox + 0.25·pref + 0.10·fresh
```
- `CategoryPref` starts at α = 1, β = 1 (no assumption). Save → α+1; skip → β+1;
  open → no change.
- Drawing θ instead of using the mean is Thompson sampling: rarely seen categories
  still sometimes draw high (exploration); consistently saved ones rise
  (exploitation).
- Diversity re-rank: never 3 of the same category in a row. Page of 30.
- RNG seeded per request `(user_id, date, request_no)` so tests can reproduce a deck.

### 9.5 Watch ranking
Candidates: verified-place videos; For you = within 100 km first, then all India.
```
quality   = percentile of wilson_lb(completions, engaged_views) among candidates
prox      = exp(−d / 25 km)        (Nearby tab: d ≤ 25 km only)
pref      = θ_c (same CategoryPref as the deck; like = α+1, skip within 2 s = β+1)
fresh     = exp(−age_days / 5)
following = 1 if you follow the creator
score     = 0.35·quality + 0.20·prox + 0.20·pref + 0.15·fresh + 0.10·following
```
Re-rank: ≤ 2 in a row from one creator; ≤ 3 in a row from one category.
Following tab: newest first.

### 9.6 Duplicate places
When a pin is placed (and again on submit), candidates = places within 300 m.
Likely duplicate if:
```
distance ≤ 300 m and name_sim ≥ 80
or distance ≤ 100 m and same category
or (Tier 2) distance ≤ 300 m and max CLIP cosine(new photos, candidate photos) ≥ 0.90
```
`name_sim` = rapidfuzz `token_set_ratio` between the new name and **every** name of
the candidate (all languages; take the max), after normalising: lowercase, strip
punctuation, drop generic words from the per-language list in config (e.g. lake /
cheruvu / talab / eri / kere; temple / gudi / mandir / kovil; hill / gutta / konda;
point; view). Show up to 3 candidates; the user decides.

### 9.7 Photo integrity
- `imagehash.phash` (64 bit) for every photo and video poster; compare with all
  stored hashes (BK-tree if slow). Hamming ≤ 8: another user's existing photo →
  reject "This photo is already on Truvel"; same user, same place → skip silently.
- EXIF GPS (read on the client before resizing) > 2 km from the pin → warn and
  flag `gps_mismatch` for review. Absent EXIF is normal (Android's photo picker
  strips location), so it's never required.
- Stored files never contain EXIF: re-encode with Pillow (display 1200 px, thumb
  400 px, JPEG q85).

### 9.8 Visit fraud rules
- **Impossible travel**: consecutive visits A→B with `haversine(A,B) / hours > 120
  km/h` → B flagged `speed`.
- New accounts (< 24 h) earn no kadam from likes given or received.
- No self-dealing: likes, visits, views and attribution on your own content earn
  you nothing.
- Rate limits per user: 20 uploads/hour, 300 likes/hour, 10 check-in attempts/hour,
  10 Pulse/hour.
- A place's discovery reward is paid only when it reaches `verified` through 2
  visits by 2 different users, neither the discoverer, both unflagged.

### 9.9 Visit attribution (who caused this visit?)
When user U makes a **first** verified, unflagged, non-simulated visit to place P:
1. Collect U's `Touch` rows for P in the 30 days before the visit: place-page views
   (creator = discoverer), engaged video views (creator = uploader), last-mile steps
   read for ≥ 10 s (creator = author), deck saves (creator = owner of the card's
   lead photo or the discoverer).
2. Drop touches where creator = U, and invalid ones (§9.10).
3. Weight each touch `w = 2^(−age_days / 7)`; sum weights per creator; normalise so
   shares sum to 1. Store `Attribution(visit, creator, share)`.
4. No touches → organic visit, no attribution.
"Visits caused" for a creator = Σ shares. Why time-decay: the content seen
closest to the decision probably mattered most, but earlier content still helped.
Compared in simulation with last-touch and linear (§17, item 3).

### 9.10 Engaged views and invalid traffic
- **Engaged view**: watched ≥ 3 s (or ≥ 50 % of a video shorter than 6 s).
  **Completion**: ≥ 90 % watched.
- Rules (Tier 1). A view is invalid if: the viewer is the creator; the viewer's
  account is < 24 h old; it repeats the same user + same item within 24 h (count
  once); or it comes from a session flagged by the dev simulator.
- **Velocity hold**: if an item's engaged views in an hour exceed
  `mean + 4·sd` of its trailing 7-day hourly counts **and** > 50, the excess is
  held for review and excluded from earnings.
- Visits used for attribution must be verified, unflagged, non-simulated.
- Tier 2: Isolation Forest (scikit-learn) on creator-day features (views, unique
  viewers, avg % watched, share of new accounts, visits per 1,000 views, share of
  views from one network/device fingerprint hash) → anomalies to the admin queue.

### 9.11 CLIP auto-tags (Tier 2)
`open_clip` ViT-B-32 (`laion2b_s34b_b79k`) on CPU. Zero-shot over prompts "a photo
of a {waterfall, viewpoint at sunset, lake, fort ruins, temple, hill with rocks,
park, street market, beach, street art, stepwell}"; suggest the top category if
probability ≥ 0.5 (user confirms). Store embeddings (float16) for §9.6.

### 9.12 Transliteration (Tier 2)
Run AI4Bharat **IndicXlit** (MIT licence; English → 21 Indic languages) in a
Colab/Kaggle notebook as a batch over place names missing a language, export
CSV, import as `PlaceName(source='auto')`. Not installed on the laptop. Dogri and
Santali aren't covered by IndicXlit: no auto names for them.

---

## 10. Rewards and the Partner Program

### 10.1 Kadam (points, everyone)
| Reason | Kadam | Caps |
|---|---|---|
| discovery (your place verified) | +50 | once per place |
| visit_caused (per whole visit; fractional shares summed daily, rounded) | +10 | 20 per place per day |
| like_received | +1 | 50 per day |
| own_visit | +5 | once per place |
| steps_helpful | +2 | 20 per day |
| pulse | +3 | 5 per day |
| weekly_trail (T2) | +50 | once per week |
| reversal | −earned | + strike |

Levels: Wanderer 0 · Pathfinder 200 · Trailblazer 800 · Local Legend 2,500.

### 10.2 Where money would come from (Tier 3, designed)
1. **Local placements**: businesses near places (chai stall at a trailhead, a
   homestay) appear in "Food & stay nearby" and pay per verified visit or redeemed
   offer.
2. **Sponsored cards**: clearly labelled, at most 1 in 15 cards in Watch/Nearby.
3. **Sponsored Trails** by tourism boards or brands.
4. **Truvel Plus**: offline packs, no sponsored cards.

### 10.3 Pool and split (Tier 1 engine, simulated pool)
- Monthly **creator pool = 55 % of net revenue** (config; same share YouTube gives
  long-form creators).
- Each eligible creator's score for the month (after §9.10 filtering):
  ```
  score = 1 × engaged_views + 25 × visits_caused + 5 × helpful_votes_on_steps
        + 2 × pulse_reports_confirmed_by_a_later_report
  ```
- `amount = pool × score / Σ scores` (eligible creators only), in paise, rounded
  down; remainder stays in the pool. Stored as `EarningLine`.
- Why 25: a real visit is the outcome the app exists for; tune in config. Views
  still count so video creators aren't shut out.

### 10.4 Partner eligibility (config)
- Account ≥ 30 days, no active strikes.
- ≥ 10 pieces of verified content (places that reached verified, or videos/photos
  of verified places).
- In the last 90 days: **≥ 300 visits caused** or **≥ 1,00,000 engaged views**.
- Payout (Tier 3): identity and bank verification, tax deduction as required by
  law, minimum ₹1,000, monthly statements.

### 10.5 What's simulated in this version
- The pool is `partner.demo_pool_inr` from config. No ads are served, no payments.
- Every rupee figure in the UI carries a **Simulated** label, and Studio shows the
  banner. Tested (AC-23).

### 10.6 Why this design
- Paying for views alone pays for entertainment; paying for visits pays for
  usefulness, and visits are hard to fake (you have to physically go).
- Thresholds and caps keep fake accounts from farming small amounts.

---

**Ties.** Before anyone has liked anything, every place scores the same on
every sort. Order then falls back to Wikidata `sitelinks` (how many Wikipedias
describe the place), then id — a real signal about the place rather than
invented engagement, and stable between requests. Once there is a single like,
the ranking function decides and the tiebreak is never reached.

## 11. API

FastAPI under `/api`; cookie sessions (`HttpOnly`, `SameSite=Lax`, `Secure` on HTTPS);
mutating requests need `X-Requested-With: truvel`. Errors:
`{"error": {"code", "message", "detail"}}`.

**Accounts.** An account is an email address, a handle (`a-z0-9_`, 3–20) and a
password. The email is how an account is recovered and how a person can be told
they have been reported; the handle is what other people see. Sign-in accepts
either. Passwords follow NIST SP 800-63B: at least **8 characters**, at most
128, checked against a blocklist of the most common choices, and refused if they
contain the account's own name or email — no forced symbols, which only produce
`Password1!`. Failed sign-ins are counted per account **and** per address, and
refused for 15 minutes after 8 failures, so a correct guess at the end of a run
of wrong ones does not get through either.

**The official account.** Imported places are *posted by* `@truvel`
(`User.official`), not found by a person. It is a publisher: `kadam.award()` pays
it nothing, touches are never credited to it, it is left out of the Partner
Program and Studio rankings, and its place pages say "Posted by" instead of
"Found by". The Hidden gems tab (§9.2) lists, after places that have earned a
place through verified visits, little-known places (`fame = hidden`, no Wikidata
item) that have a credited photograph, so the tab is not empty before anyone has
visited anything; those are labelled as not yet visited.

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | `{email, username, password, display_name}`; argon2id |
| POST | `/auth/login` | `{identifier, password}` — email **or** handle; generic error; throttled |
| POST | `/auth/logout` | |
| POST | `/auth/forgot` · `/auth/reset` | `{email}` always answers the same; `{token, password}` — link valid 1 hour, once; ends every other session |
| GET | `/me` | user, balance, level, streak |
| GET | `/cities` · `/search?q=` | FTS5 over all PlaceName rows |
| GET | `/cities/{slug}/places?sort=top\|liked\|gems\|trending\|near&cat=&verified=1&lat=&lng=&page=` | 20 per page |
| GET | `/places/{id}` | records View; fragile rules applied server-side |
| POST | `/places` · `/places/candidates` | create; duplicate candidates (§9.6) |
| POST | `/places/{id}/media` | multipart photo/video (+poster); pHash |
| POST/DELETE | `/places/{id}/like` · `/places/{id}/save` | |
| POST | `/places/{id}/checkin` | `{lat,lng,accuracy}` → result; coordinates not stored |
| POST | `/places/{id}/fragile-pledge` | unlocks pin and steps |
| GET/POST | `/places/{id}/steps` · `/steps/{group}/vote` | |
| GET | `/deck?lat=&lng=&radius_km=` · POST `/deck/swipe` | §9.4 |
| GET | `/me/passport` · `/me/kadam` · `/me/fog?city=` | |
| POST | `/reports` · GET/POST `/admin/queue` · `/admin/actions` | |
| POST | `/dev/teleport` | 404 unless `DEV_ALLOW_FAKE_LOCATION=1` |
| GET/PATCH | `/me/settings` | names_mode, names_lang, ui_lang, theme |
| GET | `/places/{id}/names` · POST `/places/{id}/names` | add/vote names (verified visitors) |
| GET | `/watch?tab=foryou\|nearby\|following&lat=&lng=&cursor=` | §9.5 |
| POST | `/watch/{media_id}/view` | `{watched_s, duration_s}` heartbeat on leave; server decides engaged/completed |
| POST/DELETE | `/media/{id}/like` | |
| DELETE | `/media/{id}` | your own upload (or an admin); removes the files. Kadam already earned stays in the ledger |
| POST/DELETE | `/users/{id}/follow` · GET `/users/{handle}` | profile |
| POST | `/places/{id}/pulse` · GET `/places/{id}/pulse` | §8.8 |
| POST | `/touch` | `{place_id, content_type, content_id}`; server sets creator and time |
| GET | `/studio?period=28` | metrics, partner progress, top content, audience |
| POST | `/admin/partner/run?month=` | computes attribution summary, filters, EarningLines (admin) |
| GET | `/media/commons/{id}` | serves cached Commons thumbnail |

Media served from `/media/...` with HTTP Range support (video seeking on iOS Safari; tested).

---

## 12. Design system

Visual source of truth: `docs/design-reference.html` (9 screens, both themes).

### 12.1 Concept: "the field notebook and the painted signboard"
An explorer's notebook (paper, dashed trails, ink stamps, handwritten tips) meets
the hand-painted signboards and railway posters of Indian towns (bold display type,
flat layered landscapes, laterite and marigold). Photos and videos are the hero.
Signature motif: the **dashed footpath**: progress in Add, last-mile route, fog
edge, Partner progress, logo. Watch is the one dark, immersive surface in both
themes.

### 12.2 Colour tokens (contrast checked, WCAG 2.2)
| Token | Light | Dark | Use |
|---|---|---|---|
| `paper` | `#F6F1E7` | `#111512` | Page background |
| `surface` | `#FFFCF6` | `#1A201C` | Cards, sheets |
| `ink` | `#1D2420` | `#EEE9DE` | Text (14.1:1 / 15.2:1) |
| `inkMuted` | `#5A635D` | `#A9B1AA` | Secondary text (5.5:1 / 8.4:1) |
| `line` | `#E2D9C8` | `#2D3530` | Dividers (decorative) |
| `laterite` | `#A8401C` | `#F08B63` | Brand, primary buttons, ♥ (5.5:1 / 7.5:1) |
| `marigold` | `#E9A21B` | `#F3B843` | Trails, saved, highlights. Light: fill only; text on it = `#1D2420` (7.3:1) |
| `moss` | `#2E6A4E` | `#6CC495` | Verified, live, success (5.7:1 / 8.7:1) |
| `lake` | `#25627F` | `#6FB3D6` | Water, links, focus (6.0:1 / 8.0:1) |
| `danger` | `#A3263A` | `#F2848F` | Safety, errors (6.4:1 / 7.4:1) |
| `fog` | `rgba(196,190,176,.62)` + 10 % ink hatch | `rgba(4,6,5,.68)` + 7 % hatch | Map fog |
| `scrim` | `linear-gradient(transparent, rgba(10,12,10,.85))` | same | Text on photos/video: `#FFFFFF` |
On-primary text: `#FFFCF6` (light) / `#111512` (dark). "Simulated" labels use
`marigold` fill with `#1D2420` text.

### 12.3 Type
- **Rozha One** (display: names on cards, titles, big numbers), ≥ 22 px.
- **Mukta** 400–700 (UI, Latin + Devanagari), body 16/1.5.
- **Kalam** (handwritten tips and last-mile steps only).
- **Indic scripts** per §7.1 (Anek family for 8 scripts; Noto for Perso-Arabic, Ol
  Chiki, Meetei Mayek). One font stack lists them all after Mukta, so each script
  picks its font automatically; `:lang(sd)` switches to Naskh.
- `font-variant-numeric: tabular-nums` for stats, money, ledgers.

### 12.4 Shape, space, elevation
4 px grid; 16 px screen gutters. Radii: cards 20, sheets 24 (top), chips 999,
buttons 14, thumbnails 12. Elevation only for the deck, sheets and map overlays:
`0 12px 32px -12px rgba(29,36,32,.35)` (dark `rgba(0,0,0,.6)`). Paper grain (inline
SVG noise, 3 %) on `paper` only. Photos 4:5 on deck cards, 9:16 in Watch, ~4:3 in
the place carousel, 1:1 thumbnails.

### 12.5 Components
`DeckCard`, `DeckActions`, `PlaceRow`, `SortTabs`, `CategoryChip`, `Stat`,
`StepList` (numbered on a dashed trail), `SafetyCard`, `StampTile`, `KadamBadge`,
`FogMap`, `BottomSheet`, `DashedProgress`, `Toast`, `EmptyState`, `TipNote` (Kalam on
a paper slip, rotated −1°), `WatchPlayer`, `WatchRail`, `CreatorChip`, `LivePill`, `PulseStrip`,
`NameBlock` (implements §7.2), `LangChip`, `MetricCard` (with sparkline),
`PartnerChecklist`, `SimulatedTag`, `Segmented` (List|Map, Passport|Studio).

### 12.6 Illustrations
One flat layered-landscape illustration per category for places without photos;
never a grey box.

### 12.7 Motion
- Deck: card follows the finger, rotation `x/12` deg; release past 30 % width
  commits, else spring back (stiffness 400, damping 30); saved cards flash a marigold
  "Want to go" stamp as they leave.
- Check-in: passport stamp drops in (scale 1.4 → 1, 280 ms, slight rotate), then the
  fog hole grows on the map (600 ms). Kadam toast from the top, 2.5 s.
- Watch: vertical snap scroll, 220 ms ease-out; Live pill dot pulses.
- `prefers-reduced-motion`: no rotation, springs or pulsing; cross-fades ≤ 150 ms.
- Haptics: `navigator.vibrate(12)` on save and check-in where supported.

### 12.8 Voice
Warm, short, local; "You're here!"; safety copy plain; money copy precise and
never hyped ("Estimated, simulated" not "Earn big!").

### 12.9 Empty states
Deck with nothing in range → widen radius / add the first place here. City with
< 5 places → "This city is mostly unmapped. Be its first pathfinder." Passport with
no stamps → stamp outline "Your first stamp is one visit away." Watch Following empty → "Follow creators from any video to see them here";
Studio before any content → "Your first place or video starts your Studio."

---

## 13. Accessibility (WCAG 2.2 AA)
Every gesture has a button; touch targets ≥ 44 × 44 px; visible focus ring (2 px
`lake` + 2 px offset); captions/alt text required on media; colour never the only
signal (icons + words); text over photos always on the scrim; 200 % zoom without
loss; layout tested at 360 px. Plus: video captions required (uploader text) and shown as on-video text
on request; Watch fully operable with buttons and keys; `lang` attributes on all
names; RTL names isolated with `<bdi>`; sparkline values also in text.

---

## 14. Privacy, licences, content
- Never store user coordinates (Visit/Pulse/Touch have none).
- EXIF stripped on stored media.
- Licences: OSM (ODbL) attribution; Wikidata (CC0) credited; Commons per-photo
  attribution with licence allowlist; Wikivoyage (CC BY-SA) attribution (Tier 2);
  OpenFreeMap via MapLibre.
- **Maps of India**: Indian law and policy are strict about how India's external
  boundaries are shown. We hide international boundary layers on our maps and never
  draw state or country borders. States come from Wikidata's administrative
  hierarchy (§6.2), not from boundary polygons.
- No third-party network calls from the frontend except `tiles.openfreemap.org`;
  Commons photos are proxied and cached by our server.
- Uploader keeps ownership; grants display licence at sign-up.
- Money: no payments in this version; Simulated labels everywhere (§10.5).

---

## 15. Performance
First deck card ≤ 2.0 s on a mid-range Android over 4G after first load; app shell
≤ 250 KB gzipped JS; MapLibre lazy-loaded on Explore Map and Add; thumbnails 400 px
in lists, 1200 px display; next 2 deck cards preloaded; deck endpoint ≤ 200 ms for
10k places (bbox prefilter, then haversine). First Watch video starts ≤ 2.5 s on mid-range Android over 4G
(poster shows immediately); preload next video's first 500 KB only; Indic fonts
load per script via `unicode-range` (a Hyderabad user downloads Telugu + Urdu
subsets, not all 13 fonts).

---

## 16. Config

```yaml
city_default: hyderabad
languages: [en, hi, mr, ne, sa, gom, mai, doi, brx, bn, as, gu, pa, or, te, ta, kn, ml, ur, ks, sd, sat, mni]
state_languages:            # regional languages per state/UT (extend in Phase 1)
  Telangana: [te, ur]
  Andhra Pradesh: [te]
  Tamil Nadu: [ta]
  Karnataka: [kn]
  Kerala: [ml]
  Maharashtra: [mr]
  Gujarat: [gu]
  Punjab: [pa]
  Odisha: [or]
  West Bengal: [bn]
  Assam: [as]
  Manipur: [mni]
  Jammu and Kashmir: [ur, ks]
  Goa: [gom]
  Bihar: [hi, mai]
  Jharkhand: [hi, sat]
  Sikkim: [ne]
  Delhi: [hi]
  Uttar Pradesh: [hi, ur]
wikidata:
  classes: [Q570116, Q33506, Q34038, Q23397, Q8502, Q40080, Q22698, Q46169, Q179049,
            Q1107656, Q23413, Q57821, Q44539, Q4989906, Q839954, Q35509]   # verify in Phase 1
  famous_sitelinks: 15
commons:
  licence_allowlist: ["CC0", "Public domain", "CC BY", "CC BY-SA"]
  thumb_width: 1200
watch:
  weights: {quality: 0.35, prox: 0.20, pref: 0.20, fresh: 0.15, following: 0.10}
  prox_tau_km: 25
  fresh_tau_days: 5
  engaged_min_s: 3
  completion_ratio: 0.9
  break_nudge_min: 20
  video_max_s: 60
  video_max_mb: 60
pulse:
  live_hours: 6
  recent_hours: 48
  hide_days: 7
  visit_window_hours: 2
attribution:
  lookback_days: 30
  half_life_days: 7
  steps_min_read_s: 10
invalid_traffic:
  new_account_hours: 24
  repeat_window_hours: 24
  velocity_sd: 4
  velocity_min: 50
partner:
  creator_share: 0.55
  weights: {engaged_view: 1, visit_caused: 25, helpful_vote: 5, pulse_confirmed: 2}
  min_account_days: 30
  min_verified_content: 10
  min_visits_caused_90d: 300
  min_engaged_views_90d: 100000
  min_payout_inr: 1000
  demo_pool_inr: 250000
ranking:
  wilson_z: 1.96
  hidden_weight: {hidden: 1.0, known: 0.7, famous: 0.3}
  trending_half_life_days: 7
  trending_window_days: 30
  trending_weights: {like: 1, visit: 3, pulse: 1}
deck:
  weights: {q: 0.40, prox: 0.25, pref: 0.25, fresh: 0.10}
  prox_tau_km: 4
  page_size: 30
  skip_cooldown_days: 14
  max_same_category_run: 2
verification:
  min_radius_m: 150
  max_accuracy_m: 100
  add_pin_max_drag_m: 300
  verify_visits_needed: 2
  max_speed_kmh: 120
dedupe:
  radius_m: 300
  name_sim_min: 80
  same_category_radius_m: 100
  clip_sim_min: 0.90
  generic_words:
    en: [the, lake, hill, temple, point, view, park, fort, falls]
    te: [cheruvu, gutta, konda, gudi]
    hi: [talab, mandir, pahadi, kila]
    ta: [eri, kovil, malai]
    kn: [kere, gudi, betta]
integrity:
  phash_max_hamming: 8
  exif_mismatch_km: 2
kadam:
  discovery: 50
  visit_caused: 10
  visit_caused_daily_cap_per_place: 20
  like_received: 1
  like_received_daily_cap: 50
  own_visit: 5
  steps_helpful: 2
  steps_helpful_daily_cap: 20
  pulse: 3
  pulse_daily_cap: 5
  weekly_trail: 50
  levels: {Wanderer: 0, Pathfinder: 200, Trailblazer: 800, Local Legend: 2500}
fog:
  clear_radius_km: 1.0
media:
  max_photos: 10
  max_videos: 2
  photo_long_side: 2048
cities:
  hyderabad:
    name: Hyderabad
    state: Telangana
    bbox: [17.20, 78.20, 17.62, 78.70]    # example; set yours in Phase 1 (Q2)
```

---

## 17. Evaluation (for the report)

Simulations show behaviour under stated assumptions; they are not user studies,
and the report says so. Each writes `results/<name>/<timestamp>/` with config,
commit, seeds, `metrics.json` and a figure.

1. **Ranking** (`sim/ranking_sim.py`): 500 places, true like rate ~ Beta(2,5),
   power-law exposure; raw likes vs ratio vs Wilson; Kendall τ and precision@10;
   200 seeds; 95 % CI.
2. **Deck/Watch bandit** (`sim/bandit_sim.py`): 300 users with hidden category
   preferences; random vs popularity vs fixed weights vs Thompson; save rate over 30
   swipes; 50 seeds; CI; curve.
3. **Attribution** (`sim/attribution_sim.py`): simulate creators, users, touches
   and visits from a known ground-truth influence model (each touch raises visit
   probability by a creator-specific amount that decays with time). Compare
   last-touch, linear and time-decay (§9.9) on how well credited visits match each
   creator's true influence (Spearman ρ and mean absolute error of shares); 100 seeds.
4. **Invalid traffic** (`sim/fraud_sim.py`): inject bot bursts, sock-puppet accounts
   and self-views into simulated traffic; precision and recall of §9.10 rules (Tier 2:
   plus Isolation Forest); effect on the money a fraudster would get.
5. **pHash robustness**: 50 own photos × transforms; detection and false-match rates.
6. **Dedupe** (Tier 2): 60 labelled pairs; precision/recall with and without CLIP.
7. **Data coverage**: counts of seeded places per state and category, share with a
   photo, share with a name in each of the 22 languages (a table that also shows
   where coverage is weak).
8. **App checks**: the AC table (§18) with evidence.
9. **Demo data** (`scripts/demo_data.py`, users flagged `demo`): 12 demo users incl.
   3 creators, videos, likes, views, saves, simulated visits; plus **at least 2 real
   places and 2 real videos you add on site** on 24–25 Oct.

---

## 18. Acceptance criteria

- **AC-1 OSM seed.** `seed_osm` imports ≥ 150 named places + neighbourhoods for the
  city; idempotent; all `name:*` tags become PlaceName rows.
- **AC-2 Wikidata seed.** `seed_wikidata` imports India-wide items for the
  configured classes with labels in all available languages, sitelinks, image names;
  merges with OSM by wikidata id; counts recorded in PLAN.md; re-run idempotent.
- **AC-3 Commons photos.** A Wikidata place's photo is fetched once, cached, served
  from our origin, shows author + licence + link; a non-allowlisted licence is
  refused (test with fixtures).
- **AC-4 Names.** For each of the 3 `names_mode` values, a fixture place renders the
  §7.2 lines correctly; `lang` attributes present; an Urdu name is isolated RTL;
  glyphs render for all 23 languages on the Languages screen (screenshot check).
- **AC-5 Explore.** Search works in English and in a local script; 5 sorts; Wilson
  test values; Map shows pins, clusters, no international boundary layer.
- **AC-6 Place page.** All §8.5 sections render for a community, an OSM and a
  Wikidata place; Open in Maps URL exact; attributions correct.
- **AC-7 Add.** All three (+) flows work on phone; resize ≤ 2048 px; stored files have
  no EXIF; pHash rejects another user's photo; duplicate candidates use all names.
- **AC-8 Verification.** Radius/accuracy boundaries; no coordinates in Visit, Pulse,
  Touch or logs; impossible travel flag.
- **AC-9 Likes, follows.** One like per user per place/media; self-like rejected;
  `likes ≤ viewers` (property test); follow/unfollow idempotent.
- **AC-10 Deck.** Swipe + buttons; reproducible with seed; α/β updates; no 3 in a row;
  end card.
- **AC-11 Watch.** Tabs work; ranking reproducible with seed and follows §9.5
  weights (unit test); ≤ 2 same-creator in a row; engaged/completed computed
  server-side from heartbeat; saveData path shows poster; 20-min nudge appears
  (fake clock).
- **AC-12 Pulse.** Only verified recent visitors can post; freshness labels; mixed
  reports rule; Live pill appears on deck/Watch/Explore within one refresh.
- **AC-13 Map & fog.** 1 km holes for verified, unflagged visits (simulated only in
  dev); neighbourhood count on fixture.
- **AC-14 Kadam.** Every §10.1 rule and cap tested; balance = ledger sum; reversals.
- **AC-15 Unverified & fragile.** Unverified excluded from Top/Gems/Trending, discovery
  paid after 2 qualifying visits; fragile coordinates/steps never returned before
  pledge (direct API test); fragile videos excluded from For you.
- **AC-16 Attribution.** On hand-built fixtures, shares match hand-computed values
  to 1e-9, sum to 1, exclude self and invalid touches, and organic visits get none.
- **AC-17 Invalid traffic.** Each §9.10 rule has a test; velocity hold excludes only
  the excess.
- **AC-18 Partner split.** For a fixture month: eligibility per §10.4, scores per
  §10.3, amounts sum ≤ pool, rounding down in paise, ineligible creators get 0.
- **AC-19 Studio.** Metrics match the database for a fixture creator; checklist
  reflects eligibility; sparkline values available as text.
- **AC-20 Design.** Tokens match §12.2 in both themes; the 9 reference screens at
  390 × 844 match the reference's structure (Prompt 7); no horizontal scroll at 360 px.
- **AC-21 Accessibility.** axe-core no serious/critical issues on the 9 screens;
  keyboard operable incl. Watch; reduced motion honoured.
- **AC-22 Privacy & licences.** Playwright run observes only allowed origins;
  attribution present for OSM, Commons, Wikidata; boundary layers hidden.
- **AC-23 Simulated money.** Every element showing ₹ has a Simulated label (DOM test
  over Studio, profile, earnings sheet); Studio banner always present.
- **AC-24 Simulations.** §17 items 1–5 and 7 produce results with CIs and figures;
  README quotes `metrics.json` exactly.
- **AC-25 Dev tools.** Production build has no teleport UI; `/api/dev/teleport` 404
  without the flag; simulated visits never reach attribution or earnings.

---

## 19. Decisions

- **D1 Web app (PWA)**: zero budget, one codebase; Play Store needs a paid account.
- **D2 FastAPI + SQLite**: laptop-only; Python explainable in the viva.
- **D3 OSM + Wikidata + Commons, never Google data**: free, storable, legal (§6.6).
- **D4 OpenFreeMap tiles; boundary layers hidden.**
- **D5 "Open in Maps" link, no routing API.**
- **D6 Kadam points for everyone; money only via the Partner Program; simulated now.**
- **D7 Pay for visits caused more than views** (§10.6).
- **D8 Wilson lower bound** for ranking.
- **D9 Thompson sampling** shared by deck and Watch.
- **D10 Time-decay attribution**, validated against last-touch and linear in simulation.
- **D11 Never store user coordinates.**
- **D12 Weekly streak; the deck ends; Watch nudges after 20 min.**
- **D13 Fragile places hide their pin.**
- **D14 No video transcoding**: limits instead.
- **D15 All 22 scheduled languages for names from day one; UI languages only when
  native-reviewed.**
- **D16 Self-hosted fonts per script with unicode-range** (no font CDN, small downloads).

---

## 20. Open questions (answer before Phase 0)

- **Q1 Name.** "Truvel": no app found with this name in a quick search; a café in
  Pune uses it. Check the Play Store and domains. Backups: *Kona*, *Ankahi*, *Gully Map*.
- **Q2 Deep city.** Which city gets the full OSM seed (the reference uses Hyderabad).
- **Q3 Your regional UI language** for Tier 2, and who reviews it (native speaker).
- **Q4 Deployment.** Laptop demo + phone on Wi-Fi (default), or does the submission
  need a public URL?
- **Q5 Team.** Solo or group (affects the day split).
- **Q6 Partner numbers.** Keep 55 % share, 25× visit weight and the thresholds, or
  change them? (Changing them is a config edit; say why in the report.)
