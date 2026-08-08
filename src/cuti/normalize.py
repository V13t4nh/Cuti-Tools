"""Title normalization: brand, model key and condition cluster.

All vocabulary lives in ``config/rules.json`` so the matching behaviour can be
tuned without touching code. Unknown brands raise instead of being guessed:
a wrong model key silently poisons every downstream price.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

from .errors import ConfigError, NormalizationError
from .models import Condition

# Dots and hyphens survive tokenization so reference numbers such as
# "210.30.42" or "116610-LN" stay a single, highly discriminative token.
_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9.\-]+")
_TRIM_CHARS = ".-"
_REFERENCE_CUES = frozenset({"ref", "reference"})
_YEAR_MIN = 1900
_YEAR_MAX = 2099


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
class Rules:
    """Normalization vocabulary loaded from disk."""

    brand_aliases: dict[str, str]
    condition_keywords: tuple[tuple[Condition, tuple[str, ...]], ...]
    stopwords: frozenset[str]
    identity_tokens: frozenset[str]
    model_token_limit: int
    reference_pattern: re.Pattern[str] | None

    @property
    def brands(self) -> frozenset[str]:
        return frozenset(self.brand_aliases.values())


def _require(mapping: dict, key: str, kind: type, path: Path):
    if key not in mapping:
        raise ConfigError(f"{path}: missing required key {key!r}")
    value = mapping[key]
    if not isinstance(value, kind):
        raise ConfigError(f"{path}: {key!r} must be {kind.__name__}, got {type(value).__name__}")
    return value


def load_rules(path: Path) -> Rules:
    """Load and validate the normalization rules file."""
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
                raise ConfigError(
                    f"{path}: alias {alias_key!r} maps to both {existing!r} and {key!r}"
                )
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
        condition_keywords.append(
            (condition, tuple(normalize_text(str(word)) for word in words))
        )
    stopwords = frozenset(
        normalize_text(str(word)) for word in _require(raw, "stopwords", list, path)
    )
    identity_raw = _require(raw, "identity_tokens", list, path)
    identity_tokens = frozenset(normalize_text(str(word)) for word in identity_raw)
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

    return Rules(
        brand_aliases=brand_aliases,
        condition_keywords=tuple(condition_keywords),
        stopwords=stopwords,
        identity_tokens=identity_tokens,
        model_token_limit=model_token_limit,
        reference_pattern=reference_pattern,
    )


def detect_brand(title: str, rules: Rules) -> str:
    """Return the canonical brand. Longest alias wins ("a lange sohne")."""
    tokens = tokenize(title)
    if not tokens:
        raise NormalizationError(f"title {title!r} contains no usable tokens")
    max_alias_len = max(len(alias.split()) for alias in rules.brand_aliases)
    for width in range(min(max_alias_len, len(tokens)), 0, -1):
        for start in range(0, len(tokens) - width + 1):
            candidate = " ".join(tokens[start : start + width])
            brand = rules.brand_aliases.get(candidate)
            if brand is not None:
                return brand
    raise NormalizationError(f"no known brand found in title {title!r}")


def detect_condition(title: str, rules: Rules) -> Condition | None:
    """Detect accessory completeness; return ``None`` when evidence is absent."""
    normalized = normalize_text(title)
    padded = f" {normalized} "
    no_box = any(
        phrase in padded
        for phrase in (" no box ", " without box ", " khong hop ", " mat hop ")
    )
    no_papers = any(
        phrase in padded
        for phrase in (
            " no papers ",
            " without papers ",
            " khong giay ",
            " mat giay ",
            " mat so ",
            " mat the ",
        )
    )
    evidence_text = padded
    for phrase in (
        " no box ",
        " without box ",
        " khong hop ",
        " mat hop ",
        " no papers ",
        " without papers ",
        " khong giay ",
        " mat giay ",
        " mat so ",
        " mat the ",
    ):
        evidence_text = evidence_text.replace(phrase, " ")
    matches: list[Condition] = []
    for condition, keywords in rules.condition_keywords:
        if any(f" {keyword} " in evidence_text for keyword in keywords):
            matches.append(condition)
    evidence = set(matches)
    contradiction = (
        (Condition.FULLSET in evidence and (no_box or no_papers))
        or (no_box and Condition.BOX in evidence)
        or (no_papers and Condition.PAPERS in evidence)
    )
    if contradiction:
        raise NormalizationError(f"contradictory condition evidence in title {title!r}")
    if Condition.NAKED in evidence and any(item is not Condition.NAKED for item in evidence):
        raise NormalizationError(f"contradictory condition evidence in title {title!r}")
    if Condition.FULLSET in evidence or {Condition.BOX, Condition.PAPERS} <= evidence:
        return Condition.FULLSET
    if Condition.PAPERS in evidence:
        return Condition.PAPERS
    if Condition.BOX in evidence:
        return Condition.BOX
    if Condition.NAKED in evidence or (no_box and no_papers):
        return Condition.NAKED
    return None


def _is_uncued_year(tokens: list[str], index: int) -> bool:
    token = tokens[index]
    if len(token) != 4 or not token.isdigit():
        return False
    previous = tokens[index - 1] if index else ""
    return _YEAR_MIN <= int(token) <= _YEAR_MAX and previous not in _REFERENCE_CUES


def _reference_tokens_from(tokens: list[str], rules: Rules) -> tuple[str, ...]:
    if rules.reference_pattern is None:
        return ()
    return tuple(
        sorted(
            {
                token
                for index, token in enumerate(tokens)
                if not _is_uncued_year(tokens, index)
                and rules.reference_pattern.fullmatch(token)
            }
        )
    )


def model_tokens(title: str, rules: Rules, *, brand: str | None = None) -> tuple[str, ...]:
    """Discriminative tokens of a title: reference number, else salient words."""
    brand = brand or detect_brand(title, rules)
    raw_tokens = tokenize(title)
    references = _reference_tokens_from(raw_tokens, rules)
    if references:
        return references

    brand_tokens = set(brand.split())
    condition_words = {
        word for _, keywords in rules.condition_keywords for word in " ".join(keywords).split()
    }
    tokens = [
        token
        for index, token in enumerate(raw_tokens)
        if token not in brand_tokens
        and token not in rules.stopwords
        and token not in rules.identity_tokens
        and token not in condition_words
        and not _is_uncued_year(raw_tokens, index)
    ]
    if not tokens:
        raise NormalizationError(f"title {title!r} has no model tokens after filtering")
    identity = sorted(set(raw_tokens) & rules.identity_tokens)
    return tuple(dict.fromkeys([*tokens[: rules.model_token_limit], *identity]))


def reference_tokens(title: str, rules: Rules) -> tuple[str, ...]:
    """Return explicit reference-number tokens from a title."""
    return _reference_tokens_from(tokenize(title), rules)


def model_key(title: str, rules: Rules, *, brand: str | None = None) -> str:
    """Stable identity of a watch model, e.g. ``omega:seamaster diver``."""
    brand = brand or detect_brand(title, rules)
    return f"{brand}:{' '.join(model_tokens(title, rules, brand=brand))}"


def similarity(left: str, right: str) -> float:
    """Order-insensitive similarity in [0, 1] between two titles."""
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return 0.0
    return fuzz.token_set_ratio(left_norm, right_norm) / 100.0


@dataclass(frozen=True, slots=True)
class Classification:
    brand: str
    model_key: str
    references: tuple[str, ...]
    condition: Condition | None


def classify(title: str, rules: Rules) -> Classification:
    """Single entry point used by every ingestion path (DRY)."""
    brand = detect_brand(title, rules)
    references = reference_tokens(title, rules)
    if len(references) > 1:
        raise NormalizationError(
            f"multiple reference numbers are ambiguous in title {title!r}: "
            + ", ".join(references)
        )
    return Classification(
        brand=brand,
        model_key=model_key(title, rules, brand=brand),
        references=references,
        condition=detect_condition(title, rules),
    )
