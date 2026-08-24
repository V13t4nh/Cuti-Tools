"""Two-phase live capture: queue open lots, settle them after they close.

No network is used: a fake API object replays payload-shaped dataclasses, and
the URL prober is injected. The point of these tests is the state machine
(queue -> settle -> delete) and the refusal to guess anything the source did
not state.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from support import settings_for

from cuti import storage
from cuti.models import Condition, Lot, WatchForm
from cuti.normalize import load_rules
from cuti.pipeline import (
    check_source_urls,
    ingest_one_lot,
    settle_lots,
    watch_live,
)
from cuti.scrapers import catawiki_api as api

# The temp project dir has no config/, so point at the repository rules file:
# classification must be exercised against the real rules, not a fixture.
RULES_PATH = str(Path(__file__).resolve().parents[1] / "config" / "rules.json")
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 8, 17)
ROLEX = "Rolex - Submariner Date - 16610 - Men - full set"
OMEGA = "Omega - Speedmaster Professional 3570.50 - Men - with box"

def ref(lot_id: str, title: str, subtitle: str | None = None) -> api.LotRef:
    return api.LotRef(
        lot_id=lot_id,
        title=title,
        subtitle=subtitle,
        url=f"https://www.catawiki.com/en/l/{lot_id}-lot",
    )

def state(
    lot_id: str,
    *,
    closed: bool = True,
    hearts: int = 12,
    opened: date = date(2026, 8, 1),
    ended: date = date(2026, 8, 10),
) -> api.LiveState:
    return api.LiveState(
        lot_id=lot_id,
        closed=closed,
        favorite_count=hearts,
        opened_at=opened,
        ended_at=ended,
        current_bid_eur=None,
    )

def outcome(
    lot_id: str, *, sold: bool = True, hammer: int | None = 1401, bids: int = 17
) -> api.BiddingOutcome:
    return api.BiddingOutcome(
        lot_id=lot_id,
        is_closed=True,
        is_sold=sold,
        hammer_eur=hammer if sold else None,
        bids_count=bids,
    )

class FakeApi:
    """Stands in for CatawikiApi; records how many calls each phase made."""

    def __init__(
        self,
        *,
        pages: dict[tuple[str, int], api.SearchPage] | None = None,
        states: dict[str, api.LiveState] | None = None,
        outcomes: dict[str, api.BiddingOutcome] | None = None,
        titles: dict[str, api.LotTitle] | None = None,
    ) -> None:
        self._pages = pages or {}
        self._states = states or {}
        self._outcomes = outcomes or {}
        self._titles = titles or {}
        self.requests_made = 0
        self.state_batches: list[tuple[str, ...]] = []

    def search(self, query: str, page: int) -> api.SearchPage:
        self.requests_made += 1
        return self._pages.get((query, page), api.SearchPage(total=0, lots=()))

    def live_states(self, lot_ids) -> dict[str, api.LiveState]:
        ids = tuple(lot_ids)
        if not ids:
            return {}
        self.requests_made += 1
        self.state_batches.append(ids)
        return {i: self._states[i] for i in ids if i in self._states}

    def titles(self, lot_ids) -> dict[str, api.LotTitle]:
        ids = tuple(lot_ids)
        if not ids:
            return {}
        self.requests_made += 1
        return {i: self._titles[i] for i in ids if i in self._titles}

    def outcome(self, lot_id: str) -> api.BiddingOutcome:
        self.requests_made += 1
        return self._outcomes[lot_id]

class LiveWatchTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = settings_for(
            self.tmp,
            CUTI_RULES_PATH=RULES_PATH,
            CUTI_CATAWIKI_QUERIES="watch",
            CUTI_CATAWIKI_SEARCH_MAX_PAGES="2",
            CUTI_CATAWIKI_BATCH_SIZE="2",
            CUTI_CATAWIKI_PAUSE_SECONDS="0",
        )
        self.rules = load_rules(self.settings.rules_path)

    def queue(self, conn, lot_id: str, title: str, end: date | None) -> None:
        storage.upsert_live_watch(
            conn,
            [
                storage.LiveWatchRow(
                    lot_id=lot_id,
                    source=api.SOURCE_NAME,
                    title=title,
                    subtitle="Men - 2000s",
                    url=f"https://www.catawiki.com/en/l/{lot_id}-lot",
                    bidding_end_at=end,
                )
            ],
            NOW,
        )

class WatchLiveTests(LiveWatchTestCase):
    def test_queues_open_lots_with_their_close_date(self) -> None:
        fake = FakeApi(
            pages={
                ("watch", 1): api.SearchPage(
                    total=2, lots=(ref("1", ROLEX), ref("2", OMEGA, "Men"))
                )
            },
            states={
                "1": state("1", closed=False, ended=date(2026, 8, 20)),
                "2": state("2", closed=False, ended=date(2026, 8, 21)),
            },
        )
        with storage.connect(self.settings.db_path) as conn:
            report = watch_live(conn, self.settings, NOW, api=fake)
            self.assertEqual((report.lots_seen, report.lots_tracked), (2, 2))
            self.assertEqual(report.windows_unknown, 0)
            self.assertEqual(report.pages_fetched, 2, "stops after the first empty page")
            due_now = storage.fetch_live_watch_due(conn, until=TODAY, limit=10)
            self.assertEqual(due_now, [], "lots that are still open are not due")
            due_later = storage.fetch_live_watch_due(conn, until=date(2026, 8, 22), limit=10)
            self.assertEqual([row.lot_id for row in due_later], ["1", "2"])

    def test_second_run_refreshes_instead_of_duplicating(self) -> None:
        page = api.SearchPage(total=1, lots=(ref("1", ROLEX),))
        fake = FakeApi(
            pages={("watch", 1): page},
            states={"1": state("1", closed=False, ended=date(2026, 8, 20))},
        )
        with storage.connect(self.settings.db_path) as conn:
            watch_live(conn, self.settings, NOW, api=fake)
            again = watch_live(conn, self.settings, NOW, api=fake)
            self.assertEqual((again.lots_tracked, again.lots_refreshed), (0, 1))
            self.assertEqual(storage.count_live_watch(conn), 1)

    def test_lot_that_closed_during_paging_is_due_immediately(self) -> None:
        fake = FakeApi(
            pages={("watch", 1): api.SearchPage(total=1, lots=(ref("1", ROLEX),))},
            states={"1": state("1", closed=True)},
        )
        with storage.connect(self.settings.db_path) as conn:
            report = watch_live(conn, self.settings, NOW, api=fake)
            self.assertEqual(report.windows_unknown, 1)
            due = storage.fetch_live_watch_due(conn, until=TODAY, limit=10)
            self.assertEqual([row.lot_id for row in due], ["1"])

    def test_batches_live_state_lookups(self) -> None:
        lots = tuple(ref(str(index), ROLEX) for index in range(1, 6))
        fake = FakeApi(
            pages={("watch", 1): api.SearchPage(total=5, lots=lots)},
            states={str(index): state(str(index), closed=False) for index in range(1, 6)},
        )
        with storage.connect(self.settings.db_path) as conn:
            watch_live(conn, self.settings, NOW, api=fake)
        self.assertEqual(
            [len(batch) for batch in fake.state_batches],
            [2, 2, 1],
            "ids are grouped by CUTI_CATAWIKI_BATCH_SIZE",
        )

class SettleTests(LiveWatchTestCase):
    def test_sold_lot_is_stored_with_hammer_hearts_and_bids(self) -> None:
        fake = FakeApi(
            states={"1": state("1", hearts=42)},
            outcomes={"1": outcome("1", hammer=1401, bids=17)},
        )
        with storage.connect(self.settings.db_path) as conn:
            self.queue(conn, "1", ROLEX, date(2026, 8, 10))
            report = settle_lots(conn, self.rules, self.settings, TODAY, NOW, api=fake)
            self.assertEqual((report.sold, report.unsold, report.lots_written), (1, 0, 1))
            self.assertEqual(report.queue_remaining, 0, "a settled lot leaves the queue")
            stored = storage.fetch_lots_for_model(
                conn, "submariner date", Condition.FULLSET, date(2026, 1, 1), TODAY
            )
            if not stored:  # model_key depends on rules.json; fall back to a direct read
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM lots WHERE lot_id = '1'").fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["hammer_eur"], 1401)
                self.assertEqual(row["bids_count"], 17)
                self.assertEqual(row["hearts"], 42)
                self.assertEqual(row["form"], WatchForm.UNKNOWN.value)
                self.assertEqual(row["subtitle"], "Men - 2000s")
                self.assertEqual(row["source_available"], storage.YES)
            else:
                self.assertEqual(stored[0].hammer_eur, 1401)
                self.assertEqual(stored[0].bids_count, 17)

    def test_unsold_lot_is_stored_without_a_price(self) -> None:
        fake = FakeApi(
            states={"1": state("1")}, outcomes={"1": outcome("1", sold=False, bids=0)}
        )
        with storage.connect(self.settings.db_path) as conn:
            self.queue(conn, "1", ROLEX, date(2026, 8, 10))
            report = settle_lots(conn, self.rules, self.settings, TODAY, NOW, api=fake)
            self.assertEqual((report.sold, report.unsold), (0, 1))
            row = conn.execute(
                "SELECT sold, hammer_eur, bids_count FROM lots WHERE lot_id = '1'"
            ).fetchone()
            self.assertEqual(tuple(row), (0, None, 0))

    def test_lot_below_settle_min_hearts_is_discarded_from_queue_without_write(self) -> None:
        fake = FakeApi(
            states={"1": state("1", hearts=5)}, outcomes={"1": outcome("1", sold=True, hammer=1000)}
        )
        settings = settings_for(self.tmp, CUTI_RULES_PATH=RULES_PATH, CUTI_SETTLE_MIN_HEARTS="10")
        with storage.connect(settings.db_path) as conn:
            self.queue(conn, "1", ROLEX, date(2026, 8, 10))
            report = settle_lots(conn, self.rules, settings, TODAY, NOW, api=fake)
            self.assertEqual(report.lots_written, 0)
            self.assertEqual(report.queue_remaining, 0)
            self.assertEqual(storage.count_rows(conn, "lots"), 0)

    def test_extended_auction_is_requeued_with_the_new_end_date(self) -> None:
        fake = FakeApi(states={"1": state("1", closed=False, ended=date(2026, 8, 25))})
        with storage.connect(self.settings.db_path) as conn:
            self.queue(conn, "1", ROLEX, date(2026, 8, 10))
            report = settle_lots(conn, self.rules, self.settings, TODAY, NOW, api=fake)
            self.assertEqual((report.still_open, report.lots_written), (1, 0))
            self.assertEqual(report.queue_remaining, 1)
            remaining = storage.fetch_live_watch_due(conn, until=date(2026, 8, 30), limit=10)
            self.assertEqual(remaining[0].bidding_end_at, date(2026, 8, 25))

    def test_lot_forgotten_by_the_source_is_dropped(self) -> None:
        fake = FakeApi(states={})
        with storage.connect(self.settings.db_path) as conn:
            self.queue(conn, "1", ROLEX, date(2026, 8, 10))
            report = settle_lots(conn, self.rules, self.settings, TODAY, NOW, api=fake)
            self.assertEqual((report.vanished, report.queue_remaining), (1, 0))
            self.assertEqual(storage.count_rows(conn, "lots"), 0)

    def test_unclassifiable_title_is_counted_not_guessed(self) -> None:
        fake = FakeApi(
            states={"1": state("1"), "2": state("2")},
            outcomes={"1": outcome("1"), "2": outcome("2")},
        )
        with storage.connect(self.settings.db_path) as conn:
            self.queue(conn, "1", "Unknownbrand - Mystery watch - full set", date(2026, 8, 10))
            self.queue(conn, "2", "Rolex - Submariner Date - 16610 - Men", date(2026, 8, 10))
            report = settle_lots(conn, self.rules, self.settings, TODAY, NOW, api=fake)
            self.assertEqual(report.unclassified, 2, "no brand, and no stated condition")
            self.assertEqual(report.lots_written, 0)
            self.assertEqual(report.queue_remaining, 0, "they are not retried forever")

    def test_settle_respects_the_lot_cap(self) -> None:
        settings = settings_for(
            self.tmp,
            CUTI_RULES_PATH=RULES_PATH,
            CUTI_CATAWIKI_PAUSE_SECONDS="0",
            CUTI_SETTLE_MAX_LOTS="1",
        )
        fake = FakeApi(
            states={"1": state("1"), "2": state("2")},
            outcomes={"1": outcome("1"), "2": outcome("2")},
        )
        with storage.connect(settings.db_path) as conn:
            self.queue(conn, "1", ROLEX, date(2026, 8, 9))
            self.queue(conn, "2", ROLEX, date(2026, 8, 10))
            report = settle_lots(conn, self.rules, settings, TODAY, NOW, api=fake)
            self.assertEqual(report.candidates, 1, "oldest close first")
            self.assertEqual(report.queue_remaining, 1)

class IngestOneLotTests(LiveWatchTestCase):
    def test_single_url_is_tracked_and_settled(self) -> None:
        url = "https://www.catawiki.com/en/l/1-rolex-submariner"
        fake = FakeApi(
            states={"1": state("1")},
            outcomes={"1": outcome("1")},
            titles={"1": api.LotTitle(lot_id="1", title=ROLEX, url=url)},
        )
        with storage.connect(self.settings.db_path) as conn:
            report = ingest_one_lot(
                conn, self.rules, self.settings, TODAY, NOW, url=url, api=fake
            )
            self.assertEqual((report.candidates, report.sold, report.lots_written), (1, 1, 1))
            self.assertEqual(storage.count_rows(conn, "lots"), 1)

    def test_unreadable_lot_raises_instead_of_writing_a_blank_row(self) -> None:
        from cuti.errors import ScrapeError

        fake = FakeApi(titles={})
        with storage.connect(self.settings.db_path) as conn:
            with self.assertRaises(ScrapeError):
                ingest_one_lot(
                    conn,
                    self.rules,
                    self.settings,
                    TODAY,
                    NOW,
                    url="https://www.catawiki.com/en/l/1-gone",
                    api=fake,
                )
            self.assertEqual(storage.count_rows(conn, "lots"), 0)

class SourceUrlCheckTests(LiveWatchTestCase):
    def store_lot(self, conn, lot_id: str) -> None:
        storage.upsert_lots(
            conn,
            [
                Lot(
                    lot_id=lot_id,
                    source=api.SOURCE_NAME,
                    title=ROLEX,
                    brand="rolex",
                    model_key="submariner",
                    condition_tag=Condition.FULLSET,
                    hearts=5,
                    sold=True,
                    hammer_eur=1000,
                    opened_at=date(2026, 8, 1),
                    ended_at=date(2026, 8, 10),
                    url=f"https://www.catawiki.com/en/l/{lot_id}-lot",
                )
            ],
            NOW,
        )

    def test_live_page_stays_available(self) -> None:
        def probe(url: str, timeout: float) -> tuple[int, str]:
            return 200, url

        with storage.connect(self.settings.db_path) as conn:
            self.store_lot(conn, "1")
            report = check_source_urls(conn, self.settings, NOW, probe=probe)
            self.assertEqual((report.checked, report.alive, report.dead), (1, 1, 0))
            row = conn.execute(
                "SELECT source_available, source_checked_at FROM lots WHERE lot_id = '1'"
            ).fetchone()
            self.assertEqual(row[0], storage.YES)
            self.assertIsNotNone(row[1])

    def test_redirect_to_a_category_page_counts_as_expired(self) -> None:
        # A 200 is not enough: an expired lot is redirected to its category.
        def probe(url: str, timeout: float) -> tuple[int, str]:
            return 200, "https://www.catawiki.com/en/c/333-watches"

        with storage.connect(self.settings.db_path) as conn:
            self.store_lot(conn, "1")
            report = check_source_urls(conn, self.settings, NOW, probe=probe)
            self.assertEqual((report.alive, report.dead), (0, 1))
            self.assertEqual(
                conn.execute("SELECT source_available FROM lots WHERE lot_id='1'").fetchone()[0],
                storage.NO,
            )

    def test_dead_page_keeps_its_hammer_price(self) -> None:
        def probe(url: str, timeout: float) -> tuple[int, str]:
            return 404, url

        with storage.connect(self.settings.db_path) as conn:
            self.store_lot(conn, "1")
            check_source_urls(conn, self.settings, NOW, probe=probe)
            self.assertEqual(
                conn.execute("SELECT hammer_eur FROM lots WHERE lot_id='1'").fetchone()[0],
                1000,
                "the snapshot remains the source of truth",
            )

    def test_expired_lots_are_not_probed_again(self) -> None:
        calls: list[str] = []

        def probe(url: str, timeout: float) -> tuple[int, str]:
            calls.append(url)
            return 404, url

        with storage.connect(self.settings.db_path) as conn:
            self.store_lot(conn, "1")
            check_source_urls(conn, self.settings, NOW, probe=probe)
            check_source_urls(conn, self.settings, NOW, probe=probe)
            self.assertEqual(len(calls), 1, "a dead page is never re-probed")

class MigrationTests(unittest.TestCase):
    def test_v1_database_gains_the_new_columns_and_queue(self) -> None:
        tmp = Path(tempfile.mkdtemp()) / "legacy.db"
        legacy = sqlite3.connect(tmp)
        legacy.executescript(
            """
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta VALUES ('version', '1');
            CREATE TABLE lots (
                lot_id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL,
                brand TEXT NOT NULL, model_key TEXT NOT NULL, condition_tag TEXT NOT NULL,
                hearts INTEGER NOT NULL, sold INTEGER NOT NULL, hammer_eur INTEGER,
                opened_at TEXT NOT NULL, ended_at TEXT NOT NULL, url TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO lots VALUES ('9', 'catawiki', 'Rolex', 'rolex', 'sub', 'fullset',
                3, 1, 900, '2026-01-01', '2026-01-10', 'https://x/l/9', '2026-01-10T00:00:00+00:00');
            """
        )
        legacy.commit()
        legacy.close()

        with storage.connect(tmp) as conn:
            version = conn.execute(
                "SELECT value FROM schema_meta WHERE key='version'"
            ).fetchone()[0]
            self.assertEqual(int(version), storage.SCHEMA_VERSION)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(lots)")}
            self.assertTrue(
                {"subtitle", "bids_count", "source_available", "source_checked_at"} <= columns
            )
            self.assertEqual(storage.count_rows(conn, "live_watch"), 0)
            row = conn.execute(
                "SELECT hammer_eur, source_available FROM lots WHERE lot_id='9'"
            ).fetchone()
            self.assertEqual(tuple(row), (900, storage.YES), "old rows survive and default to alive")

    def test_reopening_a_current_database_is_a_no_op(self) -> None:
        tmp = Path(tempfile.mkdtemp()) / "twice.db"
        with storage.connect(tmp) as conn:
            storage.upsert_live_watch(
                conn,
                [
                    storage.LiveWatchRow(
                        lot_id="1",
                        source="catawiki",
                        title="Rolex",
                        subtitle=None,
                        url="https://x/l/1",
                        bidding_end_at=date(2026, 8, 10),
                    )
                ],
                NOW,
            )
        with storage.connect(tmp) as conn:
            self.assertEqual(storage.count_live_watch(conn), 1)

class CliWiringTests(unittest.TestCase):
    def test_new_commands_are_exposed(self) -> None:
        from cuti.cli import build_parser

        parser = build_parser()
        for command in ("watch-live", "settle", "check-urls"):
            self.assertEqual(parser.parse_args([command]).command, command)
        parsed = parser.parse_args(["ingest-lot", "--url", "https://x/l/1"])
        self.assertEqual((parsed.command, parsed.url), ("ingest-lot", "https://x/l/1"))

if __name__ == "__main__":
    unittest.main()
