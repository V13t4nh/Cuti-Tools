"""Catawiki listing parser.

The markup contract is a flat list of ``lot-card`` elements carrying data
attributes plus an optional ``pagination-next`` link. Missing or malformed
attributes raise :class:`ScrapeError`; nothing is inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser

from ..errors import ScrapeError
from ..models import Condition, WatchForm

SOURCE_NAME = "catawiki"
LOT_CLASS = "lot-card"
NEXT_CLASS = "pagination-next"
REQUIRED_ATTRS = (
    "data-lot-id",
    "data-title",
    "data-condition",
    "data-form",
    "data-hearts",
    "data-sold",
    "data-opened-at",
    "data-ended-at",
    "data-url",
)
BOOLEAN_VALUES = {"true": True, "false": False}


@dataclass(frozen=True, slots=True)
class RawLot:
    """Source-shaped lot, before normalization."""

    lot_id: str
    title: str
    condition: Condition
    form: WatchForm
    hearts: int
    sold: bool
    hammer_eur: int | None
    opened_at: date
    ended_at: date
    url: str


@dataclass(frozen=True, slots=True)
class ListingPage:
    lots: tuple[RawLot, ...]
    next_href: str | None


def _classes(attrs: dict[str, str]) -> set[str]:
    return set(attrs.get("class", "").split())


def _require_attr(attrs: dict[str, str], name: str, context: str) -> str:
    value = attrs.get(name)
    if value is None or not value.strip():
        raise ScrapeError(f"{context}: missing attribute {name}")
    return value.strip()


def _parse_int(value: str, name: str, context: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ScrapeError(f"{context}: {name} must be an integer, got {value!r}") from exc


def _parse_bool(value: str, name: str, context: str) -> bool:
    parsed = BOOLEAN_VALUES.get(value.lower())
    if parsed is None:
        raise ScrapeError(f"{context}: {name} must be true/false, got {value!r}")
    return parsed


def _parse_date(value: str, name: str, context: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ScrapeError(f"{context}: {name} must be YYYY-MM-DD, got {value!r}") from exc


def _to_raw_lot(attrs: dict[str, str]) -> RawLot:
    context = f"{SOURCE_NAME} lot {attrs.get('data-lot-id', '<unknown>')}"
    for name in REQUIRED_ATTRS:
        _require_attr(attrs, name, context)
    sold = _parse_bool(attrs["data-sold"], "data-sold", context)
    hammer_raw = attrs.get("data-hammer-eur", "").strip()
    if sold:
        if not hammer_raw:
            raise ScrapeError(f"{context}: sold lot without data-hammer-eur")
        hammer = _parse_int(hammer_raw, "data-hammer-eur", context)
        if hammer <= 0:
            raise ScrapeError(f"{context}: data-hammer-eur must be > 0, got {hammer}")
    else:
        if hammer_raw:
            raise ScrapeError(f"{context}: unsold lot must not carry data-hammer-eur")
        hammer = None
    hearts = _parse_int(attrs["data-hearts"], "data-hearts", context)
    if hearts < 0:
        raise ScrapeError(f"{context}: data-hearts must be >= 0, got {hearts}")
    opened_at = _parse_date(attrs["data-opened-at"], "data-opened-at", context)
    ended_at = _parse_date(attrs["data-ended-at"], "data-ended-at", context)
    if ended_at < opened_at:
        raise ScrapeError(f"{context}: data-ended-at is before data-opened-at")
    return RawLot(
        lot_id=attrs["data-lot-id"].strip(),
        title=attrs["data-title"].strip(),
        condition=Condition.parse(attrs["data-condition"]),
        form=WatchForm.parse(attrs["data-form"]),
        hearts=hearts,
        sold=sold,
        hammer_eur=hammer,
        opened_at=opened_at,
        ended_at=ended_at,
        url=attrs["data-url"].strip(),
    )


class _ListingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lots: list[RawLot] = []
        self.next_href: str | None = None
        self._seen_ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: (value or "") for key, value in attrs}
        classes = _classes(attributes)
        if LOT_CLASS in classes:
            lot = _to_raw_lot(attributes)
            if lot.lot_id in self._seen_ids:
                raise ScrapeError(f"{SOURCE_NAME}: duplicate lot id {lot.lot_id} on one page")
            self._seen_ids.add(lot.lot_id)
            self.lots.append(lot)
        elif NEXT_CLASS in classes:
            href = attributes.get("href", "").strip()
            if not href:
                raise ScrapeError(f"{SOURCE_NAME}: pagination-next without href")
            if self.next_href is not None:
                raise ScrapeError(f"{SOURCE_NAME}: more than one pagination-next link")
            self.next_href = href

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def parse_listing(html: str) -> ListingPage:
    """Parse one listing page into raw lots plus the next-page href."""
    parser = _ListingParser()
    parser.feed(html)
    parser.close()
    if not parser.lots:
        raise ScrapeError(f"{SOURCE_NAME}: no '{LOT_CLASS}' elements found in page")
    return ListingPage(lots=tuple(parser.lots), next_href=parser.next_href)
