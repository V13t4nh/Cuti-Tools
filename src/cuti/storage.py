"""SQLite storage layer: schema, migrations, queries and the alert outbox.

One file, one database. FTS5 backs the comparable prefilter. All writes for a
logical operation (ingest, deal insert, quote + comparables + alert) happen in
a single transaction so partial writes are never observable.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from .errors import StorageError
from .models import Condition, Deal, Lot, WatchForm

SCHEMA_VERSION = 3

# Checkbox-style flags are stored as text so anyone reading the database sees an
# unambiguous value instead of 0/1.
YES = "__YES__"
NO = "__NO__"

# Columns added after v1. Applied with ALTER TABLE when an older database is
# opened, because CREATE TABLE IF NOT EXISTS cannot add columns.
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
    condition_tag TEXT NOT NULL,
    form TEXT NOT NULL DEFAULT 'unknown',
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

def _utcnow(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat()

def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

def _add_missing_lot_columns(conn: sqlite3.Connection) -> None:
    """Bring an older `lots` table up to the current column set."""
    existing = _table_columns(conn, "lots")
    for name, definition in LOT_COLUMNS_AFTER_V1:
        if name not in existing:
            conn.execute(f"ALTER TABLE lots ADD COLUMN {name} {definition}")

def _current_version(conn: sqlite3.Connection) -> int:
    """Schema version of an existing database, or 0 for an empty file.

    A brand new database has no `schema_meta` table yet, so the table must be
    probed before it is read.
    """
    has_meta = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_meta'"
    ).fetchone()
    if has_meta is None:
        return 0
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'version'"
    ).fetchone()
    return int(row[0]) if row else 0

def _migrate(conn: sqlite3.Connection) -> None:
    current = _current_version(conn)
    if current == 0:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES ('version', ?)",
            (str(SCHEMA_VERSION),),
        )
    elif current < SCHEMA_VERSION:
        # Every migration so far is additive: new tables plus new columns on
        # `lots`. Columns come first: the FTS triggers created by SCHEMA_SQL read
        # columns such as `form`, so creating them against an older `lots` table
        # would fail with "no such column".
        _add_missing_lot_columns(conn)
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "UPDATE schema_meta SET value = ? WHERE key = 'version'", (str(SCHEMA_VERSION),)
        )
    elif current > SCHEMA_VERSION:
        raise StorageError(f"database schema version {current} is newer than supported ({SCHEMA_VERSION})")

@contextlib.contextmanager
def open_db(path: Path) -> Iterator[sqlite3.Connection]:
    """Open (creating if needed) the SQLite database with sane pragmas."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        with conn:
            _migrate(conn)
        yield conn
    except sqlite3.DatabaseError as exc:
        raise StorageError(f"database error: {exc}") from exc
    finally:
        conn.close()

def _row_to_lot(row: sqlite3.Row) -> Lot:
    return Lot(
        lot_id=row["lot_id"],
        source=row["source"],
        title=row["title"],
        brand=row["brand"],
        model_key=row["model_key"],
        condition_tag=Condition(row["condition_tag"]),
        form=WatchForm(row["form"]),
        hearts=row["hearts"],
        sold=bool(row["sold"]),
        hammer_eur=row["hammer_eur"],
        opened_at=date.fromisoformat(row["opened_at"]),
        ended_at=date.fromisoformat(row["ended_at"]),
        url=row["url"],
        subtitle=row["subtitle"],
        bids_count=row["bids_count"],
        source_available=row["source_available"] == YES,
    )

def _with_row_factory(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    return conn

def upsert_lots(conn: sqlite3.Connection, lots: Iterable[Lot], now: datetime) -> int:
    written = 0
    timestamp = _utcnow(now)
    with conn:
        for lot in lots:
            conn.execute(
                """
                INSERT INTO lots (
                    lot_id, source, title, brand, model_key, condition_tag, form,
                    hearts, sold, hammer_eur, opened_at, ended_at, url, subtitle,
                    bids_count, source_available, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lot_id) DO UPDATE SET
                    source=excluded.source, title=excluded.title, brand=excluded.brand,
                    model_key=excluded.model_key, condition_tag=excluded.condition_tag,
                    form=excluded.form, hearts=excluded.hearts, sold=excluded.sold,
                    hammer_eur=excluded.hammer_eur, opened_at=excluded.opened_at,
                    ended_at=excluded.ended_at, url=excluded.url,
                    subtitle=excluded.subtitle, bids_count=excluded.bids_count,
                    updated_at=excluded.updated_at
                """,
                # source_available / source_checked_at are owned by the URL
                # checker, so re-ingesting a lot must not erase what the last
                # probe learned about the source page.
                (
                    lot.lot_id, lot.source, lot.title, lot.brand, lot.model_key,
                    lot.condition_tag.value, lot.form.value, lot.hearts, int(lot.sold),
                    lot.hammer_eur, lot.opened_at.isoformat(), lot.ended_at.isoformat(),
                    lot.url, lot.subtitle, lot.bids_count,
                    YES if lot.source_available else NO, timestamp,
                ),
            )
            written += 1
    return written

def fetch_lots_for_model(
    conn: sqlite3.Connection,
    model_key: str,
    condition: Condition,
    since: date,
    today: date,
) -> list[Lot]:
    _with_row_factory(conn)
    rows = conn.execute(
        """SELECT * FROM lots WHERE model_key = ? AND condition_tag = ?
           AND ended_at >= ? AND ended_at <= ? ORDER BY ended_at""",
        (model_key, condition.value, since.isoformat(), today.isoformat()),
    ).fetchall()
    return [_row_to_lot(row) for row in rows]

def fetch_lots_for_liquidity(conn: sqlite3.Connection, since: date) -> list[Lot]:
    _with_row_factory(conn)
    rows = conn.execute(
        "SELECT * FROM lots WHERE ended_at >= ? ORDER BY ended_at", (since.isoformat(),)
    ).fetchall()
    return [_row_to_lot(row) for row in rows]

def fetch_sold_lots_since(
    conn: sqlite3.Connection, condition: Condition, since: date
) -> list[Lot]:
    _with_row_factory(conn)
    rows = conn.execute(
        """SELECT * FROM lots WHERE condition_tag = ? AND sold = 1 AND ended_at >= ?
           ORDER BY ended_at""",
        (condition.value, since.isoformat()),
    ).fetchall()
    return [_row_to_lot(row) for row in rows]

def search_comparable_candidates(
    conn: sqlite3.Connection,
    *,
    fts_query: str,
    brand: str,
    model_key: str | None,
    condition_tag: Condition,
    since: date,
) -> list[Lot]:
    """FTS5 prefilter, optionally narrowed to an exact model_key."""
    _with_row_factory(conn)
    if not fts_query.strip():
        return []
    params: list[object] = [fts_query, brand, condition_tag.value, since.isoformat()]
    model_clause = ""
    if model_key is not None:
        model_clause = " AND l.model_key = ?"
        params.append(model_key)
    rows = conn.execute(
        f"""
        SELECT l.* FROM lots l
        JOIN lots_fts f ON f.rowid = l.rowid
        WHERE lots_fts MATCH ? AND l.brand = ? AND l.condition_tag = ? AND l.ended_at >= ?
        {model_clause}
        ORDER BY l.ended_at DESC
        """,
        params,
    ).fetchall()
    return [_row_to_lot(row) for row in rows]

@dataclass(frozen=True, slots=True)
class StoredDeal:
    id: int
    deal: Deal

def _row_to_deal(row: sqlite3.Row) -> Deal:
    return Deal(
        source=row["source"],
        raw_title=row["raw_title"],
        ask_vnd=row["ask_vnd"],
        url=row["url"],
        seen_at=date.fromisoformat(row["seen_at"]),
        model_key=row["model_key"],
        condition_tag=Condition(row["condition_tag"]),
        form=WatchForm(row["form"]),
        dedupe_hash=row["dedupe_hash"],
    )

def insert_deals_if_new(
    conn: sqlite3.Connection, deals: Iterable[Deal], now: datetime
) -> list[int]:
    inserted: list[int] = []
    timestamp = _utcnow(now)
    with conn:
        for deal in deals:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO deals (
                    source, raw_title, ask_vnd, url, seen_at, model_key,
                    condition_tag, form, dedupe_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    deal.source, deal.raw_title, deal.ask_vnd, deal.url,
                    deal.seen_at.isoformat(), deal.model_key, deal.condition_tag.value,
                    deal.form.value, deal.dedupe_hash, timestamp,
                ),
            )
            if cursor.rowcount:
                inserted.append(cursor.lastrowid)
    return inserted

def fetch_unquoted_deals(
    conn: sqlite3.Connection, *, since: date, until: date
) -> list[StoredDeal]:
    _with_row_factory(conn)
    rows = conn.execute(
        """SELECT * FROM deals WHERE quoted = 0 AND seen_at >= ? AND seen_at <= ?
           ORDER BY seen_at, id""",
        (since.isoformat(), until.isoformat()),
    ).fetchall()
    return [StoredDeal(id=row["id"], deal=_row_to_deal(row)) for row in rows]

@dataclass(frozen=True, slots=True)
class ComparableSnapshot:
    lot: Lot
    score: float

def insert_quote(
    conn: sqlite3.Connection,
    *,
    model_key: str,
    condition_tag: Condition,
    form: WatchForm,
    title: str,
    cost_vnd: int,
    sample_size: int,
    attempt_count: int,
    sell_through_rate: float,
    net_min_eur: float | None,
    net_avg_eur: float | None,
    net_max_eur: float | None,
    hammer_p25_eur: float | None,
    hammer_median_eur: float | None,
    hammer_p75_eur: float | None,
    median_days_to_close: float | None,
    threshold_eur: float,
    verdict: str,
    assumptions: dict[str, object],
    comparables: Iterable[ComparableSnapshot],
    deal_id: int | None,
    alert_payload: dict[str, object] | None,
    now: datetime,
) -> int:
    timestamp = _utcnow(now)
    with conn:
        cursor = conn.execute(
            """INSERT INTO quotes (
                deal_id, model_key, condition_tag, form, title, cost_vnd, sample_size,
                attempt_count, sell_through_rate, net_min_eur, net_avg_eur, net_max_eur,
                hammer_p25_eur, hammer_median_eur, hammer_p75_eur, median_days_to_close,
                threshold_eur, verdict, assumptions, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                deal_id, model_key, condition_tag.value, form.value, title, cost_vnd,
                sample_size, attempt_count, sell_through_rate, net_min_eur, net_avg_eur,
                net_max_eur, hammer_p25_eur, hammer_median_eur, hammer_p75_eur,
                median_days_to_close, threshold_eur, verdict,
                json.dumps(assumptions, sort_keys=True), timestamp,
            ),
        )
        quote_id = cursor.lastrowid
        for item in comparables:
            conn.execute(
                """INSERT INTO quote_comparables (quote_id, lot_id, score, snapshot)
                   VALUES (?, ?, ?, ?)""",
                (
                    quote_id, item.lot.lot_id, item.score,
                    json.dumps(
                        {
                            "lot_id": item.lot.lot_id,
                            "title": item.lot.title,
                            "hammer_eur": item.lot.hammer_eur,
                            "sold": item.lot.sold,
                            "ended_at": item.lot.ended_at.isoformat(),
                            "opened_at": item.lot.opened_at.isoformat(),
                            "hearts": item.lot.hearts,
                            "url": item.lot.url,
                        },
                        sort_keys=True,
                    ),
                ),
            )
        if deal_id is not None:
            conn.execute("UPDATE deals SET quoted = 1 WHERE id = ?", (deal_id,))
        if alert_payload is not None:
            conn.execute(
                """INSERT INTO alert_outbox (quote_id, payload, status, created_at)
                   VALUES (?, ?, 'pending', ?)""",
                (quote_id, json.dumps(alert_payload, sort_keys=True), timestamp),
            )
    return quote_id

@dataclass(frozen=True, slots=True)
class PendingAlert:
    id: int
    quote_id: int
    payload: dict[str, object]

def claim_pending_alerts(conn: sqlite3.Connection, now: datetime) -> list[PendingAlert]:
    _with_row_factory(conn)
    timestamp = _utcnow(now)
    with conn:
        rows = conn.execute(
            "SELECT id, quote_id, payload FROM alert_outbox WHERE status = 'pending'"
        ).fetchall()
        ids = [row["id"] for row in rows]
        if ids:
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE alert_outbox SET status = 'sending' WHERE id IN ({placeholders})",
                ids,
            )
    return [
        PendingAlert(id=row["id"], quote_id=row["quote_id"], payload=json.loads(row["payload"]))
        for row in rows
    ]

def mark_alert_sent(conn: sqlite3.Connection, alert_id: int, now: datetime) -> None:
    with conn:
        conn.execute(
            "UPDATE alert_outbox SET status = 'sent', sent_at = ? WHERE id = ?",
            (_utcnow(now), alert_id),
        )

def mark_alert_failed(
    conn: sqlite3.Connection, alert_id: int, error: str, *, max_attempts: int
) -> None:
    with conn:
        row = conn.execute(
            "SELECT attempts FROM alert_outbox WHERE id = ?", (alert_id,)
        ).fetchone()
        attempts = (row[0] if row else 0) + 1
        status = "dead" if attempts >= max_attempts else "pending"
        conn.execute(
            "UPDATE alert_outbox SET status = ?, attempts = ?, last_error = ? WHERE id = ?",
            (status, attempts, error, alert_id),
        )

def outbox_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, COUNT(*) FROM alert_outbox GROUP BY status"
    ).fetchall()
    counts = {"pending": 0, "sending": 0, "sent": 0, "dead": 0}
    counts.update({status: count for status, count in rows})
    return counts

def count_rows(conn: sqlite3.Connection, table: str) -> int:
    if table not in {
        "lots",
        "live_watch",
        "deals",
        "quotes",
        "quote_comparables",
        "alert_outbox",
    }:
        raise StorageError(f"unknown table {table!r}")
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

def fetch_quote_audit(conn: sqlite3.Connection, quote_id: int) -> dict[str, object]:
    _with_row_factory(conn)
    quote_row = conn.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
    if quote_row is None:
        raise StorageError(f"quote {quote_id} not found")
    comparable_rows = conn.execute(
        "SELECT lot_id, score, snapshot FROM quote_comparables WHERE quote_id = ? ORDER BY score DESC",
        (quote_id,),
    ).fetchall()
    assumptions = json.loads(quote_row["assumptions"])
    legacy_snapshot = assumptions.get("audit_version") != 2
    return {
        "quote_id": quote_row["id"],
        "title": quote_row["title"],
        "model_key": quote_row["model_key"],
        "condition": quote_row["condition_tag"],
        "form": quote_row["form"],
        "verdict": quote_row["verdict"],
        "created_at": quote_row["created_at"],
        "assumptions": assumptions,
        "legacy_snapshot": "unavailable" if legacy_snapshot else "available",
        "comparables": [
            {
                "lot_id": row["lot_id"],
                "score": row["score"],
                "snapshot": json.loads(row["snapshot"]),
            }
            for row in comparable_rows
        ],
    }

@dataclass(frozen=True, slots=True)
class LiveWatchRow:
    """One open lot being tracked until its bidding window ends."""

    lot_id: str
    source: str
    title: str
    subtitle: str | None
    url: str
    bidding_end_at: date | None

def _row_to_live_watch(row: sqlite3.Row) -> LiveWatchRow:
    end = row["bidding_end_at"]
    return LiveWatchRow(
        lot_id=row["lot_id"],
        source=row["source"],
        title=row["title"],
        subtitle=row["subtitle"],
        url=row["url"],
        bidding_end_at=date.fromisoformat(end) if end else None,
    )

def upsert_live_watch(
    conn: sqlite3.Connection, rows: Iterable[LiveWatchRow], now: datetime
) -> tuple[int, int]:
    """Track open lots. Returns (newly tracked, refreshed).

    first_seen_at is never overwritten: it records when the lot entered the
    queue, which is the only proof of how long a lot stayed open.
    """
    timestamp = _utcnow(now)
    tracked = 0
    refreshed = 0
    with conn:
        for row in rows:
            end = row.bidding_end_at.isoformat() if row.bidding_end_at else None
            exists = conn.execute(
                "SELECT 1 FROM live_watch WHERE lot_id = ?", (row.lot_id,)
            ).fetchone()
            conn.execute(
                """
                INSERT INTO live_watch (
                    lot_id, source, title, subtitle, url, bidding_end_at,
                    first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lot_id) DO UPDATE SET
                    source=excluded.source, title=excluded.title,
                    subtitle=excluded.subtitle, url=excluded.url,
                    bidding_end_at=excluded.bidding_end_at,
                    last_seen_at=excluded.last_seen_at
                """,
                (
                    row.lot_id, row.source, row.title, row.subtitle, row.url, end,
                    timestamp, timestamp,
                ),
            )
            if exists:
                refreshed += 1
            else:
                tracked += 1
    return tracked, refreshed

def fetch_live_watch_due(
    conn: sqlite3.Connection, *, until: date, limit: int
) -> list[LiveWatchRow]:
    """Tracked lots whose bidding window has ended, oldest close first.

    An unknown window (NULL) is treated as due: the lot must be probed once to
    learn whether it closed, otherwise it would sit in the queue forever.
    """
    if limit < 1:
        raise StorageError(f"limit must be >= 1, got {limit}")
    _with_row_factory(conn)
    rows = conn.execute(
        """SELECT * FROM live_watch
           WHERE bidding_end_at IS NULL OR bidding_end_at <= ?
           ORDER BY bidding_end_at IS NULL, bidding_end_at, lot_id
           LIMIT ?""",
        (until.isoformat(), limit),
    ).fetchall()
    return [_row_to_live_watch(row) for row in rows]

def delete_live_watch(conn: sqlite3.Connection, lot_ids: Iterable[str]) -> int:
    """Drop settled (or unreachable) lots from the work queue."""
    ids = list(lot_ids)
    if not ids:
        return 0
    with conn:
        cursor = conn.executemany(
            "DELETE FROM live_watch WHERE lot_id = ?", [(lot_id,) for lot_id in ids]
        )
    return cursor.rowcount if cursor.rowcount != -1 else len(ids)

def count_live_watch(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM live_watch").fetchone()[0]

def fetch_lots_for_source_check(
    conn: sqlite3.Connection, *, limit: int
) -> list[tuple[str, str]]:
    """Stored lots whose source page is still believed reachable.

    Never-checked lots come first, then the least recently checked ones, so a
    capped weekly run eventually covers the whole table.
    """
    if limit < 1:
        raise StorageError(f"limit must be >= 1, got {limit}")
    rows = conn.execute(
        """SELECT lot_id, url FROM lots
           WHERE source_available = ?
           ORDER BY source_checked_at IS NOT NULL, source_checked_at, ended_at
           LIMIT ?""",
        (YES, limit),
    ).fetchall()
    return [(row[0], row[1]) for row in rows]

def mark_source_availability(
    conn: sqlite3.Connection, results: dict[str, bool], now: datetime
) -> int:
    """Record whether each lot page can still be opened by a human.

    A dead page keeps its stored hammer price: the number stays usable as a
    comparable, it just can no longer be re-verified at the source.
    """
    timestamp = _utcnow(now)
    updated = 0
    with conn:
        for lot_id, alive in results.items():
            cursor = conn.execute(
                "UPDATE lots SET source_available = ?, source_checked_at = ? WHERE lot_id = ?",
                (YES if alive else NO, timestamp, lot_id),
            )
            updated += cursor.rowcount
    return updated
