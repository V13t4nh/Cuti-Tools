"""Configuration and text primitives shared by normalization adapters."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigError
from .models import Condition

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9.\-]+")
_TRIM_CHARS = ".-"


def normalize_text(value: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    value = value.replace("Đ", "D").replace("đ", "d")
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    parts = (part.strip(_TRIM_CHARS) for part in _TOKEN_SPLIT_RE.split(ascii_text.lower()))
    return " ".join(part for part in parts if part)


def tokenize(value: str) -> list[str]:
    normalized = normalize_text(value)
    return normalized.split() if normalized else []


@dataclass(frozen=True, slots=True)
class IdentityRules:
    """Rules for extracting caliber and case code from a source reference."""

    split_patterns: tuple[tuple[str, re.Pattern[str]], ...] = ()
    vintage_brands: frozenset[str] = frozenset()
    modern_brands: frozenset[str] = frozenset()
    modern_ref_patterns: tuple[re.Pattern[str], ...] = ()
    caliber_patterns: tuple[re.Pattern[str], ...] = ()


@dataclass(frozen=True, slots=True)
class Rules:
    """Normalization vocabulary loaded from disk."""

    brand_aliases: dict[str, str]
    condition_keywords: tuple[tuple[Condition, tuple[str, ...]], ...]
    stopwords: frozenset[str]
    identity_tokens: frozenset[str]
    model_token_limit: int
    reference_pattern: re.Pattern[str] | None
    identity: IdentityRules = field(default_factory=IdentityRules)

    @property
    def brands(self) -> frozenset[str]:
        return frozenset(self.brand_aliases.values())

    @property
    def identity_rules(self) -> IdentityRules:
        """Compatibility alias used by source adapters."""
        return self.identity


def _require(mapping: dict, key: str, kind: type, path: Path):
    if key not in mapping:
        raise ConfigError(f"{path}: missing required key {key!r}")
    value = mapping[key]
    if not isinstance(value, kind):
        raise ConfigError(f"{path}: {key!r} must be {kind.__name__}, got {type(value).__name__}")
    return value


def _compile(value: object, path: Path, label: str) -> re.Pattern[str]:
    if not isinstance(value, str):
        raise ConfigError(f"{path}: {label} must be a string")
    try:
        return re.compile(value, re.IGNORECASE)
    except re.error as exc:
        raise ConfigError(f"{path}: invalid regex {label} ({exc})") from exc


def _identity_rules(raw: object, path: Path) -> IdentityRules:
    if raw is None:
        return IdentityRules()
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: identity must be an object")
    split_raw = raw.get("split_patterns", {})
    if not isinstance(split_raw, dict):
        raise ConfigError(f"{path}: identity.split_patterns must be an object")
    split = tuple((normalize_text(str(brand)), _compile(pattern, path, f"identity.split_patterns.{brand}"))
                  for brand, pattern in split_raw.items())
    vint = raw.get("vintage_brands", [])
    modern = raw.get("modern_brands", [])
    modern_patterns = raw.get("modern_ref_patterns", [])
    caliber = raw.get("caliber_patterns", [])
    for label, value in (("vintage_brands", vint), ("modern_brands", modern),
                         ("modern_ref_patterns", modern_patterns), ("caliber_patterns", caliber)):
        if not isinstance(value, list):
            raise ConfigError(f"{path}: identity.{label} must be a list")
    return IdentityRules(
        split_patterns=split,
        vintage_brands=frozenset(normalize_text(str(item)) for item in vint),
        modern_brands=frozenset(normalize_text(str(item)) for item in modern),
        modern_ref_patterns=tuple(_compile(item, path, f"identity.modern_ref_patterns[{i}]")
                                  for i, item in enumerate(modern_patterns)),
        caliber_patterns=tuple(_compile(item, path, f"identity.caliber_patterns[{i}]")
                               for i, item in enumerate(caliber)),
    )


def load_rules(path: Path) -> Rules:
    """Load and validate normalization plus source identity rules."""
    if not path.is_file():
        raise ConfigError(f"rules file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be an object")

    brands_raw = _require(raw, "brands", dict, path)
    brand_aliases: dict[str, str] = {}
    for canonical, aliases in brands_raw.items():
        if not isinstance(aliases, list):
            raise ConfigError(f"{path}: brands.{canonical} must be a list of aliases")
        key = normalize_text(canonical)
        if not key:
            raise ConfigError(f"{path}: brand name {canonical!r} normalizes to an empty string")
        brand_aliases[key] = key
        for alias in [*aliases, canonical]:
            alias_key = normalize_text(str(alias))
            if not alias_key:
                raise ConfigError(f"{path}: empty alias for brand {canonical!r}")
            existing = brand_aliases.get(alias_key)
            if existing is not None and existing != key:
                raise ConfigError(f"{path}: alias {alias_key!r} maps to both {existing!r} and {key!r}")
            brand_aliases[alias_key] = key
    if not brand_aliases:
        raise ConfigError(f"{path}: at least one brand is required")

    condition_raw = _require(raw, "condition", dict, path)
    priority = _require(condition_raw, "priority", list, path)
    keywords_raw = _require(condition_raw, "keywords", dict, path)
    condition_keywords: list[tuple[Condition, tuple[str, ...]]] = []
    for name in priority:
        condition = Condition.parse(str(name))
        words = keywords_raw.get(str(name))
        if not isinstance(words, list) or not words:
            raise ConfigError(f"{path}: condition.keywords.{name} must be a non-empty list")
        condition_keywords.append((condition, tuple(normalize_text(str(word)) for word in words)))
    stopwords = frozenset(normalize_text(str(word)) for word in _require(raw, "stopwords", list, path))
    identity_tokens = frozenset(normalize_text(str(word)) for word in _require(raw, "identity_tokens", list, path))
    if not identity_tokens or "" in identity_tokens:
        raise ConfigError(f"{path}: identity_tokens must contain non-empty values")
    model_token_limit = int(_require(raw, "model_token_limit", int, path))
    if model_token_limit < 1:
        raise ConfigError(f"{path}: model_token_limit must be >= 1")
    pattern_raw = raw.get("reference_pattern")
    if pattern_raw is not None and not isinstance(pattern_raw, str):
        raise ConfigError(f"{path}: reference_pattern must be a string")
    try:
        reference_pattern = re.compile(pattern_raw) if pattern_raw else None
    except re.error as exc:
        raise ConfigError(f"{path}: invalid reference_pattern ({exc})") from exc
    return Rules(brand_aliases, tuple(condition_keywords), stopwords, identity_tokens,
                 model_token_limit, reference_pattern, _identity_rules(raw.get("identity"), path))
