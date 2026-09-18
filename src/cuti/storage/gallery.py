"""Lot gallery images querying and storage."""

from __future__ import annotations

import sqlite3


def find_lots_missing_gallery(conn: sqlite3.Connection, limit: int | None = None) -> list[tuple[str, str, str]]:
    """Return stored lots without any idx >= 1 gallery images: (lot_id, source, url)."""
    limit_clause = f"LIMIT {int(limit)}" if limit is not None and limit > 0 else ""
    query = f"""
        SELECT lot_id, source, url FROM (
            SELECT lot_id, source, url,
                   coalesce(bidding_end_at, last_seen_at, '') AS time_sort FROM live_watch
            WHERE NOT EXISTS (
                SELECT 1 FROM lot_images WHERE lot_images.lot_id = live_watch.lot_id AND idx >= 1
            )
            UNION
            SELECT lot_id, source, url,
                   coalesce(ended_at, updated_at, '') AS time_sort FROM lots
            WHERE NOT EXISTS (
                SELECT 1 FROM lot_images WHERE lot_images.lot_id = lots.lot_id AND idx >= 1
            )
        )
        ORDER BY time_sort DESC, lot_id DESC
        {limit_clause}
    """
    rows = conn.execute(query).fetchall()
    seen: set[str] = set()
    result: list[tuple[str, str, str]] = []
    for row in rows:
        lid = str(row[0])
        if lid not in seen:
            seen.add(lid)
            result.append((lid, str(row[1]), str(row[2])))
    return result


def upsert_lot_gallery_images(conn: sqlite3.Connection, lot_id: str, image_urls: list[str]) -> int:
    """Store extended gallery images (idx >= 1) with direct CDN URLs in ready state."""
    inserted = 0
    with conn:
        conn.execute("DELETE FROM lot_images WHERE lot_id = ? AND idx > ?", (lot_id, len(image_urls)))
        for idx, url in enumerate(image_urls, start=1):
            if not isinstance(url, str) or not url.strip():
                continue
            cursor = conn.execute(
                """INSERT INTO lot_images (
                       lot_id, idx, source_url, state
                   ) VALUES (?, ?, ?, 'ready')
                   ON CONFLICT(lot_id, idx) DO UPDATE SET
                       source_url = excluded.source_url,
                       state = 'ready'
                """,
                (lot_id, idx, url.strip()),
            )
            inserted += cursor.rowcount
    return inserted
