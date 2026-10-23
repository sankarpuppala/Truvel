---
name: commit
description: Run tests, check for files on CLAUDE.md's "Never commit" list, and commit the current changes. Use at the end of every phase or card.
---

# Commit

1. Run `pytest -q` in `backend/` and `npm run test` in `frontend/`. If either
   fails, stop and show the failure — do not commit.
2. Run `git status`. Refuse to stage or commit anything matching CLAUDE.md's
   "Never commit" list: `backend/media/`, `*.db`, `data/`, `.env*`, `.venv/`,
   `node_modules/`, uploaded photos/videos, Commons cache. If `git status` shows
   any of these as staged or about to be added, unstage them and warn instead of
   committing.
3. Write the commit message as `phase N: <what>` (or `card <ID>: <what>` for
   Track A/B cards), with a body listing the ACs touched and the PLAN.md tasks
   ticked in this change.
4. Commit and print the short hash (`git rev-parse --short HEAD`).
