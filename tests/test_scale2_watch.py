"""Offline Scale 2 cap and alert-outbox acceptance tests."""

from __future__ import annotations

import unittest

from cuti.pipeline import watch_deals
from cuti.price_limit import max_buy_cost_vnd
from cuti.pricing import quote
from cuti.storage import count_rows, outbox_counts

from support import NOW, TODAY, ProjectTestCase, make_lot


class _GoodNotifier:
    def send(self, payload: dict[str, object]) -> None:
        return None


class _FailingNotifier:
    def send(self, payload: dict[str, object]) -> None:
        raise OSError("offline notifier failure")


class PriceLimitTests(ProjectTestCase):
    def test_cap_is_quote_compatible_and_thin_pool_is_none(self) -> None:
        price = quote([5000] * 6, [10] * 6, 1_000_000, self.settings)
        cap = max_buy_cost_vnd(price, self.settings)

        self.assertIsNotNone(cap)
        assert cap is not None
        self.assertEqual(quote([5000] * 6, [10] * 6, cap, self.settings).verdict.value, "green")
        self.assertNotEqual(quote([5000] * 6, [10] * 6, cap + 1, self.settings).verdict.value, "green")

        thin = quote([5000] * 4, [10] * 4, 1_000_000, self.settings)
        self.assertIsNone(max_buy_cost_vnd(thin, self.settings))


class WatchOutboxTests(ProjectTestCase):
    title = "Omega Seamaster Diver 300M 210.30.42 - watch only"

    def setUp(self) -> None:
        super().setUp()
        self.seed_lots(
            [
                make_lot(
                    f"omega-{index}", title=self.title, hammer_eur=5000, ended_at=TODAY
                )
                for index in range(6)
            ]
        )

    def _feed(self, ask_vnd: int, name: str) -> None:
        path = self.write_json(
            f"data/deals/{name}.json",
            [
                {
                    "source": "local",
                    "title": self.title,
                    "ask_vnd": ask_vnd,
                    "url": f"https://example.invalid/{name}",
                    "seen_at": TODAY.isoformat(),
                    "condition": "naked",
                    "form": "round",
                }
            ],
        )
        self.settings = self.make_settings(CUTI_DEALS_SOURCE_URL=str(path))

    def test_same_deal_twice_has_one_outbox_row_and_over_cap_has_none(self) -> None:
        self._feed(1_000_000, "under-cap")
        first = watch_deals(self.conn, self.rules, self.settings, _GoodNotifier(), today=TODAY, now=NOW)
        second = watch_deals(self.conn, self.rules, self.settings, _GoodNotifier(), today=TODAY, now=NOW)
        self.assertEqual(first.alerts_sent, 1)
        self.assertEqual(second.alerts_sent, 0)
        self.assertEqual(count_rows(self.conn, "alert_outbox"), 1)
        self.assertEqual(outbox_counts(self.conn)["sent"], 1)

        pool = quote([5000] * 6, [10] * 6, 1_000_000, self.settings)
        cap = max_buy_cost_vnd(pool, self.settings)
        assert cap is not None
        self._feed(cap + 1, "over-cap")
        watch_deals(self.conn, self.rules, self.settings, _GoodNotifier(), today=TODAY, now=NOW)
        self.assertEqual(count_rows(self.conn, "alert_outbox"), 1)

    def test_failing_notifier_increments_attempts_then_dead(self) -> None:
        self._feed(1_000_000, "failing")
        self.settings = self.make_settings(
            CUTI_DEALS_SOURCE_URL=self.settings.deals_source_url,
            CUTI_ALERT_MAX_ATTEMPTS="2",
        )
        notifier = _FailingNotifier()

        first = watch_deals(self.conn, self.rules, self.settings, notifier, today=TODAY, now=NOW)
        row = self.conn.execute("SELECT status, attempts FROM alert_outbox").fetchone()
        self.assertEqual((first.alerts_failed, row[0], row[1]), (1, "pending", 1))
        self.assertEqual(outbox_counts(self.conn)["sent"], 0)

        second = watch_deals(self.conn, self.rules, self.settings, notifier, today=TODAY, now=NOW)
        row = self.conn.execute("SELECT status, attempts FROM alert_outbox").fetchone()
        self.assertEqual((second.alerts_failed, row[0], row[1]), (1, "dead", 2))
        self.assertEqual(outbox_counts(self.conn)["sent"], 0)

        third = watch_deals(self.conn, self.rules, self.settings, notifier, today=TODAY, now=NOW)
        row = self.conn.execute("SELECT status, attempts FROM alert_outbox").fetchone()
        self.assertEqual((third.alerts_failed, row[0], row[1]), (0, "dead", 2))


if __name__ == "__main__":
    unittest.main()
