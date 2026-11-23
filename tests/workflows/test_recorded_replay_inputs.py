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
from tests.workflows import test_numeric_export as numeric_fixture


class RecordedReplayInputsTests(unittest.TestCase):
    def setUp(self):
        producer = numeric_fixture.NumericExportTests()
        producer.setUp()
        self.addCleanup(producer.doCleanups)
        producer.prepare()
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

    def adopted(self):
        value = replay.frame_evidence_template(self.frame)
        value.update(
            path_frame="synthetic_path", odometry_frame="synthetic_odometry",
            frame_and_pose_evidence_reference="synthetic fixture frame declaration",
            both_original_paths_verified_in_same_frame_at_epoch=True,
            recorded_rear_axle_pose_valid_at_epoch=True,
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

    def test_rejects_wrong_pair_and_drifted_raw(self):
        origin = Pose2D(0.25, 0.0, 0.0)
        wrong_pair = replace(self.frame, identity={**self.frame.identity, "pair_index": 1})
        with self.assertRaisesRegex(RegistryError, "replay_original_pair_mismatch"):
            replay.recover_frame(wrong_pair, origin, self.scratch, lambda: None)
        drifted = replace(self.frame, identity={**self.frame.identity, "raw_sha256": "0" * 64})
        with patch.object(replay.decoder, "check_decoding") as reader:
            with self.assertRaisesRegex(RegistryError, "replay_raw_size_or_digest_mismatch"):
                replay.recover_frame(drifted, origin, self.scratch, lambda: None)
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
                def changed(sink, frame, pose):
                    key = replay._time_key(int(frame.identity["estimate_source_time_ns"]))
                    sink.db.execute(query, (key,))
                    return reconcile(sink, frame, pose)

                with patch.object(replay, "reconcile_staged_frame", side_effect=changed):
                    with self.assertRaises(GeometryValidationError) as failure:
                        replay.recover_frame(self.frame, origin, self.scratch, lambda: None)
                self.assertEqual(failure.exception.code, code)
