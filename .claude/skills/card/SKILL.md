---
name: card
description: Run one task card (A1..A7, B0..B8) from docs/NEXT_LEVEL_PLAN.md with minimal reading. Use when the user types /card <ID> or asks to do the next card.
---

# Run a card

Argument: a card ID such as `A1` or `B2`. No ID → read the status boxes in
`docs/NEXT_LEVEL_PLAN.md` (`grep -n '^### [AB][0-9]' docs/NEXT_LEVEL_PLAN.md`) and pick
the first `[ ]` in the stated order; say which and why in one line.

1. Read only that card: `grep -n '^### <ID> ' docs/NEXT_LEVEL_PLAN.md`, then read
   from that line to the next `### `.
2. Read only the `docs/CONTEXT_MAP.md` rows and SPEC line ranges the card needs.
   Never open `docs/design-reference.html`; use `results/screens/` PNGs.
3. Track B card, or more than 3 files, or any SPEC change → show the plan and the
   SPEC.md diff first and wait for approval.
4. Tests first for SPEC §9/§10 logic. While working run only the relevant test file
   (`pytest tests/test_x.py -q`, `npx vitest run <file>`), output through `tail -20`.
5. Before committing: `pytest -q` and `npm run test` once, both green; re-check
   CLAUDE.md invariants 1, 4, 5, 7, 13 against the diff.
6. Tick the card (`[x]`), add one line to PLAN.md "Progress log", commit as
   `card <ID>: <what>`.
7. Final message: the card checklist from the bottom of NEXT_LEVEL_PLAN.md, filled in,
   and "next: card <ID>" — the next card goes in a new session.
