"""Standalone TLS Impersonation Crawler for Catawiki."""
from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from curl_cffi import requests

# Add project root to sys.path so we can reuse existing parsers if needed
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from cuti.normalize import load_rules
    from cuti.scrapers.catawiki_lot_page import parse_lot_page
    _HAS_CUTI_PARSER = True
    _RULES = load_rules(PROJECT_ROOT / "config" / "rules.json")
except Exception:
    _HAS_CUTI_PARSER = False
    _RULES = None


@dataclass
class CrawledLot:
    lot_id: str
    title: str
    subtitle: str | None
    url: str
    image_url: str | None
    current_bid_eur: float | None = None
    favorite_count: int | None = None
    bidding_end_time: str | None = None
    is_closed: bool = False
    brand: str | None = None
    model: str | None = None
    ref_number: str | None = None
    specs: dict[str, str] | None = None


class CatawikiTlsCrawler:
    """Polite, high-speed crawler using TLS fingerprint impersonation (Chrome 124)."""

    BASE_URL = "https://www.catawiki.com"

    def __init__(
        self,
        impersonate: str = "chrome124",
        pause_seconds: float = 0.8,
        timeout_seconds: float = 12.0,
    ) -> None:
        self.impersonate = impersonate
        self.pause_seconds = pause_seconds
        self.timeout = timeout_seconds
        self.session = requests.Session(impersonate=impersonate)
        self.headers = {
            "Accept": "application/json, text/plain, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }
        self._last_request_time = 0.0

    def _wait_pacing(self) -> None:
        """Polite delay between consecutive requests to avoid rate limits."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if self._last_request_time > 0 and elapsed < self.pause_seconds:
            time.sleep(self.pause_seconds - elapsed)
        self._last_request_time = time.monotonic()

    def _get(self, url: str, is_json: bool = True) -> Any:
        self._wait_pacing()
        t0 = time.perf_counter()
        headers = dict(self.headers)
        if not is_json:
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"

        resp = self.session.get(url, headers=headers, timeout=self.timeout)
        duration_ms = (time.perf_counter() - t0) * 1000

        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code} on {url} ({duration_ms:.1f}ms): {resp.text[:150]}")

        return resp.json() if is_json else resp.text

    def search(self, query: str, page: int = 1) -> tuple[int, list[CrawledLot]]:
        """Search active lots via Catawiki Buyer API."""
        url = f"{self.BASE_URL}/buyer/api/v1/search?q={requests.utils.quote(query)}&page={page}"
        print(f"[*] GET Search API: {query} (trang {page})...", end=" ", flush=True)
        t0 = time.perf_counter()
        data = self._get(url, is_json=True)
        ms = (time.perf_counter() - t0) * 1000
        print(f"OK ({ms:.1f}ms)")

        total = data.get("total", 0)
        lots_raw = data.get("lots", [])
        results: list[CrawledLot] = []
        for item in lots_raw:
            lot_id = str(item.get("id"))
            results.append(
                CrawledLot(
                    lot_id=lot_id,
                    title=item.get("title", ""),
                    subtitle=item.get("subtitle"),
                    url=item.get("url") or f"{self.BASE_URL}/en/l/{lot_id}",
                    image_url=item.get("thumbImageUrl") or item.get("imageUrl"),
                )
            )
        return total, results

    def fill_live_states(self, lots: list[CrawledLot]) -> None:
        """Batch-query live status (current bids, closing date, favorites) for a list of lots."""
        if not lots:
            return
        lot_ids = [lot.lot_id for lot in lots]
        ids_str = ",".join(lot_ids)
        url = f"{self.BASE_URL}/buyer/api/v1/lots/live?ids={ids_str}"
        print(f"[*] GET Live States cho {len(lots)} lots...", end=" ", flush=True)
        t0 = time.perf_counter()
        data = self._get(url, is_json=True)
        ms = (time.perf_counter() - t0) * 1000
        print(f"OK ({ms:.1f}ms)")

        state_map = {str(item.get("id", "")): item for item in data.get("lots", [])}
        for lot in lots:
            st = state_map.get(lot.lot_id)
            if not st:
                continue
            cur_bid = st.get("current_bid_amount", {})
            lot.current_bid_eur = cur_bid.get("EUR") if isinstance(cur_bid, dict) else None
            lot.favorite_count = st.get("favorite_count")
            lot.bidding_end_time = st.get("bidding_end_time")
            lot.is_closed = bool(st.get("closed", False))

    def fetch_lot_details(self, lot: CrawledLot) -> None:
        """Fetch the HTML lot page and parse detailed watch specifications."""
        print(f"[*] GET Lot HTML {lot.lot_id}...", end=" ", flush=True)
        t0 = time.perf_counter()
        html = self._get(lot.url, is_json=False)
        ms = (time.perf_counter() - t0) * 1000
        print(f"OK ({ms:.1f}ms, {len(html)/1024:.1f} KB)")

        if _HAS_CUTI_PARSER and _RULES:
            parsed = parse_lot_page(html, rules=_RULES)
            lot.brand = parsed.brand
            lot.model = parsed.model
            lot.ref_number = parsed.ref_number or parsed.case_code
            lot.specs = parsed.specs
        else:
            # Fallback simple parser if CUTI module is not loaded
            lot.specs = {"html_length": str(len(html))}
