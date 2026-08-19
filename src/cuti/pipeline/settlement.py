"""Internal two-phase settlement state machine shared by report commands."""

from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass, fields
from datetime import datetime

from ..config import Settings
from ..errors import NormalizationError
from ..models import Lot, WatchForm
from ..normalize import Rules, classify
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
    row_details = details if details is not None else getattr(row, "details", None)
    row_description = description or getattr(row, "description", None)
    if row_description is None and row_details is not None:
        row_description = getattr(row_details, "description", None)
    if row_description is None and isinstance(row_details, dict):
        row_description = row_details.get("description")
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
    lot_names = {item.name for item in fields(Lot)}
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
    values.update({name: value for name, value in extras.items() if name in lot_names})
    return Lot(
        **values,
    )


def settle(
    client: catawiki_api.CatawikiApi,
    rules: Rules,
    settings: Settings,
    candidates: list[LiveWatchRow],
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
                lot = _settled_lot(row, state, outcome, rules)
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
