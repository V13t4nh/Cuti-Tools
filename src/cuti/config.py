"""Environment-driven, validated application settings.

Resolution order is real environment, ``.env`` file, then the defaults in
``SETTING_SPECS``. Each setting's parser, default, validation, and
normalization is declared once in that table.
"""

from __future__ import annotations

import os
from datetime import timedelta, timezone
from pathlib import Path
from typing import Mapping

from .config_specs import DEFAULTS, NOTIFIER_KINDS, SETTING_SPECS
from .config_types import Settings
from .errors import ConfigError

ENV_FILE_NAME = ".env"
HOME_VAR = "CUTI_HOME"
BUSINESS_TIMEZONE = timezone(timedelta(hours=7), name="Asia/Bangkok")


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
