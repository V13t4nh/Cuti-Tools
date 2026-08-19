"""Title normalization: brand detection, condition clustering and model keys."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from .errors import NormalizationError
from .models import Condition
from .normalize_rules import IdentityRules, Rules, load_rules, normalize_text, tokenize
from .normalize_identity import IdentityParts, extract_caliber, identity_value, split_identity

__all__ = [
    "IdentityRules", "IdentityParts", "Rules", "load_rules", "normalize_text", "tokenize",
    "extract_caliber", "identity_value", "split_identity",
    "detect_brand", "detect_condition", "model_tokens", "reference_tokens",
    "model_key", "similarity", "Classification", "classify",
]

_REFERENCE_CUES = frozenset({"ref", "reference"})
_YEAR_MIN = 1900
_YEAR_MAX = 2099


def detect_brand(title: str, rules: Rules) -> str:
    """Return the canonical brand. Longest alias wins."""
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
    no_box = any(phrase in padded for phrase in (" no box ", " without box ", " khong hop ", " mat hop "))
    no_papers = any(phrase in padded for phrase in (
        " no papers ", " without papers ", " khong giay ", " mat giay ", " mat so ", " mat the "))
    evidence_text = padded
    for phrase in (" no box ", " without box ", " khong hop ", " mat hop ", " no papers ",
                   " without papers ", " khong giay ", " mat giay ", " mat so ", " mat the "):
        evidence_text = evidence_text.replace(phrase, " ")
    matches: list[Condition] = []
    for condition, keywords in rules.condition_keywords:
        if any(f" {keyword} " in evidence_text for keyword in keywords):
            matches.append(condition)
    evidence = set(matches)
    contradiction = ((Condition.FULLSET in evidence and (no_box or no_papers))
                     or (no_box and Condition.BOX in evidence)
                     or (no_papers and Condition.PAPERS in evidence))
    if contradiction or (Condition.NAKED in evidence and any(item is not Condition.NAKED for item in evidence)):
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
    return tuple(sorted({token for index, token in enumerate(tokens)
                         if not _is_uncued_year(tokens, index)
                         and rules.reference_pattern.fullmatch(token)}))


def model_tokens(title: str, rules: Rules, *, brand: str | None = None) -> tuple[str, ...]:
    """Discriminative tokens of a title: reference number, else salient words."""
    brand = brand or detect_brand(title, rules)
    raw_tokens = tokenize(title)
    references = _reference_tokens_from(raw_tokens, rules)
    if references:
        return references
    brand_tokens = set(brand.split())
    condition_words = {word for _, keywords in rules.condition_keywords for word in " ".join(keywords).split()}
    tokens = [token for index, token in enumerate(raw_tokens)
              if token not in brand_tokens and token not in rules.stopwords
              and token not in rules.identity_tokens and token not in condition_words
              and not _is_uncued_year(raw_tokens, index)]
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
    """Return order-insensitive token-set similarity on a 0..100 scale."""
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    if not left_tokens or not right_tokens:
        return 0.0
    common = " ".join(sorted(left_tokens & right_tokens))
    left_full = " ".join(sorted(left_tokens))
    right_full = " ".join(sorted(right_tokens))
    return 100.0 * max(SequenceMatcher(None, common, left_full).ratio(),
                        SequenceMatcher(None, common, right_full).ratio(),
                        SequenceMatcher(None, left_full, right_full).ratio())


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
        raise NormalizationError(f"multiple reference numbers are ambiguous in title {title!r}: " + ", ".join(references))
    return Classification(brand, model_key(title, rules, brand=brand), references, detect_condition(title, rules))
