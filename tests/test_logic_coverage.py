"""Executable coverage for the round-17 logic fixture contracts."""

from __future__ import annotations

import csv
import json
import unittest
from datetime import date
from pathlib import Path

from cuti.evaluation import evaluate_deal
from cuti.evaluation_chart import evaluate_deal_with_chart
from cuti.liquidity import liquidity_series
from cuti.models import Condition, Lot, Verdict, WatchForm
from cuti.scrapers.deals import RawDeal, parse_feed
from cuti.storage import upsert_lots
from cuti.storage.lots import SYNTHETIC_SOURCE

from support import NOW, ProjectTestCase


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "logic_coverage"
MANIFEST_PATH = FIXTURE_DIR / "logic_coverage_manifest.json"
QUERY = "Omega Seamaster Diver 300M 210.30.42 watch only"


class LogicCoverageTests(ProjectTestCase):
    def _rows(self) -> list[dict[str, str]]:
        with (FIXTURE_DIR / "logic_coverage.csv").open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    def _lots(self, source: str | None = None, prefix: str = "") -> list[Lot]:
        result: list[Lot] = []
        for row in self._rows():
            title = " ".join(
                part for part in (row["brand"], row["model"], row["ref_number"], "watch only") if part
            )
            result.append(
                Lot(
                    lot_id=prefix + row["lot_id"],
                    source=source or row["source"],
                    title=title,
                    brand=row["brand"].lower(),
                    model_key=(
                        f"omega:210.30.42"
                        if row["brand"].lower() == "omega"
                        else f"{row['brand'].lower()}:{row['model'].lower()}"
                    ),
                    condition_tag=Condition.parse(row["condition_tag"]),
                    form=WatchForm.parse(row["form"]),
                    hearts=int(row["hearts"]),
                    sold=row["status"] == "sold",
                    hammer_eur=int(row["hammer_eur"]) if row["hammer_eur"] else None,
                    opened_at=date.fromisoformat(row["opened_at"]),
                    ended_at=date.fromisoformat(row["ended_at"]),
                    url=row["url"],
                    bids_count=int(row["bids_count"]),
                    description=row["description"],
                )
            )
        return result

    def test_csv_covers_lot_shape_and_dimensions(self) -> None:
        rows = self._rows()
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 20)
        self.assertEqual(len({row["lot_id"] for row in rows}), 20)
        self.assertTrue(all(row["source"] == SYNTHETIC_SOURCE for row in rows))
        self.assertEqual(manifest["provenance"], f"{SYNTHETIC_SOURCE}_only")
        self.assertEqual(sum(row["status"] == "sold" for row in rows), 17)
        self.assertEqual(sum(row["status"] == "unsold" for row in rows), 3)
        self.assertEqual({row["condition_tag"] for row in rows}, {item.value for item in Condition})
        self.assertEqual({row["form"] for row in rows}, {item.value for item in WatchForm})
        for row in rows:
            for field in ("hearts", "bids_count", "opened_at", "ended_at"):
                self.assertTrue(row[field], (row["lot_id"], field))
            self.assertGreaterEqual(row["ended_at"], row["opened_at"])

    def test_deals_fixture_parses_five_raw_deals(self) -> None:
        payload = json.loads((FIXTURE_DIR / "logic_coverage_deals.json").read_text(encoding="utf-8"))
        deals = parse_feed(payload)
        self.assertEqual(len(deals), 5)
        self.assertTrue(all(isinstance(deal, RawDeal) for deal in deals))
        self.assertTrue(all(deal.source == SYNTHETIC_SOURCE for deal in deals))

    def test_csv_db_evaluates_all_verdicts_and_three_liquidity_windows(self) -> None:
        synthetic = self._lots()
        real = self._lots(source="catawiki", prefix="real-")
        upsert_lots(self.conn, [*synthetic, *real], NOW)
        cases = (
            (QUERY, 1000, Verdict.GREEN),
            (QUERY, 1400, Verdict.YELLOW),
            (QUERY, 1500, Verdict.RED),
            ("Unknown Zenith El Primero 9999", 1000, Verdict.INSUFFICIENT_DATA),
        )
        verdicts = tuple(
            evaluate_deal(
                self.conn,
                self.rules,
                self.settings,
                query=query,
                cost=cost,
                currency="eur",
                condition=Condition.NAKED,
                today=date(2026, 8, 1),
            ).verdict
            for query, cost, _expected in cases
        )
        self.assertEqual(verdicts, tuple(expected for _query, _cost, expected in cases))
        omega_round = [lot for lot in real if lot.brand == "omega" and lot.form is WatchForm.ROUND]
        series = liquidity_series(omega_round, self.settings, date(2026, 8, 1))
        self.assertIsNotNone(series)
        self.assertGreaterEqual(len(series or ()), 3)
        self.assertTrue(all(window.sample_size >= 5 for window in series or ()))

    def test_mixed_pool_excludes_synthetic_source_from_evaluation(self) -> None:
        real = self._lots(source="catawiki", prefix="real-")
        upsert_lots(self.conn, real, NOW)
        baseline = evaluate_deal(
            self.conn,
            self.rules,
            self.settings,
            query=QUERY,
            cost=1000,
            currency="eur",
            condition=Condition.NAKED,
            today=date(2026, 8, 1),
        )
        baseline_chart = evaluate_deal_with_chart(
            self.conn,
            self.rules,
            self.settings,
            query=QUERY,
            cost=1000,
            currency="eur",
            condition=Condition.NAKED,
            today=date(2026, 8, 1),
        )
        upsert_lots(self.conn, self._lots(source=SYNTHETIC_SOURCE), NOW)
        mixed = evaluate_deal(
            self.conn,
            self.rules,
            self.settings,
            query=QUERY,
            cost=1000,
            currency="eur",
            condition=Condition.NAKED,
            today=date(2026, 8, 1),
        )
        mixed_chart = evaluate_deal_with_chart(
            self.conn,
            self.rules,
            self.settings,
            query=QUERY,
            cost=1000,
            currency="eur",
            condition=Condition.NAKED,
            today=date(2026, 8, 1),
        )
        self.assertEqual(baseline.attempt_count, 15)
        self.assertEqual(baseline.sample_size, 12)
        self.assertNotEqual(baseline.verdict, Verdict.INSUFFICIENT_DATA)
        self.assertEqual(mixed, baseline)
        self.assertEqual(mixed_chart, baseline_chart)


if __name__ == "__main__":
    unittest.main()
