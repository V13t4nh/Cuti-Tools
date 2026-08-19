"""Domain records shared by every layer.

These dataclasses are the contract between scraping, storage, pricing and
reporting. They validate themselves on construction so an invalid record can
never reach the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from .errors import ScrapeError

class Condition(str, Enum):
    """The only four condition clusters the MVP distinguishes."""

    NAKED = "naked"
    BOX = "box"
    PAPERS = "papers"
    FULLSET = "fullset"

    @classmethod
    def parse(cls, value: str) -> "Condition":
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ScrapeError(f"unknown condition {value!r}; allowed: {allowed}") from exc

class WatchForm(str, Enum):
    """Case shape supplied by the source or explicitly selected by the buyer."""

    ROUND = "round"
    RECTANGULAR = "rectangular"
    SQUARE = "square"
    TONNEAU = "tonneau"
    OTHER = "other"
    UNKNOWN = "unknown"

    @classmethod
    def parse(cls, value: str) -> "WatchForm":
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ScrapeError(f"unknown watch form {value!r}; allowed: {allowed}") from exc

class Verdict(str, Enum):
    """Traffic-light output of a quote."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    INSUFFICIENT_DATA = "insufficient_data"

@dataclass(frozen=True, slots=True)
class Lot:
    """A finished auction lot (sold or unsold)."""

    lot_id: str
    source: str
    title: str
    brand: str
    model_key: str
    condition_tag: Condition
    hearts: int
    sold: bool
    hammer_eur: int | None
    opened_at: date
    ended_at: date
    url: str
    form: WatchForm = WatchForm.UNKNOWN
    subtitle: str | None = None
    # Number of bids at close. Kept for heat analysis; the per-bid ledger is
    # never stored. None means the source did not report it.
    bids_count: int | None = None
    # False once the public lot page no longer resolves. The snapshot stays the
    # source of truth either way.
    source_available: bool = True
    # Typed identity captured at settlement. All are optional because source
    # evidence may be absent or intentionally blocked by a conflict.
    model: str | None = None
    ref_number: str | None = None
    caliber: str | None = None
    case_code: str | None = None
    movement: str | None = None
    case_material: str | None = None
    case_diameter_mm: int | None = None
    specs_json: str | None = None
    ai_json: str | None = None
    needs_review: int = 0
    review_status: str = "pending"
    reviewed_at: str | None = None
    override_json: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.lot_id.strip():
            raise ScrapeError("lot_id must not be empty")
        if not self.title.strip():
            raise ScrapeError(f"{self.lot_id}: title must not be empty")
        if self.hearts < 0:
            raise ScrapeError(f"{self.lot_id}: hearts must be >= 0, got {self.hearts}")
        if self.ended_at < self.opened_at:
            raise ScrapeError(
                f"{self.lot_id}: ended_at {self.ended_at} is before opened_at {self.opened_at}"
            )
        if self.sold:
            if self.hammer_eur is None or self.hammer_eur <= 0:
                raise ScrapeError(
                    f"{self.lot_id}: a sold lot needs a positive hammer price, got {self.hammer_eur}"
                )
        elif self.hammer_eur is not None:
            raise ScrapeError(f"{self.lot_id}: an unsold lot must not have a hammer price")
        if self.bids_count is not None and self.bids_count < 0:
            raise ScrapeError(f"{self.lot_id}: bids_count must be >= 0, got {self.bids_count}")
        if self.needs_review not in (0, 1):
            raise ScrapeError(f"{self.lot_id}: needs_review must be 0 or 1")
        if self.review_status not in {"pending", "resolved", "ignored"}:
            raise ScrapeError(f"{self.lot_id}: invalid review_status {self.review_status!r}")

    @property
    def days_to_close(self) -> int:
        return (self.ended_at - self.opened_at).days

@dataclass(frozen=True, slots=True)
class Deal:
    """A watch offered for sale on the Vietnamese market."""

    source: str
    raw_title: str
    ask_vnd: int
    url: str
    seen_at: date
    model_key: str
    condition_tag: Condition
    dedupe_hash: str
    form: WatchForm = WatchForm.UNKNOWN

    def __post_init__(self) -> None:
        if not self.raw_title.strip():
            raise ScrapeError("raw_title must not be empty")
        if self.ask_vnd <= 0:
            raise ScrapeError(f"{self.raw_title!r}: ask_vnd must be > 0, got {self.ask_vnd}")
