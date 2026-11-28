"""Synthetic pinned artifacts exercise all three pilot stages without MCAP."""

import hashlib
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.domain import a2_budget_pilot as policy, numeric_export as numeric
from lane_residuals.domain import artifact_registry as registry_policy
from lane_residuals.domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from lane_residuals.domain.spatial_planner_response import STATIONS_M
from lane_residuals.io import a2_budget_pilot as reader, artifact_registry as registry, development_experiment as original
from lane_residuals.workflows import a2_budget_pilot as workflow
from lane_residuals.workflows.locked_development_export import write


class PilotFixture:
    def __init__(self, project):
        self.rng = np.random.default_rng(9851)
        self.project = project
        self.experiment = project / "accepted-experiment"
        self.checkpoint = project / "registry-checkpoint"
        self.experiment.mkdir()
        (self.checkpoint / "objects").mkdir(parents=True)
        self.outings = [f"outing_{i}" for i in range(7)]
        self.archives, self.rows, self.events, self.objects = [], [], [], set()
        self.numeric_paths = {}
        for i in range(7):
            self.make_outing(i)
        mark = self.checkpoint / "registry.json"
        write(mark, {"contract_revision": registry_policy.REVISION, "events": self.events,
                     "objects_sha256": sorted(self.objects)})
        pin = original.sha(mark)
        request = {field: "unused" for field in original.REQUEST_FIELDS}
        request.update(contract_revision=original.REVISION, expected_cohort_sha256="3" * 64,
                       expected_original_registry_sha256=pin, expected_export_receipt_sha256="4" * 64,
                       original_registry_directory=str(self.checkpoint), descendants=[],
                       archive_sha256=sorted(entry["archive_sha256"] for entry in self.archives))
        write(self.experiment / "request.json", request)
        write(self.experiment / "row_manifest.json", self.rows)
        write(self.experiment / "experiment.json", {
            "contract_revision": original.REVISION, "status": "complete_matched_development_experiment",
            "protocol": original.PROTOCOL, "final_evaluation_authorized": False,
            "request_sha256": original.sha(self.experiment / "request.json"),
            "row_manifest_sha256": original.sha(self.experiment / "row_manifest.json"),
            "latest_registry_sha256": pin, "archives": self.archives,
            "folds": [{"fold_id": f"hold_out_{held}", "validation_outing": held,
                       "training_outings": [oid for oid in self.outings if oid != held]} for held in self.outings],
        })

    def object(self, raw, *, payload=True):
        digest = hashlib.sha256(raw).hexdigest()
        path = self.checkpoint / "objects" / digest
        if payload and not path.exists():
            path.write_bytes(raw)
        self.objects.add(digest)
        return digest, path

    def sequence_lengths(self, number):
        return (6,) * 14

    def make_outing(self, number):
        outing = self.outings[number]
        lengths = self.sequence_lengths(number)
        offsets = np.cumsum((0, *lengths))
        starts = set(offsets[:-1].tolist())
        repeats, count = len(lengths), int(offsets[-1])
        x = self.rng.normal(size=(count, 6))
        x[:, 0] = 19. + np.tanh(x[:, 0])
        times = 5_000_000_000 + 100_000_000 * np.arange(count) + 400_000_000 * np.repeat(np.arange(repeats), lengths)
        residuals = self.rng.normal(0, .06, size=(count, 21))
        for index in range(count):
            if index not in starts:
                residuals[index] += .67 * residuals[index - 1]
        arrays = {
            "stations_m": STATIONS_M, "condition_names": BMW_CONDITION_FEATURE_NAMES,
            "residuals_m": residuals, "conditions": x, "conditioned_profile_indices": np.arange(count),
            "conditioned_sequence_offsets": offsets,
            "geometry_sequence_offsets": offsets,
            "recording_id": np.full(count, f"recording_{number}"),
            "estimate_source_time_ns_decimal": times.astype(str), "reference_source_time_ns_decimal": times.astype(str),
        }
        for field in reader.IDENTITIES:
            arrays.setdefault(field, np.arange(count))
        arrays = {name: np.asarray(values, dtype=numeric.ARRAY_DTYPES[name]) for name, values in arrays.items()}
        b = BytesIO()
        np.savez_compressed(b, **arrays)
        # The original outer held NPZ is absent. A forbidden read fails the test.
        numeric_pin, path = self.object(b.getvalue(), payload=number != 0)
        self.numeric_paths[outing] = path
        archive_pin, _ = self.object(original.encoded({
            "status": "complete", "artifacts_sha256": {numeric.ARCHIVE: numeric_pin},
        }))
        files = dict.fromkeys(registry.ARCHIVE_FILES, "1" * 64)
        files.update({"numeric/numeric_export.json": archive_pin, "numeric/residuals.npz": numeric_pin})
        self.events.append({"kind": "archive", "files": files})
        self.archives.append({"outing_id": outing, "archive_sha256": archive_pin, "complete_feature_rows": count,
                              "geometry_vectors": count, "sequences": repeats})
        self.rows.append({
            "outing_id": outing, "archive_sha256": archive_pin,
            **{field: arrays[field].tolist() for field in (*reader.IDENTITIES, "conditioned_profile_indices",
                                                           "conditioned_sequence_offsets")},
        })

    def arguments(self, output):
        return {
            "source": self.project, "project": self.project, "experiment": self.experiment, "output": output,
            "expected_tree": "2" * 40, "expected_runtime": "3" * 64,
            "experiment_sha256": original.sha(self.experiment / "experiment.json"),
            "archive_set_sha256": reader.value_sha256([
                {name: item[name] for name in ("outing_id", "archive_sha256")} for item in self.archives
            ]),
        }


class A2BudgetPilotTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        project = root / "project"
        project.mkdir()
        self.output = root / "output"
        self.fixture = PilotFixture(project)
        self.args = self.fixture.arguments(self.output)
        patcher = patch.object(workflow, "source_guard", return_value={"fixture_source": True})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_native_three_stage_pilot_keeps_the_outer_and_inner_boundaries(self):
        with (
            patch.object(reader, "_read_member", wraps=reader._read_member) as members,
            patch.object(reader, "open_accepted_outing", wraps=reader.open_accepted_outing) as opened,
        ):
            report = workflow.preflight(**self.args)
            self.assertEqual(report["status"], workflow.READY)
            self.assertEqual(report["roles"]["outer_held_outing"], "outing_0")
            self.assertEqual(report["roles"]["inner_audit_outing"], "outing_6")
            self.assertFalse(any(call.args[1] == "residuals_m" for call in members.call_args_list))
            self.assertEqual({call.args[0].outing_id for call in opened.call_args_list},
                             set(self.fixture.outings[1:6]))

        seen_fits = []
        native_fit = workflow.fit_one_state_ar

        def record_fit(base, blocks):
            seen_fits.append([block.outing_id for block in blocks])
            self.assertEqual(base.training_rows, sum(len(block.y) for block in blocks))
            return native_fit(base, blocks)

        with (
            patch.object(workflow, "fit_one_state_ar", side_effect=record_fit),
            patch.object(reader, "open_accepted_outing", wraps=reader.open_accepted_outing) as opened,
        ):
            frozen = workflow.select(preflight_sha256=original.sha(self.output / workflow.PREFLIGHT), **self.args)
            self.assertEqual(frozen["status"], workflow.FROZEN, frozen["failed_ar_budgets"])
            self.assertEqual(seen_fits, [self.fixture.outings[1:b + 1] for b in policy.BUDGETS])
            opened_labels = [call.args[0].outing_id for call in opened.call_args_list if call.kwargs["labels"]]
            self.assertEqual(opened_labels, self.fixture.outings[1:6])
            self.assertTrue(all(len(arms) == 2 for arms in frozen["choices"].values()))

        pin = original.sha(self.output / workflow.CHOICES)
        with patch.object(reader, "open_accepted_outing") as unopened:
            with self.assertRaisesRegex(registry_policy.RegistryError, "experiment_input_digest_mismatch"):
                workflow.audit(choices_sha256="a" * 64, **self.args)
            unopened.assert_not_called()
        with patch.object(reader, "open_accepted_outing", wraps=reader.open_accepted_outing) as opened:
            audit = workflow.audit(choices_sha256=pin, **self.args)
            self.assertEqual(audit["status"], workflow.COMPLETE)
            self.assertEqual([call.args[0].outing_id for call in opened.call_args_list], ["outing_6"] * 2)
            self.assertEqual([call.kwargs["labels"] for call in opened.call_args_list], [False, True])
        self.assertEqual(audit["audit_sequences"], 12)
        self.assertEqual(audit["comparisons"]["5"]["methods"]["empirical"]["loss_minus_full_empirical"], 0.0)
        with self.assertRaises(FileExistsError):
            workflow.audit(choices_sha256=pin, **self.args)

    def test_failed_budget_preserves_all_other_selection_panels(self):
        self.assertEqual(workflow.preflight(**self.args)["status"], workflow.READY)

        def mocked_fit(blocks, conditions, _offsets, _state_path):
            if len(blocks) == 1:
                return None, {"native_converged": False}
            return np.zeros((policy.DRAWS, len(conditions), 21)), {"native_converged": True}

        with patch.object(workflow, "_fit_panel", side_effect=mocked_fit) as fit:
            result = workflow.select(preflight_sha256=original.sha(self.output / workflow.PREFLIGHT), **self.args)
        self.assertEqual(fit.call_count, 3)
        self.assertEqual(result["status"], "a2_budget_selection_incomplete")
        self.assertEqual(result["failed_ar_budgets"], [1])
        self.assertTrue(all(result["choices"][str(b)]["empirical"]["status"] == "selected" for b in policy.BUDGETS))
        with patch.object(reader, "open_accepted_outing") as unopened:
            with self.assertRaisesRegex(registry_policy.RegistryError, "budget_complete_frozen_choices_required"):
                workflow.audit(choices_sha256=original.sha(self.output / workflow.CHOICES), **self.args)
            unopened.assert_not_called()

    def test_mismatched_archive_set_and_choices_cannot_open_numeric_payload(self):
        with patch.object(reader, "open_accepted_outing") as open_blob:
            with self.assertRaisesRegex(registry_policy.RegistryError, "budget_accepted_archive_set_mismatch"):
                workflow.preflight(**{**self.args, "archive_set_sha256": "0" * 64})
            self.output.mkdir()
            write(self.output / workflow.CHOICES, {"revision": policy.REVISION, "status": "a2_budget_selection_incomplete"})
            with self.assertRaisesRegex(registry_policy.RegistryError, "budget_complete_frozen_choices_required"):
                workflow.audit(choices_sha256=original.sha(self.output / workflow.CHOICES), **self.args)
            open_blob.assert_not_called()

    def test_nominal_stop_has_no_fits_and_no_audit(self):
        with patch.object(policy.a2, "feasible_candidates", return_value=(np.zeros(9, dtype=bool), {})):
            report = workflow.preflight(**self.args)
        self.assertEqual(report["status"], "a2_budget_preflight_stopped")
        self.assertIn("fewer_than_two_a2_nominal_candidates", report["design"]["reasons"])
        with patch.object(workflow, "fit_one_state_ar") as fit:
            with self.assertRaisesRegex(registry_policy.RegistryError, "budget_ready_preflight_required"):
                workflow.select(preflight_sha256=original.sha(self.output / workflow.PREFLIGHT), **self.args)
            fit.assert_not_called()

    def test_donor_windows_preserve_reset_and_match_every_interval(self):
        target = policy.Sequence("target", 0, 0, 3, (100_000_000, 100_000_000))
        donors = [
            policy.Sequence("donor", 0, 0, 4, (125_000_000, 100_000_000, 119_000_000)),
            policy.Sequence("donor", 1, 4, 6, (100_000_000,)),
            policy.Sequence("donor", 2, 6, 8, (100_000_000,)),
        ]
        self.assertEqual(policy.donor_windows(target, donors), [(1,)])
