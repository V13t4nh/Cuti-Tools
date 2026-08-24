"""Synthetic-source exclusion at every comparable-pool storage boundary."""

from __future__ import annotations

import unittest
from datetime import date

from cuti.models import Condition
from cuti.storage import fetch_lots_for_liquidity, fetch_lots_for_model, fetch_sold_lots_since
from cuti.storage.lots import SYNTHETIC_SOURCE

from support import ProjectTestCase, make_lot


class SyntheticSourceStorageTests(ProjectTestCase):
    def test_all_pool_fetches_exclude_synthetic_lots(self) -> None:
        self.seed_lots(
            [
                make_lot("real-sold"),
                make_lot("real-unsold", sold=False, hammer_eur=None),
                make_lot("synthetic-sold", source=SYNTHETIC_SOURCE),
                make_lot(
                    "synthetic-unsold",
                    source=SYNTHETIC_SOURCE,
                    sold=False,
                    hammer_eur=None,
                ),
            ]
        )

        self.assertEqual(
            {lot.lot_id for lot in fetch_lots_for_model(
                self.conn,
                "omega:210.30.42",
                Condition.NAKED,
                date(2020, 1, 1),
                date(2026, 8, 1),
            )},
            {"real-sold", "real-unsold"},
        )
        self.assertEqual(
            {lot.lot_id for lot in fetch_lots_for_liquidity(self.conn, date(2020, 1, 1))},
            {"real-sold", "real-unsold"},
        )
        self.assertEqual(
            {lot.lot_id for lot in fetch_sold_lots_since(
                self.conn, Condition.NAKED, date(2020, 1, 1)
            )},
            {"real-sold"},
        )


if __name__ == "__main__":
    unittest.main()
