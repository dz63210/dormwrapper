"""Raw sqlite3 persistence for the API.

One SQLite file (path from ``settings.database_url``). A connection-per-request
dependency (``get_db``) for routes, and an equivalent context manager
(``db_session``) for scripts. The full schema lives in ``init_db``.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

# Tolerate a legacy "sqlite:///<path>" value from an older .env / .env.example.
_raw = settings.database_url
if _raw.startswith("sqlite:///"):
    _raw = _raw[len("sqlite:///") :]
DB_PATH = Path(_raw)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    handle     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalogue_items (
    id             INTEGER PRIMARY KEY,          -- IKEA product_id (leading zeros dropped)
    name           TEXT NOT NULL,
    category       TEXT NOT NULL,                -- furniture type, e.g. "Beds", "Desks"
    price          REAL NOT NULL,                -- USD
    dominant_color TEXT NOT NULL DEFAULT '',
    style_tags     TEXT NOT NULL DEFAULT '',     -- comma-separated DecorStyle values
    description    TEXT NOT NULL DEFAULT '',
    image_url      TEXT NOT NULL DEFAULT '',     -- served path: /catalogue-images/<product_id>.jpg
    product_url    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS sessions_user_id ON sessions(user_id);

CREATE TABLE IF NOT EXISTS rate_attempts (
    scope TEXT NOT NULL,
    subject TEXT NOT NULL,
    attempted_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS rate_attempts_lookup
ON rate_attempts(scope, subject, attempted_at);

CREATE TABLE IF NOT EXISTS submissions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    room_image_path TEXT NOT NULL,
    budget          REAL NOT NULL,
    style           TEXT NOT NULL,
    notes           TEXT NOT NULL DEFAULT '',
    room_width_ft   REAL,
    room_length_ft  REAL,
    user_id         INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS suggestions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id        INTEGER NOT NULL UNIQUE REFERENCES submissions(id) ON DELETE CASCADE,
    generated_image_path TEXT NOT NULL,
    total_price          REAL NOT NULL DEFAULT 0,
    item_ids             TEXT NOT NULL DEFAULT '',
    -- Stage 1 (furniture recommendation) output, serialized. Shape:
    -- {"items":[{"item_id","quantity","placement","reason"}],"total_price","summary"}
    recommendation_json  TEXT NOT NULL DEFAULT '',
    saved                INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL
);
"""

# Columns added after the first release. init_db() adds any that a pre-existing
# database is missing (CREATE TABLE IF NOT EXISTS won't alter an existing table).
_MIGRATIONS = [
    ("catalogue_items", "retailer", "TEXT NOT NULL DEFAULT 'ikea'"),
    ("catalogue_items", "external_product_id", "TEXT NOT NULL DEFAULT ''"),
    ("catalogue_items", "currency", "TEXT NOT NULL DEFAULT 'USD'"),
    ("catalogue_items", "availability", "TEXT NOT NULL DEFAULT 'unknown'"),
    ("catalogue_items", "room_type", "TEXT NOT NULL DEFAULT ''"),
    ("catalogue_items", "dimensions_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("catalogue_items", "materials_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("catalogue_items", "affiliate_url", "TEXT NOT NULL DEFAULT ''"),
    ("catalogue_items", "source_type", "TEXT NOT NULL DEFAULT 'ikea_snapshot'"),
    ("catalogue_items", "license_status", "TEXT NOT NULL DEFAULT 'unreviewed'"),
    ("catalogue_items", "fetched_at", "TEXT NOT NULL DEFAULT ''"),
    ("catalogue_items", "last_verified_at", "TEXT NOT NULL DEFAULT ''"),
    ("users", "email", "TEXT"),
    ("users", "auth_subject", "TEXT"),
    ("submissions", "user_id", "INTEGER REFERENCES users(id)"),
    ("submissions", "room_width_ft", "REAL"),
    ("submissions", "room_length_ft", "REAL"),
    ("suggestions", "saved", "INTEGER NOT NULL DEFAULT 0"),
    ("suggestions", "recommendation_json", "TEXT NOT NULL DEFAULT ''"),
]


def _connect() -> sqlite3.Connection:
    if DB_PATH.parent and not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, roll back on error, always close."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request (see ``db_session``)."""
    with db_session() as conn:
        yield conn


def init_db() -> None:
    """Create tables if missing, then apply any column migrations. Fine for a scaffold."""
    with db_session() as conn:
        conn.executescript(SCHEMA)
        for table, column, decl in _MIGRATIONS:
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_auth_subject ON users(auth_subject)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email ON users(email COLLATE NOCASE)")
        # Preserve legacy IDs and references; keep IKEA's leading zeros separately.
        conn.execute("UPDATE catalogue_items SET external_product_id = printf('%08d', id) WHERE external_product_id = '' AND retailer = 'ikea'")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS catalogue_source_identity ON catalogue_items(retailer, external_product_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS catalogue_retrieval ON catalogue_items(currency, availability, category, price)")
        conn.execute("""CREATE TABLE IF NOT EXISTS research_products (
            retailer TEXT NOT NULL,
            external_product_id TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            source_type TEXT NOT NULL,
            normalized_json TEXT NOT NULL,
            PRIMARY KEY (retailer, external_product_id)
        )""")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
