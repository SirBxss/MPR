import builtins
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from lane_residuals.io.velocity_history import PREFIX, load_return, read_archive, sha
from tests.io.velocity_history_fixture import fixture, write_archive


class CachedReturnTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.files = fixture(self.base)

    def test_full_cached_return_replay_does_not_query_raw_paths(self):
        path, pin = write_archive(self.base, self.files)
        violations = []
        def guarded(function):
            def call(name, *args, **kwargs):
                try: text = os.fsdecode(name)
                except TypeError: return function(name, *args, **kwargs)
                if text.lower().endswith(".mcap") or "DO_NOT_READ_SYNTHETIC_PATH" in text:
                    violations.append(text); raise AssertionError("raw query")
                return function(name, *args, **kwargs)
            return call
        with patch("os.stat", guarded(os.stat)), patch("os.lstat", guarded(os.lstat)), patch("os.open", guarded(os.open)), patch("builtins.open", guarded(builtins.open)), patch("io.open", guarded(io.open)):
            result = load_return(path, pin)
        self.assertEqual(len(result["targets"]), 120)
        self.assertEqual(len(result["original_frames"]), 240)
        self.assertEqual(violations, [])
        self.assertEqual(sha(path.read_bytes()), pin)

    def test_wrong_archive_pin_refused(self):
        path, _ = write_archive(self.base, self.files)
        with self.assertRaisesRegex(ValueError, "archive_sha256"): load_return(path, "0"*64)

    def test_non_zip_and_symlink_inputs_refused(self):
        path, pin = write_archive(self.base, self.files)
        for other in (self.base/"raw.mcap", self.base/"alias.zip"):
            other.symlink_to(path)
            with self.assertRaises((ValueError, OSError)): read_archive(other, pin)

    def test_duplicate_member_and_traversal_member_refused(self):
        path, _ = write_archive(self.base, self.files)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(path, "a") as z: z.writestr("source_gate.private.json", b"duplicate")
        with self.assertRaisesRegex(ValueError, "archive_members"): read_archive(path, sha(path.read_bytes()))
        files = dict(self.files); files["../outside.json"] = files.pop("source_gate.private.json")
        path, pin = write_archive(self.base, files)
        with self.assertRaisesRegex(ValueError, "archive_members"): load_return(path, pin)

    def test_archive_symlink_member_refused(self):
        path = self.base/"cached_results.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in self.files.items():
                entry = zipfile.ZipInfo(name)
                if name == "source_gate.private.json": entry.external_attr = 0o120777 << 16
                archive.writestr(entry, data)
        with self.assertRaisesRegex(ValueError, "archive_path"): read_archive(path, sha(path.read_bytes()))

    def test_expansion_budget_checked_before_member_reads(self):
        files = dict(self.files); files[PREFIX+"01_velocity_observations.png"] = b"x"*(8*1024**2)
        path, pin = write_archive(self.base, files)
        with self.assertRaisesRegex(ValueError, "archive_expansion"): load_return(path, pin)

    def test_tampered_frame_csv_fails_frozen_replay(self):
        files = dict(self.files)
        files[PREFIX+"frame_screens.private.csv"] = files[PREFIX+"frame_screens.private.csv"].replace(b"future_source_timestamp", b"different_failure")
        path, pin = write_archive(self.base, files)
        with self.assertRaisesRegex(ValueError, "original_analysis_replay"): load_return(path, pin)

    def test_missing_or_drifted_csv_columns_refused(self):
        files = dict(self.files)
        files[PREFIX+"velocity_updates.private.csv"] = files[PREFIX+"velocity_updates.private.csv"].replace(b"publish_ns", b"different_ns", 1)
        path, pin = write_archive(self.base, files)
        with self.assertRaisesRegex(ValueError, "csv_columns"): load_return(path, pin)

    def test_incomplete_receipt_refused(self):
        files = dict(self.files); name = "timing_a2_attempt_001/launcher_receipt.private.json"
        receipt = json.loads(files[name]); receipt["status"] = "incomplete"; files[name] = json.dumps(receipt).encode()
        path, pin = write_archive(self.base, files)
        with self.assertRaisesRegex(ValueError, "complete_parent"): load_return(path, pin)

    def test_cached_name_traversal_refused_before_frozen_loader(self):
        with tempfile.TemporaryDirectory() as temporary:
            files = fixture(temporary, change_request=lambda r: r.update(audit_file="/synthetic/private_raw/output.mcap"))
            path, pin = write_archive(temporary, files)
            with self.assertRaisesRegex(ValueError, "cached_input_names"): load_return(path, pin)

    def test_final_role_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            files = fixture(temporary, role="final_test"); path, pin = write_archive(temporary, files)
            with self.assertRaisesRegex(ValueError, "development_only"): load_return(path, pin)


if __name__ == "__main__":
    unittest.main()
