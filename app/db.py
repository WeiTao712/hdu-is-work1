"""SQLite access layer.

Every statement in this module is a *parameterised* statement: SQL text and
data never travel in the same string.  See ``like_pattern`` for the no-sides
handling of ``LIKE`` wildcards, which is the only place where user input
influences the shape of a pattern.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    display_name  TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT    NOT NULL,
    body       TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_id);
"""


def get_db() -> sqlite3.Connection:
    """Return the per-request connection (created lazily)."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_PATH"])
    return g.db


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def close_db(_exc: BaseException | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ---------------------------------------------------------------------------
# Queries -- all parameterised
# ---------------------------------------------------------------------------

def create_user(conn: sqlite3.Connection, username: str, password_hash: str, display_name: str) -> int:
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
        (username, password_hash, display_name),
    )
    conn.commit()
    return int(cur.lastrowid)


def find_user_by_username(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    cur = conn.execute(
        # Parameter binding -- the username can never alter the statement.
        "SELECT id, username, password_hash, display_name FROM users WHERE username = ?",
        (username,),
    )
    return cur.fetchone()


def find_user_by_id(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT id, username, display_name FROM users WHERE id = ?",
        (user_id,),
    )
    return cur.fetchone()


def create_post(conn: sqlite3.Connection, author_id: int, title: str, body: str) -> int:
    cur = conn.execute(
        "INSERT INTO posts (author_id, title, body) VALUES (?, ?, ?)",
        (author_id, title, body),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_post(conn: sqlite3.Connection, post_id: int) -> sqlite3.Row | None:
    cur = conn.execute(
        """
        SELECT p.id, p.title, p.body, p.created_at, u.username AS author
        FROM posts p JOIN users u ON u.id = p.author_id
        WHERE p.id = ?
        """,
        (post_id,),
    )
    return cur.fetchone()


def like_pattern(term: str) -> str:
    """Turn free text into a *containing* LIKE pattern, escaping wildcards.

    ``%`` and ``_`` are LIKE metacharacters; without escaping a user could
    turn ``a_b`` into "a<any char>b".  This is an escaping concern, not an
    injection concern -- the value is still bound as a parameter.
    """
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_posts(conn: sqlite3.Connection, search: str | None = None, limit: int = 50) -> list[sqlite3.Row]:
    if search:
        pattern = like_pattern(search)
        cur = conn.execute(
            """
            SELECT p.id, p.title, p.body, p.created_at, u.username AS author
            FROM posts p JOIN users u ON u.id = p.author_id
            WHERE p.title LIKE ? ESCAPE '\\' OR p.body LIKE ? ESCAPE '\\'
            ORDER BY p.id DESC
            LIMIT ?
            """,
            (pattern, pattern, limit),
        )
    else:
        cur = conn.execute(
            """
            SELECT p.id, p.title, p.body, p.created_at, u.username AS author
            FROM posts p JOIN users u ON u.id = p.author_id
            ORDER BY p.id DESC
            LIMIT ?
            """,
            (limit,),
        )
    return list(cur.fetchall())


def count_users(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def executemany(conn: sqlite3.Connection, sql: str, rows: Iterable[tuple[Any, ...]]) -> None:
    conn.executemany(sql, rows)
    conn.commit()
