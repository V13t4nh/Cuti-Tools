"""Deal deduplication and quote-queue queries."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from ..models import Condition, Deal, WatchForm
from .schema import utcnow


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


def insert_deal_if_new(conn: sqlite3.Connection, deal: Deal, now: datetime) -> int | None:
    timestamp = utcnow(now)
    with conn:
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
    return cursor.lastrowid if cursor.rowcount else None


def fetch_unquoted_deals(
    conn: sqlite3.Connection, *, since: date, until: date
) -> list[StoredDeal]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM deals WHERE quoted = 0 AND seen_at >= ? AND seen_at <= ?
           ORDER BY seen_at, id""",
        (since.isoformat(), until.isoformat()),
    ).fetchall()
    return [StoredDeal(id=row["id"], deal=_row_to_deal(row)) for row in rows]
