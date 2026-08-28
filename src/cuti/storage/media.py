"""Storage operations for immutable lot covers and their upload queue."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from ..errors import StorageError

QUEUE_STATES = ("queued", "uploading", "ready", "retryable_error", "permanent_error")


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _image(row: tuple[Any, ...] | sqlite3.Row) -> dict[str, Any]:
    keys = ("lot_id", "idx", "source_url", "telegram_file_id", "telegram_file_path",
            "telegram_message_id", "uploaded_at", "state", "attempts", "last_error",
            "next_attempt_at", "lease_owner", "lease_expires_at")
    return {key: row[key] if isinstance(row, sqlite3.Row) else row[pos] for pos, key in enumerate(keys)}


def upsert_lot_image(
    conn: sqlite3.Connection,
    *,
    lot_id: str,
    idx: int,
    source_url: str,
    telegram_file_id: str | None = None,
    telegram_file_path: str | None = None,
    telegram_message_id: int | None = None,
    uploaded_at: datetime | None = None,
) -> None:
    """Insert a cover snapshot or update Telegram metadata for the same URL."""
    if not isinstance(source_url, str) or not source_url.strip():
        raise StorageError("image source URL must not be empty")
    uploaded_str = _iso(uploaded_at) if uploaded_at else None
    cursor = conn.execute(
        """INSERT INTO lot_images (
               lot_id, idx, source_url, telegram_file_id, telegram_file_path,
               telegram_message_id, uploaded_at, state
           ) VALUES (?, ?, ?, ?, ?, ?, ?, CASE WHEN ? IS NULL THEN 'queued' ELSE 'ready' END)
           ON CONFLICT(lot_id, idx) DO UPDATE SET
               telegram_file_id = coalesce(excluded.telegram_file_id, lot_images.telegram_file_id),
               telegram_file_path = coalesce(excluded.telegram_file_path, lot_images.telegram_file_path),
               telegram_message_id = coalesce(excluded.telegram_message_id, lot_images.telegram_message_id),
               uploaded_at = coalesce(excluded.uploaded_at, lot_images.uploaded_at),
               state = CASE WHEN excluded.telegram_file_id IS NULL THEN lot_images.state ELSE 'ready' END
           WHERE lot_images.source_url = excluded.source_url""",
        (lot_id, idx, source_url.strip(), telegram_file_id, telegram_file_path, telegram_message_id, uploaded_str, telegram_file_id),
    )
    if cursor.rowcount != 1:
        raise StorageError(f"{lot_id}: image slot {idx} conflicts with the stored snapshot")


def _select_images(conn: sqlite3.Connection, lot_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT lot_id, idx, source_url, telegram_file_id, telegram_file_path,
                  telegram_message_id, uploaded_at, state, attempts, last_error,
                  next_attempt_at, lease_owner, lease_expires_at
           FROM lot_images WHERE lot_id = ? ORDER BY idx ASC""", (lot_id,)
    ).fetchall()
    return [_image(row) for row in rows]


def fetch_lot_images(conn: sqlite3.Connection, lot_id: str) -> list[dict[str, Any]]:
    """Retrieve media metadata for a lot ordered by slot index."""
    return _select_images(conn, lot_id)


def fetch_lot_image(conn: sqlite3.Connection, lot_id: str, idx: int = 0) -> dict[str, Any] | None:
    """Retrieve one media slot, or ``None`` when the cover is explicitly missing."""
    rows = _select_images(conn, lot_id)
    return next((row for row in rows if row["idx"] == idx), None)


def find_lots_missing_cover(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return unique stored lots without an idx-0 image and their source kinds."""
    rows = conn.execute(
        """SELECT lot_id, source FROM live_watch
           WHERE NOT EXISTS (
               SELECT 1 FROM lot_images WHERE lot_images.lot_id = live_watch.lot_id AND idx = 0
           )
           UNION
           SELECT lot_id, source FROM lots
           WHERE NOT EXISTS (
               SELECT 1 FROM lot_images WHERE lot_images.lot_id = lots.lot_id AND idx = 0
           )
           ORDER BY lot_id, source"""
    ).fetchall()
    sources: dict[str, str] = {}
    for lot_id, source in rows:
        previous = sources.setdefault(lot_id, source)
        if previous != source:
            raise StorageError(f"{lot_id}: conflicting source kinds {previous!r} and {source!r}")
    return list(sources.items())


def find_lot_ids_missing_cover(conn: sqlite3.Connection) -> list[str]:
    """Return unique stored lot IDs without an idx-0 image row."""
    return [lot_id for lot_id, _source in find_lots_missing_cover(conn)]


def claim_lot_image(conn: sqlite3.Connection, *, worker_id: str, now: datetime, lease_seconds: float) -> dict[str, Any] | None:
    """Recover expired claims and atomically claim one eligible queue row."""
    if not worker_id.strip() or lease_seconds <= 0:
        raise StorageError("media worker lease configuration is invalid")
    now_s, expiry_s = _iso(now), _iso(now + timedelta(seconds=lease_seconds))
    own_transaction = not conn.in_transaction
    if own_transaction:
        conn.execute("BEGIN IMMEDIATE")
    else:
        conn.execute("SAVEPOINT media_claim")
    try:
        conn.execute(
            """UPDATE lot_images SET state = 'queued', lease_owner = NULL, lease_expires_at = NULL
               WHERE state = 'uploading' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?""", (now_s,)
        )
        row = conn.execute(
            """SELECT lot_id, idx, source_url, telegram_file_id, telegram_file_path,
                      telegram_message_id, uploaded_at, state, attempts, last_error,
                      next_attempt_at, lease_owner, lease_expires_at
               FROM lot_images
               WHERE state IN ('queued', 'retryable_error')
                 AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
               ORDER BY COALESCE(next_attempt_at, ''), lot_id, idx LIMIT 1""", (now_s,)
        ).fetchone()
        if row is None:
            conn.commit() if own_transaction else conn.execute("RELEASE SAVEPOINT media_claim")
            return None
        key = (row[0], row[1]) if not isinstance(row, sqlite3.Row) else (row["lot_id"], row["idx"])
        changed = conn.execute(
            """UPDATE lot_images SET state = 'uploading', attempts = attempts + 1,
                      lease_owner = ?, lease_expires_at = ?
               WHERE lot_id = ? AND idx = ? AND state IN ('queued', 'retryable_error')""",
            (worker_id, expiry_s, key[0], key[1]),
        ).rowcount
        if changed != 1:
            raise StorageError("media queue claim lost its row lock")
        claimed = conn.execute(
            """SELECT lot_id, idx, source_url, telegram_file_id, telegram_file_path,
                      telegram_message_id, uploaded_at, state, attempts, last_error,
                      next_attempt_at, lease_owner, lease_expires_at
               FROM lot_images WHERE lot_id = ? AND idx = ?""", key
        ).fetchone()
        conn.commit() if own_transaction else conn.execute("RELEASE SAVEPOINT media_claim")
        return _image(claimed)
    except Exception:
        if own_transaction:
            conn.rollback()
        else:
            conn.execute("ROLLBACK TO SAVEPOINT media_claim")
            conn.execute("RELEASE SAVEPOINT media_claim")
        raise


def mark_lot_image_ready(conn: sqlite3.Connection, *, lot_id: str, idx: int, worker_id: str,
                         file_id: str, file_path: str | None, message_id: int | None,
                         uploaded_at: datetime) -> None:
    """Commit a successful Telegram upload only for the active lease owner."""
    changed = conn.execute(
        """UPDATE lot_images SET state = 'ready', telegram_file_id = ?, telegram_file_path = ?,
                  telegram_message_id = ?, uploaded_at = ?, last_error = NULL,
                  next_attempt_at = NULL, lease_owner = NULL, lease_expires_at = NULL
           WHERE lot_id = ? AND idx = ? AND state = 'uploading' AND lease_owner = ?""",
        (file_id, file_path, message_id, _iso(uploaded_at), lot_id, idx, worker_id),
    ).rowcount
    if changed != 1:
        raise StorageError(f"{lot_id}: media lease is no longer owned by {worker_id}")
    conn.commit()


def mark_lot_image_failed(conn: sqlite3.Connection, *, lot_id: str, idx: int, worker_id: str,
                          error: str, now: datetime, retryable: bool, max_attempts: int,
                          base_pause_seconds: float, max_backoff_seconds: float) -> str:
    """Persist a typed failure and bounded exponential retry schedule."""
    row = conn.execute("SELECT attempts FROM lot_images WHERE lot_id = ? AND idx = ? AND state = 'uploading' AND lease_owner = ?", (lot_id, idx, worker_id)).fetchone()
    if row is None:
        raise StorageError(f"{lot_id}: media lease is no longer owned by {worker_id}")
    attempts = row[0]
    state = "retryable_error" if retryable and attempts < max_attempts else "permanent_error"
    delay = min(max_backoff_seconds, base_pause_seconds * (2 ** min(max(attempts - 1, 0), 30)))
    next_at = _iso(now + timedelta(seconds=delay)) if state == "retryable_error" else None
    conn.execute(
        """UPDATE lot_images SET state = ?, last_error = ?, next_attempt_at = ?,
                  lease_owner = NULL, lease_expires_at = NULL
           WHERE lot_id = ? AND idx = ? AND state = 'uploading' AND lease_owner = ?""",
        (state, error[:1000], next_at, lot_id, idx, worker_id),
    )
    conn.commit()
    return state


def count_lot_images(conn: sqlite3.Connection) -> dict[str, int]:
    """Count total and ready lot images."""
    total = conn.execute("SELECT count(*) FROM lot_images").fetchone()[0]
    uploaded = conn.execute("SELECT count(*) FROM lot_images WHERE state = 'ready' OR telegram_file_id IS NOT NULL").fetchone()[0]
    states = {state: 0 for state in QUEUE_STATES}
    states.update(dict(conn.execute("SELECT state, count(*) FROM lot_images GROUP BY state").fetchall()))
    return {"total": total, "uploaded": uploaded, **states}
