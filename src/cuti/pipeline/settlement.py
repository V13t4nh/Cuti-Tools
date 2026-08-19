"""Internal two-phase settlement state machine shared by report commands."""

from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from ..config import Settings
from ..errors import FetchError, NormalizationError
from ..models import Lot, WatchForm
from ..normalize import Rules, classify
from ..scrapers.catawiki_lot_page import parse_lot_page
from .settlement_resolver import resolve_typed_fields
from ..scrapers import catawiki_api
from ..storage import LiveWatchRow, delete_live_watch, upsert_live_watch, upsert_lots


@dataclass(slots=True)
class _Settlement:
    lots: list[Lot]
    finished: list[str]
    refreshed: list[LiveWatchRow]
    sold: int = 0
    unsold: int = 0
    still_open: int = 0
    vanished: int = 0
    unclassified: int = 0


def _settled_lot(
    row: LiveWatchRow,
    state: catawiki_api.LiveState,
    outcome: catawiki_api.BiddingOutcome,
    rules: Rules,
    details: object = None,
    description: str | None = None,
    override_json: object = None,
    ai_json: object = None,
) -> Lot:
    classification = classify(row.title, rules)
    if classification.condition is None:
        raise NormalizationError(f"{row.lot_id}: title states no condition")
    row_details = details
    row_description = description
    resolved = resolve_typed_fields(
        row.title,
        rules,
        details=row_details,
        description=row_description,
        override_json=override_json,
        ai_json=ai_json,
    )
    values: dict[str, object] = {
        "lot_id": row.lot_id,
        "source": row.source,
        "title": row.title,
        "brand": resolved.brand or classification.brand,
        "model_key": resolved.model_key,
        "condition_tag": classification.condition,
        "form": WatchForm.UNKNOWN,
        "hearts": state.favorite_count,
        "sold": outcome.is_sold,
        "hammer_eur": outcome.hammer_eur,
        "opened_at": state.opened_at,
        "ended_at": state.ended_at,
        "url": row.url,
        "subtitle": row.subtitle,
        "bids_count": outcome.bids_count,
    }
    extras: dict[str, object] = {
        "model": resolved.model,
        "ref_number": resolved.ref_number,
        "caliber": resolved.caliber,
        "case_code": resolved.case_code,
        "movement": resolved.movement,
        "case_material": resolved.case_material,
        "case_diameter_mm": resolved.case_diameter_mm,
        "specs_json": json.dumps(resolved.specs or {}, sort_keys=True),
        "ai_json": None,
        "needs_review": resolved.needs_review,
        "review_status": "pending",
        "reviewed_at": None,
        "override_json": (
            json.dumps(override_json, sort_keys=True) if isinstance(override_json, (dict, list)) else override_json
        ),
        "description": row_description,
    }
    values.update(extras)
    return Lot(
        **values,
    )


def settle(
    client: catawiki_api.CatawikiApi,
    rules: Rules,
    settings: Settings,
    candidates: list[LiveWatchRow],
    *,
    fetch_details: Callable[[str], str | None] | None = None,
) -> _Settlement:
    """Read final state for every candidate without writing anything."""
    by_id = {row.lot_id: row for row in candidates}
    result = _Settlement(lots=[], finished=[], refreshed=[])
    for batch in catawiki_api.chunks(list(by_id), settings.catawiki_batch_size):
        states = client.live_states(batch)
        for lot_id in batch:
            row = by_id[lot_id]
            state = states.get(lot_id)
            if state is None:
                result.vanished += 1
                result.finished.append(lot_id)
                continue
            if not state.closed:
                result.still_open += 1
                result.refreshed.append(
                    LiveWatchRow(
                        lot_id=row.lot_id,
                        source=row.source,
                        title=row.title,
                        subtitle=row.subtitle,
                        url=row.url,
                        bidding_end_at=state.ended_at,
                    )
                )
                continue
            outcome = client.outcome(lot_id)
            if not outcome.is_closed:
                result.still_open += 1
                continue
            try:
                try:
                    html = fetch_details(lot_id) if fetch_details is not None else None
                except FetchError:
                    html = None
                page = parse_lot_page(html, rules=rules) if html is not None else None
                lot = _settled_lot(
                    row,
                    state,
                    outcome,
                    rules,
                    details=page,
                    description=page.description if page is not None else None,
                )
            except NormalizationError:
                result.unclassified += 1
                result.finished.append(lot_id)
                continue
            result.lots.append(lot)
            result.finished.append(lot_id)
            if outcome.is_sold:
                result.sold += 1
            else:
                result.unsold += 1
    return result


def persist(
    conn: sqlite3.Connection, settlement: _Settlement, now: datetime
) -> int:
    written = upsert_lots(conn, settlement.lots, now)
    if settlement.refreshed:
        upsert_live_watch(conn, settlement.refreshed, now)
    delete_live_watch(conn, settlement.finished)
    return written
