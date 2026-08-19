"""Focused regression tests for modern and vintage reference identities."""

from __future__ import annotations

import unittest
from pathlib import Path

from cuti.normalize import load_rules
from cuti.normalize_identity import split_identity


RULES = load_rules(Path(__file__).resolve().parents[1] / "config" / "rules.json")


class IdentityReferenceShapeTests(unittest.TestCase):
    def test_seiko_four_by_four_reference_splits(self) -> None:
        parts = split_identity("seiko", "7T12-0AT0", rules=RULES)
        self.assertEqual((parts.caliber, parts.case_code), ("7T12", "0AT0"))

    def test_citizen_four_by_four_reference_splits(self) -> None:
        parts = split_identity("citizen", "8210-0AT0", rules=RULES)
        self.assertEqual((parts.caliber, parts.case_code), ("8210", "0AT0"))

    def test_citizen_prefixed_reference_stays_whole(self) -> None:
        parts = split_identity("citizen", "NJ0153-82X", rules=RULES)
        self.assertEqual((parts.caliber, parts.case_code), (None, "NJ0153-82X"))

    def test_rolex_five_digit_parenthesized_reference_stays_whole(self) -> None:
        parts = split_identity("rolex", "16234(Y)", rules=RULES)
        self.assertEqual((parts.caliber, parts.case_code), (None, "16234(Y)"))

    def test_rolex_six_digit_reference_with_suffix_stays_whole(self) -> None:
        parts = split_identity("rolex", "116610LN", rules=RULES)
        self.assertEqual((parts.caliber, parts.case_code), (None, "116610LN"))

    def test_longines_dotted_reference_stays_whole(self) -> None:
        parts = split_identity("longines", "L2.785.4.76.6", rules=RULES)
        self.assertEqual((parts.caliber, parts.case_code), (None, "L2.785.4.76.6"))

    def test_omega_vintage_reference_reads_caliber_from_description(self) -> None:
        parts = split_identity(
            "omega",
            "2849-6 SC",
            description="Vintage Omega Cal. 503 movement",
            rules=RULES,
        )
        self.assertEqual((parts.caliber, parts.case_code), ("503", "2849-6 SC"))


if __name__ == "__main__":
    unittest.main()
