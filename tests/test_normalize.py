"""Normalization: brand detection, condition clustering, model keys, similarity."""

from __future__ import annotations

import json
import unittest

from cuti.errors import ConfigError, NormalizationError
from cuti.models import Condition
from cuti.normalize import (
    classify,
    detect_brand,
    detect_condition,
    load_rules,
    model_key,
    normalize_text,
    similarity,
    tokenize,
)

from support import ProjectTestCase


class TextTests(unittest.TestCase):
    def test_strips_accents_punctuation_and_case(self) -> None:
        self.assertEqual(normalize_text("Đồng-hồ  OMEGA/Seamaster!"), "dong-ho omega seamaster")

    def test_empty_input(self) -> None:
        self.assertEqual(normalize_text("   "), "")
        self.assertEqual(tokenize("---"), [])


class BrandTests(ProjectTestCase):
    def test_detects_simple_brand(self) -> None:
        self.assertEqual(detect_brand("Omega Speedmaster 311.30", self.rules), "omega")

    def test_prefers_longest_multi_word_brand(self) -> None:
        self.assertEqual(
            detect_brand("Grand Seiko SBGA211 snowflake", self.rules), "grand seiko"
        )

    def test_alias_maps_to_canonical(self) -> None:
        self.assertEqual(
            detect_brand("International Watch Co Portugieser", self.rules), "iwc"
        )

    def test_unknown_brand_raises_instead_of_guessing(self) -> None:
        with self.assertRaises(NormalizationError):
            detect_brand("Unknownbrand Diver 300", self.rules)

    def test_empty_title_raises(self) -> None:
        with self.assertRaises(NormalizationError):
            detect_brand("!!!", self.rules)


class ConditionTests(ProjectTestCase):
    def test_priority_fullset_beats_box_and_papers(self) -> None:
        self.assertIs(
            detect_condition("Rolex 124060 full set with box and papers", self.rules),
            Condition.FULLSET,
        )

    def test_papers_beats_box(self) -> None:
        self.assertIs(
            detect_condition("Omega 210.30 with papers", self.rules), Condition.PAPERS
        )

    def test_box_detected(self) -> None:
        self.assertIs(detect_condition("Seiko SPB143 with box", self.rules), Condition.BOX)

    def test_unknown_when_nothing_matches(self) -> None:
        self.assertIsNone(detect_condition("Seiko SPB143", self.rules))

    def test_keyword_must_be_a_whole_word(self) -> None:
        # "boxer" must not be read as "box"
        self.assertIsNone(detect_condition("Seiko SPB143 boxer edition", self.rules))


class ModelKeyTests(ProjectTestCase):
    def test_reference_number_wins_over_words(self) -> None:
        self.assertEqual(
            model_key("Omega Seamaster Diver 300M 210.30.42 - watch only", self.rules),
            "omega:210.30.42",
        )

    def test_same_model_different_condition_shares_key(self) -> None:
        left = model_key("Rolex Submariner 124060 full set", self.rules)
        right = model_key("Rolex Submariner 124060 watch only", self.rules)
        self.assertEqual(left, right)

    def test_falls_back_to_salient_words_when_no_reference(self) -> None:
        self.assertEqual(
            model_key("Tissot PRX quartz watch", self.rules),
            "tissot:prx quartz",
        )

    def test_title_without_model_tokens_raises(self) -> None:
        with self.assertRaises(NormalizationError):
            model_key("Omega watch automatic steel", self.rules)

    def test_classify_returns_all_three_facets(self) -> None:
        result = classify("Tudor Black Bay 58 79030 full set", self.rules)
        self.assertEqual(result.brand, "tudor")
        self.assertEqual(result.model_key, "tudor:79030")
        self.assertIs(result.condition, Condition.FULLSET)


class SimilarityTests(unittest.TestCase):
    def test_identical_titles(self) -> None:
        self.assertEqual(similarity("Omega 210.30", "omega  210.30!"), 1.0)

    def test_token_order_does_not_matter(self) -> None:
        self.assertEqual(similarity("Omega Seamaster", "Seamaster Omega"), 1.0)

    def test_unrelated_titles_score_low(self) -> None:
        self.assertLess(similarity("Omega Seamaster 210", "Seiko Presage SRPB41"), 0.6)

    def test_empty_input_scores_zero(self) -> None:
        self.assertEqual(similarity("", "Omega"), 0.0)

    def test_result_is_bounded(self) -> None:
        score = similarity("Rolex Datejust 126234", "Rolex Datejust 126233")
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class RulesLoadingTests(ProjectTestCase):
    def _write_rules(self, payload: object) -> None:
        (self.home / "config" / "rules.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_missing_file(self) -> None:
        with self.assertRaises(ConfigError):
            load_rules(self.home / "config" / "nope.json")

    def test_invalid_json(self) -> None:
        (self.home / "config" / "rules.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(ConfigError):
            load_rules(self.home / "config" / "rules.json")

    def test_missing_section(self) -> None:
        self._write_rules({"brands": {"omega": []}})
        with self.assertRaises(ConfigError):
            load_rules(self.home / "config" / "rules.json")

    def test_conflicting_alias_is_rejected(self) -> None:
        self._write_rules(
            {
                "brands": {"omega": ["shared"], "rolex": ["shared"]},
                "condition": {
                    "priority": ["naked"],
                    "keywords": {"naked": ["naked"]},
                    "default": "naked",
                },
                "stopwords": [],
                "model_token_limit": 2,
            }
        )
        with self.assertRaises(ConfigError):
            load_rules(self.home / "config" / "rules.json")

    def test_invalid_regex_is_rejected(self) -> None:
        self._write_rules(
            {
                "brands": {"omega": []},
                "condition": {
                    "priority": ["naked"],
                    "keywords": {"naked": ["naked"]},
                    "default": "naked",
                },
                "stopwords": [],
                "identity_tokens": ["automatic"],
                "model_token_limit": 2,
                "reference_pattern": "[unclosed",
            }
        )
        with self.assertRaises(ConfigError):
            load_rules(self.home / "config" / "rules.json")

    def test_identity_tokens_must_not_be_empty(self) -> None:
        self._write_rules(
            {
                "brands": {"omega": []},
                "condition": {
                    "priority": ["naked"],
                    "keywords": {"naked": ["naked"]},
                },
                "stopwords": [],
                "identity_tokens": [],
                "model_token_limit": 2,
            }
        )
        with self.assertRaises(ConfigError):
            load_rules(self.home / "config" / "rules.json")


if __name__ == "__main__":
    unittest.main()
