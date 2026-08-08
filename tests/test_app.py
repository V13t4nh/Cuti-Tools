"""Streamlit form regressions for explicit buyer inputs."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from support import ProjectTestCase


class AppFormTests(ProjectTestCase):
    def test_condition_and_form_have_no_implicit_default(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "src" / "cuti" / "app.py"
        env = {
            "CUTI_HOME": str(self.home),
            "CUTI_DB_PATH": str(self.home / "var" / "ui.db"),
            "CUTI_RULES_PATH": str(self.home / "config" / "rules.json"),
        }
        with patch.dict(os.environ, env, clear=False):
            app = AppTest.from_file(str(app_path)).run(timeout=20)
            self.assertEqual([item.value for item in app.selectbox], [None, None])
            app.button[0].click()
            app = app.run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        self.assertIn(
            "Hãy chọn rõ tình trạng và form vỏ trước khi chấm deal.",
            [item.value for item in app.error],
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
