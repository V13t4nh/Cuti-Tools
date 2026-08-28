"""Validated setting declarations used by :mod:`cuti.config`."""

from __future__ import annotations

import math
from pathlib import Path

from .config_types import SettingSpec
from .errors import ConfigError

NOTIFIER_KINDS = ("file", "telegram")


def _nonempty(name: str, value: object) -> object:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{name}: must not be empty")
    return value


def _number(name: str, value: object) -> object:
    if not math.isfinite(value):
        raise ConfigError(f"{name}: expected a finite number, got {value}")
    return value


def _nonnegative(name: str, value: object) -> object:
    _number(name, value)
    if value < 0:
        raise ConfigError(f"{name}: expected a value >= 0, got {value}")
    return value


def _positive(name: str, value: object) -> object:
    _number(name, value)
    if value <= 0:
        raise ConfigError(f"{name}: expected a value > 0, got {value}")
    return value


def _rate(name: str, value: object) -> object:
    _number(name, value)
    if not 0.0 <= value < 1.0:
        raise ConfigError(f"{name}: expected a rate in [0, 1), got {value}")
    return value


def _at_least_one(name: str, value: object) -> object:
    if value < 1:
        raise ConfigError(f"{name}: expected >= 1, got {value}")
    return value


def _batch_size(name: str, value: object) -> object:
    if not 1 <= value <= 100:
        raise ConfigError(f"{name}: expected 1..100, got {value}")
    return value


def _match_threshold(name: str, value: object) -> object:
    if not 0.0 < value <= 100.0:
        raise ConfigError(f"{name}: expected a value in (0, 100], got {value}")
    return value


def _notifier(name: str, value: object) -> object:
    value = value.strip().lower()
    if value not in NOTIFIER_KINDS:
        raise ConfigError(f"{name}: expected one of {', '.join(NOTIFIER_KINDS)}, got {value!r}")
    return value


def _http_url(name: str, value: object) -> object:
    value = value.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        raise ConfigError(f"{name}: expected an http(s) URL, got {value!r}")
    return value


def _parse_queries(value: str) -> object:
    return value


def _queries(name: str, value: object) -> object:
    result = tuple(part.strip() for part in value.split(",") if part.strip())
    if not result:
        raise ConfigError(f"{name}: expected at least one non-empty query")
    if len(set(result)) != len(result):
        raise ConfigError(f"{name}: duplicate queries in {result}")
    return result


def _path(base: Path, name: str, value: object) -> object:
    _nonempty(name, value)
    path = Path(value)
    return path if path.is_absolute() or value.startswith(("/", "\\")) else (base / path).resolve()


def _location(base: Path, name: str, value: object) -> object:
    _nonempty(name, value)
    if "://" in value:
        return value
    path = Path(value)
    return str(path if path.is_absolute() or value.startswith(("/", "\\")) else (base / path).resolve())


def _integer(name: str, value: object) -> object:
    if value < 0:
        raise ConfigError(f"{name}: expected a non-negative integer, got {value}")
    return value


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError("expected true or false")
    return normalized == "true"


SETTING_SPECS = (
    SettingSpec("CUTI_DB_PATH", "db_path", str, "var/auctions.db", _nonempty, _path),
    SettingSpec("CUTI_RULES_PATH", "rules_path", str, "config/rules.json", _nonempty, _path),
    SettingSpec("CUTI_LOTS_SOURCE_URL", "lots_source_url", str, "data/sample/catawiki/page-1.html", _nonempty, _location),
    SettingSpec("CUTI_DEALS_SOURCE_URL", "deals_source_url", str, "data/sample/deals/deals.json", _nonempty, _location),
    SettingSpec("CUTI_SOURCE_MAX_PAGES", "source_max_pages", int, "10", _at_least_one),
    SettingSpec("CUTI_CATAWIKI_API_BASE", "catawiki_api_base", str, "https://www.catawiki.com", _http_url),
    SettingSpec("CUTI_CATAWIKI_QUERIES", "catawiki_queries", _parse_queries, "watch", _queries),
    SettingSpec("CUTI_CATAWIKI_SEARCH_MAX_PAGES", "catawiki_search_max_pages", int, "5", _at_least_one),
    SettingSpec("CUTI_CATAWIKI_BATCH_SIZE", "catawiki_batch_size", int, "50", _batch_size),
    SettingSpec("CUTI_CATAWIKI_PAUSE_SECONDS", "catawiki_pause_seconds", float, "1.0", _nonnegative),
    SettingSpec("CUTI_DETAILS_REQUEST_DELAY_SECONDS", "details_request_delay_seconds", float, "1.0", _nonnegative),
    SettingSpec("CUTI_DETAILS_MAX_RETRIES", "details_max_retries", int, "2", _integer),
    SettingSpec("CUTI_DETAILS_ENABLED", "details_enabled", _parse_bool, "false", lambda _n, value: value),
    SettingSpec("CUTI_SETTLE_MAX_LOTS", "settle_max_lots", int, "200", _at_least_one),
    SettingSpec("CUTI_SETTLE_MIN_HEARTS", "settle_min_hearts", int, "0", _nonnegative),
    SettingSpec("CUTI_URL_CHECK_MAX_LOTS", "url_check_max_lots", int, "200", _at_least_one),
    SettingSpec("CUTI_HTTP_TIMEOUT_SECONDS", "http_timeout_seconds", float, "20", _positive),
    SettingSpec("CUTI_RESPONSE_MAX_BYTES", "response_max_bytes", int, "5000000", _at_least_one),
    SettingSpec("CUTI_COMMISSION_RATE", "commission_rate", float, "0.125", _rate),
    SettingSpec("CUTI_VAT_ON_COMMISSION_RATE", "vat_on_commission_rate", float, "0.21", _rate),
    SettingSpec("CUTI_SHIPPING_EUR", "shipping_eur", float, "35", _nonnegative),
    SettingSpec("CUTI_EUR_VND_RATE", "eur_vnd_rate", float, "27000", _positive),
    SettingSpec("CUTI_MIN_MARGIN_RATE", "min_margin_rate", float, "0.15", _rate),
    SettingSpec("CUTI_MIN_PROFIT_EUR", "min_profit_eur", float, "50", _nonnegative),
    SettingSpec("CUTI_MIN_COMPARABLES", "min_comparables", int, "5", _at_least_one),
    SettingSpec("CUTI_MATCH_THRESHOLD", "match_threshold", float, "85", _match_threshold),
    SettingSpec("CUTI_COMPARABLE_WINDOW_DAYS", "comparable_window_days", int, "730", _at_least_one),
    SettingSpec("CUTI_DATA_STALE_AFTER_HOURS", "data_stale_after_hours", float, "24", _positive),
    SettingSpec("CUTI_LIQUIDITY_REF_DAYS", "liquidity_ref_days", int, "30", _at_least_one),
    SettingSpec("CUTI_LIQUIDITY_HOT_HEARTS", "liquidity_hot_hearts", int, "50", _nonnegative),
    SettingSpec("CUTI_LIQUIDITY_W_SELL_THROUGH", "liquidity_w_sell_through", float, "0.5", _nonnegative),
    SettingSpec("CUTI_LIQUIDITY_W_SPEED", "liquidity_w_speed", float, "0.3", _nonnegative),
    SettingSpec("CUTI_LIQUIDITY_W_HEARTS", "liquidity_w_hearts", float, "0.2", _nonnegative),
    SettingSpec("CUTI_LIQUIDITY_MIN_LOTS", "liquidity_min_lots", int, "5", _at_least_one),
    SettingSpec("CUTI_LIQUIDITY_DECLINE_RATE", "liquidity_decline_rate", float, "0.20", _rate),
    SettingSpec("CUTI_DEAL_MAX_AGE_DAYS", "deal_max_age_days", int, "30", _integer),
    SettingSpec("CUTI_ALERT_MAX_ATTEMPTS", "alert_max_attempts", int, "8", _at_least_one),
    SettingSpec("CUTI_NOTIFIER", "notifier", str, "file", _notifier),
    SettingSpec("CUTI_NOTIFIER_FILE_PATH", "notifier_file_path", str, "var/alerts.jsonl", _nonempty, _path),
    SettingSpec("CUTI_TELEGRAM_API_BASE", "telegram_api_base", str, "https://api.telegram.org", _nonempty, lambda _b, _n, v: v.rstrip("/")),
    SettingSpec("CUTI_TELEGRAM_BOT_TOKEN", "telegram_bot_token", str, "", lambda _n, v: v.strip()),
    SettingSpec("CUTI_TELEGRAM_CHAT_ID", "telegram_chat_id", str, "", lambda _n, v: v.strip()),
    SettingSpec("CUTI_TELEGRAM_CHANNEL_ID", "telegram_channel_id", str, "", lambda _n, v: v.strip()),
    SettingSpec("CUTI_TELEGRAM_UPLOAD_PAUSE_SECONDS", "telegram_upload_pause_seconds", float, "1", _nonnegative),
    SettingSpec("CUTI_TELEGRAM_UPLOAD_MAX_ATTEMPTS", "telegram_upload_max_attempts", int, "5", _at_least_one),
    SettingSpec("CUTI_TELEGRAM_UPLOAD_MAX_BACKOFF_SECONDS", "telegram_upload_max_backoff_seconds", float, "60", _positive),
    SettingSpec("CUTI_TELEGRAM_UPLOAD_LEASE_SECONDS", "telegram_upload_lease_seconds", float, "300", _positive),
    SettingSpec("CUTI_REPORT_PATH", "report_path", str, "var/report.html", _nonempty, _path),
)

DEFAULTS = {spec.name: spec.default for spec in SETTING_SPECS}
