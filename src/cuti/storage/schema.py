"""SQLite schema creation and migrations.

The query modules depend on this module for the database connection and the
small set of storage constants.  Keeping DDL and migration decisions here
makes the public :mod:`cuti.storage` facade independent of schema details.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..errors import StorageError
SCHEMA_VERSION = 3

YES = "__YES__"
NO = "__NO__"
LOT_COLUMNS_AFTER_V1: tuple[tuple[str, str], ...] = (
    ("form", "TEXT NOT NULL DEFAULT 'unknown'"),
    ("subtitle", "TEXT"),
    ("bids_count", "INTEGER"),
    ("source_available", f"TEXT NOT NULL DEFAULT '{YES}'"),
    ("source_checked_at", "TEXT"),
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lots (
    lot_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    brand TEXT NOT NULL,
    model_key TEXT NOT NULL,
    condition_tag TEXT NOT NULL CHECK (condition_tag IN ('naked', 'box', 'papers', 'fullset')),
    form TEXT NOT NULL DEFAULT 'unknown' CHECK (form IN ('round', 'rectangular', 'square', 'tonneau', 'other', 'unknown')),
    hearts INTEGER NOT NULL,
    sold INTEGER NOT NULL,
    hammer_eur INTEGER,
    opened_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    url TEXT NOT NULL,
    subtitle TEXT,
    bids_count INTEGER,
    source_available TEXT NOT NULL DEFAULT '__YES__',
    source_checked_at TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lots_model ON lots(model_key, condition_tag, ended_at);
CREATE INDEX IF NOT EXISTS idx_lots_brand_form ON lots(brand, form, ended_at);

CREATE VIRTUAL TABLE IF NOT EXISTS lots_fts USING fts5(
    title, content='lots', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS lots_ai AFTER INSERT ON lots BEGIN
    INSERT INTO lots_fts(rowid, title) VALUES (new.rowid, new.title);
END;
CREATE TRIGGER IF NOT EXISTS lots_ad AFTER DELETE ON lots BEGIN
    INSERT INTO lots_fts(lots_fts, rowid, title) VALUES ('delete', old.rowid, old.title);
END;
CREATE TRIGGER IF NOT EXISTS lots_au AFTER UPDATE ON lots BEGIN
    INSERT INTO lots_fts(lots_fts, rowid, title) VALUES ('delete', old.rowid, old.title);
    INSERT INTO lots_fts(rowid, title) VALUES (new.rowid, new.title);
END;

-- Lots that are still open. The source cannot be searched for closed lots, so
-- ids are captured while bidding runs and settled once bidding ends. Rows are
-- deleted on settle: this is a work queue, not history.
CREATE TABLE IF NOT EXISTS live_watch (
    lot_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    subtitle TEXT,
    url TEXT NOT NULL,
    bidding_end_at TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_live_watch_end ON live_watch(bidding_end_at);

CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    raw_title TEXT NOT NULL,
    ask_vnd INTEGER NOT NULL,
    url TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    model_key TEXT NOT NULL,
    condition_tag TEXT NOT NULL,
    form TEXT NOT NULL DEFAULT 'unknown',
    dedupe_hash TEXT NOT NULL UNIQUE,
    quoted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deals_quoted ON deals(quoted, seen_at);

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER REFERENCES deals(id),
    model_key TEXT NOT NULL,
    condition_tag TEXT NOT NULL,
    form TEXT NOT NULL DEFAULT 'unknown',
    title TEXT NOT NULL,
    cost_vnd INTEGER NOT NULL,
    sample_size INTEGER NOT NULL,
    attempt_count INTEGER NOT NULL,
    sell_through_rate REAL NOT NULL,
    net_min_eur REAL,
    net_avg_eur REAL,
    net_max_eur REAL,
    hammer_p25_eur REAL,
    hammer_median_eur REAL,
    hammer_p75_eur REAL,
    median_days_to_close REAL,
    threshold_eur REAL NOT NULL,
    verdict TEXT NOT NULL,
    assumptions TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quotes_model ON quotes(model_key, created_at);

CREATE TABLE IF NOT EXISTS quote_comparables (
    quote_id INTEGER NOT NULL REFERENCES quotes(id),
    lot_id TEXT NOT NULL,
    score REAL NOT NULL,
    snapshot TEXT NOT NULL,
    PRIMARY KEY (quote_id, lot_id)
);

CREATE TABLE IF NOT EXISTS alert_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL REFERENCES quotes(id),
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON alert_outbox(status, created_at);
"""
def utcnow(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat()
def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
def _add_missing_lot_columns(conn: sqlite3.Connection) -> None:
    """Bring an older ``lots`` table up to the current column set."""
    existing = _table_columns(conn, "lots")
    for name, definition in LOT_COLUMNS_AFTER_V1:
        if name not in existing:
            conn.execute(f"ALTER TABLE lots ADD COLUMN {name} {definition}")
def _current_version(conn: sqlite3.Connection) -> int:
    """Return the schema version, or zero for an empty database file."""
    has_meta = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_meta'"
    ).fetchone()
    if has_meta is None:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    row = conn.execute("SELECT value FROM schema_meta WHERE key = 'version'").fetchone()
    return int(row[0]) if row else 0
def migrate(conn: sqlite3.Connection) -> None:
    """Create a new schema or migrate an older supported database."""
    current = _current_version(conn)
    if current == 0:
        conn.executescript(SCHEMA_SQL)
        conn.execute("INSERT INTO schema_meta(key, value) VALUES ('version', ?)",
                     (str(SCHEMA_VERSION),))
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    elif current < SCHEMA_VERSION:
        lots_columns = _table_columns(conn, "lots")
        quotes_columns = _table_columns(conn, "quotes")
        if "model_key" not in lots_columns or (
            quotes_columns and "assumptions" not in quotes_columns
        ):
            legacy_quotes = (
                conn.execute("SELECT id, deal_id, sample_size FROM quotes").fetchall()
                if quotes_columns else []
            )
            conn.executescript(
                """
                DROP TABLE IF EXISTS alert_outbox;
                DROP TABLE IF EXISTS quote_comparables;
                DROP TABLE IF EXISTS quotes;
                DROP TABLE IF EXISTS deals;
                DROP TABLE IF EXISTS lots;
                DROP TABLE IF EXISTS schema_meta;
                """
            )
            conn.executescript(SCHEMA_SQL)
            timestamp = datetime.now(timezone.utc).isoformat()
            for row in legacy_quotes:
                sample_size = int(row[2] or 0)
                conn.execute(
                    """INSERT INTO quotes (
                        id, deal_id, model_key, condition_tag, form, title, cost_vnd,
                        sample_size, attempt_count, sell_through_rate, net_min_eur,
                        net_avg_eur, net_max_eur, hammer_p25_eur, hammer_median_eur,
                        hammer_p75_eur, median_days_to_close, threshold_eur, verdict,
                        assumptions, created_at
                    ) VALUES (?, ?, 'legacy:unknown', 'naked', 'unknown', 'legacy', 0,
                        ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0,
                        'insufficient_data', ?, ?)""",
                    (
                        row[0], row[1], sample_size, sample_size,
                        1.0 if sample_size else 0.0,
                        json.dumps({"audit_version": 1, "legacy_snapshot": "unavailable"}, sort_keys=True),
                        timestamp,
                    ),
                )
            conn.execute("INSERT INTO schema_meta(key, value) VALUES ('version', ?)",
                         (str(SCHEMA_VERSION),))
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            return
        # Columns must be added before FTS triggers are created against them.
        _add_missing_lot_columns(conn)
        conn.executescript(SCHEMA_SQL)
        conn.execute("UPDATE schema_meta SET value = ? WHERE key = 'version'", (str(SCHEMA_VERSION),))
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    elif current > SCHEMA_VERSION:
        raise StorageError(
            f"database schema version {current} is newer than supported ({SCHEMA_VERSION})"
        )
def connect(path: Path) -> sqlite3.Connection:
    """Open (creating if needed) the SQLite database with sane pragmas."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        with conn:
            migrate(conn)
        conn.row_factory = sqlite3.Row
        return conn
    except StorageError:
        conn.close()
        raise
    except sqlite3.DatabaseError as exc:
        conn.close()
        raise StorageError(f"database error: {exc}") from exc
