"""Config-driven Catawiki reference, caliber and case-code extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .normalize_rules import IdentityRules, Rules, normalize_text


@dataclass(frozen=True, slots=True)
class IdentityParts:
    """The two optional identity facets derived from a lot reference."""

    caliber: str | None
    case_code: str | None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _rule_for(brand: str, rules: IdentityRules):
    key = normalize_text(brand)
    for candidate, pattern in rules.split_patterns:
        if candidate == key:
            return pattern
    return None


def extract_caliber(text: str, rules: Rules | IdentityRules) -> str | None:
    """Extract an explicitly labelled caliber; absent evidence stays ``None``."""
    identity = rules.identity if isinstance(rules, Rules) else rules
    for pattern in identity.caliber_patterns:
        match = pattern.search(text or "")
        if match is None:
            continue
        value = match.groupdict().get("caliber")
        if value is None:
            value = match.group(1) if match.lastindex else match.group(0)
        return _clean(value)
    return None


def split_identity(
    brand: str,
    ref_number: str | None,
    *,
    title: str = "",
    description: str = "",
    rules: Rules,
) -> IdentityParts:
    """Resolve caliber/case code according to configured brand rules.

    A split is accepted only when the configured regex captures both values.
    Vintage and modern rules deliberately keep the complete reference as the
    case code. Caliber is read only from explicit ``Cal.``/``Caliber`` source
    text, never inferred from a generation or reference number.
    """
    reference = _clean(ref_number)
    if reference is None:
        return IdentityParts(None, None)
    identity = rules.identity
    key = normalize_text(brand)
    # Generation/format rules take precedence over caliber-case parsing.  This
    # keeps modern SKUs such as ``NJ0153-82X`` and ``16234(Y)`` whole even when
    # they happen to contain a hyphen.
    if key in identity.modern_brands or any(
        pattern.fullmatch(reference) for pattern in identity.modern_ref_patterns
    ):
        return IdentityParts(None, reference)
    pattern = _rule_for(brand, identity)
    if pattern is not None:
        match = pattern.fullmatch(reference)
        if match is not None:
            groups = match.groupdict()
            caliber = _clean(groups.get("caliber"))
            case_code = _clean(groups.get("case_code"))
            if caliber is not None and case_code is not None:
                return IdentityParts(caliber, case_code)
    if key in identity.vintage_brands:
        return IdentityParts(extract_caliber(f"{title}\n{description}", identity), reference)
    return IdentityParts(extract_caliber(f"{title}\n{description}", identity), reference)


def identity_value(value: str | None) -> str | None:
    """Normalize identity values for source conflict comparison."""
    if value is None:
        return None
    return re.sub(r"[\s-]+", "", normalize_text(value)) or None
