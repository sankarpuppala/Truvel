"""SQLite engine, session dependency, and the FTS5 index over place names.

Search has to work in any script (SPEC §7.4), so the index is built over every
`PlaceName` row rather than over one English column. FTS5 with the `unicode61`
tokenizer handles Indic scripts fine: it splits on non-letters and lowercases
what it can, which is all we need to match "golconda", "Golconda" and
"గోల్కొండ" to their own rows.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from . import models  # noqa: F401  (import registers every table)
from .config import DB_PATH

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record) -> None:  # noqa: ANN001
    """WAL and foreign keys. WAL keeps reads from blocking the seed scripts."""
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


# --------------------------------------------------------------------------- #
# Full-text search over PlaceName (SPEC §7.4)
# --------------------------------------------------------------------------- #

FTS_SETUP = [
    # `name` is indexed; place_id and lang ride along unindexed so a hit can be
    # resolved to a place without a second query.
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS placename_fts USING fts5(
        name,
        place_id UNINDEXED,
        lang UNINDEXED,
        tokenize = 'unicode61 remove_diacritics 2'
    )
    """,
    # Keep the index in step with the table. Triggers mean the seed scripts and
    # the API never have to remember to reindex.
    """
    CREATE TRIGGER IF NOT EXISTS placename_ai AFTER INSERT ON placename BEGIN
        INSERT INTO placename_fts(rowid, name, place_id, lang)
        VALUES (new.id, new.name, new.place_id, new.lang);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS placename_ad AFTER DELETE ON placename BEGIN
        DELETE FROM placename_fts WHERE rowid = old.id;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS placename_au AFTER UPDATE ON placename BEGIN
        DELETE FROM placename_fts WHERE rowid = old.id;
        INSERT INTO placename_fts(rowid, name, place_id, lang)
        VALUES (new.id, new.name, new.place_id, new.lang);
    END
    """,
]


def init_db() -> None:
    """Create tables, the FTS index and its triggers. Safe to call repeatedly."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        # SQLModel creates tables but never alters an existing one, and the
        # project has no migration tool on purpose (CLAUDE.md: no Postgres, no
        # Alembic). One `ADD COLUMN` is cheaper than the tool that would
        # manage it, same pattern as `scripts/official_account.py`.
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(place)")).fetchall()}
        if "locality" not in columns:
            conn.execute(text("ALTER TABLE place ADD COLUMN locality TEXT"))
        for stmt in FTS_SETUP:
            conn.execute(text(stmt))
        # Backfill anything inserted before the triggers existed.
        conn.execute(
            text(
                """
                INSERT INTO placename_fts(rowid, name, place_id, lang)
                SELECT p.id, p.name, p.place_id, p.lang FROM placename p
                WHERE p.id NOT IN (SELECT rowid FROM placename_fts)
                """
            )
        )


def rebuild_fts() -> None:
    """Drop and rebuild the search index (used after a bulk seed)."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM placename_fts"))
        conn.execute(
            text(
                """
                INSERT INTO placename_fts(rowid, name, place_id, lang)
                SELECT id, name, place_id, lang FROM placename
                """
            )
        )


def fts_query(session: Session, q: str, limit: int = 20) -> list[int]:
    """Place ids whose name matches `q` in any language, best match first.

    The query string is escaped as an FTS5 prefix phrase, so a user typing
    `golconda fo` finds "Golconda Fort" and nothing blows up on punctuation.
    """
    words = [w for w in "".join(c if c.isalnum() else " " for c in q).split() if w]
    if not words:
        return []
    match = " ".join(f'"{w}"*' for w in words)
    rows = session.exec(
        text(
            """
            SELECT place_id, MIN(rank) AS r
            FROM placename_fts
            WHERE placename_fts MATCH :m
            GROUP BY place_id
            ORDER BY r
            LIMIT :lim
            """
        ).bindparams(m=match, lim=limit)
    ).all()
    return [int(r[0]) for r in rows]


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with Session(engine) as session:
        yield session
