"""Unit tests for the Catawiki buyer-JSON adapter.

These tests never touch the network: `CatawikiApi` takes an injected fetcher.
Every malformed payload must raise ScrapeError instead of producing a guess,
because a wrong hammer price silently corrupts every later valuation.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:  # allow running without an editable install
    sys.path.insert(0, str(SRC))

from cuti.errors import ScrapeError
from cuti.scrapers import catawiki_api as api


def search_payload(**overrides: object) -> dict:
    payload = {
        "total": 2,
        "lots": [
            {
                "id": 105916285,
                "title": "Rolex - Submariner Date - 16610",
                "subtitle": "Men - 2000-2010",
                "url": "https://www.catawiki.com/en/l/105916285-rolex-submariner",
            },
            {
                "id": 106066908,
                "title": "Omega - Speedmaster Professional",
                "url": "https://www.catawiki.com/en/l/106066908-omega-speedmaster",
            },
        ],
    }
    payload.update(overrides)
    return payload


def live_payload(**lot_overrides: object) -> dict:
    lot = {
        "id": 105916285,
        "closed": True,
        "favorite_count": 42,
        "bidding_start_time": "2026-08-01T10:00:00Z",
        "bidding_end_time": "2026-08-08T20:15:00Z",
        "current_bid_amount": {"EUR": 1401.0},
    }
    lot.update(lot_overrides)
    return {"lots": [lot]}


def bidding_payload(**lot_overrides: object) -> dict:
    lot = {"id": 105916285, "is_closed": True, "is_sold": True, "highest_bid_amount": 1401.0}
    lot.update(lot_overrides)
    return {"bidding_block": {"bids_count": 17, "lot": lot}}


class LotIdTests(unittest.TestCase):
    def test_extracts_id_from_lot_url(self) -> None:
        self.assertEqual(
            api.lot_id_from_url("https://www.catawiki.com/en/l/105916285-rolex"), "105916285"
        )

    def test_rejects_a_non_lot_url(self) -> None:
        with self.assertRaises(ScrapeError):
            api.lot_id_from_url("https://www.catawiki.com/en/c/333-watches")


class ParseUtcDateTests(unittest.TestCase):
    def test_accepts_zulu_and_offset_and_naive_forms(self) -> None:
        for value in ("2026-08-08T20:15:00Z", "2026-08-08T20:15:00+00:00", "2026-08-08T20:15:00"):
            self.assertEqual(api.parse_utc_date(value, "ctx"), date(2026, 8, 8))

    def test_converts_to_utc_before_taking_the_date(self) -> None:
        # 00:30 in +07:00 is still the previous day in UTC.
        self.assertEqual(api.parse_utc_date("2026-08-09T00:30:00+07:00", "ctx"), date(2026, 8, 8))

    def test_rejects_garbage(self) -> None:
        for value in ("", "yesterday"):
            with self.assertRaises(ScrapeError):
                api.parse_utc_date(value, "ctx")


class ParseSearchPageTests(unittest.TestCase):
    def test_parses_open_lot_references(self) -> None:
        page = api.parse_search_page(search_payload(), query="watch")
        self.assertEqual(page.total, 2)
        self.assertEqual([ref.lot_id for ref in page.lots], ["105916285", "106066908"])
        self.assertEqual(page.lots[0].subtitle, "Men - 2000-2010")
        self.assertIsNone(page.lots[1].subtitle, "a missing subtitle is None, not a guess")

    def test_rejects_duplicate_ids_on_one_page(self) -> None:
        payload = search_payload()
        payload["lots"][1]["id"] = payload["lots"][0]["id"]
        payload["lots"][1]["url"] = payload["lots"][0]["url"]
        with self.assertRaises(ScrapeError):
            api.parse_search_page(payload, query="watch")

    def test_rejects_url_that_does_not_match_the_id(self) -> None:
        payload = search_payload()
        payload["lots"][0]["url"] = "https://www.catawiki.com/en/l/999-other"
        with self.assertRaises(ScrapeError):
            api.parse_search_page(payload, query="watch")

    def test_rejects_missing_total_and_non_list_lots(self) -> None:
        broken = search_payload()
        del broken["total"]
        with self.assertRaises(ScrapeError):
            api.parse_search_page(broken, query="watch")
        with self.assertRaises(ScrapeError):
            api.parse_search_page(search_payload(lots={}), query="watch")

    def test_accepts_an_empty_page(self) -> None:
        page = api.parse_search_page({"total": 0, "lots": []}, query="watch")
        self.assertEqual(page.lots, ())


class ParseLiveLotsTests(unittest.TestCase):
    def test_parses_bidding_window_and_flags(self) -> None:
        state = api.parse_live_lots(live_payload())[0]
        self.assertEqual(state.lot_id, "105916285")
        self.assertTrue(state.closed)
        self.assertEqual(state.favorite_count, 42)
        self.assertEqual(state.opened_at, date(2026, 8, 1))
        self.assertEqual(state.ended_at, date(2026, 8, 8))
        self.assertEqual(state.current_bid_eur, 1401.0)

    def test_lot_without_a_bid_has_no_amount(self) -> None:
        payload = live_payload()
        del payload["lots"][0]["current_bid_amount"]
        self.assertIsNone(api.parse_live_lots(payload)[0].current_bid_eur)

    def test_ignores_currencies_other_than_eur(self) -> None:
        state = api.parse_live_lots(live_payload(current_bid_amount={"USD": 12.0}))[0]
        self.assertIsNone(state.current_bid_eur)

    def test_rejects_end_before_start(self) -> None:
        with self.assertRaises(ScrapeError):
            api.parse_live_lots(live_payload(bidding_end_time="2026-07-01T10:00:00Z"))

    def test_rejects_negative_favorite_count_and_non_bool_closed(self) -> None:
        with self.assertRaises(ScrapeError):
            api.parse_live_lots(live_payload(favorite_count=-1))
        with self.assertRaises(ScrapeError):
            api.parse_live_lots(live_payload(closed="yes"))

    def test_rejects_non_positive_bid_amount(self) -> None:
        with self.assertRaises(ScrapeError):
            api.parse_live_lots(live_payload(current_bid_amount={"EUR": 0}))


class ParseBiddingBlockTests(unittest.TestCase):
    def test_sold_lot_yields_an_integer_hammer_price(self) -> None:
        outcome = api.parse_bidding_block(bidding_payload(), lot_id="105916285")
        self.assertTrue(outcome.is_closed)
        self.assertTrue(outcome.is_sold)
        self.assertEqual(outcome.hammer_eur, 1401)
        self.assertEqual(outcome.bids_count, 17)

    def test_unsold_lot_has_no_hammer_price(self) -> None:
        payload = bidding_payload(is_sold=False, highest_bid_amount=None)
        outcome = api.parse_bidding_block(payload, lot_id="105916285")
        self.assertFalse(outcome.is_sold)
        self.assertIsNone(outcome.hammer_eur)

    def test_rejects_a_response_for_another_lot(self) -> None:
        with self.assertRaises(ScrapeError):
            api.parse_bidding_block(bidding_payload(), lot_id="106066908")

    def test_rejects_sold_lot_without_a_usable_amount(self) -> None:
        for amount in (None, "1401", 0):
            with self.assertRaises(ScrapeError):
                api.parse_bidding_block(
                    bidding_payload(highest_bid_amount=amount), lot_id="105916285"
                )

    def test_rejects_negative_bids_count(self) -> None:
        payload = bidding_payload()
        payload["bidding_block"]["bids_count"] = -1
        with self.assertRaises(ScrapeError):
            api.parse_bidding_block(payload, lot_id="105916285")


class ChunkTests(unittest.TestCase):
    def test_splits_into_batches(self) -> None:
        self.assertEqual(
            list(api.chunks(["1", "2", "3", "4", "5"], 2)),
            [("1", "2"), ("3", "4"), ("5",)],
        )

    def test_empty_input_yields_nothing(self) -> None:
        self.assertEqual(list(api.chunks([], 10)), [])

    def test_rejects_a_useless_batch_size(self) -> None:
        with self.assertRaises(ScrapeError):
            list(api.chunks(["1"], 0))


class RecordingFetcher:
    """Captures requested URLs and replays queued payloads."""

    def __init__(self, payloads: list[object]) -> None:
        self.payloads = payloads
        self.urls: list[str] = []

    def __call__(self, url: str, timeout: float, max_bytes: int) -> object:
        self.urls.append(url)
        return self.payloads.pop(0)


class CatawikiApiTests(unittest.TestCase):
    def build(self, payloads: list[object], *, pause: float = 0.5):
        fetcher = RecordingFetcher(payloads)
        self.sleeps: list[float] = []
        client = api.CatawikiApi(
            api_base="https://www.catawiki.com/",
            timeout_seconds=5.0,
            max_bytes=1000,
            pause_seconds=pause,
            fetch=fetcher,
            sleep=self.sleeps.append,
        )
        return client, fetcher

    def test_search_url_encodes_the_query(self) -> None:
        client, fetcher = self.build([search_payload()])
        client.search("rolex submariner", 2)
        self.assertEqual(
            fetcher.urls,
            ["https://www.catawiki.com/buyer/api/v1/search?q=rolex%20submariner&page=2"],
        )

    def test_search_rejects_page_zero(self) -> None:
        client, _ = self.build([])
        with self.assertRaises(ScrapeError):
            client.search("watch", 0)

    def test_live_states_batches_ids_into_one_request(self) -> None:
        client, fetcher = self.build([live_payload()])
        states = client.live_states(["105916285", "106066908"])
        self.assertEqual(
            fetcher.urls,
            ["https://www.catawiki.com/buyer/api/v1/lots/live?ids=105916285,106066908"],
        )
        self.assertEqual(list(states), ["105916285"], "absent ids are simply missing")

    def test_empty_id_list_makes_no_request(self) -> None:
        client, fetcher = self.build([])
        self.assertEqual(client.live_states([]), {})
        self.assertEqual(client.titles([]), {})
        self.assertEqual(fetcher.urls, [])
        self.assertEqual(client.requests_made, 0)

    def test_outcome_requests_eur_and_counts_requests(self) -> None:
        client, fetcher = self.build([bidding_payload()])
        client.outcome("105916285")
        self.assertEqual(
            fetcher.urls,
            [
                "https://www.catawiki.com/buyer/api/v3/lots/105916285"
                "/bidding_block?currency_code=EUR"
            ],
        )
        self.assertEqual(client.requests_made, 1)

    def test_pauses_between_requests_but_not_before_the_first(self) -> None:
        client, _ = self.build([search_payload(), search_payload(), search_payload()])
        for page in (1, 2, 3):
            client.search("watch", page)
        self.assertEqual(self.sleeps, [0.5, 0.5], "one pause between each pair of requests")
        self.assertEqual(client.requests_made, 3)


if __name__ == "__main__":
    unittest.main()
