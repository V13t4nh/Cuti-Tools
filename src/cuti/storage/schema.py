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
from .schema_ddl import SCHEMA_SQL
from .schema_migration import ensure_fts, ensure_media_queue
# Queue columns are additive to the established v4 schema and remain
# compatible with existing v4 databases during reopen.
SCHEMA_VERSION = 4

YES = "__YES__"
NO = "__NO__"
LOT_COLUMNS_AFTER_V1: tuple[tuple[str, str], ...] = (
    ("form", "TEXT NOT NULL DEFAULT 'unknown'"),
    ("subtitle", "TEXT"),
    ("bids_count", "INTEGER"),
    ("source_available", f"TEXT NOT NULL DEFAULT '{YES}'"),
    ("source_checked_at", "TEXT"),
    ("model", "TEXT"),
    ("ref_number", "TEXT"),
    ("caliber", "TEXT"),
    ("case_code", "TEXT"),
    ("movement", "TEXT"),
    ("case_material", "TEXT"),
    ("case_diameter_mm", "INTEGER"),
    ("specs_json", "TEXT"),
    ("ai_json", "TEXT"),
    ("needs_review", "INTEGER NOT NULL DEFAULT 0"),
    ("review_status", "TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'resolved', 'ignored'))"),
    ("reviewed_at", "TEXT"),
    ("override_json", "TEXT"),
)

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
        ensure_fts(conn)
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
        # Some v3 snapshots only retained the quote audit columns.  Keep
        # those rows intact while making the v4 index DDL applicable.
        if quotes_columns and "model_key" not in quotes_columns:
            conn.execute("ALTER TABLE quotes ADD COLUMN model_key TEXT")
        conn.executescript(SCHEMA_SQL)
        ensure_media_queue(conn)
        ensure_fts(conn)
        conn.execute("UPDATE schema_meta SET value = ? WHERE key = 'version'", (str(SCHEMA_VERSION),))
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    elif current == SCHEMA_VERSION:
        # v4 databases created before the user-facing catalog tables existed
        # receive the additive DDL on reopen; all statements are idempotent.
        conn.executescript(SCHEMA_SQL)
        ensure_media_queue(conn)
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
