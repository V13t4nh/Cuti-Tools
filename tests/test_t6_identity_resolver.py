"""T6 identity and conflict rules for settled lots."""

from __future__ import annotations

import unittest
from pathlib import Path

from cuti.normalize import load_rules
from cuti.pipeline.settlement_resolver import _model_key, resolve_typed_fields


RULES = load_rules(Path(__file__).resolve().parents[1] / "config" / "rules.json")


class IdentityAndModelKeyTests(unittest.TestCase):
    def test_seiko_reference_splits_into_a_paired_caliber_and_case_code(self) -> None:
        resolved = resolve_typed_fields(
            "Seiko chronograph 7T12-0AT0 watch only",
            RULES,
            details={"Brand": "Seiko", "Reference number": "7T12-0AT0"},
        )

        self.assertEqual((resolved.caliber, resolved.case_code), ("7T12", "0AT0"))

    def test_omega_vintage_keeps_reference_whole_and_reads_description_caliber(self) -> None:
        resolved = resolve_typed_fields(
            "Omega Seamaster 2849-6 SC watch only",
            RULES,
            details={"Brand": "Omega", "Reference number": "2849-6 SC"},
            description="Vintage Omega Cal. 503 movement",
        )

        self.assertEqual(resolved.case_code, "2849-6 SC")
        self.assertEqual(resolved.ref_number, "2849-6 SC")
        self.assertEqual(resolved.caliber, "503")

    def test_omega_two_reference_codes_are_not_cut_at_whitespace(self) -> None:
        resolved = resolve_typed_fields(
            "Omega Seamaster 2846 8 SC / 2848 watch only",
            RULES,
            details={"Brand": "Omega", "Reference number": "2846 8 SC / 2848"},
            description="Calibre 500 movement",
        )

        self.assertEqual(resolved.ref_number, "2846 8 SC / 2848")
        self.assertEqual(resolved.case_code, "2846 8 SC / 2848")
        self.assertEqual(resolved.caliber, "500")

    def test_rolex_modern_reference_does_not_invent_caliber(self) -> None:
        resolved = resolve_typed_fields(
            "Rolex Datejust 16234(Y) watch only",
            RULES,
            details={"Brand": "Rolex", "Reference number": "16234(Y)"},
        )

        self.assertIsNone(resolved.caliber)
        self.assertEqual(resolved.case_code, "16234(Y)")

    def test_model_key_records_all_five_fallback_tiers(self) -> None:
        cases = (
            (
                "Omega vintage watch",
                {"Brand": "Omega", "Caliber": "503", "Case code": "2849"},
                "omega|503|2849",
                1,
            ),
            (
                "Omega vintage watch",
                {"Brand": "Omega", "Case code": "2849"},
                "omega|2849",
                2,
            ),
            (
                "Omega vintage 2849 watch",
                {"Brand": "Omega", "Reference number": "2849"},
                "omega|2849",
                3,
            ),
            (
                "Omega Seamaster watch",
                {"Brand": "Omega", "Model": "Seamaster", "Case diameter": "34 mm"},
                "omega|seamaster|34",
                4,
            ),
            ("Omega Seamaster watch", {"Brand": "Omega"}, "omega|omega-seamaster-watch", 5),
        )
        for title, details, expected_key, expected_tier in cases:
            with self.subTest(expected_tier=expected_tier):
                if expected_tier == 3:
                    # Vintage/modern identity rules intentionally populate
                    # case_code from a reference. Exercise the pure tier-3
                    # fallback with its typed inputs before that derivation.
                    actual = _model_key(
                        {"brand": "omega", "ref_number": "2849", "case_code": None},
                        title,
                    )
                else:
                    resolved = resolve_typed_fields(title, RULES, details=details)
                    actual = (resolved.model_key, resolved.model_key_tier)
                self.assertEqual(actual, (expected_key, expected_tier))


class ResolverConflictTests(unittest.TestCase):
    def test_reference_disagreement_derives_case_code_conflict(self) -> None:
        resolved = resolve_typed_fields(
            "Seiko chronograph 7T12-0AT1 watch only",
            RULES,
            details={"Brand": "Seiko", "Reference number": "7T12-0AT0"},
        )

        self.assertEqual(resolved.case_code, "0AT0")
        self.assertEqual(resolved.needs_review, 1)

    def test_same_tier_conflict_clears_typed_value_and_marks_review(self) -> None:
        resolved = resolve_typed_fields(
            "Omega Seamaster Cal. 503 watch only",
            RULES,
            description="Omega Seamaster Cal. 500 movement",
        )

        self.assertIsNone(resolved.caliber)
        self.assertEqual(resolved.needs_review, 1)

    def test_higher_tier_conflict_keeps_details_and_marks_review(self) -> None:
        resolved = resolve_typed_fields(
            "Omega Seamaster Cal. 500 watch only",
            RULES,
            details={"Brand": "Omega", "Caliber": "503", "Case code": "2849"},
        )

        self.assertEqual(resolved.caliber, "503")
        self.assertEqual(resolved.case_code, "2849")
        self.assertEqual(resolved.needs_review, 1)


if __name__ == "__main__":
    unittest.main()
