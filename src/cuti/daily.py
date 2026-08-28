"""Daily crawl reconciliation and durable queue state helpers."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from .errors import CutiError
from .config_types import Settings
from .scrapers import catawiki_api
from .storage import count_lot_images, find_lots_missing_cover, upsert_lot_image


@dataclass(frozen=True, slots=True)
class ReconcileReport:
    candidates: int
    queued: int
    missing: tuple[str, ...]
    failures: tuple[str, ...]


def reconcile_missing_lot_images(
    conn: sqlite3.Connection,
    settings: Settings,
    now: datetime,
    *,
    api: catawiki_api.CatawikiApi | None = None,
) -> ReconcileReport:
    """Resolve exact stored lots without a cover row and queue valid URLs."""
    del now
    candidates = find_lots_missing_cover(conn)
    missing: list[str] = []
    failures: list[str] = []
    resolved: dict[str, str] = {}
    catawiki_ids: list[str] = []
    for lot_id, source in candidates:
        if source != catawiki_api.SOURCE_NAME:
            failures.append(f"{lot_id}: unsupported source {source!r}")
        else:
            catawiki_ids.append(lot_id)
    client = api or catawiki_api.CatawikiApi(
        api_base=settings.catawiki_api_base,
        timeout_seconds=settings.http_timeout_seconds,
        max_bytes=settings.response_max_bytes,
        pause_seconds=settings.catawiki_pause_seconds,
    )
    for batch in catawiki_api.chunks(catawiki_ids, settings.catawiki_batch_size):
        try:
            covers = client.covers(batch)
        except CutiError as exc:
            failures.extend(f"{lot_id}: {exc}" for lot_id in batch)
            continue
        for lot_id in batch:
            image_url = covers.get(lot_id)
            if image_url is None:
                missing.append(lot_id)
            elif not isinstance(image_url, str) or not image_url.strip():
                failures.append(f"{lot_id}: source returned an invalid cover URL")
            else:
                resolved[lot_id] = image_url
    if resolved:
        with conn:
            for lot_id, image_url in resolved.items():
                upsert_lot_image(conn, lot_id=lot_id, idx=0, source_url=image_url)
    return ReconcileReport(len(candidates), len(resolved), tuple(missing), tuple(failures))


def queue_state(conn: sqlite3.Connection) -> dict[str, int]:
    """Return queue state counts, including all nonterminal work."""
    states = count_lot_images(conn)
    states["pending"] = sum(states[state] for state in ("queued", "uploading", "retryable_error"))
    return states


def queue_is_drained(conn: sqlite3.Connection) -> bool:
    """Return true only when no queued, uploading, or retryable work remains."""
    row = conn.execute(
        "SELECT 1 FROM lot_images WHERE state IN ('queued', 'uploading', 'retryable_error') LIMIT 1"
    ).fetchone()
    return row is None
