"""Configuration contract: defaults, overrides, validation, path resolution."""

from __future__ import annotations

import unittest
from pathlib import Path

from cuti.config import DEFAULTS, load_settings, parse_env_file
from cuti.errors import ConfigError

from support import ProjectTestCase


class EnvFileTests(unittest.TestCase):
    def test_parses_comments_quotes_and_export(self) -> None:
        parsed = parse_env_file(
            "\n".join(
                [
                    "# comment",
                    "",
                    "CUTI_DB_PATH=var/x.db",
                    'export CUTI_NOTIFIER="file"',
                    "CUTI_SHIPPING_EUR = 12 ",
                ]
            )
        )
        self.assertEqual(
            parsed,
            {
                "CUTI_DB_PATH": "var/x.db",
                "CUTI_NOTIFIER": "file",
                "CUTI_SHIPPING_EUR": "12",
            },
        )

    def test_rejects_line_without_equals(self) -> None:
        with self.assertRaises(ConfigError):
            parse_env_file("CUTI_DB_PATH")

    def test_rejects_empty_key(self) -> None:
        with self.assertRaises(ConfigError):
            parse_env_file("=value")


class SettingsTests(ProjectTestCase):
    def test_defaults_are_applied(self) -> None:
        settings = self.make_settings()
        self.assertEqual(settings.commission_rate, float(DEFAULTS["CUTI_COMMISSION_RATE"]))
        self.assertEqual(settings.notifier, "file")

    def test_env_overrides_defaults(self) -> None:
        settings = self.make_settings(CUTI_MIN_COMPARABLES="9")
        self.assertEqual(settings.min_comparables, 9)

    def test_env_file_is_read_and_overridden_by_real_env(self) -> None:
        (self.home / ".env").write_text(
            "CUTI_MIN_COMPARABLES=3\nCUTI_SHIPPING_EUR=99\n", encoding="utf-8"
        )
        settings = self.make_settings(CUTI_MIN_COMPARABLES="7")
        self.assertEqual(settings.min_comparables, 7)  # real env wins
        self.assertEqual(settings.shipping_eur, 99.0)  # .env still applies

    def test_relative_paths_resolve_against_home(self) -> None:
        settings = self.make_settings(CUTI_DB_PATH="var/custom.db")
        self.assertEqual(settings.db_path, self.home / "var" / "custom.db")

    def test_absolute_paths_are_preserved(self) -> None:
        settings = self.make_settings(CUTI_DB_PATH="/tmp/abs.db")
        self.assertEqual(settings.db_path, Path("/tmp/abs.db"))

    def test_urls_are_not_turned_into_paths(self) -> None:
        settings = self.make_settings(CUTI_LOTS_SOURCE_URL="https://example.invalid/a.html")
        self.assertEqual(settings.lots_source_url, "https://example.invalid/a.html")

    def test_fee_multiplier(self) -> None:
        settings = self.make_settings(
            CUTI_COMMISSION_RATE="0.125", CUTI_VAT_ON_COMMISSION_RATE="0.21"
        )
        self.assertAlmostEqual(settings.total_fee_multiplier, 0.125 * 1.21)

    def test_rejects_unknown_cuti_variable(self) -> None:
        with self.assertRaises(ConfigError):
            self.make_settings(CUTI_TYPO_HERE="1")

    def test_rejects_non_numeric_value(self) -> None:
        with self.assertRaises(ConfigError):
            self.make_settings(CUTI_SHIPPING_EUR="abc")

    def test_rejects_out_of_range_rate(self) -> None:
        for value in ("-0.1", "1.0", "2"):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                self.make_settings(CUTI_COMMISSION_RATE=value)

    def test_rejects_zero_exchange_rate(self) -> None:
        with self.assertRaises(ConfigError):
            self.make_settings(CUTI_EUR_VND_RATE="0")

    def test_rejects_min_comparables_below_one(self) -> None:
        with self.assertRaises(ConfigError):
            self.make_settings(CUTI_MIN_COMPARABLES="0")

    def test_rejects_match_threshold_out_of_range(self) -> None:
        for value in ("0", "1.5"):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                self.make_settings(CUTI_MATCH_THRESHOLD=value)

    def test_rejects_liquidity_weights_not_summing_to_one(self) -> None:
        with self.assertRaises(ConfigError):
            self.make_settings(CUTI_LIQUIDITY_W_SELL_THROUGH="0.9")

    def test_telegram_requires_credentials(self) -> None:
        with self.assertRaises(ConfigError):
            self.make_settings(CUTI_NOTIFIER="telegram")
        settings = self.make_settings(
            CUTI_NOTIFIER="telegram",
            CUTI_TELEGRAM_BOT_TOKEN="token",
            CUTI_TELEGRAM_CHAT_ID="42",
        )
        self.assertEqual(settings.notifier, "telegram")

    def test_rejects_unknown_notifier(self) -> None:
        with self.assertRaises(ConfigError):
            self.make_settings(CUTI_NOTIFIER="carrier-pigeon")

    def test_rejects_empty_source_url(self) -> None:
        with self.assertRaises(ConfigError):
            self.make_settings(CUTI_LOTS_SOURCE_URL="")

    def test_rejects_missing_home(self) -> None:
        with self.assertRaises(ConfigError):
            load_settings(env={}, base_dir=self.home / "does-not-exist")

    def test_settings_are_immutable(self) -> None:
        settings = self.make_settings()
        with self.assertRaises(Exception):
            settings.commission_rate = 0.5  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
