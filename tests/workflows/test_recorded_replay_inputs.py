"""Exercise the native indexed replay using a synthetic numeric export."""

from contextlib import ExitStack
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.cli import recorded_replay_inputs as cli
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
    for name, number in (("AVAILABLE", 0), ("REDUCED", 1), ("ABSENT", 2), ("SIGNED_TEST", -1)):
        enum.value.add(name=name, number=number)
    odometry.message_type[0].field.add(
        name="fixture_availability", number=9, type=14, label=1, type_name=".Adp.FixtureAvailability",
    )


class RecordedReplayInputsTests(unittest.TestCase):
    def setUp(self):
        self.prepare_recording(qualifier_bytes=b"\x48\x00")

    def prepare_recording(self, qualifier_bytes, *, duplicates=()):
        producer = numeric_fixture.NumericExportTests()
        producer.setUp()
        self.addCleanup(producer.doCleanups)
        def records(message, state):
            base = state.SerializeToString()
            suffix = qualifier_bytes(state.timestamp) if callable(qualifier_bytes) else qualifier_bytes
            yield message.log_time, message.publish_time, base + suffix
            if state.timestamp == synthetic.T:
                for offset, wire in duplicates:
                    yield message.log_time + offset, message.publish_time + offset, base + wire

        producer.prepare(mutate=add_qualifier, odometry_records=records)
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

    def arguments(self, evidence, output):
        return dict(
            source=self.root / "source", project=self.root / "project",
            experiment=Path("experiment"), experiment_sha256="fixture",
            outing="fixture_outing", matched_row=0, evidence=evidence,
            evidence_sha256=sha(evidence), scratch=self.scratch, output=output,
            expected_tree="fixture", expected_runtime="fixture",
        )

    def workflow_guards(self, stack):
        stack.enter_context(patch.object(workflow, "source_guard", return_value={"synthetic": True}))
        stack.enter_context(patch.object(workflow, "_resources"))
        stack.enter_context(patch.object(workflow, "_decode_resources"))
        stack.enter_context(patch.object(workflow, "protected_inputs", return_value=[]))
        stack.enter_context(patch.object(workflow, "load_frame", return_value=(self.inputs, self.frame)))

    def test_original_export_replays_through_workflow(self):
        evidence = self.root / "frame-evidence.private.json"
        output = self.root / "replay.private.json"
        write(evidence, self.adopted())
        with ExitStack() as stack:
            self.workflow_guards(stack)
            kwargs = self.arguments(evidence, output)
            report = workflow.run(**kwargs)
            with self.assertRaisesRegex(RegistryError, "replay_new_private_receipt_required"):
                workflow.run(**kwargs)
        self.assertEqual(report["status"], "recorded_frame_geometry_verified", report)
        self.assertEqual(len(report["nominal_reference_points_m"]), 21)
        self.assertAlmostEqual(report["residual_stations_from_rear_axle_m"][0], -0.25)
        self.assertAlmostEqual(report["initial_lateral_error_m"], -0.5)
        self.assertEqual(report["odometry"]["source_time_ns"], self.frame.identity["estimate_source_time_ns"])
        self.assertEqual(report["odometry"]["availability_evidence"], "explicit_available_wire_value")
        self.assertEqual(report["odometry"]["exact_epoch_message_count"], 1)
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
        value = self.adopted()
        del value["odometry_qualifier"]
        with self.assertRaisesRegex(RegistryError, "replay_frame_evidence_schema"):
            replay.validate_frame_evidence(value, self.frame)

    def test_original_export_with_implicit_default_blocks_native_replay(self):
        self.prepare_recording(qualifier_bytes=b"")
        report = self.verify_receipt()
        self.assertEqual(report["status"], "recorded_frame_unsupported")
        self.assertEqual(report["failure_code"], "replay_odometry_qualifier_implicit")
        self.assertEqual(report["odometry"]["qualifier_outcome_counts"], {report["failure_code"]: 1})
        self.assertNotIn("nominal_reference_points_m", report)

    def verify_receipt(self):
        evidence = self.root / "frame-evidence.private.json"
        write(evidence, self.adopted())
        with ExitStack() as stack:
            self.workflow_guards(stack)
            return workflow.run(**self.arguments(evidence, self.root / "replay.private.json"))

    def test_later_qualifier_disagreement_blocks_native_replay(self):
        self.prepare_recording(qualifier_bytes=b"\x48\x00", duplicates=((1, b"\x48\x02"),))
        report = self.verify_receipt()
        self.assertEqual(report["status"], "recorded_frame_unsupported")
        self.assertEqual(report["failure_code"], "replay_odometry_qualifier_duplicate_conflict")
        self.assertEqual(report["odometry"], {
            "exact_epoch_message_count": 2,
            "qualifier_outcome_counts": {
                "explicit_available_wire_value": 1,
                "replay_odometry_qualifier_not_available": 1,
            },
        })

    def test_census_cli_counts_qualifier_wire_values_without_geometry(self):
        suffixes = {
            synthetic.T - 50_000_000: b"",
            synthetic.T: b"\x48\x00",
            synthetic.T + 50_000_000: b"\x48\x01",
            synthetic.T + 100_000_000: b"\x4a\x01\x00",
        }
        self.prepare_recording(suffixes.__getitem__, duplicates=((1, b"\x48\x63"),))
        evidence = self.root / "schema.private.json"
        output = self.root / "census.private.json"
        write(evidence, {"row": self.frame.identity, "schema_sha256": self.binding["schema_data_sha256"],
                         "field": self.binding["field"], "enum_values": {"AVAILABLE": 0}})
        args = self.arguments(evidence, output)
        args["available_symbol"] = "AVAILABLE"
        command = ["qualifier-census"]
        for key, value in args.items():
            command.extend(("--" + key.replace("_", "-"), str(value)))
        with ExitStack() as stack:
            self.workflow_guards(stack)
            science = stack.enter_context(patch.object(replay, "ScientificSink", side_effect=AssertionError("geometry")))
            self.assertEqual(cli.main(command), 0)
            science.assert_not_called()
        report = json.loads(output.read_text())
        self.assertEqual(report["status"], "recorded_odometry_census_complete")
        self.assertEqual(report["odometry_message_count"], 5)
        self.assertEqual(report["wire_counts"], {"omitted": 1, "explicit_zero": 1, "explicit_nonzero": 2,
                                                "ambiguous": 1})
        self.assertEqual(report["explicit_nonzero_value_counts"], {"1": 1, "unknown": 1})
        self.assertEqual(report["selected_epoch"]["qualifier_failure_code"],
                         "replay_odometry_qualifier_duplicate_conflict")
        self.assertNotIn("odometry", report)
        self.assertNotIn("nominal_reference_points_m", report)

    def test_census_rejects_wrong_row_before_recording_access(self):
        evidence = self.root / "schema.private.json"
        write(evidence, {"row": {**self.frame.identity, "candidate_index": 99}})
        with ExitStack() as stack:
            self.workflow_guards(stack)
            reader = stack.enter_context(patch.object(replay, "_recording_for_frame"))
            with self.assertRaisesRegex(RegistryError, "replay_census_schema_receipt_row_mismatch"):
                workflow.census(**self.arguments(evidence, self.root / "census.private.json"),
                                available_symbol="AVAILABLE")
            reader.assert_not_called()

    def test_payload_observer_failure_is_inconclusive(self):
        original = replay.decoder.check_decoding

        def decode(*args, **kwargs):
            observer = kwargs.get("payload_observer")
            if observer is None:
                return original(*args, **kwargs)
            with self.assertRaises(RuntimeError) as failed:
                original(*args, **kwargs)
            self.assertEqual(failed.exception.reader_failure_context["phase"], "payload_decode")
            raise failed.exception

        with patch.object(replay.decoder, "check_decoding", side_effect=decode), \
                patch.object(replay._ExactOdometryQualifier, "observe", side_effect=RuntimeError("fixture")):
            report = self.verify_receipt()
        self.assertEqual(report["status"], "recorded_frame_inconclusive")
        self.assertNotIn("nominal_reference_points_m", report)

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

    def test_stream_failure_takes_precedence_over_missing_pose(self):
        reconcile = replay.reconcile_staged_frame

        def invalid_pose(sink, frame, pose, qualifier):
            sink.db.execute("DELETE FROM odometry WHERE time=?", (replay._time_key(synthetic.T),))
            sink.odometry.failures["odometry_invalid_message"] = 1
            return reconcile(sink, frame, pose, qualifier)

        with patch.object(replay, "reconcile_staged_frame", side_effect=invalid_pose), \
                self.assertRaises(GeometryValidationError) as failure:
            self.recover(self.frame, Pose2D(0.25, 0.0, 0.0))
        self.assertEqual(failure.exception.code, "replay_odometry_stream_unsupported")


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
            (b"\x49" + b"\x00" * 8, "wire_ambiguous"),
            (b"\x4d" + b"\x00" * 4, "wire_ambiguous"),
            (b"\x4b\x4c", "wire_ambiguous"),
            (b"\x52\x02\x48\x00", "implicit"),  # same bytes inside a different field
        ):
            with self.subTest(wire=wire, expected=expected):
                self.assertEqual(
                    replay._qualifier_wire(*self.sample(wire), self.binding)[0],
                    None if expected is None else "replay_odometry_qualifier_" + expected,
                )

    def test_descriptor_must_resolve_binding(self):
        for binding in ({**self.binding, "field": "absent"}, {**self.binding, "available_symbol": "ABSENT_SYMBOL"}):
            with self.subTest(binding=binding):
                self.assertEqual(replay._qualifier_wire(*self.sample(b"\x48\x00"), binding)[0],
                                 "replay_odometry_qualifier_descriptor_unsupported")
        for variant in ("alias", "repeated", "int32"):
            with self.subTest(variant=variant):
                def mutate(paths, odometry):
                    add_qualifier(paths, odometry)
                    field = odometry.message_type[0].field[-1]
                    if variant == "alias":
                        enum = odometry.enum_type[0]
                        enum.options.allow_alias = True
                        enum.value.add(name="ALIAS", number=0)
                    elif variant == "repeated":
                        field.label = 3
                    else:
                        field.type = 5
                        field.ClearField("type_name")

                state = synthetic.classes(mutate)[2]()
                self.assertEqual(replay._qualifier_wire(state, b"", self.binding)[0],
                                 "replay_odometry_qualifier_descriptor_unsupported")

    def test_bound_enum_can_be_positive_or_signed(self):
        for symbol, wire in (("REDUCED", b"\x48\x01"),
                             ("SIGNED_TEST", b"\x48" + b"\xff" * 9 + b"\x01")):
            binding = {**self.binding, "available_symbol": symbol}
            self.assertIsNone(replay._qualifier_wire(*self.sample(wire), binding)[0])
            self.assertEqual(replay._qualifier_wire(*self.sample(b""), binding)[0],
                             "replay_odometry_qualifier_implicit")

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
                        check.require_available(*first, 2)
                    self.assertEqual(failure.exception.code, "replay_odometry_qualifier_duplicate_conflict")

    def test_every_target_epoch_duplicate_must_support_availability(self):
        first = (40, 50)
        for later in (b"", b"\x48\x01", b"\x48\x02", b"\x48\x7f", b"\x4a\x01\x00"):
            rows = [(first, self.sample(b"\x48\x00")), ((42, 50), self.sample(later))]
            for order in (rows, rows[::-1]):
                with self.subTest(later=later, order=order):
                    check = replay._ExactOdometryQualifier(self.epoch, self.binding)
                    for clocks, sample in order:
                        check.observe(replay.DEFAULT_ODOMETRY_TOPIC, *clocks, *sample)
                    with self.assertRaises(GeometryValidationError) as failure:
                        check.require_available(*first, 2)
                    self.assertEqual(failure.exception.code, "replay_odometry_qualifier_duplicate_conflict")

    def test_same_clock_candidates_cannot_lend_availability(self):
        check = replay._ExactOdometryQualifier(self.epoch, self.binding)
        for wire in (b"\x48\x00", b"", b"\x48\x00"):
            check.observe(replay.DEFAULT_ODOMETRY_TOPIC, 40, 50, *self.sample(wire))
        with self.assertRaises(GeometryValidationError) as failure:
            check.require_available(40, 50, 3)
        self.assertEqual(failure.exception.code, "replay_odometry_qualifier_clock_tie")

    def test_consistent_duplicates_pass_only_for_the_kept_clocks_and_multiplicity(self):
        check = replay._ExactOdometryQualifier(self.epoch, self.binding)
        for clocks in ((42, 50), (40, 50), (40, 50)):
            check.observe(replay.DEFAULT_ODOMETRY_TOPIC, *clocks, *self.sample(b"\x48\x00"))
        check.require_available(40, 50, 3)
        for request in ((42, 50, 3), (40, 50, 2)):
            with self.subTest(request=request), self.assertRaises(GeometryValidationError) as failure:
                check.require_available(*request)
            self.assertEqual(failure.exception.code, "replay_odometry_qualifier_sample_mismatch")
