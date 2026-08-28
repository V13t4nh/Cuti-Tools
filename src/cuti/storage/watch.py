"""Live-watch work queue and source availability queries."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Mapping

from ..errors import StorageError
from .schema import NO, YES, utcnow


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
    """Track open lots. Return ``(newly tracked, refreshed)``."""
    rows = list(rows)
    with conn:
        return _upsert_live_watch_rows(conn, rows, now)


def _upsert_live_watch_rows(
    conn: sqlite3.Connection, rows: Iterable[LiveWatchRow], now: datetime
) -> tuple[int, int]:
    timestamp = utcnow(now)
    tracked = 0
    refreshed = 0
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


def upsert_live_watch_with_images(
    conn: sqlite3.Connection,
    rows: Iterable[LiveWatchRow],
    image_urls: Mapping[str, str | None],
    now: datetime,
) -> tuple[int, int]:
    """Commit live-watch rows and discovered images in one outer transaction."""
    rows = list(rows)
    with conn:
        result = _upsert_live_watch_rows(conn, rows, now)
        from . import upsert_lot_image
        for row in rows:
            image_url = image_urls.get(row.lot_id)
            if image_url:
                upsert_lot_image(conn, lot_id=row.lot_id, idx=0, source_url=image_url)
    return result


def fetch_live_watch_due(
    conn: sqlite3.Connection, *, until: date, limit: int
) -> list[LiveWatchRow]:
    """Tracked lots whose bidding window has ended, oldest close first."""
    if limit < 1:
        raise StorageError(f"limit must be >= 1, got {limit}")
    conn.row_factory = sqlite3.Row
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
    """Stored lots that are still believed reachable, oldest checks first."""
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
    """Record whether each lot page can still be opened by a human."""
    timestamp = utcnow(now)
    updated = 0
    with conn:
        for lot_id, alive in results.items():
            cursor = conn.execute(
                "UPDATE lots SET source_available = ?, source_checked_at = ? WHERE lot_id = ?",
                (YES if alive else NO, timestamp, lot_id),
            )
            updated += cursor.rowcount
    return updated
