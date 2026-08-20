"""Auction listing ingestion workflow."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from ..config import Settings
from ..errors import ConfigError, ScrapeError
from ..fetch import fetch_text, resolve, to_url
from ..models import Lot
from ..normalize import Rules, classify
from ..scrapers import catawiki
from ..storage import upsert_lots


@dataclass(frozen=True, slots=True)
class IngestReport:
    pages_fetched: int
    lots_written: int
    stopped_reason: str


def _local_path(url: str) -> Path:
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if len(path) >= 3 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return Path(path).resolve()


def _safe_next_url(root_url: str, current_url: str, next_href: str) -> str:
    """Resolve pagination without allowing a feed to leave its source origin."""
    candidate = resolve(current_url, next_href)
    root = urlparse(root_url)
    target = urlparse(candidate)
    if (root.scheme, root.netloc) != (target.scheme, target.netloc):
        raise ScrapeError(f"pagination left the configured source origin: {candidate}")
    if root.scheme == "file" and not _local_path(candidate).is_relative_to(
        _local_path(root_url).parent
    ):
        raise ScrapeError(f"pagination left the configured source directory: {candidate}")
    return candidate


def _validate_max_lots(max_lots: int | None) -> None:
    if max_lots is not None and (isinstance(max_lots, bool) or not isinstance(max_lots, int) or max_lots <= 0):
        raise ConfigError(f"max_lots must be a positive integer, got {max_lots!r}")


def ingest_lots(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    now: datetime,
    max_lots: int | None = None,
) -> IngestReport:
    """Preflight every source page, then atomically store the normalized crawl."""
    _validate_max_lots(max_lots)
    root_url = to_url(settings.lots_source_url)
    url = root_url
    visited: set[str] = set()
    seen_lot_ids: set[str] = set()
    lots: list[Lot] = []
    pages = 0
    reason = "no next page"

    while True:
        if url in visited:
            raise ScrapeError(f"pagination loop detected at {url}")
        visited.add(url)
        page = catawiki.parse_listing(
            fetch_text(url, settings.http_timeout_seconds, max_bytes=settings.response_max_bytes)
        )
        pages += 1
        for raw in page.lots:
            if max_lots is not None and len(lots) >= max_lots:
                reason = "lot limit reached"
                break
            if raw.lot_id in seen_lot_ids:
                raise ScrapeError(f"duplicate lot_id across source pages: {raw.lot_id}")
            seen_lot_ids.add(raw.lot_id)
            classification = classify(raw.title, rules)
            if classification.condition is not None and classification.condition is not raw.condition:
                raise ScrapeError(f"{raw.lot_id}: title condition conflicts with data-condition")
            lots.append(
                Lot(
                    lot_id=raw.lot_id,
                    source=catawiki.SOURCE_NAME,
                    title=raw.title,
                    brand=classification.brand,
                    model_key=classification.model_key,
                    condition_tag=raw.condition,
                    form=raw.form,
                    hearts=raw.hearts,
                    sold=raw.sold,
                    hammer_eur=raw.hammer_eur,
                    opened_at=raw.opened_at,
                    ended_at=raw.ended_at,
                    url=resolve(url, raw.url),
                )
            )
        if max_lots is not None and len(lots) >= max_lots:
            reason = "lot limit reached"
            break
        if page.next_href is None:
            break
        if pages >= settings.source_max_pages:
            reason = "page limit reached"
            break
        url = _safe_next_url(root_url, url, page.next_href)

    return IngestReport(pages_fetched=pages, lots_written=upsert_lots(conn, lots, now), stopped_reason=reason)
