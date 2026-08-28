"""File backed pricing profile loading, validation, preview and apply."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from .config_pricing import (REQUIRED, FormulaError,
                             PricingParameter, PricingProfile, _NAME, profile_from_values)
from .errors import ConfigError

_LOCK = threading.RLock()
_FORMULAS = frozenset(("net_proceeds", "profit_threshold"))
_MAX_ITEMS = 64


def pricing_path(base_dir: Path) -> Path:
    return base_dir / "config" / "pricing.json"


def _profile_payload(payload: object, *, source: str, updated_at: str | None) -> PricingProfile:
    if not isinstance(payload, dict): raise ConfigError("pricing profile must be an object")
    raw_params, raw_helpers, raw_formulas = payload.get("parameters"), payload.get("helpers"), payload.get("formulas")
    if (not isinstance(raw_params, list) or not isinstance(raw_helpers, list) or not isinstance(raw_formulas, dict)
            or len(raw_params) > _MAX_ITEMS or len(raw_helpers) > _MAX_ITEMS):
        raise ConfigError("pricing profile requires parameters, helpers and formulas")
    params: list[PricingParameter] = []; names: set[str] = set()
    for item in raw_params:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str): raise ConfigError("invalid pricing parameter")
        name = item["name"]
        if name in names or name in {"hammer_eur", "cost_eur"}: raise ConfigError(f"duplicate or reserved parameter {name}")
        if not _NAME.fullmatch(name) or name in {"min", "max", "net_proceeds", "profit_threshold"}: raise ConfigError(f"invalid parameter name {name}")
        raw_value = item.get("value")
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)): raise ConfigError(f"invalid pricing parameter {name}")
        try: value, unit = float(raw_value), str(item["unit"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc: raise ConfigError(f"invalid pricing parameter {name}") from exc
        if unit not in ({"eur", "rate", "vnd_per_eur"} if name in REQUIRED else {"eur", "rate"}) or not (value == value and abs(value) != float("inf")):
            raise ConfigError(f"invalid pricing parameter {name}")
        if value < 0 or name in REQUIRED and unit == "rate" and value >= 1 or unit == "vnd_per_eur" and value <= 0: raise ConfigError(f"invalid pricing parameter {name}")
        required = name in REQUIRED
        if required and unit != REQUIRED[name][1]: raise ConfigError(f"invalid unit for {name}")
        params.append(PricingParameter(name, value, unit, required, False if required else bool(item.get("removable", True))))
        names.add(name)
    missing = set(REQUIRED) - names
    if missing: raise ConfigError("missing pricing parameters: " + ", ".join(sorted(missing)))
    helpers: list[tuple[str, str]] = []; helper_names: set[str] = set()
    for item in raw_helpers:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not isinstance(item.get("expression"), str): raise ConfigError("invalid pricing helper")
        name = item["name"]
        if not _NAME.fullmatch(name) or name in helper_names or name in names or name in _FORMULAS or name in {"hammer_eur", "cost_eur", "min", "max"}: raise ConfigError(f"duplicate helper {name}")
        helpers.append((name, item["expression"])); helper_names.add(name)
    formulas = []
    if set(raw_formulas) != _FORMULAS: raise ConfigError("formulas must contain net_proceeds and profit_threshold")
    for name in ("net_proceeds", "profit_threshold"):
        if not isinstance(raw_formulas[name], str) or not raw_formulas[name].strip(): raise ConfigError(f"invalid formula {name}")
        formulas.append((name, raw_formulas[name]))
    profile = PricingProfile(tuple(params), tuple(helpers), tuple(formulas), source, updated_at)
    profile.validate(); return profile


def profile_from_payload(payload: object) -> PricingProfile:
    return _profile_payload(payload, source="file", updated_at=None)


def load_pricing_profile(settings: object) -> PricingProfile:
    path = pricing_path(settings.base_dir)
    if not path.exists():
        return profile_from_values({name: getattr(settings, name) for name in REQUIRED}, source="env-derived")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict): raise ConfigError("pricing profile must be an object")
        profile = _profile_payload(document, source="file", updated_at=document.get("updated_at"))
        expected = document.get("revision")
        if expected is not None and expected != profile.revision: raise ConfigError("pricing profile revision does not match contents")
        stored_hash = document.get("hash")
        if stored_hash is not None and stored_hash != profile.revision: raise ConfigError("pricing profile hash does not match contents")
        return profile
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise ConfigError(f"cannot load pricing profile {path}: {exc}") from exc


def _document(profile: PricingProfile, updated_at: str) -> dict[str, object]:
    body = profile.to_dict(); body.update({"revision": profile.revision, "hash": profile.revision, "updated_at": updated_at})
    return body


def apply_pricing_profile(settings: object, candidate: PricingProfile, expected_revision: str) -> PricingProfile:
    path = pricing_path(settings.base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        active = load_pricing_profile(settings)
        if active.revision != expected_revision:
            raise FormulaError("expected_revision", "stale_revision", "pricing profile changed; reload active profile")
        candidate.validate()
        stamp = datetime.now(timezone.utc).isoformat()
        document = json.dumps(_document(candidate, stamp), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        fd, temporary = tempfile.mkstemp(prefix=".pricing.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(document); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            try: os.unlink(temporary)
            except OSError: pass
            raise ConfigError(f"cannot atomically write pricing profile {path}: {exc}") from exc
    return PricingProfile(candidate.parameters, candidate.helpers, candidate.formulas, "file", stamp)
