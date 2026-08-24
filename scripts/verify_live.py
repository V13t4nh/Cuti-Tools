"""Production-parity verification for the configured Catawiki source.

This layer is deliberately separate from ``scripts/verify.py``: the regular
verify command remains hermetic, while this command may read the two real
source URLs and records every result under ``var/live``.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import platform
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterator, Mapping

if __package__:
    from .verify import ACCEPTANCE_QUERY
else:
    from verify import ACCEPTANCE_QUERY

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIVE_LOTS = ("106019970", "105924279", "105418344", "105809071")
REQUIRED_ENV = ("CUTI_LOTS_SOURCE_URL", "CUTI_CATAWIKI_API_BASE")
# Keep the on-disk artifact strictly below the 200 KB acceptance limit.  The
# source response itself is still read in full (up to the configured transport
# limit); only the retained fixture is shortened from the tail.
FIXTURE_LIMIT = 200_000 - 1


class LiveVerificationError(RuntimeError):
    """A live source or payload failed a verification assertion."""


def _env_file_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def configured_sources(
    *, project_root: Path = PROJECT_ROOT, env: Mapping[str, str] | None = None
) -> tuple[dict[str, str], list[str]]:
    """Return explicitly configured source values and the missing names.

    Defaults are intentionally not considered real-source configuration.
    """
    values = _env_file_values(project_root / ".env")
    values.update(env if env is not None else os.environ)
    configured = {name: values.get(name, "").strip() for name in REQUIRED_ENV}
    return configured, [name for name, value in configured.items() if not value]


class _Log:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.file = path.open("w", encoding="utf-8", newline="")

    def write(self, text: str) -> None:
        self.file.write(text)
        self.file.flush()

    def line(self, text: str = "") -> None:
        self.write(text + "\n")

    def close(self) -> None:
        self.file.close()

    def __enter__(self) -> "_Log":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _environment_trace(log: _Log, env: Mapping[str, str]) -> None:
    log.line(f"PYTHON={sys.executable}")
    log.line(f"PYTHON_VERSION={platform.python_version()}")
    try:
        import subprocess

        packages = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
            check=False,
        )
        log.line("PACKAGES_BEGIN")
        log.write(packages.stdout)
        if packages.stdout and not packages.stdout.endswith("\n"):
            log.line()
        log.line("PACKAGES_END")
    except OSError as exc:
        log.line(f"PACKAGES_ERROR={exc}")
    present = sorted(name for name in env if name.startswith("CUTI_"))
    log.line("CUTI_ENV_NAMES=" + ",".join(present))


def _effective_environment() -> dict[str, str]:
    values = _env_file_values(PROJECT_ROOT / ".env")
    values.update(os.environ)
    return values


def _url_from_request(request: Any) -> str:
    return request.full_url if hasattr(request, "full_url") else str(request)


class _ResponseTrace:
    def __init__(self, response: Any, url: str, started: float, log: _Log) -> None:
        self._response = response
        self._url = url
        self._started = started
        self._log = log
        self._bytes = 0

    def read(self, *args: Any, **kwargs: Any) -> bytes:
        payload = self._response.read(*args, **kwargs)
        self._bytes += len(payload)
        return payload

    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)

    def __enter__(self) -> "_ResponseTrace":
        self._response.__enter__()
        return self

    def __exit__(self, *exc: object) -> Any:
        elapsed = (time.perf_counter() - self._started) * 1000
        status = int(getattr(self._response, "status", 0) or 0)
        self._log.line(
            f"REQUEST url={self._url} status={status} bytes={self._bytes} "
            f"time_ms={elapsed:.1f}"
        )
        return self._response.__exit__(*exc)


def _traced_urlopen(log: _Log):
    original = urllib.request.urlopen

    def traced(request: Any, *args: Any, **kwargs: Any) -> Any:
        url = _url_from_request(request)
        started = time.perf_counter()
        try:
            response = original(request, *args, **kwargs)
        except urllib.error.HTTPError as exc:
            elapsed = (time.perf_counter() - started) * 1000
            body = exc.read()
            log.line(
                f"REQUEST url={url} status={exc.code} bytes={len(body)} "
                f"time_ms={elapsed:.1f}"
            )
            if body:
                log.line("HTTP_ERROR_RESPONSE_BEGIN")
                log.write(body.decode("utf-8", errors="replace"))
                if not body.endswith(b"\n"):
                    log.line()
                log.line("HTTP_ERROR_RESPONSE_END")
            raise
        return _ResponseTrace(response, url, started, log)

    return original, traced


def _fetch_lot(url: str, *, timeout: float, max_bytes: int, retries: int, delay: float, log: _Log) -> bytes:
    """Fetch one lot with at most two retries for timeout/429/5xx."""
    from cuti.fetch import DEFAULT_HEADERS

    attempts = min(max(0, retries), 2) + 1
    for attempt in range(attempts):
        if attempt:
            time.sleep(max(1.0, delay) * (2 ** (attempt - 1)))
        started = time.perf_counter()
        request = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 0) or 0)
                body = response.read(max_bytes + 1)
            elapsed = (time.perf_counter() - started) * 1000
            log.line(
                f"REQUEST url={url} status={status} bytes={len(body)} "
                f"time_ms={elapsed:.1f} attempt={attempt + 1}"
            )
            if status != 200:
                if status == 403 or status == 404:
                    raise LiveVerificationError(f"{url}: HTTP {status}")
                if status == 429 or 500 <= status <= 599:
                    if attempt + 1 < attempts:
                        continue
                raise LiveVerificationError(f"{url}: HTTP {status}")
            if len(body) > max_bytes:
                raise LiveVerificationError(f"{url}: response exceeds {max_bytes} bytes")
            return body
        except urllib.error.HTTPError as exc:
            elapsed = (time.perf_counter() - started) * 1000
            body = exc.read()
            log.line(
                f"REQUEST url={url} status={exc.code} bytes={len(body)} "
                f"time_ms={elapsed:.1f} attempt={attempt + 1}"
            )
            if body:
                log.line("HTTP_ERROR_RESPONSE_BEGIN")
                log.write(body.decode("utf-8", errors="replace"))
                if not body.endswith(b"\n"):
                    log.line()
                log.line("HTTP_ERROR_RESPONSE_END")
            if exc.code == 429 or 500 <= exc.code <= 599:
                if attempt + 1 < attempts:
                    continue
            raise LiveVerificationError(f"{url}: HTTP {exc.code}") from exc
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            elapsed = (time.perf_counter() - started) * 1000
            log.line(
                f"REQUEST url={url} status=ERROR bytes=0 time_ms={elapsed:.1f} "
                f"attempt={attempt + 1} error={exc}"
            )
            temporary = isinstance(exc, TimeoutError) or (
                isinstance(exc, urllib.error.URLError)
                and isinstance(exc.reason, TimeoutError)
            )
            if temporary and attempt + 1 < attempts:
                continue
            raise LiveVerificationError(f"{url}: {exc}") from exc
    raise LiveVerificationError(f"{url}: retries exhausted")


def _compact_fixture(payload: bytes) -> bytes:
    if len(payload) <= FIXTURE_LIMIT:
        return payload
    text = payload.decode("utf-8", errors="replace")
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            props = data.get("props", {})
            page_props = props.get("pageProps", {})
            compacted_props = {
                "props": {
                    "pageProps": {
                        "lotDetailsData": page_props.get("lotDetailsData", {}),
                        "locale": page_props.get("locale", "en"),
                    }
                }
            }
            new_script = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(compacted_props, ensure_ascii=False)}</script>'
            text = text[:match.start()] + new_script + text[match.end():]
        except Exception:
            pass
    encoded = text.encode("utf-8")
    return encoded[:FIXTURE_LIMIT] if len(encoded) > FIXTURE_LIMIT else encoded


def _save_fixture(lot_id: str, payload: bytes, log: _Log) -> Path:
    fixture_dir = PROJECT_ROOT / "tests" / "fixtures" / "live"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    destination = fixture_dir / f"{lot_id}.html"
    if destination.is_file():
        log.line(f"FIXTURE_KEPT lot={lot_id} reason=existing path={destination}")
        return destination
    compacted = _compact_fixture(payload)
    destination.write_bytes(compacted)
    if len(payload) > len(compacted):
        log.line(
            f"FIXTURE lot={lot_id} path={destination} bytes={len(compacted)} "
            f"TRUNCATED_FROM={len(payload)} tail_discarded=true"
        )
    else:
        log.line(f"FIXTURE lot={lot_id} path={destination} bytes={len(compacted)}")
    return destination


def _fetch_fixtures(settings: Any, rules: Any, log: _Log) -> None:
    from cuti.pipeline.details import build_lot_url
    from cuti.scrapers.catawiki_lot_page import parse_lot_page

    for index, lot_id in enumerate(LIVE_LOTS):
        destination = PROJECT_ROOT / "tests" / "fixtures" / "live" / f"{lot_id}.html"
        if destination.is_file():
            log.line(f"FIXTURE_KEPT lot={lot_id} reason=existing path={destination}")
            continue
        if index:
            time.sleep(max(1.0, settings.details_request_delay_seconds))
        url = build_lot_url(settings.catawiki_api_base, lot_id)
        payload = _fetch_lot(
            url,
            timeout=settings.http_timeout_seconds,
            max_bytes=settings.response_max_bytes,
            retries=settings.details_max_retries,
            delay=settings.details_request_delay_seconds,
            log=log,
        )
        try:
            html = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LiveVerificationError(f"{lot_id}: payload is not UTF-8") from exc
        parsed = parse_lot_page(html, rules=rules)
        if not any((parsed.brand, parsed.model, parsed.ref_number, parsed.caliber, parsed.details, parsed.description)):
            raise LiveVerificationError(f"{lot_id}: payload has no recognized lot fields")
        _save_fixture(lot_id, payload, log)
        log.line(f"PARSED lot={lot_id} fields={json.dumps(asdict(parsed), sort_keys=True)}")


def _run_cli_logged(name: str, argv: list[str], env: dict[str, str], log_dir: Path) -> int:
    from cuti.cli import main

    path = log_dir / f"{name}.log"
    with _Log(path) as log:
        log.line("COMMAND=" + " ".join([sys.executable, "-m", "cuti.cli", *argv]))
        _environment_trace(log, env)
        original, traced = _traced_urlopen(log)
        old = {key: os.environ.get(key) for key in env}
        os.environ.update(env)
        try:
            urllib.request.urlopen = traced
            with contextlib.redirect_stdout(log.file), contextlib.redirect_stderr(log.file):
                try:
                    code = int(main(argv))
                except BaseException:
                    traceback.print_exc(file=log.file)
                    code = 1
        finally:
            urllib.request.urlopen = original
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        log.line(f"EXIT={code}")
    return code


def _run_pipeline(settings: Any, log_dir: Path) -> int:
    env = {
        "CUTI_HOME": str(PROJECT_ROOT),
        "CUTI_DB_PATH": str(log_dir / "live.db"),
        "CUTI_REPORT_PATH": str(log_dir / "report.html"),
        "CUTI_NOTIFIER_FILE_PATH": str(log_dir / "alerts.jsonl"),
        "CUTI_DETAILS_ENABLED": "true",
        "CUTI_SOURCE_MAX_PAGES": "1",
        "CUTI_SETTLE_MAX_LOTS": "50",
        # Make the explicitly selected live sources visible to every child
        # command, including when they came from the repository .env file.
        "CUTI_LOTS_SOURCE_URL": str(settings.lots_source_url),
        "CUTI_CATAWIKI_API_BASE": str(settings.catawiki_api_base),
    }
    common = ["--home", str(PROJECT_ROOT), "--today", date.today().isoformat(), "--json"]
    commands = {
        "init-db": [*common, "init-db"],
        "ingest": [*common, "ingest", "--max-lots", "50"],
        "settle": [*common, "settle"],
        "evaluate": [*common, "evaluate", "--query", ACCEPTANCE_QUERY, "--cost", "1000", "--currency", "eur", "--condition", "naked"],
        "liquidity": [*common, "liquidity"],
        "report": [*common, "report"],
        "status": [*common, "status"],
    }
    exit_code = 0
    for name, argv in commands.items():
        if _run_cli_logged(name, argv, env, log_dir):
            exit_code = 1
    return exit_code


def main() -> int:
    configured, missing = configured_sources()
    day_dir = PROJECT_ROOT / "var" / "live" / date.today().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    summary_path = day_dir / "verify-live.log"
    with _Log(summary_path) as summary:
        summary.line("COMMAND=" + " ".join([sys.executable, "scripts/verify_live.py"]))
        _environment_trace(summary, _effective_environment())
        if missing:
            message = "SKIP: missing real source configuration: " + ", ".join(missing)
            print(message)
            summary.line(message)
            summary.line("EXIT=0")
            return 0
        summary.line("CONFIGURED_SOURCE_NAMES=" + ",".join(configured))
        try:
            sys.path.insert(0, str(PROJECT_ROOT / "src"))
            from cuti.config import load_settings
            from cuti.normalize import load_rules

            settings = load_settings(base_dir=PROJECT_ROOT)
            rules = load_rules(settings.rules_path)
            fetch_code = 0
            with _Log(day_dir / "fetch-lots.log") as lot_log:
                lot_log.line(
                    "COMMAND="
                    + " ".join([sys.executable, "scripts/verify_live.py", "fetch-lots"])
                )
                _environment_trace(lot_log, _effective_environment())
                try:
                    _fetch_fixtures(settings, rules, lot_log)
                except BaseException:
                    traceback.print_exc(file=lot_log.file)
                    lot_log.line("EXIT=1")
                    fetch_code = 1
                else:
                    lot_log.line("EXIT=0")
            pipeline_code = _run_pipeline(settings, day_dir)
            code = 1 if fetch_code or pipeline_code else 0
        except BaseException:
            traceback.print_exc()
            summary.line("LIVE_VERIFICATION_ERROR")
            traceback.print_exc(file=summary.file)
            code = 1
        summary.line(f"EXIT={code}")
        return code


if __name__ == "__main__":
    raise SystemExit(main())
