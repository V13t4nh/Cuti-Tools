"""Catawiki buyer-JSON HTTP adapter.

Payload records and strict JSON validation live in :mod:`catawiki_payload`;
this module keeps the established import surface and request orchestration.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Iterable, Iterator, Sequence
from urllib.parse import quote

from ..errors import ScrapeError
from ..fetch import fetch_json
from .catawiki_payload import (
    CURRENCY,
    LOT_ID_RE,
    BiddingOutcome,
    LiveState,
    LotRef,
    LotTitle,
    SearchPage,
    lot_id_from_url,
    parse_bidding_block,
    parse_live_lots,
    parse_lot_titles,
    parse_search_page,
    parse_utc_date,
)

SOURCE_NAME = "catawiki"


def chunks(items: Sequence[str], size: int) -> Iterator[tuple[str, ...]]:
    """Split ids into batches so one request covers many lots."""
    if size < 1:
        raise ScrapeError(f"batch size must be >= 1, got {size}")
    for start in range(0, len(items), size):
        yield tuple(items[start : start + size])


JsonFetcher = Callable[[str, float, int], Any]


class CatawikiApi:
    """Thin HTTP client over the public buyer endpoints."""

    def __init__(
        self,
        *,
        api_base: str,
        timeout_seconds: float,
        max_bytes: int,
        pause_seconds: float,
        fetch: JsonFetcher | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes
        self._pause_seconds = pause_seconds
        self._fetch: JsonFetcher = fetch or fetch_json
        self._sleep = sleep or time.sleep
        self.requests_made = 0

    def _get(self, path: str) -> Any:
        if self._pause_seconds > 0 and self.requests_made:
            self._sleep(self._pause_seconds)
        self.requests_made += 1
        return self._fetch(f"{self._api_base}{path}", self._timeout, self._max_bytes)

    def search(self, query: str, page: int) -> SearchPage:
        if page < 1:
            raise ScrapeError(f"page must be >= 1, got {page}")
        payload = self._get(f"/buyer/api/v1/search?q={quote(query)}&page={page}")
        return parse_search_page(payload, query=query)

    def live_states(self, lot_ids: Iterable[str]) -> dict[str, LiveState]:
        ids = list(lot_ids)
        if not ids:
            return {}
        payload = self._get(f"/buyer/api/v1/lots/live?ids={','.join(ids)}")
        return {state.lot_id: state for state in parse_live_lots(payload)}

    def titles(self, lot_ids: Iterable[str]) -> dict[str, LotTitle]:
        ids = list(lot_ids)
        if not ids:
            return {}
        payload = self._get(f"/buyer/api/v1/lots?ids={','.join(ids)}")
        return {item.lot_id: item for item in parse_lot_titles(payload)}

    def outcome(self, lot_id: str) -> BiddingOutcome:
        payload = self._get(
            f"/buyer/api/v3/lots/{lot_id}/bidding_block?currency_code={CURRENCY}"
        )
        return parse_bidding_block(payload, lot_id=lot_id)
