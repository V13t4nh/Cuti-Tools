"""Keep every production Python module within the agreed source-size limit."""

from __future__ import annotations

import unittest
from pathlib import Path


class SourceLineLimitTests(unittest.TestCase):
    def test_cuti_python_files_are_at_most_250_physical_lines(self) -> None:
        source_root = Path(__file__).resolve().parents[1] / "src" / "cuti"
        violations = []
        for source_file in sorted(source_root.rglob("*.py")):
            line_count = len(source_file.read_text(encoding="utf-8").splitlines())
            if line_count > 250:
                violations.append(f"{source_file.relative_to(source_root)}: {line_count}")

        self.assertFalse(
            violations,
            "Python source files exceed the 250-line limit: " + ", ".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
