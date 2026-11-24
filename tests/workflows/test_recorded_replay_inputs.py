"""Exercise the native indexed replay using a synthetic numeric export."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.domain.artifact_registry import RegistryError
from lane_residuals.domain.geometry_validation import GeometryValidationError
from lane_residuals.domain.motion import Pose2D
from lane_residuals.domain.recording_ingestion import RecordingIngestionError
from lane_residuals.domain import numeric_export as policy
from lane_residuals.io import recorded_replay_inputs as replay
from lane_residuals.io.development_experiment import sha
from lane_residuals.workflows import recorded_replay_inputs as workflow
from lane_residuals.workflows.locked_development_export import write
from tests.io import bounded_readiness_fixture as synthetic
from tests.workflows import test_numeric_export as numeric_fixture


def add_qualifier(_paths, odometry):
    enum = odometry.enum_type.add(name="FixtureAvailability")
    for name, number in (("AVAILABLE", 0), ("REDUCED", 1), ("ABSENT", 2)):
        enum.value.add(name=name, number=number)
    odometry.message_type[0].field.add(
        name="fixture_availability", number=9, type=14, label=1, type_name=".Adp.FixtureAvailability",
    )


class RecordedReplayInputsTests(unittest.TestCase):
    def setUp(self):
        self.prepare_recording(qualifier_bytes=b"\x48\x00")

    def prepare_recording(self, qualifier_bytes):
        producer = numeric_fixture.NumericExportTests()
        producer.setUp()
        self.addCleanup(producer.doCleanups)
        producer.prepare(mutate=add_qualifier,
                         odometry_payload=lambda state: state.SerializeToString() + qualifier_bytes)
        summary = producer.export()
        self.assertEqual(producer.status, 0)
        self.root = producer.root
        directory = producer.arguments.output_directory
        summary_path = directory / policy.SUMMARY
        audit_path = directory / policy.AUDIT
        inventory_path = producer.arguments.preserved_inventory_report
        with np.load(directory / policy.ARCHIVE, allow_pickle=False) as stored:
            arrays = dict(stored)
        row, = summary["recordings"]
        native = producer.fixture.raw
        archive = SimpleNamespace(
            arrays=arrays, summary_sha256=sha(summary_path),
            raw_sha256_by_recording={row["recording_id"]: row["raw_sha256"]},
        )
        self.inputs = SimpleNamespace(
            blocks=[SimpleNamespace(archive=archive, outing_id="fixture_outing")],
            context=SimpleNamespace(
                objects={sha(p): p.read_bytes() for p in (summary_path, audit_path, inventory_path)},
                metadata={"records": [{
                    "raw_sha256": row["raw_sha256"], "canonical_paths_private": [str(native)],
                    "size_bytes": row["size_bytes"],
                }]},
            ),
            request={}, unchanged=lambda: None,
        )
        self.scratch = self.root / "replay-scratch"
        self.scratch.mkdir()
        self.frame = replay.select_frame(self.inputs, "fixture_outing", 0)
        schema, = [row["schema_data_sha256"] for row in self.frame.stream_integrity["channel_versions"]
                   if row["topic"] == replay.DEFAULT_ODOMETRY_TOPIC]
        self.binding = {"schema_data_sha256": schema, "field": "fixture_availability",
                        "available_symbol": "AVAILABLE"}

    def adopted(self):
        value = replay.frame_evidence_template(self.frame)
        value.update(
            path_frame="synthetic_path", odometry_frame="synthetic_odometry",
            frame_and_pose_evidence_reference="synthetic fixture frame declaration",
            both_original_paths_verified_in_same_frame_at_epoch=True,
            recorded_rear_axle_pose_valid_at_epoch=True,
            odometry_qualifier=self.binding.copy(),
            path_frame_in_odometry={"x_m": 0.25, "y_m": 0.0, "yaw_rad": 0.0},
        )
        return value

    def test_original_export_replays_through_workflow(self):
        evidence = self.root / "frame-evidence.private.json"
        output = self.root / "replay.private.json"
        write(evidence, self.adopted())
        with patch.object(workflow, "source_guard", return_value={"synthetic": True}), \
                patch.object(workflow, "_resources"), \
                patch.object(workflow, "protected_inputs", return_value=[]), \
                patch.object(workflow, "load_frame", return_value=(self.inputs, self.frame)):
            kwargs = dict(
                source=self.root / "source", project=self.root / "project",
                experiment=Path("experiment"), experiment_sha256="fixture",
                outing="fixture_outing", matched_row=0, evidence=evidence,
                evidence_sha256=sha(evidence), scratch=self.scratch, output=output,
                expected_tree="fixture", expected_runtime="fixture",
            )
            report = workflow.run(**kwargs)
            with self.assertRaisesRegex(RegistryError, "replay_new_private_receipt_required"):
                workflow.run(**kwargs)
        self.assertEqual(report["status"], "recorded_frame_geometry_verified", report)
        self.assertEqual(len(report["nominal_reference_points_m"]), 21)
        self.assertAlmostEqual(report["residual_stations_from_rear_axle_m"][0], -0.25)
        self.assertAlmostEqual(report["initial_lateral_error_m"], -0.5)
        self.assertEqual(report["odometry"]["source_time_ns"], self.frame.identity["estimate_source_time_ns"])
        self.assertEqual(report["odometry"]["availability_evidence"], "explicit_available_wire_value")
        self.assertEqual(report["original_sequence_matched_row_bounds"], [0, 2])

    def test_rejects_guessed_or_wrong_epoch_frame_evidence(self):
        with self.assertRaises(RegistryError):
            replay.validate_frame_evidence(replay.frame_evidence_template(self.frame), self.frame)
        value = self.adopted()
        value["path_frame_epoch_ns"] = "1"
        with self.assertRaisesRegex(RegistryError, "replay_frame_evidence_epoch_mismatch"):
            replay.validate_frame_evidence(value, self.frame)
        value = self.adopted()
        value["row"] = {**value["row"], "candidate_index": 19}
        with self.assertRaisesRegex(RecordingIngestionError, "replay_frame_evidence_row_mismatch"):
            replay.validate_frame_evidence(value, self.frame)
        value = self.adopted()
        value["odometry_qualifier"]["schema_data_sha256"] = "0" * 64
        with self.assertRaisesRegex(RegistryError, "replay_odometry_qualifier_binding_mismatch"):
            replay.validate_frame_evidence(value, self.frame)

    def test_original_export_with_implicit_default_blocks_native_replay(self):
        self.prepare_recording(qualifier_bytes=b"")
        with self.assertRaises(GeometryValidationError) as failure:
            self.recover(self.frame, Pose2D(0.25, 0.0, 0.0))
        self.assertEqual(failure.exception.code, "replay_odometry_qualifier_implicit")

    def recover(self, frame, origin):
        return replay.recover_frame(frame, origin, self.scratch, lambda: None,
                                    qualifier_binding=self.binding)

    def test_rejects_wrong_pair_and_drifted_raw(self):
        origin = Pose2D(0.25, 0.0, 0.0)
        wrong_pair = replace(self.frame, identity={**self.frame.identity, "pair_index": 1})
        with self.assertRaisesRegex(RegistryError, "replay_original_pair_mismatch"):
            self.recover(wrong_pair, origin)
        drifted = replace(self.frame, identity={**self.frame.identity, "raw_sha256": "0" * 64})
        with patch.object(replay.decoder, "check_decoding") as reader:
            with self.assertRaisesRegex(RegistryError, "replay_raw_size_or_digest_mismatch"):
                self.recover(drifted, origin)
            reader.assert_not_called()

    def test_rejects_missing_conflicting_and_late_exact_odometry(self):
        origin = Pose2D(0.25, 0.0, 0.0)
        reconcile = replay.reconcile_staged_frame
        for query, code in (
            ("DELETE FROM odometry WHERE time=?", "replay_odometry_exact_epoch_missing"),
            ("UPDATE odometry SET conflict=1 WHERE time=?", "replay_odometry_conflict_or_late"),
            ("UPDATE odometry SET log='99999999999999999999' WHERE time=?", "replay_odometry_conflict_or_late"),
        ):
            with self.subTest(code=code, query=query):
                def changed(sink, frame, pose, qualifier):
                    key = replay._time_key(int(frame.identity["estimate_source_time_ns"]))
                    sink.db.execute(query, (key,))
                    return reconcile(sink, frame, pose, qualifier)

                with patch.object(replay, "reconcile_staged_frame", side_effect=changed):
                    with self.assertRaises(GeometryValidationError) as failure:
                        self.recover(self.frame, origin)
                self.assertEqual(failure.exception.code, code)


class ExactOdometryQualifierTests(unittest.TestCase):
    def setUp(self):
        self.odometry_class = synthetic.classes(add_qualifier)[2]
        self.binding = {"field": "fixture_availability", "available_symbol": "AVAILABLE"}
        self.epoch = synthetic.T

    def sample(self, suffix, *, epoch=None):
        state = self.odometry_class(timestamp=self.epoch if epoch is None else epoch, x_position=0.5)
        payload = state.SerializeToString() + suffix
        return self.odometry_class.FromString(payload), payload

    def test_original_wire_distinguishes_default_aliasing_and_invalid_values(self):
        self.assertEqual(self.sample(b"")[0], self.sample(b"\x48\x00")[0])
        for wire, expected in (
            (b"", "implicit"),
            (b"\x48\x00", None),
            (b"\x48\x01", "not_available"),
            (b"\x48\x02", "not_available"),
            (b"\x48\x7f", "not_available"),
            (b"\x48\x80\x80\x80\x80\x10", "not_available"),  # wraps to zero as an int32
            (b"\x48\x02\x48\x00", "wire_ambiguous"),
            (b"\x48\x00\x48\x00", "wire_ambiguous"),
            (b"\x4a\x01\x00", "wire_ambiguous"),
            (b"\x52\x02\x48\x00", "implicit"),  # same bytes inside a different field
        ):
            with self.subTest(wire=wire, expected=expected):
                self.assertEqual(
                    replay._qualifier_failure(*self.sample(wire), self.binding),
                    None if expected is None else "replay_odometry_qualifier_" + expected,
                )

    def test_descriptor_must_resolve_binding(self):
        for binding in ({**self.binding, "field": "absent"}, {**self.binding, "available_symbol": "ABSENT_SYMBOL"}):
            with self.subTest(binding=binding):
                self.assertEqual(replay._qualifier_failure(*self.sample(b"\x48\x00"), binding),
                                 "replay_odometry_qualifier_descriptor_unsupported")

    def test_earliest_representative_uses_both_clocks_and_exact_source_epoch(self):
        first = (40, 50)
        for other in ((42, 49), (40, 51)):
            rows = [(first, self.sample(b"\x48\x02")), (other, self.sample(b"\x48\x00"))]
            for order in (rows, rows[::-1]):
                with self.subTest(order=order):
                    check = replay._ExactOdometryQualifier(self.epoch, self.binding)
                    for clocks, sample in order:
                        check.observe(replay.DEFAULT_ODOMETRY_TOPIC, *clocks, *sample)
                    check.observe(replay.DEFAULT_ODOMETRY_TOPIC, 38, 50,
                                  *self.sample(b"\x48\x00", epoch=self.epoch - 1))
                    with self.assertRaises(GeometryValidationError) as failure:
                        check.require_available(*first)
                    self.assertEqual(failure.exception.code, "replay_odometry_qualifier_not_available")

    def test_same_clock_candidates_cannot_lend_availability(self):
        check = replay._ExactOdometryQualifier(self.epoch, self.binding)
        for wire in (b"\x48\x00", b"", b"\x48\x00"):
            check.observe(replay.DEFAULT_ODOMETRY_TOPIC, 40, 50, *self.sample(wire))
        with self.assertRaises(GeometryValidationError) as failure:
            check.require_available(40, 50)
        self.assertEqual(failure.exception.code, "replay_odometry_qualifier_clock_tie")
