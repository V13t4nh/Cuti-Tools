"""Validated records and JSON payload parsers for the Catawiki adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from ..errors import ScrapeError

CURRENCY = "EUR"
LOT_ID_RE = re.compile(r"/l/(\d+)")


@dataclass(frozen=True, slots=True)
class LotRef:
    lot_id: str
    title: str
    subtitle: str | None
    url: str
    image_url: str | None = None

@dataclass(frozen=True, slots=True)
class SearchPage:
    total: int
    lots: tuple[LotRef, ...]

@dataclass(frozen=True, slots=True)
class LiveState:
    lot_id: str
    closed: bool
    favorite_count: int
    opened_at: date
    ended_at: date
    current_bid_eur: float | None

@dataclass(frozen=True, slots=True)
class BiddingOutcome:
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
    image_url: str | None = None

def lot_id_from_url(url: str) -> str:
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
    if value is None or not isinstance(value, str):
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

def _lots(payload: Any, context: str) -> list[Any]:
    body = _object(payload, context)
    raw_lots = _require(body, "lots", context)
    if not isinstance(raw_lots, list):
        raise ScrapeError(f"{context}: lots must be an array")
    return raw_lots

def _cover_url(record: dict[str, Any], context: str) -> str | None:
    cover_fields = [field for field in ("originalImageUrl", "original_image_url") if field in record]
    if len(cover_fields) > 1:
        raise ScrapeError(f"{context}: multiple cover URLs")
    image = record.get(cover_fields[0]) if cover_fields else None
    if image is None:
        return None
    if not isinstance(image, str):
        raise ScrapeError(f"{context}: cover URL must be an HTTP(S) URL")
    image = image.strip()
    parsed = urlsplit(image)
    if not image or parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ScrapeError(f"{context}: cover URL must be an HTTP(S) URL")
    return image

def parse_search_page(payload: Any, *, query: str) -> SearchPage:
    context = f"search {query!r}"
    body = _object(payload, context)
    total = _int(body, "total", context)
    if total < 0:
        raise ScrapeError(f"{context}: total must be >= 0, got {total}")
    refs: list[LotRef] = []
    seen: set[str] = set()
    for index, raw in enumerate(_lots(body, context)):
        item_context = f"{context} lot #{index}"
        record = _object(raw, item_context)
        lot_id = _lot_id(record, item_context)
        if lot_id in seen:
            raise ScrapeError(f"{context}: duplicate lot id {lot_id} on one page")
        seen.add(lot_id)
        url = _text(record, "url", item_context)
        if lot_id_from_url(url) != lot_id:
            raise ScrapeError(f"{item_context}: url does not match lot id {lot_id}")
        img = _cover_url(record, item_context)
        refs.append(LotRef(lot_id, _text(record, "title", item_context), _optional_text(record, "subtitle"), url, img))
    return SearchPage(total, tuple(refs))


def parse_live_lots(payload: Any) -> tuple[LiveState, ...]:
    context = "lots/live"
    states: list[LiveState] = []
    for index, raw in enumerate(_lots(payload, context)):
        item_context = f"{context} lot #{index}"
        record = _object(raw, item_context)
        lot_id = _lot_id(record, item_context)
        opened_at = parse_utc_date(_text(record, "bidding_start_time", item_context), f"{item_context}.bidding_start_time")
        ended_at = parse_utc_date(_text(record, "bidding_end_time", item_context), f"{item_context}.bidding_end_time")
        if ended_at < opened_at:
            raise ScrapeError(f"{item_context}: bidding_end_time is before bidding_start_time")
        favorite_count = _int(record, "favorite_count", item_context)
        if favorite_count < 0:
            raise ScrapeError(f"{item_context}: favorite_count must be >= 0")
        states.append(LiveState(lot_id, _bool(record, "closed", item_context), favorite_count, opened_at, ended_at, _amount_eur(record, "current_bid_amount", item_context)))
    return tuple(states)


def parse_lot_titles(payload: Any) -> tuple[LotTitle, ...]:
    context = "lots"
    titles: dict[str, LotTitle] = {}
    for index, raw in enumerate(_lots(payload, context)):
        item_context = f"{context} lot #{index}"
        record = _object(raw, item_context)
        lot_id = _lot_id(record, item_context)
        url = _text(record, "url", item_context)
        if lot_id_from_url(url) != lot_id:
            raise ScrapeError(f"{item_context}: url does not match lot id {lot_id}")
        title = LotTitle(lot_id, _text(record, "title", item_context), url, _cover_url(record, item_context))
        if lot_id in titles and titles[lot_id] != title:
            raise ScrapeError(f"{item_context}: duplicate lot id {lot_id} has conflicting records")
        titles[lot_id] = title
    return tuple(titles.values())


def parse_bidding_block(payload: Any, *, lot_id: str) -> BiddingOutcome:
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
    lot_context = f"{context}.lot"
    is_sold = _bool(lot, "is_sold", lot_context)
    highest = lot.get("highest_bid_amount")
    hammer: int | None = None
    if is_sold:
        if isinstance(highest, bool) or not isinstance(highest, (int, float)):
            raise ScrapeError(f"{context}: sold lot without a numeric highest_bid_amount")
        if highest <= 0:
            raise ScrapeError(f"{context}: sold lot with highest_bid_amount {highest}")
        hammer = int(round(float(highest)))
    return BiddingOutcome(lot_id, _bool(lot, "is_closed", lot_context), is_sold, hammer, bids_count)
