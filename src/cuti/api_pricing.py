"""HTTP handlers for the editable pricing profile."""
from __future__ import annotations

import math
from typing import Mapping

from .config_pricing import FormulaError, PricingProfile
from .config_pricing_store import apply_pricing_profile, load_pricing_profile, profile_from_payload
from .errors import ConfigError, PricingError

LABELS = {"net_proceeds": "Lợi nhuận ròng", "profit_threshold": "Ngưỡng lợi nhuận", "break_even_hammer": "Giá hòa vốn"}


def _error(exc: Exception, field: str = "draft") -> dict[str, str]:
    if isinstance(exc, FormulaError): return {"field": exc.field, "code": exc.code, "message": exc.message}
    return {"field": field, "code": "invalid_profile", "message": str(exc)}


def _draft(body: object) -> PricingProfile:
    if not isinstance(body, dict) or not isinstance(body.get("draft"), dict):
        raise ConfigError("draft is required")
    return profile_from_payload(body["draft"])


def _inputs(body: object) -> tuple[float, float]:
    if not isinstance(body, dict) or not isinstance(body.get("inputs"), dict): raise ConfigError("inputs are required")
    values = body["inputs"]
    hammer, cost = values.get("hammer_eur"), values.get("cost_eur")
    try: hammer_value, cost_value = float(hammer), float(cost)
    except (TypeError, ValueError, OverflowError): hammer_value = cost_value = float("nan")
    if isinstance(hammer, bool) or not isinstance(hammer, (int, float)) or not math.isfinite(hammer_value) or hammer <= 0:
        raise FormulaError("inputs.hammer_eur", "non_finite", "hammer_eur must be finite and > 0")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost_value) or cost < 0:
        raise FormulaError("inputs.cost_eur", "non_finite", "cost_eur must be finite and >= 0")
    return hammer_value, cost_value


def _outputs(profile: PricingProfile, hammer: float, cost: float) -> list[dict[str, object]]:
    threshold = profile.evaluate("profit_threshold", hammer_eur=hammer, cost_eur=cost)
    values = {"net_proceeds": profile.evaluate("net_proceeds", hammer_eur=hammer, cost_eur=cost),
              "profit_threshold": threshold, "break_even_hammer": profile.inverse_break_even(cost, threshold)}
    units = {"net_proceeds": "eur", "profit_threshold": "eur", "break_even_hammer": "eur"}
    return [{"name": name, "label": LABELS[name], "value": value, "unit": units[name], "formatted": f"{value:,.2f} EUR"} for name, value in values.items()]


def get(settings: object) -> tuple[int, dict[str, object]]:
    profile = settings.pricing_profile if isinstance(settings.pricing_profile, PricingProfile) else load_pricing_profile(settings)
    return 200, {"state": "active", "active": profile.public()}


def preview(settings: object, body: object) -> tuple[int, dict[str, object]]:
    active = settings.pricing_profile if isinstance(settings.pricing_profile, PricingProfile) else load_pricing_profile(settings)
    try:
        draft = _draft(body); hammer, cost = _inputs(body); draft.validate()
        return 200, {"valid": True, "active_revision": active.revision, "draft": draft.to_dict(),
                      "preview": {"outputs": _outputs(draft, hammer, cost), "active_outputs": _outputs(active, hammer, cost)}, "errors": []}
    except (ConfigError, FormulaError, PricingError, KeyError, ValueError) as exc:
        return 200, {"valid": False, "active_revision": active.revision,
                      "draft": body.get("draft") if isinstance(body, dict) else None, "preview": None, "errors": [_error(exc)]}


def apply(settings: object, body: object) -> tuple[int, dict[str, object]]:
    if not isinstance(body, dict) or not isinstance(body.get("expected_revision"), str):
        raise ConfigError("expected_revision is required")
    candidate = _draft(body)
    active = apply_pricing_profile(settings, candidate, body["expected_revision"])
    return 200, {"state": "active", "active": active.public()}


def write(settings: object, method: str, body: object) -> tuple[int, dict[str, object]]:
    try:
        if method == "POST": return preview(settings, body)
        if method == "PUT": return apply(settings, body)
        return 405, {"error": {"code": "method_not_allowed", "message": "method is not allowed"}}
    except FormulaError as exc:
        status = 409 if exc.code == "stale_revision" else 422
        detail = {"field": exc.field, "code": exc.code, "message": exc.message}
        return status, {"error": {"code": exc.code, "message": exc.message, "details": {"field": exc.field}}, "errors": [detail]}
    except (ConfigError, PricingError, KeyError, ValueError) as exc:
        detail = {"field": "draft", "code": "invalid_profile", "message": str(exc)}
        return 422, {"error": {"code": "invalid_profile", "message": str(exc), "details": None}, "errors": [detail]}
