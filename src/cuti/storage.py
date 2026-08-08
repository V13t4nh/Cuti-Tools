"""SQLite persistence, explicit schema migration, audit snapshots and alert outbox."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .errors import StorageError
from .models import Condition, Deal, Lot, WatchForm

SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lots (
    lot_id        TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    title         TEXT NOT NULL,
    brand         TEXT NOT NULL,
    model_key     TEXT NOT NULL,
    condition_tag TEXT NOT NULL CHECK (condition_tag IN ('naked','box','papers','fullset')),
    form           TEXT NOT NULL CHECK (form IN ('round','rectangular','square','tonneau','other','unknown')),
    hearts        INTEGER NOT NULL CHECK (hearts >= 0),
    sold          INTEGER NOT NULL CHECK (sold IN (0, 1)),
    hammer_eur    INTEGER CHECK (hammer_eur IS NULL OR hammer_eur > 0),
    opened_at     TEXT NOT NULL,
    ended_at      TEXT NOT NULL,
    days_to_close INTEGER NOT NULL CHECK (days_to_close >= 0),
    url           TEXT NOT NULL,
    ingested_at   TEXT NOT NULL,
    CHECK ((sold = 1 AND hammer_eur IS NOT NULL) OR (sold = 0 AND hammer_eur IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_lots_model ON lots (brand, model_key, condition_tag, ended_at);
CREATE INDEX IF NOT EXISTS idx_lots_liquidity ON lots (brand, form, ended_at);

CREATE VIRTUAL TABLE IF NOT EXISTS lots_fts USING fts5 (
    title,
    model_key,
    content='lots',
    content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS lots_ai AFTER INSERT ON lots BEGIN
    INSERT INTO lots_fts (rowid, title, model_key) VALUES (new.rowid, new.title, new.model_key);
END;
CREATE TRIGGER IF NOT EXISTS lots_ad AFTER DELETE ON lots BEGIN
    INSERT INTO lots_fts (lots_fts, rowid, title, model_key)
    VALUES ('delete', old.rowid, old.title, old.model_key);
END;
CREATE TRIGGER IF NOT EXISTS lots_au AFTER UPDATE ON lots BEGIN
    INSERT INTO lots_fts (lots_fts, rowid, title, model_key)
    VALUES ('delete', old.rowid, old.title, old.model_key);
    INSERT INTO lots_fts (rowid, title, model_key) VALUES (new.rowid, new.title, new.model_key);
END;

CREATE TABLE IF NOT EXISTS deals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    raw_title     TEXT NOT NULL,
    ask_vnd       INTEGER NOT NULL CHECK (ask_vnd > 0),
    model_key     TEXT NOT NULL,
    condition_tag TEXT NOT NULL CHECK (condition_tag IN ('naked','box','papers','fullset')),
    form           TEXT NOT NULL CHECK (form IN ('round','rectangular','square','tonneau','other','unknown')),
    url           TEXT NOT NULL,
    seen_at       TEXT NOT NULL,
    dedupe_hash   TEXT NOT NULL UNIQUE,
    ingested_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deals_seen_at ON deals (seen_at, id);

CREATE TABLE IF NOT EXISTS quotes (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    model_key            TEXT NOT NULL,
    condition_tag        TEXT NOT NULL CHECK (condition_tag IN ('naked','box','papers','fullset')),
    form                  TEXT NOT NULL CHECK (form IN ('round','rectangular','square','tonneau','other','unknown')),
    title                 TEXT NOT NULL,
    cost_vnd              INTEGER NOT NULL CHECK (cost_vnd > 0),
    sample_size           INTEGER NOT NULL CHECK (sample_size >= 0),
    attempt_count         INTEGER NOT NULL CHECK (attempt_count >= sample_size),
    sell_through_rate     REAL NOT NULL CHECK (sell_through_rate >= 0 AND sell_through_rate <= 1),
    net_min_eur           REAL,
    net_avg_eur           REAL,
    net_max_eur           REAL,
    hammer_p25_eur        REAL,
    hammer_median_eur     REAL,
    hammer_p75_eur        REAL,
    median_days_to_close  REAL,
    threshold_eur         REAL NOT NULL,
    verdict               TEXT NOT NULL CHECK (verdict IN ('green','yellow','red','insufficient_data')),
    assumptions_json      TEXT NOT NULL,
    deal_id               INTEGER UNIQUE REFERENCES deals (id),
    created_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quotes_model ON quotes (model_key, created_at);

CREATE TABLE IF NOT EXISTS quote_comparables (
    quote_id       INTEGER NOT NULL REFERENCES quotes (id) ON DELETE CASCADE,
    lot_id         TEXT NOT NULL,
    title          TEXT NOT NULL,
    model_key      TEXT NOT NULL,
    condition_tag  TEXT NOT NULL,
    form           TEXT NOT NULL,
    score          REAL NOT NULL CHECK (score >= 0 AND score <= 1),
    sold           INTEGER NOT NULL CHECK (sold IN (0, 1)),
    hammer_eur     INTEGER,
    ended_at       TEXT NOT NULL,
    days_to_close  INTEGER NOT NULL,
    PRIMARY KEY (quote_id, lot_id)
);

CREATE TABLE IF NOT EXISTS alert_outbox (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id    INTEGER NOT NULL UNIQUE REFERENCES quotes (id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','sending','sent','dead')),
    attempts    INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error  TEXT,
    claimed_at  TEXT,
    created_at  TEXT NOT NULL,
    sent_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_alert_outbox_status ON alert_outbox (status, id);
"""

MIGRATION_V1_TO_V2 = """
ALTER TABLE lots ADD COLUMN form TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE deals ADD COLUMN form TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE quotes ADD COLUMN form TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE quotes ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE quotes ADD COLUMN sell_through_rate REAL NOT NULL DEFAULT 0;
ALTER TABLE quotes ADD COLUMN hammer_p25_eur REAL;
ALTER TABLE quotes ADD COLUMN hammer_median_eur REAL;
ALTER TABLE quotes ADD COLUMN hammer_p75_eur REAL;
ALTER TABLE quotes ADD COLUMN median_days_to_close REAL;
ALTER TABLE quotes ADD COLUMN assumptions_json TEXT NOT NULL DEFAULT '{}';
UPDATE quotes
SET attempt_count = sample_size,
    sell_through_rate = CASE WHEN sample_size > 0 THEN 1.0 ELSE 0.0 END,
    assumptions_json = '{"audit_version":1,"legacy_snapshot":"unavailable"}';
CREATE UNIQUE INDEX IF NOT EXISTS idx_quotes_deal_unique ON quotes (deal_id) WHERE deal_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_lots_liquidity ON lots (brand, form, ended_at);
CREATE TABLE IF NOT EXISTS quote_comparables (
    quote_id INTEGER NOT NULL REFERENCES quotes (id) ON DELETE CASCADE,
    lot_id TEXT NOT NULL, title TEXT NOT NULL, model_key TEXT NOT NULL,
    condition_tag TEXT NOT NULL, form TEXT NOT NULL, score REAL NOT NULL,
    sold INTEGER NOT NULL, hammer_eur INTEGER, ended_at TEXT NOT NULL,
    days_to_close INTEGER NOT NULL, PRIMARY KEY (quote_id, lot_id)
);
CREATE TABLE IF NOT EXISTS alert_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL UNIQUE REFERENCES quotes (id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sending','sent','dead')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT, claimed_at TEXT, created_at TEXT NOT NULL, sent_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_alert_outbox_status ON alert_outbox (status, id);
"""


@dataclass(frozen=True, slots=True)
class ComparableSnapshot:
    lot: Lot
    score: float


@dataclass(frozen=True, slots=True)
class StoredDeal:
    id: int
    deal: Deal


@dataclass(frozen=True, slots=True)
class PendingAlert:
    id: int
    quote_id: int
    payload: dict[str, Any]
    attempts: int


def _iso(value: date) -> str:
    return value.isoformat()


def _parse_date(value: str, context: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise StorageError(f"{context}: invalid ISO date {value!r}") from exc


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
        opened_at=_parse_date(row["opened_at"], row["lot_id"]),
        ended_at=_parse_date(row["ended_at"], row["lot_id"]),
        url=row["url"],
    )


def _row_to_deal(row: sqlite3.Row) -> StoredDeal:
    return StoredDeal(
        id=int(row["id"]),
        deal=Deal(
            source=row["source"],
            raw_title=row["raw_title"],
            ask_vnd=row["ask_vnd"],
            url=row["url"],
            seen_at=_parse_date(row["seen_at"], f"deal {row['id']}"),
            model_key=row["model_key"],
            condition_tag=Condition(row["condition_tag"]),
            form=WatchForm(row["form"]),
            dedupe_hash=row["dedupe_hash"],
        ),
    )


def _require_fts5(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.cuti_fts_probe USING fts5(value)")
        conn.execute("DROP TABLE temp.cuti_fts_probe")
    except sqlite3.Error as exc:
        raise StorageError("this SQLite build lacks FTS5 support") from exc


def _migrate(conn: sqlite3.Connection) -> None:
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version > SCHEMA_VERSION:
        raise StorageError(
            f"database schema version {version} is newer than supported version {SCHEMA_VERSION}"
        )
    try:
        if version == 0:
            conn.executescript(SCHEMA_SQL)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        elif version == 1:
            conn.executescript(
                "BEGIN IMMEDIATE;\n"
                + MIGRATION_V1_TO_V2
                + f"\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;"
            )
        else:
            conn.executescript(SCHEMA_SQL)
        deal_columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(deals)").fetchall()
        }
        if "seen_at" in deal_columns:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_seen_at ON deals (seen_at, id)")
    except sqlite3.Error as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise StorageError(f"database migration failed at version {version}: {exc}") from exc


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a database and migrate it to the exact supported schema."""
    conn: sqlite3.Connection | None = None
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, isolation_level=None, timeout=10)
        conn.row_factory = sqlite3.Row
        _require_fts5(conn)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        _migrate(conn)
        return conn
    except OSError as exc:
        if conn is not None:
            conn.close()
        raise StorageError(f"cannot open database {db_path}: {exc}") from exc
    except sqlite3.Error as exc:
        if conn is not None:
            conn.close()
        raise StorageError(f"cannot open database {db_path}: {exc}") from exc
    except BaseException:
        if conn is not None:
            conn.close()
        raise


@contextmanager
def open_db(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def upsert_lots(conn: sqlite3.Connection, lots: Iterable[Lot], now: datetime) -> int:
    rows = [
        (
            lot.lot_id,
            lot.source,
            lot.title,
            lot.brand,
            lot.model_key,
            lot.condition_tag.value,
            lot.form.value,
            lot.hearts,
            int(lot.sold),
            lot.hammer_eur,
            _iso(lot.opened_at),
            _iso(lot.ended_at),
            lot.days_to_close,
            lot.url,
            now.isoformat(timespec="seconds"),
        )
        for lot in lots
    ]
    if not rows:
        return 0
    with transaction(conn):
        conn.executemany(
            """
            INSERT INTO lots (lot_id, source, title, brand, model_key, condition_tag, form,
                              hearts, sold, hammer_eur, opened_at, ended_at,
                              days_to_close, url, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (lot_id) DO UPDATE SET
                source=excluded.source, title=excluded.title, brand=excluded.brand,
                model_key=excluded.model_key, condition_tag=excluded.condition_tag,
                form=excluded.form, hearts=excluded.hearts, sold=excluded.sold,
                hammer_eur=excluded.hammer_eur, opened_at=excluded.opened_at,
                ended_at=excluded.ended_at, days_to_close=excluded.days_to_close,
                url=excluded.url, ingested_at=excluded.ingested_at
            """,
            rows,
        )
    return len(rows)


def insert_deal_if_new(conn: sqlite3.Connection, deal: Deal, now: datetime) -> int | None:
    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO deals (source, raw_title, ask_vnd, model_key, condition_tag, form,
                               url, seen_at, dedupe_hash, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (dedupe_hash) DO NOTHING
            """,
            (
                deal.source,
                deal.raw_title,
                deal.ask_vnd,
                deal.model_key,
                deal.condition_tag.value,
                deal.form.value,
                deal.url,
                _iso(deal.seen_at),
                deal.dedupe_hash,
                now.isoformat(timespec="seconds"),
            ),
        )
    return int(cursor.lastrowid) if cursor.rowcount == 1 else None


def insert_deals_if_new(
    conn: sqlite3.Connection, deals: Iterable[Deal], now: datetime
) -> tuple[int, ...]:
    """Insert one validated feed as a transaction and return newly assigned ids."""
    ids: list[int] = []
    with transaction(conn):
        for deal in deals:
            cursor = conn.execute(
                """
                INSERT INTO deals (source, raw_title, ask_vnd, model_key, condition_tag, form,
                                   url, seen_at, dedupe_hash, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (dedupe_hash) DO NOTHING
                """,
                (
                    deal.source,
                    deal.raw_title,
                    deal.ask_vnd,
                    deal.model_key,
                    deal.condition_tag.value,
                    deal.form.value,
                    deal.url,
                    _iso(deal.seen_at),
                    deal.dedupe_hash,
                    now.isoformat(timespec="seconds"),
                ),
            )
            if cursor.rowcount == 1:
                ids.append(int(cursor.lastrowid))
    return tuple(ids)


def fetch_unquoted_deals(
    conn: sqlite3.Connection, *, since: date, until: date
) -> list[StoredDeal]:
    rows = conn.execute(
        """
        SELECT deals.* FROM deals
        LEFT JOIN quotes ON quotes.deal_id = deals.id
        WHERE quotes.id IS NULL AND deals.seen_at BETWEEN ? AND ?
        ORDER BY deals.id
        """,
        (_iso(since), _iso(until)),
    ).fetchall()
    return [_row_to_deal(row) for row in rows]


def insert_quote(
    conn: sqlite3.Connection,
    *,
    model_key: str,
    condition_tag: Condition,
    form: WatchForm = WatchForm.UNKNOWN,
    title: str,
    cost_vnd: int,
    sample_size: int,
    attempt_count: int | None = None,
    sell_through_rate: float | None = None,
    net_min_eur: float | None,
    net_avg_eur: float | None,
    net_max_eur: float | None,
    hammer_p25_eur: float | None = None,
    hammer_median_eur: float | None = None,
    hammer_p75_eur: float | None = None,
    median_days_to_close: float | None = None,
    threshold_eur: float,
    verdict: str,
    assumptions: dict[str, Any] | None = None,
    comparables: Iterable[ComparableSnapshot] = (),
    deal_id: int | None,
    alert_payload: dict[str, Any] | None = None,
    now: datetime,
) -> int:
    snapshots = list(comparables)
    attempts = sample_size if attempt_count is None else attempt_count
    sell_through = (
        sample_size / attempts if sell_through_rate is None and attempts else sell_through_rate or 0.0
    )
    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO quotes (
                model_key, condition_tag, form, title, cost_vnd, sample_size,
                attempt_count, sell_through_rate, net_min_eur, net_avg_eur,
                net_max_eur, hammer_p25_eur, hammer_median_eur, hammer_p75_eur,
                median_days_to_close, threshold_eur, verdict, assumptions_json,
                deal_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_key,
                condition_tag.value,
                form.value,
                title,
                cost_vnd,
                sample_size,
                attempts,
                sell_through,
                net_min_eur,
                net_avg_eur,
                net_max_eur,
                hammer_p25_eur,
                hammer_median_eur,
                hammer_p75_eur,
                median_days_to_close,
                threshold_eur,
                verdict,
                json.dumps(assumptions or {}, sort_keys=True, separators=(",", ":")),
                deal_id,
                now.isoformat(timespec="seconds"),
            ),
        )
        quote_id = int(cursor.lastrowid)
        conn.executemany(
            """
            INSERT INTO quote_comparables (
                quote_id, lot_id, title, model_key, condition_tag, form, score,
                sold, hammer_eur, ended_at, days_to_close
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    quote_id,
                    item.lot.lot_id,
                    item.lot.title,
                    item.lot.model_key,
                    item.lot.condition_tag.value,
                    item.lot.form.value,
                    item.score,
                    int(item.lot.sold),
                    item.lot.hammer_eur,
                    _iso(item.lot.ended_at),
                    item.lot.days_to_close,
                )
                for item in snapshots
            ],
        )
        if alert_payload is not None:
            payload = {**alert_payload, "quote_id": quote_id}
            conn.execute(
                """
                INSERT INTO alert_outbox (quote_id, payload_json, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    quote_id,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    now.isoformat(timespec="seconds"),
                ),
            )
    return quote_id


def search_comparable_candidates(
    conn: sqlite3.Connection,
    *,
    fts_query: str,
    brand: str,
    model_key: str | None,
    condition_tag: Condition,
    since: date,
) -> list[Lot]:
    if model_key is not None:
        rows = conn.execute(
            """
            SELECT * FROM lots
            WHERE brand = ? AND model_key = ? AND condition_tag = ? AND ended_at >= ?
            ORDER BY ended_at DESC, lot_id
            """,
            (brand, model_key, condition_tag.value, _iso(since)),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT lots.* FROM lots_fts
            JOIN lots ON lots.rowid = lots_fts.rowid
            WHERE lots_fts MATCH ? AND lots.brand = ? AND lots.condition_tag = ?
              AND lots.ended_at >= ?
            ORDER BY bm25(lots_fts), lots.ended_at DESC
            """,
            (fts_query, brand, condition_tag.value, _iso(since)),
        ).fetchall()
    return [_row_to_lot(row) for row in rows]


def search_sold_lots(
    conn: sqlite3.Connection,
    *,
    fts_query: str,
    condition_tag: Condition,
    since: date,
    limit: int,
) -> list[Lot]:
    """Compatibility wrapper used by older callers and focused storage tests."""
    if limit <= 0:
        raise StorageError(f"limit must be > 0, got {limit}")
    rows = conn.execute(
        """
        SELECT lots.* FROM lots_fts
        JOIN lots ON lots.rowid = lots_fts.rowid
        WHERE lots_fts MATCH ? AND lots.sold = 1 AND lots.condition_tag = ?
          AND lots.ended_at >= ?
        ORDER BY bm25(lots_fts) LIMIT ?
        """,
        (fts_query, condition_tag.value, _iso(since), limit),
    ).fetchall()
    return [_row_to_lot(row) for row in rows]


def fetch_sold_lots_since(
    conn: sqlite3.Connection, condition_tag: Condition, since: date
) -> list[Lot]:
    rows = conn.execute(
        """
        SELECT * FROM lots
        WHERE sold = 1 AND condition_tag = ? AND ended_at >= ?
        ORDER BY ended_at DESC
        """,
        (condition_tag.value, _iso(since)),
    ).fetchall()
    return [_row_to_lot(row) for row in rows]


def fetch_lots_for_liquidity(conn: sqlite3.Connection, since: date) -> list[Lot]:
    rows = conn.execute(
        "SELECT * FROM lots WHERE ended_at >= ? ORDER BY brand, form, ended_at",
        (_iso(since),),
    ).fetchall()
    return [_row_to_lot(row) for row in rows]


def fetch_lots_for_model(
    conn: sqlite3.Connection, model_key: str, condition: Condition, since: date, today: date
) -> list[Lot]:
    rows = conn.execute(
        """
        SELECT * FROM lots
        WHERE model_key = ? AND condition_tag = ? AND ended_at BETWEEN ? AND ?
        ORDER BY ended_at, lot_id
        """,
        (model_key, condition.value, _iso(since), _iso(today)),
    ).fetchall()
    return [_row_to_lot(row) for row in rows]


def claim_pending_alerts(
    conn: sqlite3.Connection,
    now: datetime,
    *,
    limit: int = 100,
    lease_seconds: int = 300,
) -> list[PendingAlert]:
    cutoff = now - timedelta(seconds=lease_seconds)
    with transaction(conn):
        conn.execute(
            """
            UPDATE alert_outbox SET status='pending', claimed_at=NULL
            WHERE status='sending' AND claimed_at < ?
            """,
            (cutoff.isoformat(timespec="seconds"),),
        )
        rows = conn.execute(
            "SELECT * FROM alert_outbox WHERE status='pending' ORDER BY id LIMIT ?",
            (limit,),
        ).fetchall()
        pending: list[PendingAlert] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError as exc:
                raise StorageError(f"alert {row['id']} has invalid JSON payload") from exc
            if not isinstance(payload, dict):
                raise StorageError(f"alert {row['id']} payload must be a JSON object")
            pending.append(
                PendingAlert(
                    id=int(row["id"]),
                    quote_id=int(row["quote_id"]),
                    payload=payload,
                    attempts=int(row["attempts"]),
                )
            )
        ids = [int(row["id"]) for row in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"UPDATE alert_outbox SET status='sending', claimed_at=? WHERE id IN ({placeholders})",
                (now.isoformat(timespec="seconds"), *ids),
            )
    return pending


def mark_alert_sent(conn: sqlite3.Connection, alert_id: int, now: datetime) -> None:
    with transaction(conn):
        cursor = conn.execute(
            """
            UPDATE alert_outbox
            SET status='sent', attempts=attempts+1, sent_at=?, claimed_at=NULL, last_error=NULL
            WHERE id=? AND status='sending'
            """,
            (now.isoformat(timespec="seconds"), alert_id),
        )
        if cursor.rowcount != 1:
            raise StorageError(f"alert {alert_id} is not currently claimed")


def mark_alert_failed(
    conn: sqlite3.Connection, alert_id: int, error: str, *, max_attempts: int
) -> None:
    with transaction(conn):
        row = conn.execute(
            "SELECT attempts FROM alert_outbox WHERE id=? AND status='sending'", (alert_id,)
        ).fetchone()
        if row is None:
            raise StorageError(f"alert {alert_id} is not currently claimed")
        attempts = int(row["attempts"]) + 1
        status = "dead" if attempts >= max_attempts else "pending"
        conn.execute(
            """
            UPDATE alert_outbox
            SET status=?, attempts=?, last_error=?, claimed_at=NULL
            WHERE id=?
            """,
            (status, attempts, error[:1000], alert_id),
        )


def outbox_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {status: 0 for status in ("pending", "sending", "sent", "dead")}
    for row in conn.execute("SELECT status, COUNT(*) AS n FROM alert_outbox GROUP BY status"):
        counts[row["status"]] = int(row["n"])
    return counts


def fetch_quote_audit(conn: sqlite3.Connection, quote_id: int) -> dict[str, Any]:
    quote_row = conn.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
    if quote_row is None:
        raise StorageError(f"quote {quote_id} not found")
    comparable_rows = conn.execute(
        "SELECT * FROM quote_comparables WHERE quote_id=? ORDER BY score DESC, lot_id",
        (quote_id,),
    ).fetchall()
    quote_data = dict(quote_row)
    assumptions = json.loads(quote_data.pop("assumptions_json"))
    if not assumptions:
        assumptions = {
            "audit_version": 0,
            "legacy_snapshot": "unavailable",
        }
    quote_data["assumptions"] = assumptions
    quote_data["comparables"] = [dict(row) for row in comparable_rows]
    return quote_data


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    allowed = {"lots", "deals", "quotes", "quote_comparables", "alert_outbox"}
    if table not in allowed:
        raise StorageError(f"unknown table {table!r}")
    return int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
