"""Materialize one source detail page into gallery and parsed product data."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from ..config import Settings
from ..errors import FetchError, ScrapeError
from ..fetch import fetch_text
from ..scrapers import catawiki_api
from ..scrapers.catawiki_lot_page import parse_lot_page
from ..storage import (
    find_lots_missing_source_details,
    record_source_detail_failure,
    upsert_lot_gallery_images,
    upsert_source_details,
)
from .details import fetch_lot_page
from .gallery import extract_lot_gallery


@dataclass(frozen=True, slots=True)
class DetailEnrichmentReport:
    candidates: int
    materialized: int
    images_stored: int
    failures: tuple[str, ...]


def materialize_missing_source_details(
    conn: sqlite3.Connection,
    settings: Settings,
    now: datetime,
    *,
    limit: int | None = None,
    fetch: Callable[[str, float, int], str] = fetch_text,
    sleep: Callable[[float], None] = time.sleep,
) -> DetailEnrichmentReport:
    """Fill all deterministic source fields for lots whose detail page is absent."""
    candidates = find_lots_missing_source_details(conn, limit=limit)
    failures: list[str] = []
    materialized = images_stored = 0
    for index, (lot_id, source, url) in enumerate(candidates):
        if source != catawiki_api.SOURCE_NAME:
            error = f"unsupported detail source {source!r}"
            record_source_detail_failure(conn, lot_id, source, error, permanent=True)
            failures.append(f"{lot_id}: {error}")
            continue
        if index and settings.details_request_delay_seconds > 0:
            sleep(settings.details_request_delay_seconds)
        try:
            html = fetch_lot_page(
                url,
                timeout_seconds=settings.http_timeout_seconds,
                max_bytes=settings.response_max_bytes,
                delay_seconds=settings.details_request_delay_seconds,
                max_retries=settings.details_max_retries,
                fetch=fetch,
                sleep=sleep,
            )
            page = parse_lot_page(html)
            urls = extract_lot_gallery(html)
            with conn:
                if urls:
                    images_stored += upsert_lot_gallery_images(conn, lot_id, urls)
                upsert_source_details(conn, lot_id, source, page.details, page.description, now)
            materialized += 1
            print(f"[PROGRESS:DETAILS] current={index + 1} total={len(candidates)} lot={lot_id} materialized={materialized}", flush=True)
        except (FetchError, ScrapeError) as exc:
            permanent = "404" in str(exc)
            error = str(exc) or exc.__class__.__name__
            record_source_detail_failure(conn, lot_id, source, error, permanent=permanent)
            action = "marked permanent (404)" if permanent else "marked retryable"
            print(f"[ERROR] [STAGE-2:DETAILS] lot={lot_id} | {error} | Action: {action}", flush=True)
            failures.append(f"{lot_id}: {error}")
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            record_source_detail_failure(conn, lot_id, source, error, permanent=False)
            print(f"[ERROR] [STAGE-2:DETAILS] lot={lot_id} | unexpected error: {error} | Action: marked retryable", flush=True)
            failures.append(f"{lot_id}: unexpected detail materialization error: {error}")
    return DetailEnrichmentReport(len(candidates), materialized, images_stored, tuple(failures))
