"""Focused tests for Catawiki Details parsing and configured identity rules."""

from __future__ import annotations

import unittest
from pathlib import Path

from cuti.normalize import load_rules
from cuti.normalize_identity import split_identity
from cuti.scrapers.catawiki_lot_page import parse_lot_page


RULES = load_rules(Path(__file__).parents[1] / "config" / "rules.json")


class CatawikiLotPageTests(unittest.TestCase):
    def test_details_are_typed_without_guessing(self) -> None:
        html = """
        <table class="details">
          <tr><th>Brand</th><td>Omega</td></tr>
          <tr><th>Model</th><td>Seamaster</td></tr>
          <tr><th>Reference number</th><td>2849-6 SC</td></tr>
          <tr><th>Movement</th><td>Automatic</td></tr>
          <tr><th>Case material</th><td>Stainless steel</td></tr>
          <tr><th>Case diameter</th><td>45 mm</td></tr>
        </table>
        <section class="description"><p>Vintage watch, Cal. 503.</p></section>
        """
        result = parse_lot_page(html)
        self.assertEqual(result.brand, "Omega")
        self.assertEqual(result.ref_number, "2849-6 SC")
        self.assertEqual(result.movement, "auto")
        self.assertEqual(result.case_material, "steel")
        self.assertEqual(result.case_diameter_mm, 45)
        self.assertIn("Cal. 503", result.description or "")
        self.assertEqual(result.specs["Brand"], "Omega")

    def test_invalid_diameter_and_unknown_enums_are_none_or_other(self) -> None:
        result = parse_lot_page(
            "<table><tr><th>Case diameter</th><td>70 mm</td></tr>"
            "<tr><th>Movement</th><td>Mechanical</td></tr>"
            "<tr><th>Case material</th><td>Carbon</td></tr></table>"
        )
        self.assertIsNone(result.case_diameter_mm)
        self.assertIsNone(result.movement)
        self.assertEqual(result.case_material, "other")

    def test_brand_specific_reference_rules(self) -> None:
        seiko = split_identity("seiko", "7T12-0AT0", rules=RULES)
        self.assertEqual((seiko.caliber, seiko.case_code), ("7T12", "0AT0"))
        omega = split_identity("omega", "2846 8 SC / 2848", description="Cal. 500", rules=RULES)
        self.assertEqual((omega.caliber, omega.case_code), ("500", "2846 8 SC / 2848"))
        rolex = split_identity("rolex", "16234(Y)", title="Rolex Datejust", rules=RULES)
        self.assertEqual((rolex.caliber, rolex.case_code), (None, "16234(Y)"))

    def test_page_parser_can_apply_identity_rules_explicitly(self) -> None:
        result = parse_lot_page(
            "<table><tr><th>Brand</th><td>Seiko</td></tr>"
            "<tr><th>Reference number</th><td>7T12-0AT0</td></tr></table>",
            rules=RULES,
        )
        self.assertEqual((result.caliber, result.case_code), ("7T12", "0AT0"))


if __name__ == "__main__":
    unittest.main()
