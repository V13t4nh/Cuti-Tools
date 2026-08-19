"""Environment-driven, validated application settings.

Resolution order is real environment, ``.env`` file, then the defaults in
``SETTING_SPECS``. Each setting's parser, default, validation, and
normalization is declared once in that table.
"""

from __future__ import annotations

import math
import os
from datetime import timedelta, timezone
from pathlib import Path
from typing import Mapping

from .config_types import Normalizer, Parser, SettingSpec, Settings, Validator
from .errors import ConfigError

ENV_FILE_NAME = ".env"
HOME_VAR = "CUTI_HOME"
NOTIFIER_KINDS = ("file", "telegram")
BUSINESS_TIMEZONE = timezone(timedelta(hours=7), name="Asia/Bangkok")

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


# name, Settings attribute, parser/type, default, validator, optional normalizer
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
    SettingSpec("CUTI_REPORT_PATH", "report_path", str, "var/report.html", _nonempty, _path),
)

DEFAULTS = {spec.name: spec.default for spec in SETTING_SPECS}


def parse_env_file(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise ConfigError(f"{ENV_FILE_NAME}:{lineno}: expected KEY=VALUE, got {raw!r}")
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            raise ConfigError(f"{ENV_FILE_NAME}:{lineno}: empty key")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def _resolve_values(env: Mapping[str, str], base: Path) -> dict[str, str]:
    values = dict(DEFAULTS)
    env_file = base / ENV_FILE_NAME
    if env_file.is_file():
        file_values = parse_env_file(env_file.read_text(encoding="utf-8"))
        unknown = sorted(k for k in file_values if k.startswith("CUTI_") and k not in DEFAULTS)
        if unknown:
            raise ConfigError(f"unknown CUTI_* variables in {ENV_FILE_NAME}: {', '.join(unknown)}")
        values.update(file_values)
    values.update({k: v for k, v in env.items() if k in DEFAULTS})
    unknown = sorted(k for k in env if k.startswith("CUTI_") and k not in DEFAULTS and k != HOME_VAR)
    if unknown:
        raise ConfigError(f"unknown CUTI_* variables: {', '.join(unknown)}")
    return values


def _convert(spec: SettingSpec, raw: str, base: Path) -> object:
    try:
        value = spec.parser(raw)
    except (TypeError, ValueError) as exc:
        kind = "a number" if spec.parser is float else "an integer" if spec.parser is int else "a valid value"
        raise ConfigError(f"{spec.name}: expected {kind}, got {raw!r}") from exc
    value = spec.validator(spec.name, value)
    return spec.normalizer(base, spec.name, value) if spec.normalizer else value


def load_settings(env: Mapping[str, str] | None = None, base_dir: Path | str | None = None) -> Settings:
    env = os.environ if env is None else env
    base = Path(base_dir or env.get(HOME_VAR) or Path.cwd()).resolve()
    if not base.is_dir():
        raise ConfigError(f"{HOME_VAR}: {base} is not a directory")
    values = _resolve_values(env, base)
    converted = {spec.attr: _convert(spec, values[spec.name], base) for spec in SETTING_SPECS}
    if converted["notifier"] == "telegram" and not (converted["telegram_bot_token"] and converted["telegram_chat_id"]):
        raise ConfigError("CUTI_NOTIFIER=telegram requires CUTI_TELEGRAM_BOT_TOKEN and CUTI_TELEGRAM_CHAT_ID")
    weights = tuple(converted[key] for key in ("liquidity_w_sell_through", "liquidity_w_speed", "liquidity_w_hearts"))
    if abs(sum(weights) - 1.0) > 1e-9:
        raise ConfigError(f"CUTI_LIQUIDITY_W_*: weights must sum to 1.0, got {sum(weights):.4f}")
    settings = Settings(base_dir=base, **converted)
    if settings.total_fee_multiplier >= 1.0:
        raise ConfigError("CUTI_COMMISSION_RATE and CUTI_VAT_ON_COMMISSION_RATE produce fees >= hammer price")
    writable = {
        "CUTI_DB_PATH": settings.db_path,
        "CUTI_NOTIFIER_FILE_PATH": settings.notifier_file_path,
        "CUTI_REPORT_PATH": settings.report_path,
    }
    by_path: dict[Path, list[str]] = {}
    for name, path in writable.items():
        by_path.setdefault(path, []).append(name)
    collisions = [names for names in by_path.values() if len(names) > 1]
    if collisions:
        raise ConfigError("output paths must be distinct: " + "; ".join(" = ".join(names) for names in collisions))
    return settings
