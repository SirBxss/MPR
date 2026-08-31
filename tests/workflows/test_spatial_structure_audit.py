from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.domain.spatial_structure import (
    mean_off_diagonal_correlation,
    population_spatial_moments,
)
from lane_residuals.io.reports import write_strict_json
from lane_residuals.workflows.sequence_contract import sha256_file
from lane_residuals.workflows.spatial_structure_audit import (
    ARM_NAMES,
    FEATURE_NAMES,
    MATRIX_KEYS,
    PAIR_FIELDS,
    SEPARATION_FIELDS,
    SEQUENCE_FIELDS,
    STATIONS_M,
    run_spatial_structure_audit,
)
from lane_residuals.workflows.spatial_structure_audit_contract import (
    A2_SAMPLE_FILENAME,
    A2_SUMMARY_FILENAME,
    A3_SAMPLE_FILENAME,
    A3_SUMMARY_FILENAME,
    MATRICES_FILENAME,
    OUTPUT_FILENAMES,
    PAIR_FILENAME,
    SEPARATION_FILENAME,
    SEQUENCE_FILENAME,
    SUMMARY_FILENAME,
    SpatialStructureAuditContract,
)


def _write_samples(
    directory: Path,
    filename: str,
    residuals: np.ndarray,
    lengths: np.ndarray,
    sequence_ids: np.ndarray,
) -> str:
    directory.mkdir(parents=True)
    path = directory / filename
    np.savez_compressed(
        path,
        residual_samples_m=residuals,
        lengths=lengths,
        stations_m=STATIONS_M,
        sequence_ids=sequence_ids,
        feature_names=np.asarray(FEATURE_NAMES, dtype=np.str_),
    )
    return sha256_file(path)


def _a2_summary(sample_hash: str) -> dict[str, object]:
    return {
        "version": "0.15.4",
        "status": "complete",
        "purpose": "planner_facing_development_residual_sequence_sampling",
        "sample_file": A2_SAMPLE_FILENAME,
        "sample_file_sha256": sample_hash,
        "sample_count": 4,
        "sequence_count": 2,
        "maximum_sequence_length": 4,
        "active_frame_count": 6,
        "random_seed": 20260826,
        "residual_unit": "m",
        "generated_previous_residual_used": True,
        "sampling_is_free_running": True,
        "sequence_reset_applied_once_per_input_sequence": True,
        "independent_frame_sampling_used": False,
        "planner_executed": False,
        "path_geometry_modified": False,
        "planner_benefit_claimed": False,
        "final_model_selection_authorized": False,
        "positive_direction": (
            "left of the pseudo-reference with respect to increasing station"
        ),
        "residual_definition": (
            "EDP estimate minus spatially aligned RLMB pseudo-reference, "
            "projected onto the pseudo-reference left unit normal"
        ),
        "stations_m": STATIONS_M.tolist(),
        "feature_names_in_required_order": list(FEATURE_NAMES),
    }


def _a3_summary(
    sample_hash: str,
    *,
    a2_sample_hash: str,
    a2_summary_hash: str,
) -> dict[str, object]:
    return {
        "version": "0.16.1",
        "status": "complete",
        "purpose": "unconditional_gaussian_planner_transfer_sampling",
        "arm": "unconditional_gaussian",
        "sample_file": A3_SAMPLE_FILENAME,
        "sample_file_sha256": sample_hash,
        "sample_count": 4,
        "sequence_count": 2,
        "maximum_sequence_length": 4,
        "active_frame_count": 6,
        "random_seed": 20260828,
        "accepted_a2_sampling_seed": 20260826,
        "accepted_a2_sample_file_sha256": a2_sample_hash,
        "accepted_a2_sample_summary_sha256": a2_summary_hash,
        "residual_unit": "m",
        "temporal_dependency_order": 0,
        "sequence_state_used": False,
        "active_frames_are_independent_draws": True,
        "spatial_cross_station_covariance_preserved": True,
        "common_random_numbers_with_a1_a2_used": False,
        "paired_residual_profiles_with_a1_a2_used": False,
        "planner_executed": False,
        "planner_benefit_claimed": False,
        "bmw_planner_behavior_claimed": False,
        "journey_level_generalization_estimated": False,
        "final_model_selection_authorized": False,
        "stations_m": STATIONS_M.tolist(),
        "feature_names_in_required_order": list(FEATURE_NAMES),
        "standardizer_equality_audit": {
            "comparison_dtype": "float64",
            "elementwise_exact_equal": True,
            "tolerance_based_acceptance_used": False,
            "maximum_absolute_discrepancy": {
                "residual_mean_m": 0.0,
                "residual_scale_m": 0.0,
                "stations_m": 0.0,
            },
        },
    }


class SpatialStructureAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.a2_directory = self.root / "a2"
        self.a3_directory = self.root / "a3"
        self.output_directory = self.root / "output"
        lengths = np.asarray([4, 2], dtype=np.int64)
        sequence_ids = np.asarray(["sequence_b", "sequence_a"], dtype=np.str_)
        rng = np.random.default_rng(7)
        innovations = rng.normal(size=(4, 2, 4, len(STATIONS_M)))
        station_scale = np.linspace(0.5, 1.5, len(STATIONS_M))
        self.a2_residuals = np.asarray(
            innovations * station_scale[None, None, None, :], dtype=np.float64
        )
        common = rng.normal(size=(4, 2, 4, 1))
        local = rng.normal(size=(4, 2, 4, len(STATIONS_M)))
        self.a3_residuals = np.asarray(
            (0.8 * common + 0.2 * local) * station_scale[None, None, None, :],
            dtype=np.float64,
        )
        for residuals in (self.a2_residuals, self.a3_residuals):
            residuals[:, 1, 2:, :] = 0.0

        a2_sample_hash = _write_samples(
            self.a2_directory,
            A2_SAMPLE_FILENAME,
            self.a2_residuals,
            lengths,
            sequence_ids,
        )
        write_strict_json(
            self.a2_directory / A2_SUMMARY_FILENAME,
            _a2_summary(a2_sample_hash),
        )
        a2_summary_hash = sha256_file(self.a2_directory / A2_SUMMARY_FILENAME)
        a3_sample_hash = _write_samples(
            self.a3_directory,
            A3_SAMPLE_FILENAME,
            self.a3_residuals,
            lengths,
            sequence_ids,
        )
        write_strict_json(
            self.a3_directory / A3_SUMMARY_FILENAME,
            _a3_summary(
                a3_sample_hash,
                a2_sample_hash=a2_sample_hash,
                a2_summary_hash=a2_summary_hash,
            ),
        )
        self.contract = SpatialStructureAuditContract(
            a2_sample_sha256=a2_sample_hash,
            a2_summary_sha256=a2_summary_hash,
            a3_sample_sha256=a3_sample_hash,
            a3_summary_sha256=sha256_file(
                self.a3_directory / A3_SUMMARY_FILENAME
            ),
            sample_count=4,
            sequence_count=2,
            maximum_sequence_length=4,
            active_frame_count=6,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_writes_exact_five_file_numeric_contract(self) -> None:
        summary, status = run_spatial_structure_audit(
            self.a2_directory,
            self.a3_directory,
            self.output_directory,
            contract=self.contract,
        )

        self.assertEqual(status, 0)
        self.assertEqual(
            {path.name for path in self.output_directory.iterdir()},
            set(OUTPUT_FILENAMES),
        )
        with np.load(
            self.output_directory / MATRICES_FILENAME, allow_pickle=False
        ) as archive:
            self.assertEqual(set(archive.files), MATRIX_KEYS)
            self.assertEqual(tuple(archive["arm_names"].tolist()), ARM_NAMES)
            np.testing.assert_array_equal(archive["lengths"], [4, 2])
            self.assertEqual(archive["lengths"].dtype, np.dtype(np.int64))
            self.assertEqual(archive["pooled_covariances_m2"].shape, (2, 21, 21))
            self.assertEqual(
                archive["per_sequence_correlations"].shape, (2, 2, 21, 21)
            )
            for name in archive.files:
                self.assertNotEqual(archive[name].dtype, np.dtype(object))

            mask = np.arange(4)[None, :] < np.asarray([4, 2])[:, None]
            expected_a2 = population_spatial_moments(
                self.a2_residuals[:, mask, :].reshape(-1, 21)
            )
            np.testing.assert_allclose(
                archive["pooled_covariances_m2"][0], expected_a2.covariance
            )
            np.testing.assert_allclose(
                archive["pooled_correlation_difference"],
                archive["pooled_correlations"][1]
                - archive["pooled_correlations"][0],
            )

        with (self.output_directory / PAIR_FILENAME).open(
            "r", encoding="utf-8", newline=""
        ) as stream:
            pair_rows = list(csv.DictReader(stream))
        self.assertEqual(tuple(pair_rows[0]), PAIR_FIELDS)
        self.assertEqual(len(pair_rows), 210)
        self.assertEqual(
            (pair_rows[0]["station_i_m"], pair_rows[0]["station_j_m"]),
            ("0.0", "5.0"),
        )
        self.assertEqual(
            (pair_rows[-1]["station_i_m"], pair_rows[-1]["station_j_m"]),
            ("95.0", "100.0"),
        )

        with (self.output_directory / SEPARATION_FILENAME).open(
            "r", encoding="utf-8", newline=""
        ) as stream:
            separation_rows = list(csv.DictReader(stream))
        self.assertEqual(tuple(separation_rows[0]), SEPARATION_FIELDS)
        self.assertEqual(len(separation_rows), 20)
        self.assertEqual(separation_rows[0]["station_pair_count"], "20")
        self.assertEqual(separation_rows[-1]["station_pair_count"], "1")

        with (self.output_directory / SEQUENCE_FILENAME).open(
            "r", encoding="utf-8", newline=""
        ) as stream:
            sequence_rows = list(csv.DictReader(stream))
        self.assertEqual(tuple(sequence_rows[0]), SEQUENCE_FIELDS)
        self.assertEqual(
            [row["sequence_id"] for row in sequence_rows],
            ["sequence_b", "sequence_a"],
        )

        stored_summary = json.loads(
            (self.output_directory / SUMMARY_FILENAME).read_text(encoding="utf-8")
        )
        self.assertEqual(stored_summary, summary)
        self.assertTrue(summary["reviewer_preimplementation_calculation_disclosed"])
        self.assertFalse(summary["statistic_added_or_removed_after_reviewer_calculation"])
        self.assertFalse(summary["temporal_dependence"]["scalar_effective_sample_size_reported"])
        self.assertTrue(summary["generated_outputs_remain_outside_version_control"])
        self.assertFalse(summary["planner_benefit_claimed"])
        self.assertFalse(summary["causal_contribution_estimated"])
        self.assertFalse(
            summary["marginal_scale_and_spatial_coherence_causally_separated"]
        )
        self.assertEqual(
            set(summary["output_files_sha256"]),
            set(OUTPUT_FILENAMES) - {SUMMARY_FILENAME},
        )
        for name, expected_hash in summary["output_files_sha256"].items():
            self.assertEqual(sha256_file(self.output_directory / name), expected_hash)

        expected_off = mean_off_diagonal_correlation(expected_a2.correlation)
        self.assertAlmostEqual(
            summary["pooled_correlation_summary"]["mean_off_diagonal"]["frozen_ar"],
            expected_off,
        )

    def test_hash_tamper_fails_before_creating_output(self) -> None:
        with (self.a2_directory / A2_SAMPLE_FILENAME).open("ab") as stream:
            stream.write(b"tamper")

        with self.assertRaisesRegex(ValueError, "SHA-256"):
            run_spatial_structure_audit(
                self.a2_directory,
                self.a3_directory,
                self.output_directory,
                contract=self.contract,
            )

        self.assertFalse(self.output_directory.exists())

    def test_extra_input_file_fails_before_creating_output(self) -> None:
        (self.a3_directory / "unexpected.txt").write_text("extra", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "filename set"):
            run_spatial_structure_audit(
                self.a2_directory,
                self.a3_directory,
                self.output_directory,
                contract=self.contract,
            )

        self.assertFalse(self.output_directory.exists())

    def test_nonzero_padding_fails_after_valid_lineage_before_output(self) -> None:
        changed = np.array(self.a2_residuals, copy=True)
        changed[0, 1, 3, 0] = 0.25
        lengths = np.asarray([4, 2], dtype=np.int64)
        sequence_ids = np.asarray(["sequence_b", "sequence_a"], dtype=np.str_)
        np.savez_compressed(
            self.a2_directory / A2_SAMPLE_FILENAME,
            residual_samples_m=changed,
            lengths=lengths,
            stations_m=STATIONS_M,
            sequence_ids=sequence_ids,
            feature_names=np.asarray(FEATURE_NAMES, dtype=np.str_),
        )
        a2_sample_hash = sha256_file(self.a2_directory / A2_SAMPLE_FILENAME)
        write_strict_json(
            self.a2_directory / A2_SUMMARY_FILENAME,
            _a2_summary(a2_sample_hash),
        )
        a2_summary_hash = sha256_file(self.a2_directory / A2_SUMMARY_FILENAME)
        a3_sample_hash = sha256_file(self.a3_directory / A3_SAMPLE_FILENAME)
        write_strict_json(
            self.a3_directory / A3_SUMMARY_FILENAME,
            _a3_summary(
                a3_sample_hash,
                a2_sample_hash=a2_sample_hash,
                a2_summary_hash=a2_summary_hash,
            ),
        )
        contract = SpatialStructureAuditContract(
            a2_sample_sha256=a2_sample_hash,
            a2_summary_sha256=a2_summary_hash,
            a3_sample_sha256=a3_sample_hash,
            a3_summary_sha256=sha256_file(
                self.a3_directory / A3_SUMMARY_FILENAME
            ),
            sample_count=4,
            sequence_count=2,
            maximum_sequence_length=4,
            active_frame_count=6,
        )

        with self.assertRaisesRegex(ValueError, "padding"):
            run_spatial_structure_audit(
                self.a2_directory,
                self.a3_directory,
                self.output_directory,
                contract=contract,
            )

        self.assertFalse(self.output_directory.exists())

    def test_nonempty_output_is_never_overwritten(self) -> None:
        self.output_directory.mkdir()
        sentinel = self.output_directory / "keep.txt"
        sentinel.write_text("preserve", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "not empty"):
            run_spatial_structure_audit(
                self.a2_directory,
                self.a3_directory,
                self.output_directory,
                contract=self.contract,
            )

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
