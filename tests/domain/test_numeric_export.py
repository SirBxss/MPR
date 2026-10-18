import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.domain import numeric_export as policy, path_source_probe as probe
from lane_residuals.io.numeric_archive import reconstruct_sequences, independent_support, _speed
from tests.domain.test_exploratory_residuals import row

PINS = {
    "domain/path_source_probe.py": "3a0ab8928630739dd0cbf8a9f3d1498f3f23e7e7bbc11c1c0bbfce62141b69f1",
    "domain/geometry_validation.py": "19dc27abf75593d567fa277055b80a874eaa8c165a132d93033405e16386edce",
    "domain/recording_readiness_bindings.py": "406695ba2b098a32d8611ab3351a1fb948ec363aa336016feff3d2e59e5bc2a0",
    "io/independent_outing_intake.py": "0f9e8c875c812321d2e900273ade5a040f181677eb19f8db0bfc3d32d811621a",
    "io/bounded_recording_readiness.py": "9343691296296f6b0a4847271266dba2adf419e0f31fa2ccad43ae1fe8b9aae1",
}


class NumericDomainTests(unittest.TestCase):
    def test_five_scientific_sources_match_accepted_main_bytes(self):
        root = Path(probe.__file__).parents[1]
        for name, digest in PINS.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(), digest)

    def test_complete_seven_use_four_definition_surface_including_values(self):
        root = Path(probe.__file__).parents[1]
        uses, definitions = [], []
        for path in sorted(root.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call):
                    for keyword in node.keywords:
                        if keyword.arg == "allow_bounded_v01911_edp":
                            uses.append((path.relative_to(root).as_posix(), node.lineno, ast.unparse(keyword.value)))
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                        if arg.arg == "allow_bounded_v01911_edp":
                            definitions.append((path.relative_to(root).as_posix(), node.name, ast.unparse(default)))
        self.assertEqual(uses, [
            ("domain/geometry_validation.py", 463, "allow_bounded_v01911_edp"),
            ("domain/recording_readiness_bindings.py", 163, "allow_bounded_v01911_edp"),
            ("io/bounded_recording_readiness.py", 60, "True"),
            ("io/bounded_recording_readiness.py", 110, "True"),
            ("io/bounded_recording_readiness.py", 127, "True"),
            ("io/independent_outing_intake.py", 179, "allow_bounded_v01911_edp"),
            ("io/independent_outing_intake.py", 193, "allow_bounded_v01911_edp")])
        self.assertEqual(definitions, [
            ("domain/geometry_validation.py", "estimated_frame_from_message", "False"),
            ("domain/path_source_probe.py", "estimate_descriptor_support", "False"),
            ("domain/recording_readiness_bindings.py", "classify", "False"),
            ("io/independent_outing_intake.py", "iter_geometry_records", "False")])

    def test_new_modules_do_not_import_or_directly_call_admission_helpers(self):
        root = Path(probe.__file__).parents[1]
        forbidden = {"classify", "estimated_frame_from_message", "estimate_descriptor_support", "iter_geometry_records"}
        for name in ("io/numeric_residuals.py", "io/numeric_archive.py", "io/numeric_export_inputs.py", "workflows/numeric_export.py"):
            for node in ast.walk(ast.parse((root/name).read_text())):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse({a.name for a in node.names} & forbidden, name)
                if isinstance(node, ast.Call):
                    called = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else None
                    self.assertNotIn(called, forbidden, name)
                    if called == "getattr" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                        self.assertNotIn(node.args[1].value, forbidden, name)

    def test_serialized_policy_matches_both_existing_fixed_roots_and_is_frozen(self):
        data = policy.admission_policy()
        self.assertEqual(data["flag_absent_v2_root_file_sha256"], [probe.ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
            probe.ADDITIONAL_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256])
        self.assertTrue(data["structural_legacy_v1"] and data["historical_defaults_unchanged"])
        with self.assertRaises(TypeError):policy.NUMERIC_ESTIMATE_ADMISSION_POLICY_V01912["mechanism"] = "other"
        data["flag_absent_v2_root_file_sha256"].clear()
        self.assertEqual(len(policy.admission_policy()["flag_absent_v2_root_file_sha256"]), 2)

    def test_u48_and_full_uint64_roundtrip_without_truncation_or_float(self):
        identifier = "a"+"x"*47
        arrays, _ = policy.build_numeric_archive([row(0, 2**64-1, recording=identifier)])
        self.assertEqual(str(arrays["recording_id"][0]), identifier)
        self.assertEqual(str(arrays["estimate_source_time_ns_decimal"][0]), "18446744073709551615")
        self.assertEqual(arrays["recording_id"].dtype.str, "<U48")
        self.assertTrue(all(a.flags.c_contiguous and a.dtype.kind != "O" for a in arrays.values()))

    def test_independent_sequence_oracle_handles_gaps_duplicates_and_files(self):
        rows = [row(0, 2**53+1), row(1, 2**53+1+200_000_000), row(3, 2**53+1+300_000_000),
            row(4, 2**53+1+300_000_000), row(5, 2**53+1+500_000_001), row(6, 2**53+1+600_000_000, recording="other")]
        offsets, sequences = reconstruct_sequences(rows)
        self.assertEqual(offsets, [0, 2, 3, 4, 5, 6])
        self.assertEqual([s["start_reasons"] for s in sequences], [["recording_start"], ["estimate_index_gap", "pair_index_gap"],
            ["timestamp_non_monotonic"], ["temporal_gap_exceeds_200ms"], ["recording_boundary"]])
        self.assertEqual(sequences[0]["duration_ns"], 200_000_000)

    def test_condition_subset_and_residual_loss_split_populations_separately(self):
        candidates = [row(0, 1_000_000_000), row(1, 1_100_000_000, conditions=False), row(2, 1_200_000_000),
            row(3, 1_300_000_000, residual=False), row(4, 1_400_000_000)]
        arrays, support = policy.build_numeric_archive(candidates)
        self.assertEqual(arrays["geometry_sequence_offsets"].tolist(), [0, 3, 4])
        self.assertEqual(arrays["conditioned_sequence_offsets"].tolist(), [0, 1, 2, 3])
        audit = [{**r, "residual_available": r["residuals_m"] is not None, "conditions_available": r["conditions"] is not None} for r in candidates]
        with patch("lane_residuals.domain.numeric_export.sequence_layout", side_effect=AssertionError("shared reconstruction forbidden")):
            self.assertEqual(independent_support(audit), support)

    def test_canonical_decimal_rejects_lossy_alternate_or_out_of_range_values(self):
        for value in (1, True, "01", "+1", "-0", "1.0", "1e3", str(2**64), "１２"):
            with self.subTest(value=value), self.assertRaises(ValueError):policy.decimal(value)
        self.assertEqual(policy.decimal(str(2**64-1)), 2**64-1)

    def test_minimum_log_evidence_is_required_and_rejections_are_symmetric(self):
        evidence = {"previous_lower_timestamp_ns_decimal_private": "950000000", "previous_upper_timestamp_ns_decimal_private": "950000000",
            "current_lower_timestamp_ns_decimal_private": "1000000000", "current_upper_timestamp_ns_decimal_private": "1000000000",
            "maximum_input_log_time_ns_decimal_private": "2000000000", "maximum_input_publish_time_ns_decimal_private": "2000000001",
            "minimum_input_log_time_ns_decimal_private": "2000000000"}
        value = {"condition_failure_codes": [], "speed_bracket_evidence": evidence,
            "estimate_source_time_ns_private": 1_000_000_000, "estimate_log_time_ns_private": 2_000_000_000}
        _speed(value)
        for changed in ({"minimum_input_log_time_ns_decimal_private": "0"}, {"maximum_input_log_time_ns_decimal_private": "2000000001"},
                {"current_upper_timestamp_ns_decimal_private": "1010000000"}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                _speed({**value, "speed_bracket_evidence": {**evidence, **changed}})
        with self.assertRaises(ValueError):_speed({**value, "condition_failure_codes": ["speed_uses_future_source_sample"]})


if __name__ == "__main__":
    unittest.main()
