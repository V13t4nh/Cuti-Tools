"""Transport layer: fetch a source document as text or JSON.

Supports ``http(s)://`` via curl-cffi TLS Impersonation with HTTP/2 connection reuse,
dynamic TLS profile rotation on 403, optional environment proxy support, and ``file://``
via standard Python I/O. Any unrecoverable non-200 response, unknown scheme or missing
file raises :class:`FetchError` — never an empty string. Strictly NO silent fallback.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .errors import FetchError

try:
    from curl_cffi import requests as curl_requests
except ImportError as exc:
    curl_requests = None
    _IMPORT_ERROR: Exception | None = exc
else:
    _IMPORT_ERROR = None

SUPPORTED_SCHEMES = ("http", "https", "file")
TLS_PROFILES = ("chrome124", "safari17_0", "chrome120")
_CURRENT_PROFILE_IDX = 0
_SESSIONS: dict[str, Any] = {}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}
DEFAULT_MAX_BYTES = 5_000_000


def _get_proxy() -> dict[str, str] | None:
    proxy = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("ALL_PROXY")
    )
    return {"http": proxy, "https": proxy} if proxy else None


def _get_session_for_profile(profile: str) -> Any:
    if curl_requests is None:
        raise FetchError(
            f"curl-cffi is required for HTTP/HTTPS transport but failed to import: {_IMPORT_ERROR}"
        )
    if profile not in _SESSIONS:
        proxies = _get_proxy()
        _SESSIONS[profile] = curl_requests.Session(impersonate=profile, proxies=proxies)
    return _SESSIONS[profile]


def _get_tls_session() -> tuple[Any, str]:
    profile = TLS_PROFILES[_CURRENT_PROFILE_IDX % len(TLS_PROFILES)]
    return _get_session_for_profile(profile), profile


def _rotate_profile() -> tuple[Any, str]:
    global _CURRENT_PROFILE_IDX
    _CURRENT_PROFILE_IDX = (_CURRENT_PROFILE_IDX + 1) % len(TLS_PROFILES)
    return _get_tls_session()


def _safe_url(url: str) -> str:
    """Redact Telegram-style bot credentials and proxy passwords."""
    cleaned = re.sub(r"/bot[^/]+/", "/bot<redacted>/", url)
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:<redacted>@", cleaned)


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
    """Fetch a document and decode it as UTF-8. WAF 403 triggers profile rotation."""
    url = to_url(location)

    # 1. Local file transport (file:// scheme)
    if url.startswith("file://"):
        request = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
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

    # 2. Remote HTTP/HTTPS transport via TLS Impersonation (Scenario 2 self-healing)
    session, _ = _get_tls_session()
    try:
        resp = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout_seconds)
        if resp.status_code == 403:
            alt_session, _ = _rotate_profile()
            resp = alt_session.get(url, headers=DEFAULT_HEADERS, timeout=timeout_seconds)
        if resp.status_code != 200:
            raise FetchError(f"{_safe_url(url)}: HTTP {resp.status_code}")
        payload = resp.content
        if len(payload) > max_bytes:
            raise FetchError(f"{_safe_url(url)}: response exceeds {max_bytes} bytes")
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FetchError(f"{url}: payload is not valid UTF-8") from exc
    except FetchError:
        raise
    except Exception as exc:
        raise FetchError(f"{_safe_url(url)}: {exc}") from exc


def fetch_json(location: str, timeout_seconds: float, max_bytes: int = DEFAULT_MAX_BYTES) -> Any:
    text = fetch_text(location, timeout_seconds, max_bytes)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError(f"{location}: invalid JSON ({exc})") from exc


def probe_url(url: str, timeout_seconds: float) -> tuple[int, str]:
    """Check whether a page still exists, without reading its body."""
    if url.startswith("file://"):
        request = urllib.request.Request(url, headers=DEFAULT_HEADERS)
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

    # Remote HTTP/HTTPS via TLS Impersonation (rotates profile if 403)
    session, _ = _get_tls_session()
    try:
        resp = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout_seconds, allow_redirects=True)
        if resp.status_code == 403:
            alt_session, _ = _rotate_profile()
            resp = alt_session.get(url, headers=DEFAULT_HEADERS, timeout=timeout_seconds, allow_redirects=True)
        return int(resp.status_code), str(resp.url)
    except Exception as exc:
        raise FetchError(f"{_safe_url(url)}: {exc}") from exc


def post_json(
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Any:
    """POST a JSON body and decode the JSON response."""
    session, _ = _get_tls_session()
    headers = {**DEFAULT_HEADERS, "Content-Type": "application/json"}
    try:
        resp = session.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        if resp.status_code == 403:
            alt_session, _ = _rotate_profile()
            resp = alt_session.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        if len(resp.content) > max_bytes:
            raise FetchError(f"{_safe_url(url)}: response exceeds {max_bytes} bytes")
        if resp.status_code != 200:
            raise FetchError(f"{_safe_url(url)}: HTTP {resp.status_code}")
        try:
            return resp.json()
        except Exception as exc:
            raise FetchError(f"{_safe_url(url)}: invalid JSON response ({exc})") from exc
    except FetchError:
        raise
    except Exception as exc:
        raise FetchError(f"{_safe_url(url)}: {exc}") from exc
