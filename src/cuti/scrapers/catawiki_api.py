"""Catawiki buyer-JSON adapter: capture open lots, settle them once closed.

Catawiki publishes no developer API and no way to list closed lots: the search
and category endpoints only return lots that are still open. A hammer price is
readable per lot id after bidding ends, but lot pages expire (measured on real
lots: readable at ~9 weeks, lot page redirected away at ~6 months, API silent
beyond that). Historical sold prices therefore cannot be queried on demand.

The adapter has two phases:

1. :meth:`CatawikiApi.search` captures ids of lots open right now.
2. :meth:`CatawikiApi.live_states` and :meth:`CatawikiApi.outcome` read the
   final hammer price, sold flag, favourite count and bid count once
   ``bidding_end_time`` has passed.

Every response is validated strictly: a missing or malformed field raises
:class:`ScrapeError` rather than yielding a guessed value. Images are never
read or stored, and the per-bid ledger is never persisted - only ``bids_count``.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable, Iterator, Sequence
from urllib.parse import quote

from ..errors import ScrapeError
from ..fetch import fetch_json

SOURCE_NAME = "catawiki"
LOT_ID_RE = re.compile(r"/l/(\d+)")
CURRENCY = "EUR"


@dataclass(frozen=True, slots=True)
class LotRef:
    """An open lot seen in a search page. No price is known yet."""

    lot_id: str
    title: str
    subtitle: str | None
    url: str


@dataclass(frozen=True, slots=True)
class SearchPage:
    total: int
    lots: tuple[LotRef, ...]


@dataclass(frozen=True, slots=True)
class LiveState:
    """Bidding window and closed flag for one lot."""

    lot_id: str
    closed: bool
    favorite_count: int
    opened_at: date
    ended_at: date
    current_bid_eur: float | None


@dataclass(frozen=True, slots=True)
class BiddingOutcome:
    """Final result of one closed lot."""

    lot_id: str
    is_closed: bool
    is_sold: bool
    hammer_eur: int | None
    bids_count: int


@dataclass(frozen=True, slots=True)
class LotTitle:
    lot_id: str
    title: str
    url: str


def lot_id_from_url(url: str) -> str:
    """Extract the numeric lot id from a Catawiki lot URL."""
    match = LOT_ID_RE.search(url)
    if match is None:
        raise ScrapeError(f"not a Catawiki lot URL: {url!r}")
    return match.group(1)


def _object(payload: Any, context: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ScrapeError(f"{context}: expected an object, got {type(payload).__name__}")
    return payload


def _require(record: dict[str, Any], field: str, context: str) -> Any:
    if field not in record:
        raise ScrapeError(f"{context}: missing field {field!r}")
    return record[field]


def _text(record: dict[str, Any], field: str, context: str) -> str:
    value = _require(record, field, context)
    if not isinstance(value, str) or not value.strip():
        raise ScrapeError(f"{context}: {field} must be a non-empty string")
    return value.strip()


def _optional_text(record: dict[str, Any], field: str) -> str | None:
    value = record.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _int(record: dict[str, Any], field: str, context: str) -> int:
    value = _require(record, field, context)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ScrapeError(f"{context}: {field} must be an integer, got {value!r}")
    return value


def _bool(record: dict[str, Any], field: str, context: str) -> bool:
    value = _require(record, field, context)
    if not isinstance(value, bool):
        raise ScrapeError(f"{context}: {field} must be true/false, got {value!r}")
    return value


def _lot_id(record: dict[str, Any], context: str) -> str:
    value = _require(record, "id", context)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ScrapeError(f"{context}: id must be a positive integer, got {value!r}")
    return str(value)


def parse_utc_date(value: str, context: str) -> date:
    """Parse an ISO-8601 timestamp (``Z`` or ``+00:00``) into its UTC date."""
    if not isinstance(value, str) or not value.strip():
        raise ScrapeError(f"{context}: expected an ISO-8601 timestamp")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ScrapeError(f"{context}: invalid ISO-8601 timestamp {value!r}") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).date()


def _amount_eur(record: dict[str, Any], field: str, context: str) -> float | None:
    """Read a currency map such as ``{"EUR": 1401.0}``. Absent means no bid."""
    value = record.get(field)
    if value is None:
        return None
    amounts = _object(value, f"{context}.{field}")
    if CURRENCY not in amounts:
        return None
    amount = amounts[CURRENCY]
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ScrapeError(f"{context}: {field}.{CURRENCY} must be a number, got {amount!r}")
    if amount <= 0:
        raise ScrapeError(f"{context}: {field}.{CURRENCY} must be > 0, got {amount}")
    return float(amount)


def parse_search_page(payload: Any, *, query: str) -> SearchPage:
    """Parse ``/buyer/api/v1/search`` into open-lot references."""
    context = f"search {query!r}"
    body = _object(payload, context)
    total = _int(body, "total", context)
    if total < 0:
        raise ScrapeError(f"{context}: total must be >= 0, got {total}")
    raw_lots = _require(body, "lots", context)
    if not isinstance(raw_lots, list):
        raise ScrapeError(f"{context}: lots must be an array")
    refs: list[LotRef] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_lots):
        item_context = f"{context} lot #{index}"
        record = _object(raw, item_context)
        lot_id = _lot_id(record, item_context)
        if lot_id in seen:
            raise ScrapeError(f"{context}: duplicate lot id {lot_id} on one page")
        seen.add(lot_id)
        url = _text(record, "url", item_context)
        if lot_id_from_url(url) != lot_id:
            raise ScrapeError(f"{item_context}: url does not match lot id {lot_id}")
        refs.append(
            LotRef(
                lot_id=lot_id,
                title=_text(record, "title", item_context),
                subtitle=_optional_text(record, "subtitle"),
                url=url,
            )
        )
    return SearchPage(total=total, lots=tuple(refs))


def parse_live_lots(payload: Any) -> tuple[LiveState, ...]:
    """Parse ``/buyer/api/v1/lots/live``. Absent ids are simply not returned."""
    context = "lots/live"
    body = _object(payload, context)
    raw_lots = _require(body, "lots", context)
    if not isinstance(raw_lots, list):
        raise ScrapeError(f"{context}: lots must be an array")
    states: list[LiveState] = []
    for index, raw in enumerate(raw_lots):
        item_context = f"{context} lot #{index}"
        record = _object(raw, item_context)
        lot_id = _lot_id(record, item_context)
        opened_at = parse_utc_date(
            _text(record, "bidding_start_time", item_context), f"{item_context}.bidding_start_time"
        )
        ended_at = parse_utc_date(
            _text(record, "bidding_end_time", item_context), f"{item_context}.bidding_end_time"
        )
        if ended_at < opened_at:
            raise ScrapeError(f"{item_context}: bidding_end_time is before bidding_start_time")
        favorite_count = _int(record, "favorite_count", item_context)
        if favorite_count < 0:
            raise ScrapeError(f"{item_context}: favorite_count must be >= 0")
        states.append(
            LiveState(
                lot_id=lot_id,
                closed=_bool(record, "closed", item_context),
                favorite_count=favorite_count,
                opened_at=opened_at,
                ended_at=ended_at,
                current_bid_eur=_amount_eur(record, "current_bid_amount", item_context),
            )
        )
    return tuple(states)


def parse_lot_titles(payload: Any) -> tuple[LotTitle, ...]:
    """Parse ``/buyer/api/v1/lots`` (title and canonical URL only)."""
    context = "lots"
    body = _object(payload, context)
    raw_lots = _require(body, "lots", context)
    if not isinstance(raw_lots, list):
        raise ScrapeError(f"{context}: lots must be an array")
    titles: list[LotTitle] = []
    for index, raw in enumerate(raw_lots):
        item_context = f"{context} lot #{index}"
        record = _object(raw, item_context)
        lot_id = _lot_id(record, item_context)
        titles.append(
            LotTitle(
                lot_id=lot_id,
                title=_text(record, "title", item_context),
                url=_text(record, "url", item_context),
            )
        )
    return tuple(titles)


def parse_bidding_block(payload: Any, *, lot_id: str) -> BiddingOutcome:
    """Parse ``/buyer/api/v3/lots/{id}/bidding_block`` into a final outcome."""
    context = f"bidding_block {lot_id}"
    body = _object(payload, context)
    block = _object(_require(body, "bidding_block", context), f"{context}.bidding_block")
    lot = _object(_require(block, "lot", context), f"{context}.lot")
    reported_id = _lot_id(lot, f"{context}.lot")
    if reported_id != lot_id:
        raise ScrapeError(f"{context}: response is for lot {reported_id}")
    bids_count = _int(block, "bids_count", context)
    if bids_count < 0:
        raise ScrapeError(f"{context}: bids_count must be >= 0, got {bids_count}")
    is_sold = _bool(lot, "is_sold", f"{context}.lot")
    highest = lot.get("highest_bid_amount")
    hammer: int | None = None
    if is_sold:
        if isinstance(highest, bool) or not isinstance(highest, (int, float)):
            raise ScrapeError(f"{context}: sold lot without a numeric highest_bid_amount")
        if highest <= 0:
            raise ScrapeError(f"{context}: sold lot with highest_bid_amount {highest}")
        hammer = int(round(float(highest)))
    return BiddingOutcome(
        lot_id=lot_id,
        is_closed=_bool(lot, "is_closed", f"{context}.lot"),
        is_sold=is_sold,
        hammer_eur=hammer,
        bids_count=bids_count,
    )


def chunks(items: Sequence[str], size: int) -> Iterator[tuple[str, ...]]:
    """Split ids into batches so one request covers many lots."""
    if size < 1:
        raise ScrapeError(f"batch size must be >= 1, got {size}")
    for start in range(0, len(items), size):
        yield tuple(items[start : start + size])


JsonFetcher = Callable[[str, float, int], Any]


class CatawikiApi:
    """Thin HTTP client over the public buyer endpoints.

    ``fetch`` and ``sleep`` are injectable so tests never touch the network.
    A pause is applied before every request to keep the crawl polite; Catawiki
    rate-limits and blocks aggressive callers.
    """

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
