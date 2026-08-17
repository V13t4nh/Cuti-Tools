"""Transport layer: fetch a source document as text.

Supports ``http(s)://``, ``file://`` and plain local paths so the same code
path serves production URLs and the bundled sample data. Any non-200 response,
unknown scheme or missing file raises :class:`FetchError` — never an empty
string.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .errors import FetchError

SUPPORTED_SCHEMES = ("http", "https", "file")
USER_AGENT = "cuti-tools/1.0 (+https://github.com/V13t4nh/Cuti-Tools)"
DEFAULT_MAX_BYTES = 5_000_000

def _safe_url(url: str) -> str:
    """Redact Telegram-style bot credentials before including a URL in errors."""
    return re.sub(r"/bot[^/]+/", "/bot<redacted>/", url)

def to_url(location: str) -> str:
    """Normalize a plain path into a ``file://`` URL; leave URLs untouched."""
    if not location:
        raise FetchError("empty source location")
    path = Path(location)
    if path.is_absolute():
        return path.resolve().as_uri()
    parsed = urllib.parse.urlparse(location)
    if parsed.scheme in SUPPORTED_SCHEMES:
        return location
    if parsed.scheme:
        raise FetchError(
            f"unsupported scheme {parsed.scheme!r}; allowed: {', '.join(SUPPORTED_SCHEMES)}"
        )
    return Path(location).resolve().as_uri()

def resolve(base_url: str, href: str) -> str:
    """Resolve a possibly relative link against the page it was found on."""
    return urllib.parse.urljoin(base_url, href)

def fetch_text(
    location: str, timeout_seconds: float, max_bytes: int = DEFAULT_MAX_BYTES
) -> str:
    """Fetch a document and decode it as UTF-8."""
    url = to_url(location)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None)
            # file:// responses carry no status; http(s) must answer exactly 200.
            if url.startswith(("http://", "https://")) and status != 200:
                raise FetchError(f"{url}: HTTP {status}")
            payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise FetchError(f"{_safe_url(url)}: response exceeds {max_bytes} bytes")
    except urllib.error.HTTPError as exc:
        raise FetchError(f"{_safe_url(url)}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"{_safe_url(url)}: {exc.reason}") from exc
    except OSError as exc:
        raise FetchError(f"{_safe_url(url)}: {exc}") from exc
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FetchError(f"{url}: payload is not valid UTF-8") from exc

def fetch_json(location: str, timeout_seconds: float, max_bytes: int = DEFAULT_MAX_BYTES) -> Any:
    text = fetch_text(location, timeout_seconds, max_bytes)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError(f"{location}: invalid JSON ({exc})") from exc

def probe_url(url: str, timeout_seconds: float) -> tuple[int, str]:
    """Check whether a page still exists, without reading its body.

    Returns the HTTP status and the final URL after redirects, so a caller can
    tell "still the same lot page" from "redirected to a category page". A 4xx
    answer is a result, not an error; only transport failures raise.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 0) or 0)
            return status, response.geturl()
    except urllib.error.HTTPError as exc:
        return int(exc.code), url
    except urllib.error.URLError as exc:
        raise FetchError(f"{_safe_url(url)}: {exc.reason}") from exc
    except OSError as exc:
        raise FetchError(f"{_safe_url(url)}: {exc}") from exc


def post_json(
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Any:
    """POST a JSON body and decode the JSON response."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read(max_bytes + 1)
            if len(raw_body) > max_bytes:
                raise FetchError(f"{_safe_url(url)}: response exceeds {max_bytes} bytes")
            body = raw_body.decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise FetchError(f"{_safe_url(url)}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"{_safe_url(url)}: {exc.reason}") from exc
    except OSError as exc:
        raise FetchError(f"{_safe_url(url)}: {exc}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise FetchError(f"{_safe_url(url)}: invalid JSON response ({exc})") from exc
