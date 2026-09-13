from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ModelComparisonReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Path(__file__).resolve().parents[2]
        self.script = (
            self.repository / "scripts" / "inspection" / "render_model_comparison.py"
        )

    def test_renderer_is_deterministic_and_contains_reviewed_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            first = Path(temporary_directory) / "first.svg"
            second = Path(temporary_directory) / "second.svg"
            for output in (first, second):
                result = subprocess.run(
                    [sys.executable, str(self.script), "--output", str(output)],
                    cwd=self.repository,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            svg = first.read_text(encoding="utf-8")
            self.assertIn("no universal winner", svg)
            self.assertIn("Unconditional Gaussian", svg)
            self.assertIn("One-state AR", svg)
            self.assertIn("Final model", svg)
            self.assertIn("Not authorized", svg)
            for reviewed_value in (
                "0.359350",
                "0.362535",
                "0.364830",
                "0.374542",
                "0.365110",
                "0.984050",
                "0.994829",
                "1.007659",
                "1.018113",
                "1.009150",
                "0.297740",
                "0.286028",
                "0.276110",
                "0.286286",
                "0.276216",
                "0.888345",
                "0.008472",
                "0.018276",
                "0.007590",
            ):
                self.assertIn(reviewed_value, svg)

            report = (
                self.repository / "docs" / "model_comparison.md"
            ).read_text(encoding="utf-8")
            for reviewed_coverage in (
                "0.937690",
                "0.928183",
                "0.907818",
                "0.868940",
                "0.917083",
            ):
                self.assertIn(reviewed_coverage, report)

    def test_renderer_rejects_non_figure_extension(self) -> None:
        result = subprocess.run(
            [sys.executable, str(self.script), "--output", "comparison.txt"],
            cwd=self.repository,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("must end in .svg or .png", result.stderr)


if __name__ == "__main__":
    unittest.main()
