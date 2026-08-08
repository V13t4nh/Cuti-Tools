"""Environment-driven configuration.

Every tunable lives here exactly once (DRY). Nothing downstream reads
``os.environ`` directly, and no module hard-codes a business constant.

Resolution order: real environment > ``.env`` file > ``DEFAULTS``.
Defaults are declared values, not runtime fallbacks: an invalid value always
raises :class:`ConfigError` instead of being silently repaired.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import timedelta, timezone
from pathlib import Path
from typing import Mapping

from .errors import ConfigError

ENV_FILE_NAME = ".env"
HOME_VAR = "CUTI_HOME"

DEFAULTS: dict[str, str] = {
    # storage
    "CUTI_DB_PATH": "var/auctions.db",
    "CUTI_RULES_PATH": "config/rules.json",
    # sources
    "CUTI_LOTS_SOURCE_URL": "data/sample/catawiki/page-1.html",
    "CUTI_DEALS_SOURCE_URL": "data/sample/deals/deals.json",
    "CUTI_SOURCE_MAX_PAGES": "10",
    "CUTI_HTTP_TIMEOUT_SECONDS": "20",
    "CUTI_RESPONSE_MAX_BYTES": "5000000",
    # pricing
    "CUTI_COMMISSION_RATE": "0.125",
    "CUTI_VAT_ON_COMMISSION_RATE": "0.21",
    "CUTI_SHIPPING_EUR": "35",
    "CUTI_EUR_VND_RATE": "27000",
    "CUTI_MIN_MARGIN_RATE": "0.15",
    "CUTI_MIN_PROFIT_EUR": "50",
    # matching
    "CUTI_MIN_COMPARABLES": "5",
    "CUTI_MATCH_THRESHOLD": "0.85",
    "CUTI_COMPARABLE_WINDOW_DAYS": "730",
    # liquidity index
    "CUTI_LIQUIDITY_REF_DAYS": "30",
    "CUTI_LIQUIDITY_HOT_HEARTS": "50",
    "CUTI_LIQUIDITY_W_SELL_THROUGH": "0.5",
    "CUTI_LIQUIDITY_W_SPEED": "0.3",
    "CUTI_LIQUIDITY_W_HEARTS": "0.2",
    "CUTI_LIQUIDITY_MIN_LOTS": "5",
    "CUTI_LIQUIDITY_DECLINE_RATE": "0.20",
    # deal freshness
    "CUTI_DEAL_MAX_AGE_DAYS": "30",
    "CUTI_ALERT_MAX_ATTEMPTS": "8",
    # notifications
    "CUTI_NOTIFIER": "file",
    "CUTI_NOTIFIER_FILE_PATH": "var/alerts.jsonl",
    "CUTI_TELEGRAM_API_BASE": "https://api.telegram.org",
    "CUTI_TELEGRAM_BOT_TOKEN": "",
    "CUTI_TELEGRAM_CHAT_ID": "",
    # reporting
    "CUTI_REPORT_PATH": "var/report.html",
}

NOTIFIER_KINDS = ("file", "telegram")
BUSINESS_TIMEZONE = timezone(timedelta(hours=7), name="Asia/Bangkok")


def parse_env_file(text: str) -> dict[str, str]:
    """Parse a minimal ``KEY=VALUE`` env file. Unparsable lines are errors."""
    values: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
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


def _resolve_values(env: Mapping[str, str], base_dir: Path) -> dict[str, str]:
    values = dict(DEFAULTS)
    env_file = base_dir / ENV_FILE_NAME
    if env_file.is_file():
        file_values = parse_env_file(env_file.read_text(encoding="utf-8"))
        unknown_file = sorted(k for k in file_values if k.startswith("CUTI_") and k not in DEFAULTS)
        if unknown_file:
            raise ConfigError(f"unknown CUTI_* variables in {ENV_FILE_NAME}: {', '.join(unknown_file)}")
        values.update(file_values)
    values.update({k: v for k, v in env.items() if k in DEFAULTS})
    unknown = sorted(
        k for k in env if k.startswith("CUTI_") and k not in DEFAULTS and k != HOME_VAR
    )
    if unknown:
        raise ConfigError(f"unknown CUTI_* variables: {', '.join(unknown)}")
    return values


def _as_float(values: Mapping[str, str], key: str) -> float:
    raw = values[key]
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{key}: expected a number, got {raw!r}") from exc


def _as_int(values: Mapping[str, str], key: str) -> int:
    raw = values[key]
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key}: expected an integer, got {raw!r}") from exc


def _require_rate(name: str, value: float) -> float:
    if not 0.0 <= value < 1.0:
        raise ConfigError(f"{name}: expected a rate in [0, 1), got {value}")
    return value


def _require_positive(name: str, value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ConfigError(f"{name}: expected a value > 0, got {value}")
    return value


def _require_non_negative(name: str, value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise ConfigError(f"{name}: expected a value >= 0, got {value}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable, validated runtime configuration."""

    base_dir: Path
    db_path: Path
    rules_path: Path
    lots_source_url: str
    deals_source_url: str
    source_max_pages: int
    http_timeout_seconds: float
    response_max_bytes: int
    commission_rate: float
    vat_on_commission_rate: float
    shipping_eur: float
    eur_vnd_rate: float
    min_margin_rate: float
    min_profit_eur: float
    min_comparables: int
    match_threshold: float
    comparable_window_days: int
    liquidity_ref_days: int
    liquidity_hot_hearts: int
    liquidity_w_sell_through: float
    liquidity_w_speed: float
    liquidity_w_hearts: float
    liquidity_min_lots: int
    liquidity_decline_rate: float
    deal_max_age_days: int
    alert_max_attempts: int
    notifier: str
    notifier_file_path: Path
    telegram_api_base: str
    telegram_bot_token: str
    telegram_chat_id: str
    report_path: Path

    @property
    def total_fee_multiplier(self) -> float:
        """Fraction of the hammer price kept by the marketplace (fee + VAT)."""
        return self.commission_rate * (1.0 + self.vat_on_commission_rate)


def _resolve_location(base_dir: Path, value: str, name: str) -> str:
    """Turn a plain path into an absolute one; leave real URLs untouched."""
    if not value:
        raise ConfigError(f"{name}: must not be empty")
    if "://" in value:
        return value
    path = Path(value)
    return str(path if path.is_absolute() or value.startswith(("/", "\\")) else (base_dir / path).resolve())


def _resolve_path(base_dir: Path, value: str, name: str) -> Path:
    if not value:
        raise ConfigError(f"{name}: must not be empty")
    path = Path(value)
    return path if path.is_absolute() or value.startswith(("/", "\\")) else (base_dir / path).resolve()


def load_settings(
    env: Mapping[str, str] | None = None, base_dir: Path | str | None = None
) -> Settings:
    """Build validated settings from the environment."""
    env = os.environ if env is None else env
    if base_dir is None:
        base_dir = env.get(HOME_VAR) or Path.cwd()
    base = Path(base_dir).resolve()
    if not base.is_dir():
        raise ConfigError(f"{HOME_VAR}: {base} is not a directory")

    values = _resolve_values(env, base)

    notifier = values["CUTI_NOTIFIER"].strip().lower()
    if notifier not in NOTIFIER_KINDS:
        raise ConfigError(
            f"CUTI_NOTIFIER: expected one of {', '.join(NOTIFIER_KINDS)}, got {notifier!r}"
        )
    telegram_token = values["CUTI_TELEGRAM_BOT_TOKEN"].strip()
    telegram_chat = values["CUTI_TELEGRAM_CHAT_ID"].strip()
    if notifier == "telegram" and not (telegram_token and telegram_chat):
        raise ConfigError(
            "CUTI_NOTIFIER=telegram requires CUTI_TELEGRAM_BOT_TOKEN and CUTI_TELEGRAM_CHAT_ID"
        )

    weights = {
        "CUTI_LIQUIDITY_W_SELL_THROUGH": _as_float(values, "CUTI_LIQUIDITY_W_SELL_THROUGH"),
        "CUTI_LIQUIDITY_W_SPEED": _as_float(values, "CUTI_LIQUIDITY_W_SPEED"),
        "CUTI_LIQUIDITY_W_HEARTS": _as_float(values, "CUTI_LIQUIDITY_W_HEARTS"),
    }
    for name, weight in weights.items():
        _require_non_negative(name, weight)
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ConfigError(
            "CUTI_LIQUIDITY_W_*: weights must sum to 1.0, got "
            + f"{sum(weights.values()):.4f}"
        )

    match_threshold = _as_float(values, "CUTI_MATCH_THRESHOLD")
    if not 0.0 < match_threshold <= 1.0:
        raise ConfigError(
            f"CUTI_MATCH_THRESHOLD: expected a value in (0, 1], got {match_threshold}"
        )

    min_comparables = _as_int(values, "CUTI_MIN_COMPARABLES")
    if min_comparables < 1:
        raise ConfigError(f"CUTI_MIN_COMPARABLES: expected >= 1, got {min_comparables}")

    max_pages = _as_int(values, "CUTI_SOURCE_MAX_PAGES")
    if max_pages < 1:
        raise ConfigError(f"CUTI_SOURCE_MAX_PAGES: expected >= 1, got {max_pages}")

    window_days = _as_int(values, "CUTI_COMPARABLE_WINDOW_DAYS")
    if window_days < 1:
        raise ConfigError(f"CUTI_COMPARABLE_WINDOW_DAYS: expected >= 1, got {window_days}")

    liquidity_min_lots = _as_int(values, "CUTI_LIQUIDITY_MIN_LOTS")
    if liquidity_min_lots < 1:
        raise ConfigError(f"CUTI_LIQUIDITY_MIN_LOTS: expected >= 1, got {liquidity_min_lots}")

    response_max_bytes = _as_int(values, "CUTI_RESPONSE_MAX_BYTES")
    if response_max_bytes < 1:
        raise ConfigError(f"CUTI_RESPONSE_MAX_BYTES: expected >= 1, got {response_max_bytes}")

    deal_max_age_days = _as_int(values, "CUTI_DEAL_MAX_AGE_DAYS")
    if deal_max_age_days < 0:
        raise ConfigError(f"CUTI_DEAL_MAX_AGE_DAYS: expected >= 0, got {deal_max_age_days}")

    alert_max_attempts = _as_int(values, "CUTI_ALERT_MAX_ATTEMPTS")
    if alert_max_attempts < 1:
        raise ConfigError(f"CUTI_ALERT_MAX_ATTEMPTS: expected >= 1, got {alert_max_attempts}")

    decline_rate = _require_rate(
        "CUTI_LIQUIDITY_DECLINE_RATE", _as_float(values, "CUTI_LIQUIDITY_DECLINE_RATE")
    )

    settings = Settings(
        base_dir=base,
        db_path=_resolve_path(base, values["CUTI_DB_PATH"], "CUTI_DB_PATH"),
        rules_path=_resolve_path(base, values["CUTI_RULES_PATH"], "CUTI_RULES_PATH"),
        lots_source_url=_resolve_location(
            base, values["CUTI_LOTS_SOURCE_URL"], "CUTI_LOTS_SOURCE_URL"
        ),
        deals_source_url=_resolve_location(
            base, values["CUTI_DEALS_SOURCE_URL"], "CUTI_DEALS_SOURCE_URL"
        ),
        source_max_pages=max_pages,
        http_timeout_seconds=_require_positive(
            "CUTI_HTTP_TIMEOUT_SECONDS", _as_float(values, "CUTI_HTTP_TIMEOUT_SECONDS")
        ),
        response_max_bytes=response_max_bytes,
        commission_rate=_require_rate(
            "CUTI_COMMISSION_RATE", _as_float(values, "CUTI_COMMISSION_RATE")
        ),
        vat_on_commission_rate=_require_rate(
            "CUTI_VAT_ON_COMMISSION_RATE", _as_float(values, "CUTI_VAT_ON_COMMISSION_RATE")
        ),
        shipping_eur=_require_non_negative(
            "CUTI_SHIPPING_EUR", _as_float(values, "CUTI_SHIPPING_EUR")
        ),
        eur_vnd_rate=_require_positive(
            "CUTI_EUR_VND_RATE", _as_float(values, "CUTI_EUR_VND_RATE")
        ),
        min_margin_rate=_require_rate(
            "CUTI_MIN_MARGIN_RATE", _as_float(values, "CUTI_MIN_MARGIN_RATE")
        ),
        min_profit_eur=_require_non_negative(
            "CUTI_MIN_PROFIT_EUR", _as_float(values, "CUTI_MIN_PROFIT_EUR")
        ),
        min_comparables=min_comparables,
        match_threshold=match_threshold,
        comparable_window_days=window_days,
        liquidity_ref_days=int(
            _require_positive(
                "CUTI_LIQUIDITY_REF_DAYS", _as_int(values, "CUTI_LIQUIDITY_REF_DAYS")
            )
        ),
        liquidity_hot_hearts=int(
            _require_non_negative(
                "CUTI_LIQUIDITY_HOT_HEARTS", _as_int(values, "CUTI_LIQUIDITY_HOT_HEARTS")
            )
        ),
        liquidity_w_sell_through=weights["CUTI_LIQUIDITY_W_SELL_THROUGH"],
        liquidity_w_speed=weights["CUTI_LIQUIDITY_W_SPEED"],
        liquidity_w_hearts=weights["CUTI_LIQUIDITY_W_HEARTS"],
        liquidity_min_lots=liquidity_min_lots,
        liquidity_decline_rate=decline_rate,
        deal_max_age_days=deal_max_age_days,
        alert_max_attempts=alert_max_attempts,
        notifier=notifier,
        notifier_file_path=_resolve_path(
            base, values["CUTI_NOTIFIER_FILE_PATH"], "CUTI_NOTIFIER_FILE_PATH"
        ),
        telegram_api_base=values["CUTI_TELEGRAM_API_BASE"].rstrip("/"),
        telegram_bot_token=telegram_token,
        telegram_chat_id=telegram_chat,
        report_path=_resolve_path(base, values["CUTI_REPORT_PATH"], "CUTI_REPORT_PATH"),
    )
    if settings.total_fee_multiplier >= 1.0:
        raise ConfigError(
            "CUTI_COMMISSION_RATE and CUTI_VAT_ON_COMMISSION_RATE produce fees >= hammer price"
        )
    writable_paths = {
        "CUTI_DB_PATH": settings.db_path,
        "CUTI_NOTIFIER_FILE_PATH": settings.notifier_file_path,
        "CUTI_REPORT_PATH": settings.report_path,
    }
    by_path: dict[Path, list[str]] = {}
    for name, path in writable_paths.items():
        by_path.setdefault(path, []).append(name)
    collisions = [names for names in by_path.values() if len(names) > 1]
    if collisions:
        joined = "; ".join(" = ".join(names) for names in collisions)
        raise ConfigError(f"output paths must be distinct: {joined}")
    return settings
