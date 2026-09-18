"""Source-hash-bound LLM refinement storage and candidate selection."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from ..errors import StorageError
from .schema import utcnow


@dataclass(frozen=True, slots=True)
class SourceRefinementCandidate:
    lot_id: str
    source_hash: str
    title: str
    specs_json: str
    description: str | None


def count_unrefined_source_details(conn: sqlite3.Connection, *, force: bool = False) -> int:
    condition = "" if force else "AND (r.lot_id IS NULL OR r.state <> 'ready' OR r.source_hash <> d.content_hash)"
    row = conn.execute(
        f"""SELECT count(*) FROM lot_source_details d
            LEFT JOIN lot_refinements r ON r.lot_id = d.lot_id
            WHERE d.state = 'ready' {condition}"""
    ).fetchone()
    return int(row[0]) if row else 0


def fetch_source_refinement_candidates(
    conn: sqlite3.Connection,
    *,
    lot_ids: Iterable[str] | None = None,
    limit: int = 3,
    force: bool = False,
    exclude_ids: Iterable[str] = (),
) -> list[SourceRefinementCandidate]:
    """Return ready source snapshots whose matching LLM refinement is absent."""
    ids = [lot_id for lot_id in (lot_ids or ()) if lot_id]
    excluded = [lot_id for lot_id in exclude_ids if lot_id]
    clauses = ["d.state = 'ready'", "coalesce(w.title, l.title) IS NOT NULL"]
    params: list[object] = []
    if ids:
        clauses.append(f"d.lot_id IN ({', '.join('?' for _ in ids)})")
        params.extend(ids)
    if not force:
        clauses.append("(r.lot_id IS NULL OR r.state <> 'ready' OR r.source_hash <> d.content_hash)")
    if excluded:
        clauses.append(f"d.lot_id NOT IN ({', '.join('?' for _ in excluded)})")
        params.extend(excluded)
    params.append(limit)
    rows = conn.execute(
        f"""SELECT d.lot_id, d.content_hash, coalesce(w.title, l.title),
                   d.specs_json, d.description
            FROM lot_source_details d
            LEFT JOIN live_watch w ON w.lot_id = d.lot_id
            LEFT JOIN lots l ON l.lot_id = d.lot_id
            LEFT JOIN lot_refinements r ON r.lot_id = d.lot_id
            WHERE {' AND '.join(clauses)}
            ORDER BY w.last_seen_at IS NOT NULL DESC,
                     coalesce(w.last_seen_at, l.ended_at, d.fetched_at) DESC, d.lot_id DESC
            LIMIT ?""",
        params,
    ).fetchall()
    return [SourceRefinementCandidate(*map(str, row[:4]), row[4]) for row in rows]


def upsert_source_refinement(
    conn: sqlite3.Connection, lot_id: str, source_hash: str, ai_data: dict[str, Any], now: datetime,
) -> None:
    """Save an LLM result only for the exact source snapshot it analyzed."""
    if not lot_id or not source_hash or not isinstance(ai_data, dict):
        raise StorageError("source refinement requires lot_id, source_hash and an object result")
    identity = ai_data.get("identity") if isinstance(ai_data.get("identity"), dict) else {}
    specs = ai_data.get("specs") if isinstance(ai_data.get("specs"), dict) else {}
    payload = dict(ai_data)
    for field, value in {
        "brand": identity.get("brand"),
        "model": identity.get("model"),
        "ref_number": identity.get("ref_number"),
        "caliber": identity.get("caliber"),
        "case_code": identity.get("case_code"),
        "movement": specs.get("movement"),
        "case_material": specs.get("case_material"),
        "case_diameter_mm": specs.get("case_diameter_mm"),
    }.items():
        if value is not None:
            payload[field] = value
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    with conn:
        conn.execute(
            """INSERT INTO lot_refinements (lot_id, source_hash, ai_json, refined_at, state, last_error)
               VALUES (?, ?, ?, ?, 'ready', NULL)
               ON CONFLICT(lot_id) DO UPDATE SET source_hash = excluded.source_hash,
                   ai_json = excluded.ai_json, refined_at = excluded.refined_at,
                   state = 'ready', last_error = NULL""",
            (lot_id, source_hash, encoded, utcnow(now)),
        )


def record_source_refinement_failure(
    conn: sqlite3.Connection, lot_id: str, source_hash: str, error: str,
) -> None:
    """Persist an LLM failure against the exact source snapshot for retry."""
    if not lot_id or not source_hash or not error.strip():
        raise StorageError("source refinement failure requires lot_id, source_hash and error")
    with conn:
        conn.execute(
            """INSERT INTO lot_refinements (lot_id, source_hash, ai_json, refined_at, state, last_error)
               VALUES (?, ?, '{}', NULL, 'retryable_error', ?)
               ON CONFLICT(lot_id) DO UPDATE SET source_hash = excluded.source_hash,
                   ai_json = excluded.ai_json, refined_at = NULL,
                   state = 'retryable_error', last_error = excluded.last_error""",
            (lot_id, source_hash, error),
        )


def fetch_current_source_refinements(conn: sqlite3.Connection, lot_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Load only AI output produced from the currently stored source hash."""
    if not lot_ids:
        return {}
    marks = ", ".join("?" for _ in lot_ids)
    rows = conn.execute(
        f"""SELECT r.lot_id, r.ai_json FROM lot_refinements r
            JOIN lot_source_details d ON d.lot_id = r.lot_id AND d.content_hash = r.source_hash
            WHERE r.state = 'ready' AND d.state = 'ready' AND r.lot_id IN ({marks})""",
        lot_ids,
    ).fetchall()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            value = json.loads(row[1])
        except (TypeError, json.JSONDecodeError) as exc:
            raise StorageError(f"{row[0]}: corrupt refinement ai_json") from exc
        if not isinstance(value, dict):
            raise StorageError(f"{row[0]}: corrupt refinement result")
        result[str(row[0])] = value
    return result
