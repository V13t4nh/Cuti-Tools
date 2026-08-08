"""Vietnamese marketplace deal feed parser.

The feed contract is a JSON array of objects. Every record is validated
strictly; a malformed record aborts the batch instead of being skipped.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlparse

from ..errors import ScrapeError
from ..models import Condition, WatchForm

REQUIRED_FIELDS = ("source", "title", "ask_vnd", "url", "seen_at", "condition", "form")


@dataclass(frozen=True, slots=True)
class RawDeal:
    source: str
    title: str
    ask_vnd: int
    url: str
    seen_at: date
    condition: Condition
    form: WatchForm

    @property
    def dedupe_hash(self) -> str:
        digest = hashlib.sha256()
        digest.update(
            f"{self.source}|{self.title}|{self.ask_vnd}|{self.url}|"
            f"{self.condition.value}|{self.form.value}".encode("utf-8")
        )
        return digest.hexdigest()


def _require(record: dict[str, Any], field: str, index: int) -> Any:
    if field not in record:
        raise ScrapeError(f"deal #{index}: missing field {field!r}")
    return record[field]


def _require_text(record: dict[str, Any], field: str, index: int) -> str:
    value = _require(record, field, index)
    if not isinstance(value, str) or not value.strip():
        raise ScrapeError(f"deal #{index}: {field} must be a non-empty string")
    return value.strip()


def _to_raw_deal(record: Any, index: int) -> RawDeal:
    if not isinstance(record, dict):
        raise ScrapeError(f"deal #{index}: expected an object, got {type(record).__name__}")
    for field in REQUIRED_FIELDS:
        _require(record, field, index)

    title = _require_text(record, "title", index)
    source = _require_text(record, "source", index)
    url = _require_text(record, "url", index)
    if urlparse(url).scheme not in {"http", "https"}:
        raise ScrapeError(f"deal #{index}: url must use http or https")

    ask_raw = record["ask_vnd"]
    if isinstance(ask_raw, bool) or not isinstance(ask_raw, int):
        raise ScrapeError(f"deal #{index}: ask_vnd must be an integer, got {ask_raw!r}")
    if ask_raw <= 0:
        raise ScrapeError(f"deal #{index}: ask_vnd must be > 0, got {ask_raw}")

    seen_raw = _require_text(record, "seen_at", index)
    try:
        seen_at = date.fromisoformat(seen_raw)
    except ValueError as exc:
        raise ScrapeError(
            f"deal #{index}: seen_at must be YYYY-MM-DD, got {seen_raw!r}"
        ) from exc

    return RawDeal(
        source=source,
        title=title,
        ask_vnd=ask_raw,
        url=url,
        seen_at=seen_at,
        condition=Condition.parse(_require_text(record, "condition", index)),
        form=WatchForm.parse(_require_text(record, "form", index)),
    )


def parse_feed(payload: Any) -> tuple[RawDeal, ...]:
    """Parse a decoded JSON feed into validated raw deals."""
    if not isinstance(payload, list):
        raise ScrapeError(f"deal feed must be a JSON array, got {type(payload).__name__}")
    return tuple(_to_raw_deal(record, index) for index, record in enumerate(payload))
