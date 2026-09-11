"""Daily crawl reconciliation and durable queue state helpers."""

from __future__ import annotations

import json
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


@dataclass(frozen=True, slots=True)
class GalleryReconcileReport:
    candidates: int
    resolved: int
    missing: tuple[str, ...]
    failures: tuple[str, ...]
    images_stored: int


def reconcile_missing_lot_galleries(
    conn: sqlite3.Connection,
    settings: Settings,
    now: datetime,
    *,
    limit: int = 20,
    fetch_text_fn: Any = None,
    sleep_fn: Any = None,
) -> GalleryReconcileReport:
    """Self-healing loop: discover lots missing gallery photos, fetch HTML, and populate images."""
    del now
    if not hasattr(conn, "execute"):
        return GalleryReconcileReport(0, 0, (), (), 0)
    from .fetch import fetch_text
    from .pipeline.gallery import extract_lot_gallery
    from .storage.gallery import find_lots_missing_gallery, upsert_lot_gallery_images

    fetcher = fetch_text_fn or fetch_text
    sleeper = sleep_fn or (lambda s: None)
    candidates = find_lots_missing_gallery(conn, limit=limit)
    resolved = 0
    images_stored = 0
    missing: list[str] = []
    failures: list[str] = []

    for idx, (lot_id, source, url) in enumerate(candidates):
        if source != catawiki_api.SOURCE_NAME:
            failures.append(f"{lot_id}: unsupported gallery source {source!r}")
            continue
        if idx > 0 and settings.details_request_delay_seconds > 0:
            sleeper(settings.details_request_delay_seconds)
        try:
            html = fetcher(url, timeout_seconds=settings.http_timeout_seconds)
            urls = extract_lot_gallery(html)
            if urls:
                stored = upsert_lot_gallery_images(conn, lot_id, urls)
                images_stored += stored
                resolved += 1
            else:
                missing.append(lot_id)

            # Piggyback: if lot is in 'lots' but lacks specs_json or description, populate it
            try:
                row = conn.execute("SELECT specs_json FROM lots WHERE lot_id = ?", (lot_id,)).fetchone()
                if row and not row[0]:
                    from .scrapers.catawiki_lot_page import parse_lot_page
                    parsed_page = parse_lot_page(html)
                    if parsed_page.details or parsed_page.description:
                        specs = dict(parsed_page.details)
                        if parsed_page.description:
                            specs["description"] = parsed_page.description
                        conn.execute(
                            "UPDATE lots SET specs_json = ? WHERE lot_id = ?",
                            (json.dumps(specs, sort_keys=True), lot_id),
                        )
            except Exception:
                pass

        except Exception as exc:
            failures.append(f"{lot_id}: {exc}")

    return GalleryReconcileReport(
        candidates=len(candidates),
        resolved=resolved,
        missing=tuple(missing),
        failures=tuple(failures),
        images_stored=images_stored,
    )


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


def recover_permanent_image_failures(
    conn: sqlite3.Connection,
    settings: Settings,
    now: datetime,
    *,
    limit: int = 20,
) -> int:
    """Attempt a direct cache-busting upload for permanent_error images before reporting failure."""
    from .storage.media import _iso
    from .telegram_media import upload_image_to_telegram

    rows = conn.execute(
        """SELECT lot_id, idx, source_url FROM lot_images
           WHERE state = 'permanent_error' ORDER BY lot_id, idx LIMIT ?""",
        (limit,),
    ).fetchall()
    recovered = 0
    for row in rows:
        lot_id, idx, source_url = row[0], row[1], row[2]
        title_row = conn.execute("SELECT title FROM lots WHERE lot_id = ?", (lot_id,)).fetchone()
        if title_row is None:
            title_row = conn.execute("SELECT title FROM live_watch WHERE lot_id = ?", (lot_id,)).fetchone()
        title = title_row[0] if title_row else ""
        caption = f"Lot {lot_id} | {title} (#{idx + 1})"
        try:
            res = upload_image_to_telegram(source_url, caption, settings)
            with conn:
                conn.execute(
                    """UPDATE lot_images SET state = 'ready', telegram_file_id = ?,
                              telegram_file_path = ?, telegram_message_id = ?,
                              uploaded_at = ?, last_error = NULL, next_attempt_at = NULL,
                              lease_owner = NULL, lease_expires_at = NULL
                       WHERE lot_id = ? AND idx = ?""",
                    (res["file_id"], res.get("file_path"), res.get("message_id"), _iso(now), lot_id, idx),
                )
            recovered += 1
        except Exception:
            pass
    return recovered

