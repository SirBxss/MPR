"""Distribution-content checks for the categorized source tree."""

from __future__ import annotations

import os
import unittest
import zipfile
from pathlib import Path


class WheelContentTests(unittest.TestCase):
    def test_wheel_contains_only_the_lane_residuals_top_level_package(self) -> None:
        raw_path = os.environ.get("MPR_WHEEL_PATH")
        if raw_path is None:
            self.skipTest("set MPR_WHEEL_PATH after building the wheel")
        wheel = Path(raw_path)
        self.assertTrue(wheel.is_file(), wheel)
        with zipfile.ZipFile(wheel) as archive:
            names = tuple(archive.namelist())
        self.assertTrue(any(name.startswith("lane_residuals/") for name in names))
        self.assertFalse(any(name.startswith("preprocessing/") for name in names))


if __name__ == "__main__":
    unittest.main()
