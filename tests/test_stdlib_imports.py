"""Core modules must import on a source-only, standard-library runtime."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


class CoreImportTests(unittest.TestCase):
    def test_all_non_ui_modules_avoid_optional_ui_dependencies(self) -> None:
        source_root = Path(__file__).resolve().parents[1] / "src"
        script = """
import importlib
import pkgutil
import sys
import cuti

for module in pkgutil.walk_packages(cuti.__path__, cuti.__name__ + '.'):
    if module.name == 'cuti.app':
        continue
    importlib.import_module(module.name)

forbidden = {'streamlit', 'plotly', 'rapidfuzz'}
loaded = sorted(
    name for name in sys.modules
    if name.split('.', 1)[0] in forbidden
)
if loaded:
    raise SystemExit('optional modules imported: ' + ', '.join(loaded))
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = str(source_root)
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
