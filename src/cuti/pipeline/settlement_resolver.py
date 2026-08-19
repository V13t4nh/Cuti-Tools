"""Resolve typed watch identity fields before a settled lot is stored."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping

from ..errors import NormalizationError
from ..normalize import Rules, detect_brand, normalize_text, reference_tokens, tokenize
from ..normalize_identity import extract_caliber, split_identity

_IDENTITY = ("brand", "caliber", "case_code")
_FIELDS = (*_IDENTITY, "model", "ref_number", "movement", "case_material", "case_diameter_mm")
_KEYS = {
    "brand": "brand", "model": "model", "reference": "ref_number", "ref": "ref_number",
    "reference number": "ref_number", "ref number": "ref_number", "ref_number": "ref_number",
    "caliber": "caliber", "calibre": "caliber", "case code": "case_code", "case_code": "case_code",
    "movement": "movement", "case material": "case_material", "case_material": "case_material",
    "case diameter": "case_diameter_mm", "case diameter mm": "case_diameter_mm",
    "case_diameter_mm": "case_diameter_mm",
}
@dataclass(frozen=True, slots=True)
class ResolvedFields:
    """Typed values plus review state and the model-key provenance tier."""

    brand: str | None = None
    model: str | None = None
    ref_number: str | None = None
    caliber: str | None = None
    case_code: str | None = None
    movement: str | None = None
    case_material: str | None = None
    case_diameter_mm: int | None = None
    model_key: str = ""
    model_key_tier: int = 5
    needs_review: int = 0
    specs: dict[str, Any] | None = None
def _object(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise NormalizationError(f"{name}: invalid JSON") from exc
    if is_dataclass(value):
        value = asdict(value)
    elif not isinstance(value, Mapping):
        value = {key: getattr(value, key) for key in _FIELDS if hasattr(value, key)}
    if not isinstance(value, Mapping):
        raise NormalizationError(f"{name}: expected an object")
    return dict(value)


def _key(value: Any) -> str | None:
    normalized = normalize_text(str(value))
    return _KEYS.get(normalized, normalized if normalized in _FIELDS else None)


def _text(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    result = " ".join(str(value).strip().split())
    return result or None


def _enum(value: Any, allowed: tuple[str, ...]) -> str | None:
    text = normalize_text(str(value)) if value is not None else ""
    if not text:
        return None
    if text in allowed:
        return text
    return None


def _typed_values(mapping: Mapping[str, Any], rules: Rules) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = {field: [] for field in _FIELDS}
    for raw_key, raw_value in mapping.items():
        field = _key(raw_key)
        if field is None:
            continue
        value: Any = raw_value
        if field == "brand":
            alias = normalize_text(str(raw_value))
            value = rules.brand_aliases.get(alias)
        elif field in {"model", "ref_number", "caliber", "case_code"}:
            value = _text(raw_value)
        elif field == "movement":
            value = _enum(raw_value, ("auto", "automatic", "manual", "quartz"))
            value = {"automatic": "auto"}.get(value, value)
        elif field == "case_material":
            value = _enum(raw_value, ("steel", "gold", "gold plated", "titanium", "other"))
            value = {"gold plated": "gold_plated"}.get(value, value)
        elif field == "case_diameter_mm":
            try:
                number = int(float(str(raw_value).lower().replace("mm", "").strip()))
            except (TypeError, ValueError):
                number = None
            value = number if number is not None and 15 <= number <= 60 else None
        if value is not None:
            result[field].append(value)
    return result


def _parse_text(text: str | None, rules: Rules) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = {field: [] for field in _FIELDS}
    if not text or not text.strip():
        return result
    try:
        result["brand"].append(detect_brand(text, rules))
    except NormalizationError:
        pass
    refs = reference_tokens(text, rules)
    if not refs:
        identity = rules.identity_rules
        refs = tuple(
            token
            for token in tokenize(text)
            if any(pattern.fullmatch(token) for _, pattern in identity.split_patterns)
            or any(pattern.fullmatch(token) for pattern in identity.modern_ref_patterns)
        )
    if len(refs) == 1:
        result["ref_number"].append(refs[0])
    value = extract_caliber(text, rules)
    if value:
        result["caliber"].append(value)
    return result


def _derive_source(values: dict[str, list[Any]], text: str, rules: Rules) -> dict[str, list[Any]]:
    """Derive identity facets per source before precedence/conflict merging."""
    brands = values.get("brand", [])
    if not brands:
        return values
    for ref in values.get("ref_number", []):
        parts = split_identity(str(brands[0]), str(ref), title=text, rules=rules)
        if parts.caliber is not None:
            values["caliber"].append(parts.caliber)
        if parts.case_code is not None:
            values["case_code"].append(parts.case_code)
    return values


def _canonical(value: Any) -> str:
    return re.sub(r"[\s-]+", "", normalize_text(str(value)))


def _merge_sources(sources: list[tuple[int, dict[str, list[Any]]]]) -> tuple[dict[str, Any], int, set[str]]:
    selected: dict[str, Any] = {}
    review = 0
    blocked: set[str] = set()
    for field in _FIELDS:
        present: list[tuple[int, Any]] = []
        conflict_tiers: set[int] = set()
        for tier, values in sources:
            if not values.get(field):
                continue
            normalized: dict[str, Any] = {}
            for value in values[field]:
                normalized.setdefault(_canonical(value), value)
            if len(normalized) > 1:
                if field in _IDENTITY:
                    review = 1
                conflict_tiers.add(tier)
                continue
            present.append((tier, next(iter(normalized.values()))))
        if not present:
            selected[field] = None
            continue
        best_tier = max(tier for tier, _ in present)
        best = [value for tier, value in present if tier == best_tier]
        best_keys = {_canonical(value) for value in best}
        if conflict_tiers and max(conflict_tiers) >= best_tier:
            selected[field] = None
            blocked.add(field)
        elif len(best_keys) > 1:
            selected[field] = None
            blocked.add(field)
        else:
            selected[field] = best[0]
        if field in _IDENTITY and len({_canonical(value) for _, value in present}) > 1:
            review = 1
    return selected, review, blocked


def _slug(title: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", normalize_text(title))).strip("-")


def _model_key(values: Mapping[str, Any], title: str) -> tuple[str, int]:
    brand = values.get("brand")
    prefix = normalize_text(str(brand)) if brand else ""
    candidates = (
        (1, ("caliber", "case_code")),
        (2, ("case_code",)),
        (3, ("ref_number",)),
        (4, ("model", "case_diameter_mm")),
    )
    for tier, names in candidates:
        if prefix and all(values.get(name) is not None for name in names):
            parts = [prefix, *(normalize_text(str(values[name])) for name in names)]
            return "|".join(parts), tier
    return "|".join(part for part in (prefix, _slug(title)) if part), 5


def _identity(
    values: dict[str, Any], title: str, description: str | None, rules: Rules, blocked: set[str]
) -> None:
    """Apply configured reference rules after source precedence is resolved."""
    ref = values.get("ref_number")
    brand = normalize_text(str(values.get("brand") or ""))
    if not ref or not brand:
        return
    parts = split_identity(brand, str(ref), title=title, description=description or "", rules=rules)
    if "caliber" not in blocked:
        values["caliber"] = values.get("caliber") or parts.caliber
    if "case_code" not in blocked:
        values["case_code"] = values.get("case_code") or parts.case_code


def resolve_typed_fields(
    title: str,
    rules: Rules,
    *,
    details: Any = None,
    description: str | None = None,
    override_json: Any = None,
    ai_json: Any = None,
) -> ResolvedFields:
    """Resolve fields by priority: override, Details, parse, AI, then None."""
    detail_obj = _object(details, "details")
    raw_details = detail_obj.get("details") if isinstance(detail_obj.get("details"), Mapping) else {}
    raw_details = {**detail_obj, **raw_details}
    override = _derive_source(_typed_values(_object(override_json, "override_json"), rules), "", rules)
    details_values = _derive_source(_typed_values(raw_details, rules), "", rules)
    title_values = _derive_source(_parse_text(title, rules), title, rules)
    description_values = _derive_source(_parse_text(description, rules), description or "", rules)
    ai_values = _derive_source(_typed_values(_object(ai_json, "ai_json"), rules), "", rules)
    sources = [(4, override), (3, details_values), (2, title_values), (2, description_values), (1, ai_values)]
    values, review, blocked = _merge_sources(sources)
    _identity(values, title, description, rules, blocked)
    model_key, tier = _model_key(values, title)
    specs = {"model_key_tier": tier}
    if isinstance(raw_details, Mapping) and raw_details:
        specs["details"] = dict(raw_details)
    return ResolvedFields(model_key=model_key, model_key_tier=tier, needs_review=review, specs=specs, **values)
