import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.cli.reference_planner_sensitivity import main as sensitivity_main
from lane_residuals.cli.reference_planner_scenarios import main as scenario_main
from lane_residuals.domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from lane_residuals.workflows.development_residual_sampling import (
    SAMPLES_FILENAME,
    SUMMARY_FILENAME as SAMPLE_SUMMARY_FILENAME,
)
from lane_residuals.workflows.reference_planner_scenarios import (
    CONDITION_FILENAME,
    SCENARIO_FILENAME,
)
from lane_residuals.workflows.reference_planner_sensitivity import (
    ARM_NAMES,
    FRAME_FILENAME,
    SEQUENCE_FILENAME,
    SUMMARY_OUTPUT_FILENAME,
    _time_shuffle,
)
from lane_residuals.workflows.sequence_contract import sha256_file


class ReferencePlannerSensitivityCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.expanded = self.root / "expanded"
        self.alignment = self.root / "alignment"
        self.expanded.mkdir()
        self.alignment.mkdir()
        self._write_expanded_input()
        self._write_alignment_input()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_expanded_input(self) -> None:
        count = 4
        base = {
            "residuals_m": np.zeros((count, 21)),
            "conditions": np.column_stack(
                (np.full(count, 10.0), np.zeros((count, 5)))
            ),
            "timestamps_ns_private": np.arange(count, dtype=np.int64) * 80_000_000 + 1,
            "recording_ids": np.asarray(["recording_001"] * count),
            "drive_ids": np.asarray(["drive_001"] * count),
            "mcap_basenames_private": np.asarray(["private.mcap"] * count),
            "sequence_ids": np.asarray(["sequence_a"] * count),
            "pair_indices": np.arange(count, dtype=np.int64),
            "estimate_message_indices": np.arange(count, dtype=np.int64),
            "stations_m": np.arange(0.0, 101.0, 5.0),
            "eligibility": np.ones(count, dtype=np.bool_),
            "exclusion_reasons": np.asarray([""] * count),
            "speed_context_states": np.asarray(["recording_local"] * count),
            "speed_context_left_mcap_basenames_private": np.asarray([""] * count),
            "speed_context_right_mcap_basenames_private": np.asarray([""] * count),
            "speed_context_odometry_timestamps_ns_json_private": np.asarray(["[]"] * count),
        }
        archive = self.expanded / "expanded_profile_dataset.npz"
        np.savez_compressed(archive, **base)
        output_names = [
            "expanded_profile_dataset.npz",
            "profile_eligibility_audit.csv",
            "sequence_manifest.csv",
            "sequence_summary_by_drive.csv",
            "cross_mcap_stitching_audit.csv",
            "boundary_odometry_context_audit.csv",
            "exclusion_reason_summary.csv",
            "v0130_parity_audit.json",
            "expanded_sequence_contract.json",
            "train_only_standardization_metadata.json",
            "expanded_sequence_diagnostics.png",
        ]
        identity = {
            "version": "0.13.1",
            "purpose": "quality_gated_expanded_sensor_topology_sequential_dataset_with_boundary_odometry_context",
        }
        for name in output_names:
            path = self.expanded / name
            if path == archive:
                continue
            if name == "expanded_sequence_contract.json":
                path.write_text(json.dumps({**identity, "status": "complete"}), encoding="utf-8")
            else:
                path.write_bytes(b"fixture")
        manifest = {
            **identity,
            "status": "complete",
            "output_files": output_names,
            "archive_sha256": sha256_file(archive),
        }
        manifest_path = self.expanded / "expanded_sequence_manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        generated = {
            name: sha256_file(self.expanded / name)
            for name in [*output_names, "expanded_sequence_manifest.json"]
        }
        (self.expanded / "expanded_sequence_provenance.json").write_text(
            json.dumps({**identity, "generated_outputs_sha256": generated}),
            encoding="utf-8",
        )

    def _write_alignment_input(self) -> None:
        fields = (
            "recording_id", "pair_index", "station_m",
            "aligned_reference_x_m", "aligned_reference_y_m", "h100_aligned_eligible",
        )
        with (self.alignment / "alignment_station_comparison.csv").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for pair in range(4):
                for station in np.arange(0.0, 101.0, 5.0):
                    writer.writerow(
                        {
                            "recording_id": "recording_001",
                            "pair_index": pair,
                            "station_m": station,
                            "aligned_reference_x_m": station,
                            "aligned_reference_y_m": 0.0,
                            "h100_aligned_eligible": "True",
                        }
                    )
        station_path = self.alignment / "alignment_station_comparison.csv"
        (self.alignment / "alignment_batch_summary.json").write_text(
            json.dumps({"version": "0.5.2", "status": "complete"}),
            encoding="utf-8",
        )
        (self.alignment / "batch_output_provenance.json").write_text(
            json.dumps(
                {
                    "generated_batch_outputs_sha256": {
                        station_path.name: sha256_file(station_path)
                    }
                }
            ),
            encoding="utf-8",
        )

    def _write_samples(self, scenario_directory: Path, sample_directory: Path) -> None:
        with np.load(scenario_directory / SCENARIO_FILENAME, allow_pickle=False) as scenario:
            residuals = np.zeros((20, 1, 4, 21), dtype=np.float64)
            for sample in range(20):
                residuals[sample, 0, :, :] = np.asarray([0.0, 0.2, -0.1, 0.3])[:, None]
            sample_directory.mkdir()
            np.savez_compressed(
                sample_directory / SAMPLES_FILENAME,
                residual_samples_m=residuals,
                lengths=scenario["lengths"],
                stations_m=scenario["stations_m"],
                sequence_ids=scenario["sequence_ids"],
                feature_names=scenario["feature_names"],
            )
        sample_path = sample_directory / SAMPLES_FILENAME
        (sample_directory / SAMPLE_SUMMARY_FILENAME).write_text(
            json.dumps(
                {
                    "version": "0.15.4",
                    "status": "complete",
                    "sample_file": SAMPLES_FILENAME,
                    "sample_file_sha256": sha256_file(sample_path),
                    "sampling_is_free_running": True,
                    "random_seed": 7,
                }
            ),
            encoding="utf-8",
        )

    def test_end_to_end_build_and_sensitivity(self) -> None:
        scenario_directory = self.root / "scenarios"
        self.assertEqual(
            scenario_main(
                [str(self.expanded), str(self.alignment), "--output-directory", str(scenario_directory)]
            ),
            0,
        )
        self.assertTrue((scenario_directory / CONDITION_FILENAME).is_file())
        sample_directory = self.root / "samples"
        self._write_samples(scenario_directory, sample_directory)
        output = self.root / "evaluation"
        arguments = [
            str(sample_directory), str(scenario_directory / SCENARIO_FILENAME),
            "--output-directory", str(output), "--shuffle-seed", "19",
        ]
        self.assertEqual(sensitivity_main(arguments), 0)
        self.assertTrue((output / FRAME_FILENAME).is_file())
        self.assertTrue((output / SEQUENCE_FILENAME).is_file())
        summary = json.loads((output / SUMMARY_OUTPUT_FILENAME).read_text(encoding="utf-8"))
        self.assertEqual(summary["arms_in_required_order"], list(ARM_NAMES))
        self.assertEqual(summary["sample_count"], 20)
        self.assertTrue(summary["temporal_propagation_used"])
        self.assertFalse(summary["global_pose_replay_used"])
        effect = summary["paired_comparisons"][
            "a2_frozen_ar_minus_a1_time_shuffled_ar"
        ]["integrated_abs_lateral_error_m_s"]["mean_difference"]
        self.assertNotEqual(effect, 0.0)
        second_output = self.root / "evaluation_again"
        arguments[3] = str(second_output)
        self.assertEqual(sensitivity_main(arguments), 0)
        self.assertEqual(
            sha256_file(output / SEQUENCE_FILENAME),
            sha256_file(second_output / SEQUENCE_FILENAME),
        )

    def test_shuffle_preserves_profiles_and_boundaries(self) -> None:
        values = np.arange(2 * 2 * 4 * 21, dtype=np.float64).reshape(2, 2, 4, 21)
        values[:, 1, 2:] = 0.0
        shuffled, changed = _time_shuffle(values, np.asarray([4, 2]), seed=5)
        self.assertGreater(changed, 0)
        for sample in range(2):
            for sequence, length in enumerate((4, 2)):
                before = sorted(map(tuple, values[sample, sequence, :length]))
                after = sorted(map(tuple, shuffled[sample, sequence, :length]))
                self.assertEqual(before, after)
        self.assertTrue(np.all(shuffled[:, 1, 2:] == 0.0))

    def test_fewer_than_twenty_draws_fail_closed(self) -> None:
        scenario_directory = self.root / "scenarios"
        scenario_main([str(self.expanded), str(self.alignment), "--output-directory", str(scenario_directory)])
        sample_directory = self.root / "samples"
        self._write_samples(scenario_directory, sample_directory)
        sample_path = sample_directory / SAMPLES_FILENAME
        with np.load(sample_path, allow_pickle=False) as archive:
            payload = {name: np.asarray(archive[name]) for name in archive.files}
        payload["residual_samples_m"] = payload["residual_samples_m"][:19]
        np.savez_compressed(sample_path, **payload)
        summary_path = sample_directory / SAMPLE_SUMMARY_FILENAME
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["sample_file_sha256"] = sha256_file(sample_path)
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        self.assertEqual(
            sensitivity_main([str(sample_directory), str(scenario_directory / SCENARIO_FILENAME)]),
            2,
        )


if __name__ == "__main__":
    unittest.main()
