"""UI module contracts that run without installing the optional UI stack."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import unittest


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
