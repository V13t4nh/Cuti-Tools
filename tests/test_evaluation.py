"""Offline tests for the Buyer decision contract."""

from __future__ import annotations

import io
import json
import math
from dataclasses import replace
from datetime import date
from contextlib import redirect_stdout

from cuti.cli import main
from cuti.evaluation import cost_to_eur, evaluate_deal
from cuti.errors import PricingError
from cuti.models import Condition, Verdict

from support import TODAY, ProjectTestCase, make_lot


QUERY = "Omega Seamaster Diver 300M 210.30.42"


class EvaluationTests(ProjectTestCase):
    def _seed(self, *, condition=Condition.NAKED, count=6, hammer=4000):
        self.seed_lots(
            [
                make_lot(
                    f"eval-{condition.value}-{index}",
                    title=QUERY,
                    condition=condition,
                    hammer_eur=hammer,
                )
                for index in range(count)
            ]
        )

    def _evaluate(self, cost_eur=1000, condition=Condition.NAKED):
        return evaluate_deal(
            self.conn,
            self.rules,
            self.settings,
            query=QUERY,
            cost_eur=cost_eur,
            condition=condition,
            today=TODAY,
        )

    def test_percentiles_and_threshold_verdict(self):
        self._seed()
        result = self._evaluate(cost_eur=100)
        self.assertLessEqual(result.net_p25_eur, result.net_median_eur)
        self.assertLessEqual(result.net_median_eur, result.net_p75_eur)
        self.assertEqual(result.verdict, Verdict.GREEN)
        self.assertEqual(result.sample_size, 6)

    def test_expensive_input_is_red_at_threshold(self):
        self._seed()
        self.assertEqual(self._evaluate(cost_eur=100_000).verdict, Verdict.RED)

    def test_thin_pool_has_no_guessed_profit(self):
        self._seed(count=2)
        result = self._evaluate()
        self.assertEqual(result.verdict, Verdict.INSUFFICIENT_DATA)
        self.assertIsNone(result.net_p25_eur)
        self.assertIsNone(result.net_median_eur)
        self.assertIsNone(result.net_p75_eur)
        self.assertIsNone(result.sell_through_rate)
        self.assertIsNone(result.heart_to_hammer_rate)

    def test_vnd_and_eur_adapters_converge(self):
        self._seed()
        vnd_cost = cost_to_eur(27_000_000, "vnd", self.settings)
        eur_cost = cost_to_eur(1000, "eur", self.settings)
        vnd = self._evaluate(cost_eur=vnd_cost)
        eur = self._evaluate(cost_eur=eur_cost)
        self.assertEqual(vnd, eur)

    def test_hot_heart_conversion_rate_uses_sold_hot_pool(self):
        self.seed_lots(
            [
                make_lot(f"hot-sold-{index}", title=QUERY, hearts=80)
                for index in range(3)
            ]
            + [
                make_lot(
                    f"hot-unsold-{index}",
                    title=QUERY,
                    hearts=80,
                    sold=False,
                    hammer_eur=None,
                )
                for index in range(3)
            ]
        )
        result = self._evaluate()
        self.assertEqual(result.heart_to_hammer_rate, 0.5)

    def test_no_hot_lots_have_no_conversion_rate_and_price_verdict(self):
        self._seed()
        result = self._evaluate(cost_eur=100)
        self.assertIsNone(result.heart_to_hammer_rate)
        self.assertEqual(result.verdict, Verdict.GREEN)

    def test_sell_through_rate_uses_full_comparable_pool(self):
        self._seed(condition=Condition.NAKED, count=6)
        self.seed_lots(
            [
                make_lot(
                    f"half-{index}",
                    title=QUERY,
                    condition=Condition.BOX,
                    sold=index < 3,
                    hammer_eur=4000 if index < 3 else None,
                )
                for index in range(6)
            ]
        )
        all_sold = self._evaluate(condition=Condition.NAKED)
        half_sold = self._evaluate(condition=Condition.BOX)
        self.assertEqual(all_sold.sell_through_rate, 1.0)
        self.assertEqual(half_sold.sell_through_rate, 0.5)

    def test_condition_cluster_is_not_mixed(self):
        self._seed(condition=Condition.NAKED, hammer=1000)
        self._seed(condition=Condition.FULLSET, hammer=5000)
        naked = self._evaluate(condition=Condition.NAKED)
        fullset = self._evaluate(condition=Condition.FULLSET)
        self.assertEqual(naked.sample_size, 6)
        self.assertEqual(fullset.sample_size, 6)
        self.assertLess(naked.net_median_eur, fullset.net_median_eur)

    def test_cost_eur_rejects_non_finite_and_bool(self):
        for invalid in (True, False, math.nan, math.inf, -math.inf):
            with self.subTest(invalid=invalid), self.assertRaises(PricingError):
                self._evaluate(cost_eur=invalid)

    def test_pending_review_is_excluded(self):
        lot = replace(make_lot("eval-pending", title=QUERY), needs_review=1, review_status="pending")
        self.seed_lots([lot])
        result = self._evaluate()
        self.assertEqual(result.sample_size, 0)
        self.assertEqual(result.verdict, Verdict.INSUFFICIENT_DATA)

    def test_cli_evaluate_is_json_and_currency_stable(self):
        self._seed()
        self.assertEqual(
            cost_to_eur(27_000_000, "vnd", self.settings),
            cost_to_eur(1000, "eur", self.settings),
        )
        self.home.joinpath(".env").write_text(
            f"CUTI_DB_PATH={self.settings.db_path}\n", encoding="utf-8"
        )
        self.conn.close()

        def run(*extra):
            output = io.StringIO()
            argv = ["--home", str(self.home), "--today", TODAY.isoformat(), "evaluate", *extra]
            with redirect_stdout(output):
                self.assertEqual(main(argv), 0)
            return json.loads(output.getvalue())

        vnd = run("--query", QUERY, "--cost", "27000000", "--currency", "vnd", "--condition", "naked")
        eur = run("--query", QUERY, "--cost", "1000", "--currency", "eur", "--condition", "naked")
        self.assertEqual(vnd, eur)
        self.assertEqual(
            set(vnd),
            {
                "query", "model_key", "condition", "cost_eur", "verdict", "reason",
                "sample_size", "attempt_count", "sell_through_rate", "heart_to_hammer_rate",
                "net_p25_eur", "net_median_eur", "net_p75_eur", "threshold_eur",
                "median_days_to_close",
            },
        )
        self.assertNotIn("liquidity_index", vnd)
        self.assertNotIn("liquidity_sell_through", vnd)
        self.assertNotIn("net_profit_p25_eur", vnd)
