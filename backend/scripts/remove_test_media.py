"""Remove media that the end-to-end tests posted, and their files on disk.

The tests upload real (tiny) videos through the real endpoint to have something
to watch. There is deliberately no endpoint for a person to delete their own
upload yet (see PLAN.md, ideas parked), so the tests clean up here instead of
the product growing a route just for them.

    python -m scripts.remove_test_media            # captions starting "Test clip"
"""
from __future__ import annotations

import sys

from sqlalchemy import delete as sa_delete
from sqlmodel import Session, select

from app.config import MEDIA_DIR
from app.db import engine
from app.models import Media, MediaLike, MediaView

PREFIX = "Test clip"


def main() -> int:
    removed = 0
    with Session(engine) as session:
        rows = session.exec(select(Media).where(Media.caption.like(f"{PREFIX}%"))).all()  # type: ignore[attr-defined]
        for row in rows:
            # Bulk deletes run in the order written, children first. Deleting
            # ORM objects one by one lets the unit of work reorder them, and a
            # parent row can be deleted before the rows that point at it.
            for related in (MediaLike, MediaView):
                session.exec(sa_delete(related).where(related.media_id == row.id))
            for rel in (row.path_display, row.path_poster, row.path_thumb):
                if rel:
                    target = MEDIA_DIR / rel
                    if target.is_file():
                        target.unlink()
            session.exec(sa_delete(Media).where(Media.id == row.id))
            removed += 1
        session.commit()
    print(f"removed {removed} test upload(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
