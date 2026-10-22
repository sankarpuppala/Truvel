# PROMPT.md — Truvel (v2)

Copy-paste prompts for Claude Code, in the order you'll use them. `[brackets]` are
for you to fill in.

**Setup once**: put `CLAUDE.md`, `SPEC.md`, `PLAN.md`, `PROMPT.md` in the repo
root and `docs/design-reference.html`, `docs/VIVA.md` in `docs/`. Open the folder
in Claude Code. Use the most capable model for Prompts 1, 2, 8 and 9 (thinking and
reviewing); the default model is fine for routine phases.

**Rhythm for every phase**: new session → Prompt 4 in Plan Mode → approve →
implement + verify → Prompt 5 (teach-back) → Prompt 3 (commit).

---

## Part A — Before code (tonight)

### Prompt 1 — Interrogate the spec
```
Read CLAUDE.md, SPEC.md, PLAN.md and docs/design-reference.html. Don't write code.

Act as a sceptical senior engineer who must build this in 8 days on a Windows
laptop with zero budget. Give me:
1. Contradictions or gaps between SPEC sections (cite § numbers).
2. Anything that can't work as written: browser APIs, Wikidata/Overpass/Commons
   limits, licences, font rendering for the 23 languages, Windows specifics.
3. The 6 riskiest items for the 25 Oct Tier 1 gate and how to de-risk each on Day 1.
4. Where the plan is overloaded, and what you'd cut first (SPEC §4 order).
5. Questions I must answer — start with SPEC §20 Q1–Q6, one at a time, wait for
   each answer.
After I answer, propose SPEC.md edits as a diff and wait for approval.
```

### Prompt 2 — Plan review
```
Review PLAN.md against SPEC.md.
- Is every acceptance criterion AC-1..AC-25 delivered and tested by some phase?
  List any that aren't.
- Estimate hours per phase for one student with Claude Code; flag days over 9 hours
  and propose moves or cuts (SPEC §4 cut order).
- Check dependency order (e.g. Touch recording must exist before attribution).
Propose PLAN.md edits as a diff. Don't edit until I approve.
```

### Prompt 3 — Commit skill (end of Phase 0, reused after every phase)
```
Create a project skill at .claude/skills/commit/SKILL.md that:
1. Runs `pytest -q` (backend) and `npm run test` (frontend); stops on failure and
   shows it.
2. Shows `git status` and refuses to commit anything on CLAUDE.md's "Never commit"
   list (media, *.db, data/, .env*, venv, node_modules, uploads, Commons cache).
3. Writes `phase N: <what>` with a body listing ACs touched and PLAN.md tasks ticked.
4. Commits and prints the short hash.
Then commit the current state as "phase 0: setup, specs and design reference".
```

---

## Part B — Every phase

### Prompt 4 — Phase template (Plan Mode)
```
We are doing Phase [N] — [name] from PLAN.md.
Read CLAUDE.md, the SPEC.md sections the phase references, and the phase in
PLAN.md. If it has UI, open docs/design-reference.html and find the matching
screen(s).

In Plan Mode give me: files to create/change; tests you'll write first (named after
ACs); SPEC ambiguities for me to decide (don't guess); what "done" looks like.
Wait for approval.

Then implement. Rules: tests first for SPEC §9 and §10 logic; constants from
config.yaml; tokens only in CSS; names only via NameBlock/names.ts; every ₹ via
<Money>; no libraries beyond CLAUDE.md's stack.
Verify: all tests; for UI, Playwright screenshots at 390x844 light + dark compared
with the reference; list and fix differences. Update PLAN.md (tasks, Measured
values, Progress log).
```

### Prompt 5 — Teach-back (end of every phase; quiz mode on Day 8)
```
I have to explain this project in a viva and I'm not an expert. Teach me Phase [N]:
1. Plain English: what it does, which files matter and why (max 10 files).
2. Walk through the single most important function line by line.
3. Ask me 3 viva-style questions, one at a time; after each answer tell me what was
   right, what was missing, and the model answer.
4. Append the 3 questions and model answers to docs/VIVA.md under "Phase [N]".
Define any jargon the first time you use it.
```
Quiz mode: "Quiz me on docs/VIVA.md: 10 random questions, hardest first, score me."

---

## Part C — Checks and reviews

### Prompt 6 — Tier 1 gate (end of Day 5)
```
Run the Tier 1 gate in PLAN.md Phase 6.
For AC-1..AC-15 and AC-25: run the tests, show pass/fail with test names. For anything
without an automated test, tell me exactly what to check by hand and wait.
Then run the journey in Playwright at 390x844 with the dev simulator: deck → save →
place → check in → Pulse → fog clears → passport stamp → Watch → Go here. Save
screenshots to results/gate/.
Output a table: AC, status, evidence. For failures propose the smallest fix or the
SPEC §4 cut, and wait.
```

### Prompt 7 — Design critique
```
Take Playwright screenshots of all 9 reference screens — Nearby, Watch, Explore
List, Explore Map, Place (full length), Add (step 2 with duplicate prompt), You
Passport, You Studio, Languages & cities — at 390x844 in light and dark
(results/design/). Open docs/design-reference.html and compare screen by screen.

Be a demanding product designer. For each screen list: layout/hierarchy differences;
token violations (literal colours, wrong fonts/radii); text overflow or bad wraps at
360px; wrong or missing glyphs in any script; contrast problems (SPEC §12.2); touch
targets < 44px; missing focus states; gestures without buttons; anything generic or
templated. Rank by first-impression damage. Fix the top 10, re-screenshot, show
before/after.
```

### Prompt 8 — Independent security, privacy and fraud review (subagent)
```
Use a subagent that has NOT seen our conversation. Give it only SPEC.md §5, §8.7,
§8.8, §8.14, §9.6–9.10, §10, §14, CLAUDE.md invariants, and the backend code. Its job:
find ways to
- learn a user's location or home from anything stored, logged or returned;
- get kadam or earnings without real visits: sock puppets, self-dealing, view bots,
  collusion rings that view each other's videos, replayed check-ins, racing
  requests, gaming time-decay attribution with last-minute touches;
- see a fragile place's pin before pledging;
- upload a non-image/video, or a stolen photo that passes pHash;
- show a ₹ figure without the Simulated label;
- break auth (session fixation, CSRF, user enumeration).
For each: severity, concrete reproduction, fix. Then you (not the subagent) fix all
high and medium findings with tests, and list what remains.
```

### Prompt 9 — Results audit (subagent, after Phase 8)
```
Use a subagent that has NOT seen our conversation. Give it SPEC.md §9, §10, §17,
sim/, results/ and README.md. Ask it to check:
- simulations import the real ranking/deck/watch/partner code, not copies;
- seeds, config and commit recorded; README numbers match metrics.json exactly;
- CIs computed correctly (show the formula used);
- the attribution simulation's ground truth isn't secretly the same formula as
  time-decay (that would make the comparison circular);
- README never presents simulations as user behaviour and states assumptions;
- any claim stronger than the evidence ("proves", "users prefer", "fraud-proof").
Then fix what it finds and show me the diff.
```

### Prompt 10 — Fix the spec (whenever reality disagrees, or you're behind)
```
Stop coding. We found that [what happened / we're behind by X hours]. Explain why
SPEC [§X] can't be met as written, give 2 options with trade-offs (one must be the
SPEC §4 cut order), recommend one. After I choose, edit SPEC.md (and PLAN.md) first,
show the diff, then update code and tests.
```

---

## Part D — Finishing

### Prompt 11 — Report (Day 8 morning)
```
Write docs/REPORT.md for my Applied Data Science and AI submission, using only facts
from SPEC.md, PLAN.md Measured values, results/ and the code.
Sections: Abstract (150 words); Problem and users; Related apps and moat (SPEC §3);
Data sources and licences (OSM, Wikidata, Commons; why not Google); Languages (22 +
English, how names are chosen, fonts); System design (Mermaid architecture diagram,
data model); Algorithms with formulas and reasons (Wilson, gems, trending, Thompson
sampling, Watch ranking, dedupe, pHash, fraud rules, time-decay attribution, invalid
traffic, Partner split); Evaluation (all simulations with CIs, pHash, coverage
table, AC table); Ethics, privacy, safety, money honesty; Limitations (simulations
not user studies, one deep city, GPS spoofable, simulated pool, translation review);
Roadmap (SPEC §4 Tier 3, §10.2); References.
Plain English; every number must appear in results/ or Measured values. Then update
docs/VIVA.md so every answer matches the final code.
```

### Prompt 12 — Demo rehearsal
```
Help me rehearse a 6-minute live demo.
1. Script (what I click, 1–2 sentences each): problem → Nearby deck (Thompson in one
   line) → Watch → Go here → Place (Pulse, last-mile, safety) → Languages screen
   (switch names to Tamil/Hindi) → Explore Top vs Most liked (Wilson in one line) →
   a real place I added on site → check-in with simulator → fog + stamp → Studio
   (attribution and the Simulated pool) → one simulation figure → limitations.
2. What could fail live and the fallback for each; a pre-demo checklist.
3. Ask me the 5 hardest examiner questions, one at a time.
```

### Prompt 13 — IndicXlit batch in Colab (Tier 2)
```
Write notebooks/indicxlit_batch.ipynb to run in Google Colab (free tier):
1. Install ai4bharat-transliteration as its README says (in Colab, not on my laptop).
2. Read places_missing_names.csv (place_id, english_name, target_langs) that you also
   add as an export command: `python -m scripts.export_missing_names`.
3. For each row and target language IndicXlit supports, take the top-1 candidate.
4. Write auto_names.csv (place_id, lang, name, source='auto').
Add `python -m scripts.import_auto_names auto_names.csv` that inserts PlaceName rows
with source 'auto' (never overwriting other sources). Tell me exactly what to
upload/download. Note in the notebook that Dogri and Santali aren't supported.
```

### Prompt 14 — UI translation with native review (Tier 2)
```
Add UI language [code]. Steps:
1. Draft frontend/src/i18n/[code].json from en.json; keep placeholders and plurals.
2. Export review.csv (key, English, draft, notes on context) for a native speaker.
3. Keep the language disabled with a "Beta" label until I give you the reviewed CSV.
4. When I do, apply it, enable the language, and screenshot every screen in it at
   360px to catch overflow.
Never mark the language reviewed yourself (CLAUDE.md invariant 11).
```

---

## Quick fixes

- **Works on laptop, not phone** → `npm run dev -- --host`, open
  `https://<laptop-ip>:5173`, accept the certificate; same Wi-Fi; allow Node through
  Windows Firewall (private networks).
- **Boxes instead of letters in some script** → "Open the Phase 0 glyph test page;
  the [script] font isn't loading. Check fonts.css unicode-range and the @fontsource
  import for [script]."
- **Check-in accuracy too poor** → go outdoors and wait 10 s; demo with the simulator.
- **Wikidata query timeout** → "Split the query by class and by state; cache results."
- **Claude Code drifting from the design** → "Open docs/design-reference.html, screen
  [name]. Your screenshot differs in: [list]. Match it using tokens.css only."
- **Claude Code adding features** → "Not in SPEC.md. Park it in PLAN.md Ideas parked
  and continue Phase [N]."
- **Behind schedule** → Prompt 10 with "we're behind; apply the SPEC §4 cut order."
