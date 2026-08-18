"""Lot ingestion and comparable search queries."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from ..errors import StorageError
from ..models import Condition, Lot, WatchForm
from .schema import NO, YES, utcnow


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
    timestamp = utcnow(now)
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
                # source availability belongs to the URL checker and is not
                # overwritten by re-ingesting a lot.
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


def search_sold_lots(
    conn: sqlite3.Connection,
    *,
    fts_query: str,
    brand: str,
    model_key: str | None,
    condition_tag: Condition,
    since: date,
    limit: int | None = None,
    include_unsold: bool = False,
) -> list[Lot]:
    """Search sold lots, optionally retaining unsold attempts for pricing."""
    _with_row_factory(conn)
    if not fts_query.strip():
        return []
    if limit is not None and limit <= 0:
        raise StorageError(f"limit must be positive, got {limit}")
    params: list[object] = [fts_query, brand, condition_tag.value, since.isoformat()]
    sold_clause = "" if include_unsold else " AND l.sold = 1"
    model_clause = ""
    if model_key is not None:
        model_clause = " AND l.model_key = ?"
        params.append(model_key)
    rows = conn.execute(
        f"""
        SELECT l.* FROM lots l
        JOIN lots_fts f ON f.rowid = l.rowid
        WHERE lots_fts MATCH ? AND l.brand = ? AND l.condition_tag = ? AND l.ended_at >= ?
        {sold_clause}
        {model_clause}
        ORDER BY l.ended_at DESC
        {"LIMIT ?" if limit is not None else ""}
        """,
        [*params, *([limit] if limit is not None else [])],
    ).fetchall()
    return [_row_to_lot(row) for row in rows]
