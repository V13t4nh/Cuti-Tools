"""Lot ingestion and comparable search queries."""

from __future__ import annotations

import sqlite3
import json
import zlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from ..errors import StorageError
from ..models import Condition, Lot, WatchForm
from .schema import NO, YES, utcnow


def _row_to_lot(row: sqlite3.Row) -> Lot:
    values: dict[str, object] = {
        "lot_id": row["lot_id"],
        "source": row["source"],
        "title": row["title"],
        "brand": row["brand"],
        "model_key": row["model_key"],
        "condition_tag": Condition(row["condition_tag"]),
        "form": WatchForm(row["form"]),
        "hearts": row["hearts"],
        "sold": bool(row["sold"]),
        "hammer_eur": row["hammer_eur"],
        "opened_at": date.fromisoformat(row["opened_at"]),
        "ended_at": date.fromisoformat(row["ended_at"]),
        "url": row["url"],
        "subtitle": row["subtitle"],
        "bids_count": row["bids_count"],
        "source_available": row["source_available"] == YES,
    }
    extras = {
        name: row[name]
        for name in (
            "model", "ref_number", "caliber", "case_code", "movement",
            "case_material", "case_diameter_mm", "specs_json", "ai_json",
            "needs_review", "review_status", "reviewed_at", "override_json",
        )
        if name in row.keys()
    }
    values.update(extras)
    return Lot(**values)


def _with_row_factory(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    return conn


def upsert_lots(conn: sqlite3.Connection, lots: Iterable[Lot], now: datetime) -> int:
    written = 0
    timestamp = utcnow(now)
    with conn:
        for lot in lots:
            extras = {
                "model": lot.model, "ref_number": lot.ref_number, "caliber": lot.caliber,
                "case_code": lot.case_code, "movement": lot.movement,
                "case_material": lot.case_material, "case_diameter_mm": lot.case_diameter_mm,
                "specs_json": lot.specs_json, "ai_json": lot.ai_json,
                "needs_review": lot.needs_review, "review_status": lot.review_status,
                "reviewed_at": lot.reviewed_at, "override_json": lot.override_json,
            }
            for name in ("specs_json", "ai_json", "override_json"):
                if isinstance(extras[name], (dict, list)):
                    extras[name] = json.dumps(extras[name], sort_keys=True)
            if extras["needs_review"] is None:
                extras["needs_review"] = 0
            if extras["review_status"] is None:
                extras["review_status"] = "pending"
            conn.execute(
                """
                INSERT INTO lots (
                    lot_id, source, title, brand, model_key, condition_tag, form,
                    hearts, sold, hammer_eur, opened_at, ended_at, url, subtitle,
                    bids_count, source_available, model, ref_number, caliber, case_code,
                    movement, case_material, case_diameter_mm, specs_json, ai_json,
                    needs_review, review_status, reviewed_at, override_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lot_id) DO UPDATE SET
                    source=excluded.source, title=excluded.title, brand=excluded.brand,
                    model_key=excluded.model_key, condition_tag=excluded.condition_tag,
                    form=excluded.form, hearts=excluded.hearts, sold=excluded.sold,
                    hammer_eur=excluded.hammer_eur, opened_at=excluded.opened_at,
                    ended_at=excluded.ended_at, url=excluded.url,
                    subtitle=excluded.subtitle, bids_count=excluded.bids_count,
                    model=excluded.model, ref_number=excluded.ref_number,
                    caliber=excluded.caliber, case_code=excluded.case_code,
                    movement=excluded.movement, case_material=excluded.case_material,
                    case_diameter_mm=excluded.case_diameter_mm, specs_json=excluded.specs_json,
                    ai_json=excluded.ai_json, needs_review=excluded.needs_review,
                    review_status=excluded.review_status, reviewed_at=excluded.reviewed_at,
                    override_json=excluded.override_json,
                    updated_at=excluded.updated_at
                """,
                # source availability belongs to the URL checker and is not
                # overwritten by re-ingesting a lot.
                (
                    lot.lot_id, lot.source, lot.title, lot.brand, lot.model_key,
                    lot.condition_tag.value, lot.form.value, lot.hearts, int(lot.sold),
                    lot.hammer_eur, lot.opened_at.isoformat(), lot.ended_at.isoformat(),
                    lot.url, lot.subtitle, lot.bids_count,
                    YES if lot.source_available else NO,
                    extras["model"], extras["ref_number"], extras["caliber"],
                    extras["case_code"], extras["movement"], extras["case_material"],
                    extras["case_diameter_mm"], extras["specs_json"], extras["ai_json"],
                    extras["needs_review"], extras["review_status"], extras["reviewed_at"],
                    extras["override_json"], timestamp,
                ),
            )
            description = lot.description
            if description is not None:
                conn.execute(
                    "INSERT INTO lot_desc(lot_id, desc_z) VALUES (?, ?) "
                    "ON CONFLICT(lot_id) DO UPDATE SET desc_z = excluded.desc_z",
                    (lot.lot_id, zlib.compress(description.encode("utf-8"))),
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
           AND ended_at >= ? AND ended_at <= ?
           AND NOT (needs_review = 1 AND review_status = 'pending')
           ORDER BY ended_at""",
        (model_key, condition.value, since.isoformat(), today.isoformat()),
    ).fetchall()
    return [_row_to_lot(row) for row in rows]

def fetch_lots_for_liquidity(conn: sqlite3.Connection, since: date) -> list[Lot]:
    _with_row_factory(conn)
    rows = conn.execute(
        """SELECT * FROM lots
           WHERE ended_at >= ?
           ORDER BY ended_at""",
        (since.isoformat(),),
    ).fetchall()
    return [_row_to_lot(row) for row in rows]


def fetch_sold_lots_since(
    conn: sqlite3.Connection, condition: Condition, since: date
) -> list[Lot]:
    _with_row_factory(conn)
    rows = conn.execute(
        """SELECT * FROM lots WHERE condition_tag = ? AND sold = 1 AND ended_at >= ?
           AND NOT (needs_review = 1 AND review_status = 'pending')
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
        AND NOT (l.needs_review = 1 AND l.review_status = 'pending')
        {sold_clause}
        {model_clause}
        ORDER BY l.ended_at DESC
        {"LIMIT ?" if limit is not None else ""}
        """,
        [*params, *([limit] if limit is not None else [])],
    ).fetchall()
    return [_row_to_lot(row) for row in rows]
