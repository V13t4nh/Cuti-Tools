"""Catawiki API client powered by the TLS-impersonated transport layer."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from urllib.parse import quote

# Add project src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cuti.errors import ScrapeError
from cuti.scrapers.catawiki_payload import (
    CURRENCY,
    BiddingOutcome,
    LiveState,
    LotTitle,
    SearchPage,
    parse_bidding_block,
    parse_live_lots,
    parse_lot_titles,
    parse_search_page,
)
from fetch_tls import fetch_json, fetch_text, get_tls_session


def chunks(items: Sequence[str], size: int) -> Iterator[tuple[str, ...]]:
    """Split items into fixed size chunks."""
    if size < 1:
        raise ScrapeError(f"batch size must be >= 1, got {size}")
    for start in range(0, len(items), size):
        yield tuple(items[start : start + size])


class CatawikiTlsApi:
    """Production-parity Catawiki Buyer API Client using curl-cffi TLS Impersonation."""

    def __init__(
        self,
        api_base: str = "https://www.catawiki.com",
        timeout_seconds: float = 15.0,
        max_bytes: int = 5_000_000,
        pause_seconds: float = 0.5,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout_seconds
        self.max_bytes = max_bytes
        self.pause_seconds = pause_seconds
        self.requests_made = 0
        self._session = get_tls_session()

    def _get(self, path: str) -> Any:
        if self.pause_seconds > 0 and self.requests_made > 0:
            time.sleep(self.pause_seconds)
        self.requests_made += 1
        url = f"{self.api_base}{path}"
        return fetch_json(url, timeout_seconds=self.timeout, max_bytes=self.max_bytes, session=self._session)

    def search(self, query: str, page: int = 1) -> SearchPage:
        """Search active lots."""
        if page < 1:
            raise ScrapeError(f"page must be >= 1, got {page}")
        payload = self._get(f"/buyer/api/v1/search?q={quote(query)}&page={page}")
        return parse_search_page(payload, query=query)

    def live_states(self, lot_ids: Iterable[str]) -> dict[str, LiveState]:
        """Fetch live states for a list of lot IDs."""
        ids = list(lot_ids)
        if not ids:
            return {}
        payload = self._get(f"/buyer/api/v1/lots/live?ids={','.join(ids)}")
        return {state.lot_id: state for state in parse_live_lots(payload)}

    def titles(self, lot_ids: Iterable[str]) -> dict[str, LotTitle]:
        """Fetch titles and image URLs for a list of lot IDs."""
        ids = list(lot_ids)
        if not ids:
            return {}
        payload = self._get(f"/buyer/api/v1/lots?ids={','.join(ids)}")
        return {item.lot_id: item for item in parse_lot_titles(payload)}

    def outcome(self, lot_id: str) -> BiddingOutcome:
        """Fetch outcome for a lot (closed or open)."""
        payload = self._get(f"/buyer/api/v3/lots/{lot_id}/bidding_block?currency_code={CURRENCY}")
        return parse_bidding_block(payload, lot_id=lot_id)

    def fetch_html(self, lot_id: str, url: str | None = None) -> str:
        """Fetch full HTML page for a lot."""
        target_url = url or f"{self.api_base}/en/l/{lot_id}"
        if self.pause_seconds > 0 and self.requests_made > 0:
            time.sleep(self.pause_seconds)
        self.requests_made += 1
        return fetch_text(target_url, timeout_seconds=self.timeout, max_bytes=self.max_bytes, session=self._session)
