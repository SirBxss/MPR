import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.cli.development_model_freeze import main as freeze_main
from lane_residuals.cli.development_residual_sampling import main as sample_main
from lane_residuals.cli.expanded_aiohmm import main as aiohmm_main
from lane_residuals.cli.expanded_aiohmm_convergence import (
    main as convergence_main,
)
from lane_residuals.cli.expanded_ar_ablation import main as ar_ablation_main
from lane_residuals.cli.expanded_ar_boundary import main as ar_boundary_main
from lane_residuals.cli.expanded_gaussian import main as gaussian_main
from lane_residuals.domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from lane_residuals.io.expanded_sequence_dataset import sha256_file
from lane_residuals.modeling.development_residual import DevelopmentResidualModel
from tests.io.test_expanded_modeling_dataset import write_v0131_fixture


class DevelopmentModelFreezeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls._temporary.name)
        cls.source = write_v0131_fixture(cls.root / "v0131")
        cls.gaussian = cls.root / "gaussian"
        cls.aiohmm = cls.root / "aiohmm"
        cls.one_state = cls.root / "one_state"
        cls.convergence = cls.root / "convergence"
        cls.boundary = cls.root / "boundary"
        model_arguments = [
            "--restart-count",
            "1",
            "--maximum-em-iterations",
            "3",
            "--minimum-em-iterations",
            "2",
            "--transition-adam-steps",
            "2",
            "--minimum-effective-state-observations",
            "2",
            "--minimum-state-occupancy-fraction",
            "0.001",
            "--sample-count",
            "8",
            "--seed",
            "1400",
            "--log-level",
            "ERROR",
        ]
        commands = (
            (
                gaussian_main,
                [
                    str(cls.source),
                    "--output-directory",
                    str(cls.gaussian),
                    "--sample-count",
                    "8",
                    "--seed",
                    "1400",
                ],
            ),
            (
                aiohmm_main,
                [
                    str(cls.source),
                    "--gaussian-directory",
                    str(cls.gaussian),
                    "--output-directory",
                    str(cls.aiohmm),
                    *model_arguments,
                ],
            ),
            (
                ar_ablation_main,
                [
                    str(cls.source),
                    "--gaussian-directory",
                    str(cls.gaussian),
                    "--aiohmm-directory",
                    str(cls.aiohmm),
                    "--output-directory",
                    str(cls.one_state),
                    *model_arguments,
                ],
            ),
            (
                convergence_main,
                [
                    str(cls.source),
                    "--gaussian-directory",
                    str(cls.gaussian),
                    "--aiohmm-directory",
                    str(cls.aiohmm),
                    "--one-state-ar-directory",
                    str(cls.one_state),
                    "--output-directory",
                    str(cls.convergence),
                    *model_arguments,
                ],
            ),
            (
                ar_boundary_main,
                [
                    str(cls.source),
                    "--gaussian-directory",
                    str(cls.gaussian),
                    "--aiohmm-directory",
                    str(cls.aiohmm),
                    "--one-state-ar-directory",
                    str(cls.one_state),
                    "--two-state-convergence-directory",
                    str(cls.convergence),
                    "--output-directory",
                    str(cls.boundary),
                    *model_arguments,
                ],
            ),
        )
        for command, arguments in commands:
            if command(arguments) != 0:
                raise AssertionError("development-freeze fixture generation failed")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_freeze_and_sample_are_strict_deterministic_and_physical(self) -> None:
        frozen = self.root / "frozen"
        status = freeze_main(
            [
                str(self.boundary),
                "--one-state-ar-directory",
                str(self.one_state),
                "--output-directory",
                str(frozen),
                "--log-level",
                "ERROR",
            ]
        )
        self.assertEqual(status, 0)
        self.assertEqual(
            {path.name for path in frozen.iterdir()},
            {
                "development_residual_model.json",
                "development_model_freeze_summary.json",
            },
        )
        summary = json.loads(
            (frozen / "development_model_freeze_summary.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(summary["version"], "0.15.4")
        self.assertEqual(summary["selected_ar_ceiling"], 0.99)
        self.assertFalse(summary["performance_selected"])
        self.assertFalse(summary["strict_v0153_performance_gate_passed"])
        self.assertTrue(summary["development_planner_model_frozen"])
        self.assertFalse(summary["final_model_selection_authorized"])
        model_path = frozen / "development_residual_model.json"
        self.assertEqual(summary["selected_model_sha256"], sha256_file(model_path))

        model = DevelopmentResidualModel.load(model_path)
        conditions = np.zeros((2, 4, len(BMW_CONDITION_FEATURE_NAMES)))
        conditions[0, :4, 0] = [4.0, 4.2, 4.4, 4.6]
        conditions[1, :2, 0] = [6.0, 6.1]
        lengths = np.asarray([4, 2], dtype=np.int64)
        first = model.sample(conditions, lengths, sample_count=5, seed=77)
        second = model.sample(conditions, lengths, sample_count=5, seed=77)
        np.testing.assert_array_equal(first.values, second.values)
        self.assertFalse(first.standardized)
        self.assertEqual(first.values.shape, (5, 2, 4, 21))
        np.testing.assert_array_equal(first.values[:, 1, 2:], 0.0)

        condition_path = self.root / "planner_conditions.npz"
        np.savez_compressed(
            condition_path,
            conditions=conditions,
            lengths=lengths,
            sequence_ids=np.asarray(["scenario_a", "scenario_b"]),
            feature_names=np.asarray(BMW_CONDITION_FEATURE_NAMES),
        )
        sampled = self.root / "sampled"
        self.assertEqual(
            sample_main(
                [
                    str(model_path),
                    str(condition_path),
                    "--output-directory",
                    str(sampled),
                    "--sample-count",
                    "5",
                    "--seed",
                    "77",
                    "--log-level",
                    "ERROR",
                ]
            ),
            0,
        )
        sample_summary = json.loads(
            (sampled / "sampled_residual_sequences_summary.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(sample_summary["sampling_is_free_running"])
        self.assertFalse(sample_summary["independent_frame_sampling_used"])
        self.assertFalse(sample_summary["planner_executed"])
        with np.load(sampled / "sampled_residual_sequences.npz") as archive:
            self.assertEqual(
                set(archive.files),
                {
                    "residual_samples_m",
                    "lengths",
                    "stations_m",
                    "sequence_ids",
                    "feature_names",
                },
            )
            np.testing.assert_array_equal(archive["residual_samples_m"], first.values)

        invalid_conditions = self.root / "planner_conditions_float_lengths.npz"
        np.savez_compressed(
            invalid_conditions,
            conditions=conditions,
            lengths=lengths.astype(np.float64),
            sequence_ids=np.asarray(["scenario_a", "scenario_b"]),
            feature_names=np.asarray(BMW_CONDITION_FEATURE_NAMES),
        )
        invalid_output = self.root / "invalid_sampled"
        self.assertEqual(
            sample_main(
                [
                    str(model_path),
                    str(invalid_conditions),
                    "--output-directory",
                    str(invalid_output),
                    "--log-level",
                    "ERROR",
                ]
            ),
            2,
        )
        self.assertFalse(invalid_output.exists())

    def test_tampered_v0153_candidate_fails_before_output(self) -> None:
        tampered = self.root / "tampered_boundary"
        shutil.copytree(self.boundary, tampered)
        with (
            tampered
            / "candidates"
            / "one_state_ar_cap_0_990"
            / "one_state_ar_model.json"
        ).open("a", encoding="utf-8") as handle:
            handle.write(" ")
        output = self.root / "tampered_output"
        status = freeze_main(
            [
                str(tampered),
                "--one-state-ar-directory",
                str(self.one_state),
                "--output-directory",
                str(output),
                "--log-level",
                "ERROR",
            ]
        )
        self.assertEqual(status, 2)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
