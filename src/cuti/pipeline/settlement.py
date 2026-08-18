"""Internal two-phase settlement state machine shared by report commands."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from ..config import Settings
from ..errors import NormalizationError
from ..models import Lot, WatchForm
from ..normalize import Rules, classify
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
) -> Lot:
    classification = classify(row.title, rules)
    if classification.condition is None:
        raise NormalizationError(f"{row.lot_id}: title states no condition")
    return Lot(
        lot_id=row.lot_id,
        source=row.source,
        title=row.title,
        brand=classification.brand,
        model_key=classification.model_key,
        condition_tag=classification.condition,
        form=WatchForm.UNKNOWN,
        hearts=state.favorite_count,
        sold=outcome.is_sold,
        hammer_eur=outcome.hammer_eur,
        opened_at=state.opened_at,
        ended_at=state.ended_at,
        url=row.url,
        subtitle=row.subtitle,
        bids_count=outcome.bids_count,
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
