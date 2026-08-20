"""Model-key derivation kept separate from typed-field resolution."""

from __future__ import annotations

import re
from typing import Any, Mapping

from ..normalize import normalize_text


def _slug(title: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", normalize_text(title))).strip("-")


def model_key(values: Mapping[str, Any], title: str) -> tuple[str, int]:
    """Return the strongest configured model identity and its provenance tier."""
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
