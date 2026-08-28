"""Rate-limited retrieval helpers for Catawiki lot pages."""

from __future__ import annotations

import socket
import urllib.error
from collections.abc import Callable

from ..errors import FetchError, ScrapeError


def build_lot_url(base_url: str, lot_id: str) -> str:
    """Build the canonical public Catawiki URL for one lot."""
    if not lot_id.strip() or "/" in lot_id or "?" in lot_id or "#" in lot_id:
        raise ScrapeError(f"invalid lot id: {lot_id!r}")
    return f"{base_url.rstrip('/')}/en/l/{lot_id}"


def _temporary(exc: FetchError) -> bool:
    """Recognize transport failures safe to retry without masking bad data."""
    cause: BaseException | None = exc.__cause__
    while cause is not None:
        if isinstance(cause, (TimeoutError, socket.timeout)):
            return True
        if isinstance(cause, urllib.error.URLError):
            reason = cause.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                return True
        if isinstance(cause, urllib.error.HTTPError):
            return cause.code == 429 or 500 <= cause.code <= 599
        cause = cause.__cause__
    return False


def fetch_lot_page(
    url: str,
    *,
    timeout_seconds: float,
    max_bytes: int,
    delay_seconds: float,
    max_retries: int,
    fetch: Callable[[str, float, int], str],
    sleep: Callable[[float], None],
) -> str:
    """Fetch one page, retrying only temporary transport failures."""
    last_error: FetchError | None = None
    for attempt in range(max_retries + 1):
        if attempt and delay_seconds > 0:
            sleep(delay_seconds * (2 ** (attempt - 1)))
        try:
            return fetch(url, timeout_seconds, max_bytes)
        except FetchError as exc:
            last_error = exc
            if not _temporary(exc) or attempt == max_retries:
                raise
    if last_error is None:
        raise FetchError(f"{url}: details fetch made no attempt")
    raise last_error
