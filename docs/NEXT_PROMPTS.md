# NEXT_PROMPTS.md — short prompts for the next-level plan

Each prompt is short because the detail lives in the card
(`docs/NEXT_LEVEL_PLAN.md`) and the reading list (`docs/CONTEXT_MAP.md`).
Start a **new session per card**. The `/card <ID>` skill runs Prompt N1 for you.

---

### N1 — Run one card (every session)
```
/card A1
```
or, without the skill:
```
Card A1 from docs/NEXT_LEVEL_PLAN.md. Read only that card and the
docs/CONTEXT_MAP.md rows it needs (line ranges, not whole files; never open
docs/design-reference.html). If it touches > 3 files or needs a SPEC change,
show the plan / SPEC diff and wait. Otherwise implement, run the targeted test
file, then the full suites once, tick the card, add one Progress-log line,
and commit. Final message: the card checklist, filled in.
```

### N2 — Independent review (A1, run as a subagent)
```
Use a subagent with no access to my reasoning. Brief it with CLAUDE.md
invariants 1–13 and docs/CONTEXT_MAP.md rows "Check-in", "Uploads", "Auth".
Ask it to try to break: coordinates stored or logged, fragile coordinates
leaked before pledge, EXIF surviving upload, third-party origins in the page,
kadam/earnings changed outside the ledgers, dev teleport reachable in prod,
session/cookie/CSRF gaps, upload type confusion. Each finding: file:line,
how to reproduce, severity. Then fix high + medium with one test each and
write docs/SECURITY_REVIEW.md.
```

### N3 — Propose a SPEC change (first step of every Track B card)
```
For card B2, write the smallest SPEC.md diff that makes it in scope:
the section text, any new models (fields only), the ACs it adds (AC-26…),
and which invariants it touches. Read only the SPEC sections the card names.
Show the diff; don't edit until I approve.
```

### N4 — Viva / pitch drill (cheap, no code reading)
```
Using only docs/REVIEW.md and docs/VIVA.md, quiz me: 5 viva questions on
algorithms (§9–10), then 5 investor questions (market, moat, revenue, risk,
why now). One at a time; grade each answer in two lines.
```

### N5 — Pitch deck outline (start-up track)
```
From docs/REVIEW.md §2 and §4 and README "What the measurements say", draft a
10-slide outline: problem, insight, product loop, demo moments, traction
plan (Hyderabad), moat, business model stages, metrics, team, ask.
Every number must come from a metrics.json or be marked "target".
```

### N6 — Resume after a break
```
Read the last 15 lines of PLAN.md "Progress log" and the status boxes in
docs/NEXT_LEVEL_PLAN.md (grep '\[ \]\|\[~\]'). Tell me the next card and
why, in 3 lines. Don't read anything else.
```
