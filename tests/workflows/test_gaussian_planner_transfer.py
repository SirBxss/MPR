import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from lane_residuals.domain.sequence_dataset import (
    BMW_CONDITION_FEATURE_NAMES,
    SequenceStandardizer,
)
from lane_residuals.io.expanded_modeling_dataset import load_expanded_modeling_dataset
from lane_residuals.modeling.aiohmm import AIOHMMConfig, AutoregressiveInputOutputHMM
from lane_residuals.workflows.development_residual_sampling import (
    run_development_residual_sampling,
)
from lane_residuals.workflows.gaussian_planner_transfer import (
    PRIMARY_METRICS,
    _comparison_summary,
    run_gaussian_planner_transfer,
)
from lane_residuals.workflows.gaussian_planner_transfer_contract import (
    GAUSSIAN_SAMPLE_FILENAME,
    GAUSSIAN_SAMPLE_SUMMARY_FILENAME,
    TRANSFER_FRAME_FILENAME,
    TRANSFER_SEQUENCE_FILENAME,
    TRANSFER_SUMMARY_FILENAME,
    GaussianPlannerTransferContract,
)
from lane_residuals.workflows.reference_planner_sensitivity import (
    FRAME_FILENAME,
    SUMMARY_OUTPUT_FILENAME,
    run_reference_planner_sensitivity,
)
from lane_residuals.workflows.sequence_contract import sha256_file
from lane_residuals.workflows.unconditional_gaussian_residual_sampling import (
    run_unconditional_gaussian_residual_sampling,
)
from lane_residuals.cli.expanded_gaussian import main as gaussian_main
from tests.io.test_expanded_modeling_dataset import write_v0131_fixture


class GaussianPlannerTransferWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.dataset = write_v0131_fixture(cls.root / "v0131")
        cls.gaussian = cls.root / "gaussian"
        if (
            gaussian_main(
                [
                    str(cls.dataset),
                    "--output-directory",
                    str(cls.gaussian),
                    "--sample-count",
                    "4",
                    "--seed",
                    "1400",
                ]
            )
            != 0
        ):
            raise AssertionError("Gaussian transfer fixture generation failed")
        cls.development_model = cls.root / "development_residual_model.json"
        cls._write_development_model()
        cls.scenario = cls.root / "reference_planner_scenarios.npz"
        cls.condition_archive = cls.root / "planner_condition_sequences.npz"
        cls.lengths = np.asarray([3, 20, 22], dtype=np.int64)
        cls.sequence_ids = np.asarray(
            ["sequence_short", "sequence_twenty", "sequence_long"], dtype=np.str_
        )
        cls._write_scenario()
        cls.a2_samples = cls.root / "a2_samples"
        run_development_residual_sampling(
            model_path=cls.development_model,
            condition_archive=cls.condition_archive,
            output_directory=cls.a2_samples,
            sample_count=20,
            seed=7,
        )
        cls.v016 = cls.root / "v016"
        v016_summary, _ = run_reference_planner_sensitivity(
            residual_sample_directory=cls.a2_samples,
            scenario_archive=cls.scenario,
            output_directory=cls.v016,
            shuffle_seed=19,
        )
        with np.load(cls.v016 / FRAME_FILENAME, allow_pickle=False) as archive:
            frame_metrics = np.asarray(archive["frame_metrics"], dtype=np.float64)
        a0_sequence = np.zeros((20, 3), dtype=np.float64)
        for sample in range(20):
            for sequence, length in enumerate(cls.lengths):
                a0_sequence[sample, sequence] = np.mean(
                    frame_metrics[0, sample, sequence, : int(length), 7]
                )
        cls.contract = GaussianPlannerTransferContract(
            development_model_sha256=sha256_file(cls.development_model),
            scenario_sha256=sha256_file(cls.scenario),
            a2_sample_sha256=sha256_file(
                cls.a2_samples / "sampled_residual_sequences.npz"
            ),
            v016_frame_sha256=sha256_file(cls.v016 / FRAME_FILENAME),
            v016_sequence_sha256=sha256_file(
                cls.v016 / "reference_planner_sequence_metrics.csv"
            ),
            v016_summary_sha256=sha256_file(cls.v016 / SUMMARY_OUTPUT_FILENAME),
            sample_count=20,
            sequence_count=3,
            active_frame_count=45,
            a2_sampling_seed=7,
            shuffle_seed=19,
            shuffled_frame_positions_changed=v016_summary[
                "shuffled_frame_positions_changed"
            ],
            gaussian_sampling_seed=23,
            bootstrap_seed=29,
            bootstrap_replicates=200,
            p95_minimum_active_frames=20,
            a0_macro_constraint_violation_fraction_rounded_6=round(
                float(np.mean(a0_sequence)), 6
            ),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @classmethod
    def _write_development_model(cls) -> None:
        source = load_expanded_modeling_dataset(cls.dataset)
        standardizer = SequenceStandardizer.fit(
            source.sequences, train_drive_ids=source.clean_drive_ids
        )
        standardized = standardizer.standardized_copy(source.sequences)
        training = standardized.select_drive_ids(source.clean_drive_ids)
        model = AutoregressiveInputOutputHMM(
            AIOHMMConfig(
                state_count=1,
                maximum_em_iterations=2,
                minimum_em_iterations=2,
                convergence_tolerance=1e9,
                minimum_effective_state_observations=2.0,
                maximum_absolute_autoregression=0.99,
                transition_adam_steps=1,
                minimum_state_occupancy_fraction=0.001,
                input_dependent_transitions=False,
            )
        )
        model.fit(training)
        payload = {
            "schema_version": "0.15.4",
            "status": "complete",
            "purpose": "development_residual_model_for_planner_experiments",
            "model_family": "one_state_conditional_autoregressive_gaussian",
            "selection_basis": (
                "smallest_tested_nonbinding_ceiling_above_the_identical_interior_optimum"
            ),
            "development_planner_model_frozen": True,
            "final_model_selection_authorized": False,
            "journey_level_generalization_estimated": False,
            "selected_after_held_out_performance_evaluation": False,
            "strict_v0153_performance_gate_passed": False,
            "higher_ceiling_fits_identical_except_configured_ceiling": True,
            "selected_ar_ceiling": 0.99,
            "standardizer": standardizer.to_dict(),
            "model": model.to_dict(),
        }
        cls.development_model.write_text(
            json.dumps(payload, sort_keys=True), encoding="utf-8"
        )

    @classmethod
    def _write_scenario(cls) -> None:
        maximum_time = int(np.max(cls.lengths))
        conditions = np.zeros((3, maximum_time, 6), dtype=np.float64)
        paths = np.zeros((3, maximum_time, 21, 2), dtype=np.float64)
        timestamps = np.zeros((3, maximum_time), dtype=np.int64)
        stations = np.arange(0.0, 101.0, 5.0)
        for sequence, length in enumerate(cls.lengths):
            active = int(length)
            conditions[sequence, :active, 0] = 8.0 + sequence
            conditions[sequence, :active, 1:] = 0.01 * (sequence + 1)
            timestamps[sequence, :active] = (
                1_000_000_000 * (sequence + 1)
                + np.arange(active, dtype=np.int64) * 80_000_000
            )
            paths[sequence, :active, :, 0] = stations
            paths[sequence, :active, :, 1] = (
                0.0002 * stations**2 + 0.001 * sequence
            )
        np.savez_compressed(
            cls.scenario,
            conditions=conditions,
            feature_names=np.asarray(BMW_CONDITION_FEATURE_NAMES, dtype=np.str_),
            lengths=cls.lengths,
            nominal_paths_xy_m=paths,
            sequence_ids=cls.sequence_ids,
            stations_m=stations,
            timestamps_ns=timestamps,
        )
        np.savez_compressed(
            cls.condition_archive,
            conditions=conditions,
            lengths=cls.lengths,
            sequence_ids=cls.sequence_ids,
            feature_names=np.asarray(BMW_CONDITION_FEATURE_NAMES, dtype=np.str_),
        )

    def _sample_a3(self, output: Path) -> dict[str, object]:
        summary, status = run_unconditional_gaussian_residual_sampling(
            dataset_directory=self.dataset,
            gaussian_directory=self.gaussian,
            development_model_path=self.development_model,
            accepted_a2_sample_directory=self.a2_samples,
            scenario_archive=self.scenario,
            output_directory=output,
            contract=self.contract,
        )
        self.assertEqual(status, 0)
        return summary

    def test_complete_sampling_and_transfer_are_deterministic(self) -> None:
        first_samples = self.root / "a3_samples_first"
        sample_summary = self._sample_a3(first_samples)
        self.assertTrue(
            sample_summary["standardizer_equality_audit"]["elementwise_exact_equal"]
        )
        self.assertEqual(len(sample_summary["marginal_diagnostics_by_station"]), 21)
        self.assertFalse(sample_summary["planner_executed"])
        with np.load(
            first_samples / GAUSSIAN_SAMPLE_FILENAME, allow_pickle=False
        ) as archive:
            samples = np.asarray(archive["residual_samples_m"])
            self.assertEqual(samples.shape, (20, 3, 22, 21))
            self.assertTrue(np.all(samples[:, 0, 3:] == 0.0))
            self.assertTrue(np.all(samples[:, 1, 20:] == 0.0))

        second_samples = self.root / "a3_samples_second"
        self._sample_a3(second_samples)
        with np.load(
            second_samples / GAUSSIAN_SAMPLE_FILENAME, allow_pickle=False
        ) as second:
            np.testing.assert_array_equal(samples, second["residual_samples_m"])

        output = self.root / "transfer"
        transfer_summary, status = run_gaussian_planner_transfer(
            gaussian_sample_directory=first_samples,
            scenario_archive=self.scenario,
            accepted_v016_sensitivity_directory=self.v016,
            output_directory=output,
            contract=self.contract,
        )
        self.assertEqual(status, 0)
        self.assertEqual(
            {path.name for path in output.iterdir()},
            {
                TRANSFER_FRAME_FILENAME,
                TRANSFER_SEQUENCE_FILENAME,
                TRANSFER_SUMMARY_FILENAME,
            },
        )
        self.assertFalse(transfer_summary["a0_rerun"])
        self.assertFalse(transfer_summary["a1_a2_rerun"])
        self.assertEqual(
            transfer_summary["p95_short_sequences_excluded_from_primary"],
            [{"sequence_id": "sequence_short", "active_frame_count": 3}],
        )
        self.assertEqual(
            set(transfer_summary["primary_a3_minus_a2_comparisons"]),
            set(PRIMARY_METRICS),
        )
        for name, comparison in transfer_summary[
            "primary_a3_minus_a2_comparisons"
        ].items():
            self.assertEqual(len(comparison[
                "independent_two_sample_bootstrap_interval_2_5_97_5_percent"
            ]), 2)
            expected_n = 2 if name.startswith("p95_") else 3
            self.assertEqual(
                comparison["hypothesised_sign_sequence_agreement"]["N"],
                expected_n,
            )
        self.assertIn(
            transfer_summary["overall_decision"],
            {
                "full support",
                "partial support: smoothness family only",
                "partial support: deviation family only",
                "unsupported",
            },
        )
        qualifier = transfer_summary[
            "deviation_family_length_dependence_qualifier"
        ]
        self.assertEqual(
            qualifier["role"],
            "mandatory_post_result_interpretation_not_a_decision_gate",
        )
        self.assertFalse(qualifier["changes_predeclared_decision"])
        length_by_id = dict(zip(self.sequence_ids.tolist(), self.lengths.tolist()))
        reversal_sets = []
        for name in PRIMARY_METRICS[2:]:
            values = qualifier["deviation_metrics"][name]
            reversing_ids = values["reversing_sequence_ids"]
            reversal_sets.append(set(reversing_ids))
            self.assertEqual(values["sequence_count"], 3)
            self.assertEqual(values["reversing_sequence_count"], len(reversing_ids))
            expected_frames = sum(length_by_id[value] for value in reversing_ids)
            self.assertEqual(values["reversing_active_frame_count"], expected_frames)
            self.assertEqual(values["active_frame_count"], 45)
            self.assertEqual(
                values["reversing_active_frame_fraction"], expected_frames / 45
            )
            expected_ranks = sorted(
                ["sequence_long", "sequence_twenty", "sequence_short"].index(value)
                + 1
                for value in reversing_ids
            )
            self.assertEqual(
                values["reversing_sequence_length_ranks_longest_first"],
                expected_ranks,
            )
            self.assertEqual(
                values["longest_prefix_containing_all_reversing_sequences"],
                max(expected_ranks, default=0),
            )
            self.assertEqual(
                values["reversing_sequence_count_among_two_longest"],
                sum(
                    value in {"sequence_long", "sequence_twenty"}
                    for value in reversing_ids
                ),
            )
            comparison = transfer_summary["primary_a3_minus_a2_comparisons"][name]
            self.assertEqual(
                values["equal_sequence_macro_a3_minus_a2"],
                comparison["a3_minus_a2_mean_difference"],
            )
            self.assertEqual(
                values["equal_sequence_macro_a3_minus_a2_percent_of_a2"],
                100.0
                * comparison["a3_minus_a2_mean_difference"]
                / comparison["a2_macro_mean"],
            )
        self.assertEqual(
            qualifier["reversing_sequence_sets_identical"],
            reversal_sets[0] == reversal_sets[1],
        )
        pooled = qualifier["pooled_frame_mean_abs_lateral_error_m"]
        expected_a3 = transfer_summary["pooled_frame_summaries"][
            "unconditional_gaussian"
        ]["mean_abs_lateral_error_m"]
        expected_a2 = transfer_summary["pooled_frame_summaries"]["frozen_ar"][
            "mean_abs_lateral_error_m"
        ]
        self.assertEqual(pooled["a3"], expected_a3)
        self.assertEqual(pooled["a2"], expected_a2)
        self.assertEqual(pooled["a3_minus_a2"], expected_a3 - expected_a2)
        for name in PRIMARY_METRICS[:2]:
            agreement = transfer_summary["primary_a3_minus_a2_comparisons"][name][
                "hypothesised_sign_sequence_agreement"
            ]
            self.assertEqual(
                qualifier["smoothness_hypothesised_sign_sequence_agreement"][name],
                {"k": agreement["k"], "N": agreement["N"]},
            )
        self.assertEqual(
            qualifier["smoothness_agreement_is_unanimous"],
            all(
                value["k"] == value["N"]
                for value in qualifier[
                    "smoothness_hypothesised_sign_sequence_agreement"
                ].values()
            ),
        )
        with np.load(output / TRANSFER_FRAME_FILENAME, allow_pickle=False) as archive:
            self.assertEqual(archive["frame_metrics"].shape, (20, 3, 22, 8))
            self.assertTrue(np.all(archive["frame_metrics"][:, 0, 3:] == 0.0))

    def test_standardizer_mismatch_fails_before_output(self) -> None:
        changed_model = self.root / "changed_development_model.json"
        payload = json.loads(self.development_model.read_text(encoding="utf-8"))
        payload["standardizer"]["residual_scale_m"][0] += 1e-12
        changed_model.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        changed_contract = replace(
            self.contract,
            development_model_sha256=sha256_file(changed_model),
        )
        changed_a2 = self.root / "changed_model_a2_samples"
        shutil.copytree(self.a2_samples, changed_a2)
        a2_summary_path = changed_a2 / "sampled_residual_sequences_summary.json"
        a2_summary = json.loads(a2_summary_path.read_text(encoding="utf-8"))
        a2_summary["development_model_file_sha256"] = sha256_file(changed_model)
        a2_summary_path.write_text(json.dumps(a2_summary), encoding="utf-8")
        output = self.root / "standardizer_mismatch"
        with self.assertRaisesRegex(ValueError, "residual_scale_m values differ"):
            run_unconditional_gaussian_residual_sampling(
                dataset_directory=self.dataset,
                gaussian_directory=self.gaussian,
                development_model_path=changed_model,
                accepted_a2_sample_directory=changed_a2,
                scenario_archive=self.scenario,
                output_directory=output,
                contract=changed_contract,
            )
        self.assertFalse(output.exists())

    def test_accepted_v016_hash_mismatch_fails_before_output(self) -> None:
        samples = self.root / "a3_samples_for_hash_failure"
        self._sample_a3(samples)
        changed_contract = replace(self.contract, v016_frame_sha256="0" * 64)
        output = self.root / "hash_mismatch"
        with self.assertRaisesRegex(ValueError, "accepted hashes"):
            run_gaussian_planner_transfer(
                gaussian_sample_directory=samples,
                scenario_archive=self.scenario,
                accepted_v016_sensitivity_directory=self.v016,
                output_directory=output,
                contract=changed_contract,
            )
        self.assertFalse(output.exists())

    def test_sampling_summary_tamper_fails_before_planner_output(self) -> None:
        samples = self.root / "a3_samples_for_summary_failure"
        self._sample_a3(samples)
        summary_path = samples / GAUSSIAN_SAMPLE_SUMMARY_FILENAME
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        payload["common_random_numbers_with_a1_a2_used"] = True
        summary_path.write_text(json.dumps(payload), encoding="utf-8")
        output = self.root / "summary_mismatch"
        with self.assertRaisesRegex(ValueError, "sampling summary differs"):
            run_gaussian_planner_transfer(
                gaussian_sample_directory=samples,
                scenario_archive=self.scenario,
                accepted_v016_sensitivity_directory=self.v016,
                output_directory=output,
                contract=self.contract,
            )
        self.assertFalse(output.exists())

    def test_directional_rule_and_sequence_agreement_are_exact(self) -> None:
        contract = replace(
            self.contract,
            sample_count=4,
            bootstrap_replicates=50,
        )
        a3_macro = {
            PRIMARY_METRICS[0]: np.full(4, 2.0),
            PRIMARY_METRICS[1]: np.full(4, 3.0),
            PRIMARY_METRICS[2]: np.full(4, 1.0),
            PRIMARY_METRICS[3]: np.full(4, 1.5),
        }
        a2_macro = {
            PRIMARY_METRICS[0]: np.full(4, 1.0),
            PRIMARY_METRICS[1]: np.full(4, 1.0),
            PRIMARY_METRICS[2]: np.full(4, 2.0),
            PRIMARY_METRICS[3]: np.full(4, 2.5),
        }
        a3_sequence = {
            name: np.repeat(values[:, None], 3, axis=1)
            for name, values in a3_macro.items()
        }
        a2_sequence = {
            name: np.repeat(values[:, None], 3, axis=1)
            for name, values in a2_macro.items()
        }
        comparisons, family_pass, decision = _comparison_summary(
            a3_macro=a3_macro,
            a2_macro=a2_macro,
            a3_sequence=a3_sequence,
            a2_sequence=a2_sequence,
            lengths=self.lengths,
            sequence_ids=self.sequence_ids,
            contract=contract,
        )
        self.assertEqual(family_pass, {"smoothness": True, "deviation": True})
        self.assertEqual(decision, "full support")
        for name, comparison in comparisons.items():
            expected_n = 2 if name.startswith("p95_") else 3
            self.assertEqual(
                comparison["hypothesised_sign_sequence_agreement"],
                {
                    "k": expected_n,
                    "N": expected_n,
                    "sequence_ids": (
                        ["sequence_twenty", "sequence_long"]
                        if expected_n == 2
                        else self.sequence_ids.tolist()
                    ),
                    "is_hypothesis_test": False,
                    "changes_pass_fail_rule": False,
                },
            )


if __name__ == "__main__":
    unittest.main()
