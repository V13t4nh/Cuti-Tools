"""Offline checks for HTML lot fixtures supplied from a real browser session."""

from __future__ import annotations

import unittest
from pathlib import Path

from cuti.normalize import load_rules
from cuti.scrapers.catawiki_lot_page import parse_lot_page


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "live"
RULES = load_rules(ROOT / "config" / "rules.json")
EXPECTED = {
    "106019970": {"caliber": "7T12", "case_code": "0AT0"},
    "105924279": {"caliber": "503"},
    "105418344": {"caliber": "500"},
    "105809071": {"caliber": None, "case_code": "16234(Y)"},
}


class LiveLotFixtureTests(unittest.TestCase):
    def test_real_html_fixtures_have_identity_fields(self) -> None:
        for path in sorted(FIXTURE_DIR.glob("*.html")):
            result = parse_lot_page(path.read_text(encoding="utf-8"), rules=RULES)
            self.assertTrue(result.brand, path.name)
            self.assertTrue(result.ref_number or result.case_code, path.name)
            self.assertTrue(result.movement, path.name)
            self.assertTrue(result.description, path.name)
            expected = EXPECTED.get(path.stem)
            if expected is None or expected["caliber"] is not None:
                self.assertTrue(result.caliber, path.name)
            if expected is None:
                continue
            self.assertEqual(result.caliber, expected["caliber"], path.name)
            if "case_code" in expected:
                self.assertEqual(result.case_code, expected["case_code"], path.name)


if __name__ == "__main__":
    unittest.main()
