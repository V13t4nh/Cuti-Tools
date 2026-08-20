"""Live auction capture, settlement and source-health workflows."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

from ..config import Settings
from ..errors import ScrapeError
from ..fetch import fetch_text, probe_url
from ..normalize import Rules
from ..scrapers import catawiki_api
from .settlement import persist, settle
from ..storage import (
    LiveWatchRow,
    count_live_watch,
    fetch_live_watch_due,
    fetch_lots_for_source_check,
    mark_source_availability,
    upsert_live_watch,
)
from .details import build_lot_url, fetch_lot_page

@dataclass(frozen=True, slots=True)
class WatchLiveReport:
    queries: tuple[str, ...]
    pages_fetched: int
    lots_seen: int
    lots_tracked: int
    lots_refreshed: int
    windows_unknown: int
    requests_made: int

@dataclass(frozen=True, slots=True)
class SettleReport:
    candidates: int
    sold: int
    unsold: int
    still_open: int
    vanished: int
    unclassified: int
    lots_written: int
    queue_remaining: int
    requests_made: int

@dataclass(frozen=True, slots=True)
class SourceCheckReport:
    checked: int
    alive: int
    dead: int

def _lot_page_fetcher(
    rows: list[LiveWatchRow], settings: Settings
) -> Callable[[str], str | None]:
    known_ids = {row.lot_id for row in rows}
    requested = False

    def fetch(lot_id: str) -> str | None:
        nonlocal requested
        if not settings.details_enabled or lot_id not in known_ids:
            return None
        url = build_lot_url(settings.catawiki_api_base, lot_id)
        if requested and settings.details_request_delay_seconds > 0:
            time.sleep(settings.details_request_delay_seconds)
        requested = True
        return fetch_lot_page(
            url,
            timeout_seconds=settings.http_timeout_seconds,
            max_bytes=settings.response_max_bytes,
            delay_seconds=settings.details_request_delay_seconds,
            max_retries=settings.details_max_retries,
            fetch=fetch_text,
            sleep=time.sleep,
        )

    return fetch


def _catawiki_client(
    settings: Settings, api: catawiki_api.CatawikiApi | None = None
) -> catawiki_api.CatawikiApi:
    if api is not None:
        return api
    return catawiki_api.CatawikiApi(
        api_base=settings.catawiki_api_base,
        timeout_seconds=settings.http_timeout_seconds,
        max_bytes=settings.response_max_bytes,
        pause_seconds=settings.catawiki_pause_seconds,
    )


def watch_live(
    conn: sqlite3.Connection,
    settings: Settings,
    now: datetime,
    *,
    api: catawiki_api.CatawikiApi | None = None,
) -> WatchLiveReport:
    """Phase 1: record every lot that is open right now, with its close date."""
    client = _catawiki_client(settings, api)
    refs: dict[str, catawiki_api.LotRef] = {}
    pages = 0
    for query in settings.catawiki_queries:
        for page_number in range(1, settings.catawiki_search_max_pages + 1):
            page = client.search(query, page_number)
            pages += 1
            if not page.lots:
                break
            for ref in page.lots:
                refs.setdefault(ref.lot_id, ref)
    windows: dict[str, date] = {}
    for batch in catawiki_api.chunks(list(refs), settings.catawiki_batch_size):
        for lot_id, state in client.live_states(batch).items():
            if not state.closed:
                windows[lot_id] = state.ended_at
    rows = [
        LiveWatchRow(
            lot_id=lot_id,
            source=catawiki_api.SOURCE_NAME,
            title=ref.title,
            subtitle=ref.subtitle,
            url=ref.url,
            bidding_end_at=windows.get(lot_id),
        )
        for lot_id, ref in refs.items()
    ]
    tracked, refreshed = upsert_live_watch(conn, rows, now)
    return WatchLiveReport(
        queries=settings.catawiki_queries,
        pages_fetched=pages,
        lots_seen=len(rows),
        lots_tracked=tracked,
        lots_refreshed=refreshed,
        windows_unknown=sum(row.bidding_end_at is None for row in rows),
        requests_made=client.requests_made,
    )


def settle_lots(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    today: date,
    now: datetime,
    *,
    api: catawiki_api.CatawikiApi | None = None,
) -> SettleReport:
    """Phase 2: read the hammer price of every tracked lot that has closed."""
    client = _catawiki_client(settings, api)
    candidates = fetch_live_watch_due(conn, until=today, limit=settings.settle_max_lots)
    details = _lot_page_fetcher(candidates, settings) if settings.details_enabled else None
    settlement = settle(client, rules, settings, candidates, fetch_details=details)
    written = persist(conn, settlement, now)
    return SettleReport(
        candidates=len(candidates),
        sold=settlement.sold,
        unsold=settlement.unsold,
        still_open=settlement.still_open,
        vanished=settlement.vanished,
        unclassified=settlement.unclassified,
        lots_written=written,
        queue_remaining=count_live_watch(conn),
        requests_made=client.requests_made,
    )


def ingest_one_lot(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    today: date,
    now: datetime,
    *,
    url: str,
    api: catawiki_api.CatawikiApi | None = None,
) -> SettleReport:
    """Track a single lot URL and settle it immediately if bidding has ended."""
    client = _catawiki_client(settings, api)
    lot_id = catawiki_api.lot_id_from_url(url)
    titles = client.titles([lot_id])
    if lot_id not in titles:
        raise ScrapeError(f"lot {lot_id} is no longer readable at the source")
    known = titles[lot_id]
    row = LiveWatchRow(
        lot_id=lot_id,
        source=catawiki_api.SOURCE_NAME,
        title=known.title,
        subtitle=None,
        url=known.url,
        bidding_end_at=None,
    )
    upsert_live_watch(conn, [row], now)
    details = _lot_page_fetcher([row], settings) if settings.details_enabled else None
    settlement = settle(client, rules, settings, [row], fetch_details=details)
    written = persist(conn, settlement, now)
    return SettleReport(
        candidates=1,
        sold=settlement.sold,
        unsold=settlement.unsold,
        still_open=settlement.still_open,
        vanished=settlement.vanished,
        unclassified=settlement.unclassified,
        lots_written=written,
        queue_remaining=count_live_watch(conn),
        requests_made=client.requests_made,
    )


def check_source_urls(
    conn: sqlite3.Connection,
    settings: Settings,
    now: datetime,
    *,
    probe: object = None,
) -> SourceCheckReport:
    """Flag stored lots whose source page can no longer be opened."""
    probe_fn = probe or probe_url
    candidates = fetch_lots_for_source_check(conn, limit=settings.url_check_max_lots)
    results: dict[str, bool] = {}
    for index, (lot_id, url) in enumerate(candidates):
        if index and settings.catawiki_pause_seconds > 0:
            time.sleep(settings.catawiki_pause_seconds)
        status, final_url = probe_fn(url, settings.http_timeout_seconds)
        results[lot_id] = status == 200 and f"/l/{lot_id}" in final_url
    mark_source_availability(conn, results, now)
    alive = sum(results.values())
    return SourceCheckReport(checked=len(results), alive=alive, dead=len(results) - alive)
