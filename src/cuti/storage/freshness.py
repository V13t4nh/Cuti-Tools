"""Freshness assessment for the persisted market-data snapshot."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from ..errors import StorageError


@dataclass(frozen=True, slots=True)
class DataFreshness:
    status: str
    last_updated_at: datetime | None
    age_hours: float | None
    stale_after_hours: float


def assess_data_freshness(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    stale_after_hours: float,
) -> DataFreshness:
    """Classify the latest lot/live-watch update as fresh, stale, or no-data."""
    if now.tzinfo is None:
        raise StorageError("freshness reference time must include a timezone")
    if stale_after_hours <= 0:
        raise StorageError("stale_after_hours must be > 0")
    row = conn.execute(
        """
        SELECT MAX(updated_at) FROM (
            SELECT MAX(updated_at) AS updated_at FROM lots
            UNION ALL
            SELECT MAX(last_seen_at) AS updated_at FROM live_watch
        )
        """
    ).fetchone()
    raw = row[0] if row else None
    if raw is None:
        return DataFreshness("no_data", None, None, stale_after_hours)
    try:
        last_updated = datetime.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise StorageError(f"invalid data freshness timestamp: {raw!r}") from exc
    if last_updated.tzinfo is None:
        raise StorageError(f"data freshness timestamp has no timezone: {raw!r}")
    age_hours = (now.astimezone(timezone.utc) - last_updated.astimezone(timezone.utc)).total_seconds() / 3600
    if age_hours < 0:
        raise StorageError(f"data freshness timestamp is in the future: {raw!r}")
    status = "stale" if age_hours > stale_after_hours else "fresh"
    return DataFreshness(status, last_updated, age_hours, stale_after_hours)
