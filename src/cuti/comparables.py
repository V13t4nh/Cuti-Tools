"""Comparable selection: which past lots may be used to price a watch.

Two stages: an FTS5 prefilter (cheap, recall oriented) followed by a fuzzy
similarity gate (precision oriented). Both the window and the threshold come
from configuration.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from .config import Settings
from .models import Condition, Lot
from .normalize import Rules, classify, model_tokens, similarity
from .storage import search_comparable_candidates


@dataclass(frozen=True, slots=True)
class ScoredLot:
    lot: Lot
    score: float


def build_fts_query(title: str, rules: Rules) -> str:
    """OR-query over the model tokens; quoted so FTS5 never sees an operator."""
    classification = classify(title, rules)
    tokens = [token for token in model_tokens(title, rules, brand=classification.brand) if token]
    terms = list(dict.fromkeys([*classification.brand.split(), *tokens]))
    return " OR ".join(f'"{term}"' for term in terms)


def window_start(reference_day: date, settings: Settings) -> date:
    return reference_day - timedelta(days=settings.comparable_window_days)


def find_comparables(
    conn: sqlite3.Connection,
    *,
    title: str,
    condition: Condition,
    rules: Rules,
    settings: Settings,
    today: date,
) -> list[ScoredLot]:
    """Return sold and unsold attempts similar enough to ``title``, best first."""
    classification = classify(title, rules)
    candidates = search_comparable_candidates(
        conn,
        fts_query=build_fts_query(title, rules),
        brand=classification.brand,
        # An explicit reference can use the exact index. Text-only model keys
        # still go through the FTS5 prefilter before the same exact/fuzzy gates.
        model_key=classification.model_key if classification.references else None,
        condition_tag=condition,
        since=window_start(today, settings),
    )
    scored = [
        ScoredLot(lot=lot, score=similarity(title, lot.title))
        for lot in candidates
        if lot.ended_at <= today
    ]
    matches = [
        item
        for item in scored
        if item.lot.brand == classification.brand
        and item.lot.model_key == classification.model_key
        and item.score >= settings.match_threshold
    ]
    matches.sort(key=lambda item: (-item.score, item.lot.lot_id))
    return matches
