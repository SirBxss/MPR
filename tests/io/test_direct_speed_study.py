from io import BytesIO
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lane_residuals.io import direct_speed_study as study
from lane_residuals.io.recording_inventory import read_inventory
from tests.io.direct_speed_study_fixture import fixture
from tests.io.velocity_timing_fixture import recording, LOG


class StudyInputTests(unittest.TestCase):
    def setUp(self):
        try:
            study.decoder.check_dependencies()
        except (ImportError,ValueError):
            self.skipTest("optional MCAP extras not installed")
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs,self.request,self.path,self.pin = fixture(self.root)

    def load(self):
        with patch.object(study.original,"load_experiment",return_value=(self.inputs,{})):
            return study.load(self.root,self.path,self.pin)

    def save(self):
        raw = json.dumps(self.request).encode();self.path.write_bytes(raw)
        self.pin = hashlib.sha256(raw).hexdigest()

    def test_native_boundary_fixed_cases_and_exact_metadata_bindings(self):
        loaded = self.load()
        self.assertEqual([c["outing_id"] for c in loaded["cases"]],["synthetic_1","synthetic_2"])
        self.assertEqual(len(loaded["audits"]),3)
        self.assertEqual(len(loaded["cases"][0]["targets"]),120)
        self.inputs.unchanged.assert_called_once()
        self.assertIn(self.path.parent,loaded["protected_output_roots"])

    def test_digest_or_extra_fields_fail_before_native_validation(self):
        with patch.object(study.original,"load_experiment",side_effect=AssertionError("not called")):
            with self.assertRaisesRegex(ValueError,"digest_mismatch"):
                study.load(self.root,self.path,"0"*64)
            self.request["age_ns"] = 123;self.save()
            with self.assertRaisesRegex(ValueError,"closed_request"):
                study.load(self.root,self.path,self.pin)

    def test_final_prior_altered_windows_or_subsets_are_refused(self):
        original = copy.deepcopy(self.request)
        for mode in ("prior","window","subset","order"):
            self.request = copy.deepcopy(original)
            if mode == "prior":self.request["previously_examined_outing_id"] = "final_test"
            if mode == "window":self.request["cases"][0]["window_start_log_ns"] = str(LOG+1)
            if mode == "subset":self.request["cases"].pop()
            if mode == "order":self.request["cases"].reverse()
            self.save()
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.load()

    def test_size_planning_uses_metadata_and_does_not_substitute_after_failure(self):
        self.inputs.context.metadata["records"][1]["size_bytes"] = study.MAX_FILE_BYTES+1
        with self.assertRaisesRegex(ValueError,"two_size_eligible"):
            study.fixed_cases(self.inputs,"synthetic_0")

    def test_native_role_history_failure_is_not_bypassed(self):
        with patch.object(study.original,"load_experiment",side_effect=ValueError("final_evidence_invalidated")):
            with self.assertRaisesRegex(ValueError,"final_evidence"):
                study.load(self.root,self.path,self.pin)

    def test_claim_identity_ignores_paths_and_formatting_but_binds_window(self):
        case = self.load()["cases"][0]
        alias = dict(case,raw_path_private="/renamed/alias.mcap")
        self.assertEqual(study.design_sha256(case,"a"*64),study.design_sha256(alias,"a"*64))
        alias["window_start_log_ns"] = str(int(alias["window_start_log_ns"])+1)
        self.assertNotEqual(study.design_sha256(case,"a"*64),study.design_sha256(alias,"a"*64))

    def test_unmodified_indexed_reader_three_compressions_and_descriptor_binding(self):
        for compression in ("NONE","ZSTD","LZ4"):
            raw = recording(compression)
            with self.subTest(compression=compression):
                plan = study.prepare(BytesIO(raw),len(raw),read_inventory(BytesIO(raw),len(raw)),(LOG-10**9,LOG+13*10**9),self.root)
                self.assertEqual(len(plan["summary"]["descriptor_bindings"]),2)
                from lane_residuals.io.velocity_timing_pilot import decode_prepared
                records,_ = decode_prepared(plan)
                self.assertEqual(len(records),6)

    def test_affordability_failure_precedes_decompression(self):
        raw = recording()
        with patch.dict(study.LIMITS,selected_chunk_read_bytes=0),patch.object(study.decoder,"_decompress",side_effect=AssertionError("payload")):
            with self.assertRaisesRegex(ValueError,"planned_window_budget"):
                study.prepare(BytesIO(raw),len(raw),read_inventory(BytesIO(raw),len(raw)),(LOG-10**9,LOG+13*10**9),self.root)

    def test_changed_inner_enum_or_scalar_type_fails_before_payload(self):
        from google.protobuf.descriptor_pb2 import FileDescriptorSet
        from mcap.reader import SeekingReader
        from mcap.writer import Writer, CompressionType
        for mode in ("enum","negative_enum","value_type","repeated"):
            original = recording("NONE")
            reader = SeekingReader(BytesIO(original));summary = reader.get_summary()
            stream = BytesIO();writer = Writer(stream,compression=CompressionType.NONE,chunk_size=1);writer.start()
            schemas = {}
            for key,schema in summary.schemas.items():
                descriptor = FileDescriptorSet.FromString(schema.data)
                if mode == "enum":descriptor.file[0].enum_type[0].value[1].name = "UNAVAILABLE"
                elif mode == "negative_enum":descriptor.file[0].enum_type[0].value[1].name = "NOT_VALID"
                elif mode == "repeated":descriptor.file[0].message_type[0].field[0].label = 3
                else:descriptor.file[0].message_type[0].field[0].type = 2
                schemas[key] = writer.register_schema(schema.name,schema.encoding,descriptor.SerializeToString())
            channels = {key:writer.register_channel(c.topic,c.message_encoding,schemas.get(c.schema_id,0)) for key,c in summary.channels.items()}
            for _,channel,message in reader.iter_messages():
                writer.add_message(channels[channel.id],message.log_time,message.data,message.publish_time)
            writer.finish();raw = stream.getvalue()
            with self.subTest(mode=mode),patch.object(study.decoder,"_decompress",side_effect=AssertionError("payload touched")):
                with self.assertRaisesRegex(ValueError,"study_(inner_qualifier|scalar_field)"):
                    study.prepare(BytesIO(raw),len(raw),read_inventory(BytesIO(raw),len(raw)),(LOG-10**9,LOG+13*10**9),self.root)

    def test_isolated_hash_bound_and_digest_check(self):
        case = self.load()["cases"][0]
        with Path(case["raw_path_private"]).open("rb") as stream:
            self.assertEqual(study.verify_raw(stream,case)["sha256"],case["raw_sha256"])
        with Path(case["raw_path_private"]).open("rb") as stream,self.assertRaisesRegex(ValueError,"digest_mismatch"):
            study.verify_raw(stream,dict(case,raw_sha256="0"*64))
        from lane_residuals.io.velocity_timing_pilot import LIMITS
        self.assertEqual(LIMITS["maximum_raw_file_bytes"],2*1024**3)
