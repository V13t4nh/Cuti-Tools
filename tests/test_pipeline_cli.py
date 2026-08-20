"""End-to-end tests: fetch, ingest, quote, watch, report and the CLI surface."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import patch

from cuti.cli import main
from cuti.errors import FetchError, NormalizationError, ScrapeError
from cuti.fetch import fetch_json, fetch_text, resolve, to_url
from cuti.models import Condition, Verdict
from cuti.notifier import FileNotifier, TelegramNotifier, build_notifier, format_message
from cuti.pipeline import WatchReport, ingest_lots, quote_watch, watch_deals
from cuti.report import build_histogram, render_report, write_report
from cuti.storage import count_rows

from support import NOW, TODAY, ProjectTestCase, make_lot

TITLE = "Omega Seamaster Diver 300M 210.30.42 - watch only"


class FetchTests(ProjectTestCase):
    def test_plain_path_becomes_file_url(self) -> None:
        self.assertTrue(to_url(str(self.home / "config" / "rules.json")).startswith("file://"))

    def test_reads_local_file(self) -> None:
        self.assertIn("brands", fetch_text(str(self.home / "config" / "rules.json"), 5))

    def test_reads_local_json(self) -> None:
        self.assertIn("brands", fetch_json(str(self.home / "config" / "rules.json"), 5))

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(FetchError):
            fetch_text(str(self.home / "missing.html"), 5)

    def test_unsupported_scheme_raises(self) -> None:
        with self.assertRaises(FetchError):
            to_url("ftp://example.invalid/a.html")

    def test_empty_location_raises(self) -> None:
        with self.assertRaises(FetchError):
            to_url("")

    def test_invalid_json_raises(self) -> None:
        path = self.write_text("data/broken.json", "{nope")
        with self.assertRaises(FetchError):
            fetch_json(str(path), 5)

    def test_relative_links_resolve(self) -> None:
        self.assertEqual(resolve("file:///a/b/page-1.html", "page-2.html"), "file:///a/b/page-2.html")


class IngestTests(ProjectTestCase):
    def test_full_sample_crawl(self) -> None:
        report = ingest_lots(self.conn, self.rules, self.settings, NOW)
        self.assertEqual(report.pages_fetched, 8)
        self.assertEqual(report.lots_written, 384)
        self.assertEqual(count_rows(self.conn, "lots"), 384)

    def test_lot_limit_is_applied_before_write(self) -> None:
        report = ingest_lots(self.conn, self.rules, self.settings, NOW, max_lots=10)
        self.assertEqual(report.lots_written, 10)
        self.assertEqual(count_rows(self.conn, "lots"), 10)

    def test_ingest_is_idempotent(self) -> None:
        ingest_lots(self.conn, self.rules, self.settings, NOW)
        ingest_lots(self.conn, self.rules, self.settings, NOW)
        self.assertEqual(count_rows(self.conn, "lots"), 384)

    def test_page_limit_stops_the_crawl(self) -> None:
        settings = self.make_settings(CUTI_SOURCE_MAX_PAGES="2")
        report = ingest_lots(self.conn, self.rules, settings, NOW)
        self.assertEqual(report.pages_fetched, 2)

    def test_pagination_loop_is_detected(self) -> None:
        path = self.write_text(
            "data/loop/page-1.html",
            '<div class="lot-card" data-lot-id="cw-1" data-title="Omega Seamaster 210.30.42" '
            'data-condition="naked" data-form="round" '
            'data-hearts="1" data-sold="true" data-hammer-eur="100" data-opened-at="2026-01-01" '
            'data-ended-at="2026-01-02" data-url="x.html"></div>'
            '<a class="pagination-next" href="page-1.html"></a>',
        )
        settings = self.make_settings(CUTI_LOTS_SOURCE_URL=str(path))
        with self.assertRaises(ScrapeError):
            ingest_lots(self.conn, self.rules, settings, NOW)

    def test_unknown_brand_aborts_instead_of_guessing(self) -> None:
        path = self.write_text(
            "data/unknown/page-1.html",
            '<div class="lot-card" data-lot-id="cw-1" data-title="Nosuchbrand Diver 300" '
            'data-condition="naked" data-form="round" '
            'data-hearts="1" data-sold="true" data-hammer-eur="100" data-opened-at="2026-01-01" '
            'data-ended-at="2026-01-02" data-url="x.html"></div>',
        )
        settings = self.make_settings(CUTI_LOTS_SOURCE_URL=str(path))
        with self.assertRaises(NormalizationError):
            ingest_lots(self.conn, self.rules, settings, NOW)


class QuoteTests(ProjectTestCase):
    def _quote(self, cost_vnd: int, condition=None):
        return quote_watch(
            self.conn,
            self.rules,
            self.settings,
            title=TITLE,
            cost_vnd=cost_vnd,
            condition=condition,
            today=TODAY,
            now=NOW,
        )

    def test_thin_data_returns_insufficient_and_is_recorded(self) -> None:
        report = self._quote(50_000_000)
        self.assertIs(report.price.verdict, Verdict.INSUFFICIENT_DATA)
        self.assertEqual(count_rows(self.conn, "quotes"), 1)

    def test_green_light_on_cheap_cost(self) -> None:
        self.seed_lots([make_lot(f"cw-{i}", title=TITLE, hammer_eur=4000) for i in range(6)])
        report = self._quote(20_000_000)
        self.assertIs(report.price.verdict, Verdict.GREEN)
        self.assertEqual(report.price.sample_size, 6)

    def test_red_light_on_expensive_cost(self) -> None:
        self.seed_lots([make_lot(f"cw-{i}", title=TITLE, hammer_eur=4000) for i in range(6)])
        self.assertIs(self._quote(110_000_000).price.verdict, Verdict.RED)

    def test_explicit_condition_overrides_detection(self) -> None:
        self.seed_lots(
            [
                make_lot(f"cw-{i}", title=TITLE, condition=Condition.FULLSET, hammer_eur=4000)
                for i in range(6)
            ]
        )
        report = self._quote(20_000_000, Condition.FULLSET)
        self.assertIs(report.condition, Condition.FULLSET)
        self.assertEqual(report.price.sample_size, 6)


class NotifierTests(ProjectTestCase):
    PAYLOAD = {
        "title": "Omega",
        "url": "https://example.invalid/1",
        "source": "fb",
        "model_key": "omega:210.30.42",
        "condition": "box",
        "form": "round",
        "ask_vnd": 1000,
        "verdict": "green",
        "sample_size": 6,
        "attempt_count": 8,
        "net_p25_eur": 100.0,
        "net_median_eur": 120.0,
        "threshold_eur": 50.0,
        "median_days_to_close": 10.0,
    }

    def test_file_notifier_appends_jsonl(self) -> None:
        notifier = build_notifier(self.settings)
        self.assertIsInstance(notifier, FileNotifier)
        notifier.send(self.PAYLOAD)
        notifier.send(self.PAYLOAD)
        lines = self.settings.notifier_file_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["verdict"], "green")

    def test_message_mentions_the_verdict(self) -> None:
        self.assertIn("GREEN", format_message(self.PAYLOAD))

    def test_telegram_notifier_is_selected_by_config(self) -> None:
        settings = self.make_settings(
            CUTI_NOTIFIER="telegram",
            CUTI_TELEGRAM_BOT_TOKEN="token",
            CUTI_TELEGRAM_CHAT_ID="42",
        )
        self.assertIsInstance(build_notifier(settings), TelegramNotifier)


class WatchTests(ProjectTestCase):
    def _seed_market(self) -> None:
        self.seed_lots(
            [
                make_lot(
                    f"sub-{i}",
                    title="Rolex Submariner 124060 full set",
                    brand="rolex",
                    model_key="rolex:124060",
                    condition=Condition.FULLSET,
                    hammer_eur=14000,
                    ended_at=date(2026, 6, 1),
                )
                for i in range(8)
            ]
        )

    def test_watch_dedupes_and_alerts_only_on_green(self) -> None:
        self._seed_market()
        notifier = build_notifier(self.settings)
        report = watch_deals(self.conn, self.rules, self.settings, notifier, today=TODAY, now=NOW)
        self.assertEqual(report.deals_seen, 6)
        self.assertEqual(report.deals_new, 5)
        self.assertGreaterEqual(report.alerts_sent, 1)
        alerts = self.settings.notifier_file_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(alerts), report.alerts_sent)

    def test_second_run_finds_no_new_deals(self) -> None:
        self._seed_market()
        notifier = build_notifier(self.settings)
        watch_deals(self.conn, self.rules, self.settings, notifier, today=TODAY, now=NOW)
        second = watch_deals(self.conn, self.rules, self.settings, notifier, today=TODAY, now=NOW)
        self.assertEqual(second.deals_new, 0)
        self.assertEqual(second.alerts_sent, 0)

    def test_empty_feed_is_a_no_op(self) -> None:
        path = self.write_json("data/empty/deals.json", [])
        settings = self.make_settings(CUTI_DEALS_SOURCE_URL=str(path))
        report = watch_deals(
            self.conn, self.rules, settings, build_notifier(settings), today=TODAY, now=NOW
        )
        self.assertEqual((report.deals_seen, report.deals_new, report.alerts_sent), (0, 0, 0))


class ReportTests(ProjectTestCase):
    def test_histogram_edges_and_counts(self) -> None:
        histogram = build_histogram([1.0, 2.0, 3.0, 4.0], bins=2)
        self.assertEqual(histogram.counts, (2, 2))
        self.assertEqual(histogram.edges[0], 1.0)

    def test_histogram_handles_single_value_and_empty(self) -> None:
        self.assertEqual(build_histogram([5.0]).counts, (1,))
        self.assertEqual(build_histogram([]).counts, ())

    def test_report_renders_without_data(self) -> None:
        self.assertIn("CUTI-Tools", render_report(self.conn, self.settings, TODAY))

    def test_report_file_is_written(self) -> None:
        self.seed_lots([make_lot(f"cw-{i}", hammer_eur=3000 + i * 50) for i in range(10)])
        content = write_report(self.conn, self.settings, TODAY).read_text(encoding="utf-8")
        self.assertTrue(content.startswith("<!doctype html>"))
        self.assertIn("Liquidity", content)


class CliTests(ProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.conn.close()
        lines = [
            f"CUTI_LOTS_SOURCE_URL={self.home}/data/sample/catawiki/page-1.html",
            f"CUTI_DEALS_SOURCE_URL={self.home}/data/sample/deals/deals.json",
            "CUTI_MATCH_THRESHOLD=80",
        ]
        (self.home / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _run(self, *args: str) -> tuple[int, str]:
        buffer = io.StringIO()
        argv = ["--home", str(self.home), "--today", TODAY.isoformat(), *args]
        with redirect_stdout(buffer):
            code = main(argv)
        return code, buffer.getvalue()

    def test_full_workflow(self) -> None:
        self.assertEqual(self._run("init-db")[0], 0)

        code, out = self._run("--json", "ingest")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["lots_total"], 384)

        code, out = self._run(
            "--json",
            "quote",
            "--title",
            "Omega Speedmaster Professional 311.30.42 full set",
            "--cost-vnd",
            "30000000",
            "--condition",
            "fullset",
        )
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn(payload["verdict"], {verdict.value for verdict in Verdict})
        self.assertEqual(payload["condition"], "fullset")

        code, out = self._run("--json", "watch")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["deals_seen"], 6)

        code, out = self._run("--json", "liquidity")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["brands"])

        self.assertEqual(self._run("--json", "report")[0], 0)
        self.assertTrue((self.home / "var" / "report.html").is_file())

        code, out = self._run("--json", "status")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["lots"], 384)

    def test_configuration_error_exits_with_code_one(self) -> None:
        (self.home / "config" / "rules.json").write_text("{broken", encoding="utf-8")
        self.assertEqual(self._run("status")[0], 1)

    def test_watch_delivery_errors_are_visible_and_exit_nonzero(self) -> None:
        report = WatchReport(
            deals_seen=1,
            deals_new=1,
            deals_stale=0,
            deals_quoted=1,
            alerts_sent=0,
            alerts_failed=1,
            outbox_pending=1,
            outbox_dead=0,
            verdicts=(("Omega", Verdict.GREEN),),
            errors=("alert delivery failed",),
        )
        with patch("cuti.cli.watch_deals", return_value=report):
            code, output = self._run("watch")
        self.assertEqual(code, 1)
        self.assertIn("Error      : alert delivery failed", output)

    def test_bad_usage_exits_with_code_two(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main(["--home", str(self.home), "quote", "--title", "x"])
        self.assertEqual(ctx.exception.code, 2)

    def test_unknown_condition_value_is_rejected(self) -> None:
        argv = [
            "--home",
            str(self.home),
            "quote",
            "--title",
            "x",
            "--cost-vnd",
            "1",
            "--condition",
            "pristine",
        ]
        with self.assertRaises(SystemExit):
            main(argv)

    def test_ingest_max_lots_and_invalid_limits(self) -> None:
        code, out = self._run("--json", "ingest", "--max-lots", "10")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["lots_total"], 10)
        for value in ("0", "-1"):
            with self.subTest(value=value):
                self.assertEqual(self._run("ingest", "--max-lots", value)[0], 1)


if __name__ == "__main__":
    unittest.main()
