"""UI module contracts that run without installing the optional UI stack."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import unittest
from datetime import date
from unittest.mock import patch

from cuti.app import _render_distribution
from cuti.evaluation_chart import ComparisonChartData, evaluate_deal_with_chart
from cuti.models import Condition

from support import ProjectTestCase, TODAY, make_lot


QUERY = "Omega Seamaster Diver 300M 210.30.42"


class _RecordingStreamlit:
    """Small offline recorder for asserting the UI's render contract."""

    def __init__(self) -> None:
        self.metrics: list[tuple[str, object]] = []
        self.bar_charts: list[object] = []

    def metric(self, label: str, value: object) -> None:
        self.metrics.append((label, value))

    def subheader(self, _value: str) -> None:
        return None

    def bar_chart(self, value: object) -> None:
        self.bar_charts.append(value)


class BuyerChartRenderTests(ProjectTestCase):
    def test_app_renders_accessor_cycle_and_heart_values_verbatim(self) -> None:
        self.seed_lots(
            [
                make_lot("q4", title=QUERY, ended_at=date(2025, 10, 1), hammer_eur=100),
                make_lot("q1", title=QUERY, ended_at=date(2026, 1, 1), hammer_eur=200),
                make_lot("q2", title=QUERY, ended_at=date(2026, 4, 1), hammer_eur=300),
                make_lot("old", title=QUERY, ended_at=date(2026, 6, 15), hearts=10),
                make_lot("new", title=QUERY, ended_at=date(2026, 7, 15), hearts=20),
            ]
        )
        with patch(
            "cuti.evaluation_chart.cycle_position", return_value=0.875
        ), patch(
            "cuti.evaluation_chart.heart_acceleration_rate", return_value=-0.25
        ):
            result = evaluate_deal_with_chart(
                self.conn,
                self.rules,
                self.settings,
                query=QUERY,
                cost=1000,
                currency="eur",
                condition=Condition.NAKED,
                today=TODAY,
            )
        recorder = _RecordingStreamlit()

        _render_distribution(result.chart, recorder)

        rendered = dict(recorder.metrics)
        self.assertEqual(
            rendered["Vị trí chu kỳ"], f"{result.chart.cycle_position:.0%}"
        )
        self.assertEqual(
            rendered["Gia tốc tim"], f"{result.chart.heart_acceleration_rate:+.1%}"
        )

    def test_app_hides_missing_chart_metrics(self) -> None:
        chart = ComparisonChartData(
            hammer_prices_eur=(),
            input_hammer_eur=None,
            cycle_position=None,
            heart_acceleration_rate=None,
        )
        recorder = _RecordingStreamlit()

        _render_distribution(chart, recorder)

        labels = {label for label, _ in recorder.metrics}
        self.assertNotIn("Vị trí chu kỳ", labels)
        self.assertNotIn("Gia tốc tim", labels)


class AppImportTests(unittest.TestCase):
    def setUp(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "src" / "cuti" / "app.py"
        self.source = app_path.read_text(encoding="utf-8")

    def test_app_import_has_no_optional_dependency_side_effect(self) -> None:
        module = importlib.import_module("cuti.app")
        self.assertTrue(callable(module.main))

    def test_streamlit_and_charts_imports_are_inside_ui_functions(self) -> None:
        tree = ast.parse(self.source)
        top_level_imports = [
            node
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        imported = {
            alias.name.split(".", 1)[0]
            for node in top_level_imports
            for alias in getattr(node, "names", ())
        }
        self.assertNotIn("streamlit", imported)
        self.assertNotIn("plotly", imported)

        streamlit_imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            and any(alias.name == "streamlit" for alias in node.names)
        ]
        self.assertEqual(len(streamlit_imports), 1)
        self.assertTrue(any(isinstance(parent, ast.FunctionDef) for parent in ast.walk(tree)))


if __name__ == "__main__":
    import unittest

    unittest.main()
