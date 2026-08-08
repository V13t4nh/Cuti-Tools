"""Source adapters: strict parsing of listings and the deal feed."""

from __future__ import annotations

import unittest
from datetime import date

from cuti.errors import ScrapeError
from cuti.scrapers import catawiki
from cuti.scrapers.deals import parse_feed

LOT = (
    '<div class="lot-card" data-lot-id="cw-1" data-title="Omega Seamaster 210.30.42" '
    'data-condition="naked" data-form="round" '
    'data-hearts="12" data-sold="true" data-hammer-eur="3000" data-opened-at="2026-06-01" '
    'data-ended-at="2026-06-11" data-url="lots/cw-1.html"></div>'
)


def page(body: str) -> str:
    return f"<html><body><main>{body}</main></body></html>"


class CatawikiTests(unittest.TestCase):
    def test_parses_a_sold_lot(self) -> None:
        result = catawiki.parse_listing(page(LOT))
        lot = result.lots[0]
        self.assertEqual(lot.lot_id, "cw-1")
        self.assertEqual(lot.title, "Omega Seamaster 210.30.42")
        self.assertEqual(lot.hammer_eur, 3000)
        self.assertTrue(lot.sold)
        self.assertEqual(lot.opened_at, date(2026, 6, 1))
        self.assertIsNone(result.next_href)

    def test_parses_unsold_lot_without_hammer(self) -> None:
        markup = LOT.replace('data-sold="true" data-hammer-eur="3000" ', 'data-sold="false" ')
        lot = catawiki.parse_listing(page(markup)).lots[0]
        self.assertFalse(lot.sold)
        self.assertIsNone(lot.hammer_eur)

    def test_html_entities_are_decoded(self) -> None:
        markup = LOT.replace("Omega Seamaster", "Omega &amp; Seamaster")
        lot = catawiki.parse_listing(page(markup)).lots[0]
        self.assertIn("&", lot.title)

    def test_next_link_is_returned(self) -> None:
        markup = LOT + '<a class="pagination-next" href="page-2.html">Next</a>'
        self.assertEqual(catawiki.parse_listing(page(markup)).next_href, "page-2.html")

    def test_multiple_next_links_are_rejected(self) -> None:
        markup = (
            LOT
            + '<a class="pagination-next" href="a.html"></a>'
            + '<a class="pagination-next" href="b.html"></a>'
        )
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page(markup))

    def test_next_link_without_href_is_rejected(self) -> None:
        markup = LOT + '<a class="pagination-next"></a>'
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page(markup))

    def test_empty_page_is_an_error_not_an_empty_list(self) -> None:
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page("<p>nothing here</p>"))

    def test_duplicate_lot_ids_are_rejected(self) -> None:
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page(LOT + LOT))

    def test_missing_required_attribute(self) -> None:
        markup = LOT.replace(' data-hearts="12"', "")
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page(markup))

    def test_sold_lot_without_hammer_is_rejected(self) -> None:
        markup = LOT.replace(' data-hammer-eur="3000"', "")
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page(markup))

    def test_unsold_lot_with_hammer_is_rejected(self) -> None:
        markup = LOT.replace('data-sold="true"', 'data-sold="false"')
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page(markup))

    def test_non_numeric_hammer_is_rejected(self) -> None:
        markup = LOT.replace('data-hammer-eur="3000"', 'data-hammer-eur="3k"')
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page(markup))

    def test_negative_hearts_is_rejected(self) -> None:
        markup = LOT.replace('data-hearts="12"', 'data-hearts="-1"')
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page(markup))

    def test_bad_boolean_is_rejected(self) -> None:
        markup = LOT.replace('data-sold="true"', 'data-sold="yes"')
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page(markup))

    def test_bad_date_is_rejected(self) -> None:
        markup = LOT.replace('data-ended-at="2026-06-11"', 'data-ended-at="11/06/2026"')
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page(markup))

    def test_end_before_open_is_rejected(self) -> None:
        markup = LOT.replace('data-ended-at="2026-06-11"', 'data-ended-at="2026-05-11"')
        with self.assertRaises(ScrapeError):
            catawiki.parse_listing(page(markup))


VALID_DEAL = {
    "source": "fb",
    "title": "Omega Seamaster 210.30.42 with box",
    "ask_vnd": 70_000_000,
    "url": "https://example.invalid/1",
    "seen_at": "2026-08-01",
    "condition": "box",
    "form": "round",
}


class DealFeedTests(unittest.TestCase):
    def test_parses_valid_feed(self) -> None:
        deals = parse_feed([VALID_DEAL])
        self.assertEqual(deals[0].ask_vnd, 70_000_000)
        self.assertEqual(deals[0].seen_at, date(2026, 8, 1))

    def test_empty_feed_is_valid(self) -> None:
        self.assertEqual(parse_feed([]), ())

    def test_dedupe_hash_is_stable_and_content_sensitive(self) -> None:
        same = parse_feed([VALID_DEAL, dict(VALID_DEAL)])
        self.assertEqual(same[0].dedupe_hash, same[1].dedupe_hash)
        other = parse_feed([{**VALID_DEAL, "ask_vnd": 69_000_000}])[0]
        self.assertNotEqual(same[0].dedupe_hash, other.dedupe_hash)

    def test_non_array_payload_is_rejected(self) -> None:
        with self.assertRaises(ScrapeError):
            parse_feed({"deals": []})

    def test_non_object_record_is_rejected(self) -> None:
        with self.assertRaises(ScrapeError):
            parse_feed(["not-an-object"])

    def test_missing_field_is_rejected(self) -> None:
        broken = {key: value for key, value in VALID_DEAL.items() if key != "url"}
        with self.assertRaises(ScrapeError):
            parse_feed([broken])

    def test_empty_title_is_rejected(self) -> None:
        with self.assertRaises(ScrapeError):
            parse_feed([{**VALID_DEAL, "title": "   "}])

    def test_price_must_be_a_positive_integer(self) -> None:
        for value in ("70000000", 0, -5, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ScrapeError):
                parse_feed([{**VALID_DEAL, "ask_vnd": value}])

    def test_bad_date_is_rejected(self) -> None:
        with self.assertRaises(ScrapeError):
            parse_feed([{**VALID_DEAL, "seen_at": "01-08-2026"}])


if __name__ == "__main__":
    unittest.main()
