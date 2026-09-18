"""Durable parsed source-detail snapshots for live and settled lots."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..errors import StorageError
from .schema import utcnow


@dataclass(frozen=True, slots=True)
class SourceLotDetails:
    lot_id: str
    content_hash: str
    specs: dict[str, Any]
    description: str | None


def _encode_specs(lot_id: str, specs: dict[str, Any]) -> str:
    if not isinstance(specs, dict) or not all(isinstance(key, str) for key in specs):
        raise StorageError(f"{lot_id}: source specs must be an object with string keys")
    try:
        return json.dumps(specs, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise StorageError(f"{lot_id}: source specs must be JSON serializable") from exc


def _hash(specs: dict[str, Any], description: str | None) -> str:
    payload = json.dumps(
        {"description": description, "specs": specs},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_lots_missing_source_details(
    conn: sqlite3.Connection, limit: int | None = None,
) -> list[tuple[str, str, str]]:
    """Return source lots without a successful materialized detail snapshot."""
    limit_clause = f"LIMIT {int(limit)}" if limit is not None and limit > 0 else ""
    rows = conn.execute(
        f"""
        SELECT lot_id, source, url FROM (
            SELECT lot_id, source, url, 1 AS is_live,
                   coalesce(bidding_end_at, last_seen_at, '') AS time_sort
            FROM live_watch
            WHERE NOT EXISTS (
                SELECT 1 FROM lot_source_details d
                WHERE d.lot_id = live_watch.lot_id
                  AND d.state IN ('ready', 'permanent_error')
            )
            UNION ALL
            SELECT lot_id, source, url, 0 AS is_live,
                   coalesce(ended_at, updated_at, '') AS time_sort
            FROM lots
            WHERE NOT EXISTS (
                SELECT 1 FROM lot_source_details d
                WHERE d.lot_id = lots.lot_id
                  AND d.state IN ('ready', 'permanent_error')
            )
        )
        ORDER BY is_live DESC, time_sort DESC, lot_id DESC
        {limit_clause}
        """
    ).fetchall()
    seen: set[str] = set()
    result: list[tuple[str, str, str]] = []
    for row in rows:
        lot_id = str(row[0])
        if lot_id not in seen:
            seen.add(lot_id)
            result.append((lot_id, str(row[1]), str(row[2])))
    return result


def upsert_source_details(
    conn: sqlite3.Connection,
    lot_id: str,
    source: str,
    specs: dict[str, Any],
    description: str | None,
    now: datetime,
) -> None:
    """Persist a successfully parsed source page without retaining raw HTML."""
    if not lot_id.strip() or not source.strip():
        raise StorageError("source detail requires non-empty lot_id and source")
    if description is not None and not isinstance(description, str):
        raise StorageError(f"{lot_id}: source description must be a string or null")
    encoded = _encode_specs(lot_id, specs)
    # Caller is responsible for wrapping in a transaction (e.g. ``with conn:``).
    # Do not add ``with conn:`` here: callers such as enrichment.py already wrap
    # both upsert_lot_gallery_images and this call in a single outer transaction.
    conn.execute(
        """INSERT INTO lot_source_details (
               lot_id, source, specs_json, description, content_hash, fetched_at, state, last_error
           ) VALUES (?, ?, ?, ?, ?, ?, 'ready', NULL)
           ON CONFLICT(lot_id) DO UPDATE SET
               source = excluded.source, specs_json = excluded.specs_json,
               description = excluded.description, content_hash = excluded.content_hash,
               fetched_at = excluded.fetched_at, state = 'ready', last_error = NULL""",
        (lot_id, source, encoded, description, _hash(specs, description), utcnow(now)),
    )


def record_source_detail_failure(
    conn: sqlite3.Connection, lot_id: str, source: str, error: str, *, permanent: bool,
) -> None:
    """Record a typed materialization failure so it is visible and retryable."""
    if not error.strip():
        raise StorageError(f"{lot_id}: source detail failure must include an error")
    state = "permanent_error" if permanent else "retryable_error"
    with conn:
        conn.execute(
            """INSERT INTO lot_source_details (
                   lot_id, source, specs_json, description, content_hash, fetched_at, state, last_error
               ) VALUES (?, ?, '{}', NULL, '', NULL, ?, ?)
               ON CONFLICT(lot_id) DO UPDATE SET
                   source = excluded.source, state = excluded.state, last_error = excluded.last_error""",
            (lot_id, source, state, error),
        )


def fetch_source_details(
    conn: sqlite3.Connection, lot_ids: list[str],
) -> dict[str, SourceLotDetails]:
    """Load successful source snapshots for settlement without refetching HTML."""
    if not lot_ids:
        return {}
    marks = ", ".join("?" for _ in lot_ids)
    rows = conn.execute(
        f"""SELECT lot_id, content_hash, specs_json, description FROM lot_source_details
            WHERE state = 'ready' AND lot_id IN ({marks})""",
        lot_ids,
    ).fetchall()
    result: dict[str, SourceLotDetails] = {}
    for row in rows:
        try:
            specs = json.loads(row[2])
        except (TypeError, json.JSONDecodeError) as exc:
            raise StorageError(f"{row[0]}: corrupt source-detail specs_json") from exc
        if not isinstance(specs, dict) or not all(isinstance(key, str) for key in specs):
            raise StorageError(f"{row[0]}: corrupt source-detail specs")
        result[str(row[0])] = SourceLotDetails(str(row[0]), str(row[1]), specs, row[3])
    return result
