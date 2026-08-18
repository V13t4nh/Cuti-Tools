"""Quote persistence and alert outbox operations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from ..errors import StorageError
from ..models import Condition, Lot, WatchForm
from .schema import utcnow


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
    timestamp = utcnow(now)
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
                            "model_key": item.lot.model_key,
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
            alert_payload = {**alert_payload, "quote_id": quote_id}
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
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, quote_id, payload FROM alert_outbox WHERE status = 'pending'"
    ).fetchall()
    alerts = []
    for row in rows:
        payload = json.loads(row["payload"])
        if not isinstance(payload, dict):
            raise StorageError(f"alert {row['id']} payload must be an object")
        alerts.append(PendingAlert(id=row["id"], quote_id=row["quote_id"], payload=payload))
    ids = [row["id"] for row in rows]
    if ids:
        placeholders = ",".join("?" * len(ids))
        with conn:
            conn.execute(
                f"UPDATE alert_outbox SET status = 'sending' WHERE id IN ({placeholders})",
                ids,
            )
    return alerts


def mark_alert_sent(conn: sqlite3.Connection, alert_id: int, now: datetime) -> None:
    with conn:
        cursor = conn.execute(
            "UPDATE alert_outbox SET status = 'sent', sent_at = ? WHERE id = ? AND status = 'sending'",
            (utcnow(now), alert_id),
        )
        if cursor.rowcount != 1:
            raise StorageError(f"alert {alert_id} was not claimed")


def mark_alert_failed(
    conn: sqlite3.Connection, alert_id: int, error: str, *, max_attempts: int
) -> None:
    with conn:
        row = conn.execute("SELECT attempts FROM alert_outbox WHERE id = ?", (alert_id,)).fetchone()
        attempts = (row[0] if row else 0) + 1
        status = "dead" if attempts >= max_attempts else "pending"
        conn.execute(
            "UPDATE alert_outbox SET status = ?, attempts = ?, last_error = ? WHERE id = ?",
            (status, attempts, error, alert_id),
        )


def outbox_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) FROM alert_outbox GROUP BY status").fetchall()
    counts = {"pending": 0, "sending": 0, "sent": 0, "dead": 0}
    counts.update({status: count for status, count in rows})
    return counts


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    if table not in {"lots", "live_watch", "deals", "quotes", "quote_comparables", "alert_outbox"}:
        raise StorageError(f"unknown table {table!r}")
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def fetch_quote_audit(conn: sqlite3.Connection, quote_id: int) -> dict[str, object]:
    conn.row_factory = sqlite3.Row
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
                "model_key": json.loads(row["snapshot"]).get("model_key"),
                "snapshot": json.loads(row["snapshot"]),
            }
            for row in comparable_rows
        ],
    }
