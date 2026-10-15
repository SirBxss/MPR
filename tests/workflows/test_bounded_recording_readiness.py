import argparse
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lane_residuals.cli import recording_ingestion as cli
from lane_residuals.io import recording_decode_check as reader
from lane_residuals.workflows import bounded_recording_readiness as workflow
from lane_residuals.workflows import recording_decode_check as decoding
from lane_residuals.workflows import recording_ingestion as registration
from lane_residuals.workflows import recording_inventory as inventory
from tests.domain.test_recording_ingestion import specification
from tests.io.bounded_readiness_fixture import recording,TOPICS,remove_field


class BoundedWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.raw=self.root/"recording with spaces.mcap"
        self.directory=self.root/"registration";self.inventory_dir=self.root/"inventory";self.decode_dir=self.root/"decode"
        self.source=self.root/"source.json"
        self.args=argparse.Namespace(registration_directory=self.directory,scratch_directory=self.root,output_directory=self.root/"bounded",
            preserved_inventory_report=self.inventory_dir/inventory.REPORT_NAME,preserved_decode_report=self.decode_dir/decoding.REPORT_NAME,topic=list(TOPICS))
        stack=ExitStack();self.addCleanup(stack.close)
        stack.enter_context(patch.object(registration,"_available_memory_bytes",return_value=8*1024**3))
        stack.enter_context(patch.object(workflow,"_available_memory_bytes",return_value=8*1024**3))
        stack.enter_context(patch.object(workflow.shutil,"disk_usage",return_value=SimpleNamespace(free=64*1024**3)))

    def prepare(self,*,second=False,**options):
        self.raw.write_bytes(recording(**options));spec=specification(str(self.raw))
        if second:
            other=self.root/"other.mcap";other.write_bytes(recording(compression="NONE"))
            row=deepcopy(spec["recordings"][0]);row.update(recording_id="pilot_002",local_path_private=str(other));spec["recordings"].append(row)
        self.source.write_text(json.dumps(spec))
        registration.run_registration(argparse.Namespace(specification=self.source,output_directory=self.directory))
        self.inventory=inventory.run_inventory(argparse.Namespace(registration_directory=self.directory,scratch_directory=self.root,output_directory=self.inventory_dir))[0]
        self.decode=decoding.run_decode_check(argparse.Namespace(registration_directory=self.directory,scratch_directory=self.root,output_directory=self.decode_dir,preserved_inventory_report=self.args.preserved_inventory_report,topic=list(TOPICS)))[0]

    def test_complete_exact_shape_one_hash_same_fd_and_no_whole_summary(self):
        self.prepare();original=workflow.sha256_stream;handles=[]
        before={p:p.read_bytes() for p in [self.raw,*self.directory.iterdir(),self.args.preserved_inventory_report,self.args.preserved_decode_report]}
        def hash_one(stream):handles.append(stream);return original(stream)
        original_reader=reader.check_decoding
        def decode(stream,*a,**kw):
            self.assertIs(stream,handles[0]);return original_reader(stream,*a,**kw)
        from mcap.reader import SeekingReader
        with patch.object(workflow,"sha256_stream",side_effect=hash_one),patch.object(reader,"check_decoding",side_effect=decode),patch.object(SeekingReader,"get_summary",side_effect=AssertionError("whole summary forbidden")):
            report,status=workflow.run_bounded_readiness(self.args)
        self.assertEqual(status,0);self.assertEqual(len(handles),1)
        self.assertTrue(report["recorded_input_causality_checked_for_all_recordings"])
        row=report["recordings"][0]
        self.assertEqual(set(row),{"recording_id","raw_sha256","size_bytes","source_declaration_status","status","failure_code","invalidation_codes","reader_failure_context","binding_observations","stream_integrity","readiness","condition_availability","recorded_input_causality_checked","execution_observations"})
        self.assertEqual(row["stream_integrity"],self.decode["recordings"][0]["decode_check"])
        self.assertEqual(row["readiness"]["complete_condition_support"]["frame_count"],2)
        for key in ("raw_cache_deletion_authorized","residual_profiles_constructed","numeric_conditions_exported","model_fitted","roles_assigned","physical_input_availability_proven"):
            self.assertIs(report[key],False)
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        text=json.dumps(report);self.assertNotIn(str(self.raw),text);self.assertNotIn('"conditions":',text);self.assertNotIn('"residuals_m":',text)
        self.assertEqual([p.name for p in self.args.output_directory.iterdir()],[workflow.REPORT_NAME])
        self.assertEqual(set(row["execution_observations"]["elapsed_seconds"]),{"raw_hash","fresh_summary","descriptor_binding","selected_decode","scientific_finalize"})

    def test_initial_18_point_5_gib_boundary_and_dependency_failure_before_hash(self):
        self.prepare()
        for free in (workflow.INITIAL_SCRATCH_BYTES-1,):
            with patch.object(workflow.shutil,"disk_usage",return_value=SimpleNamespace(free=free)),patch.object(workflow,"sha256_stream") as hasher:
                with self.assertRaisesRegex(ValueError,"insufficient_initial_scratch_space"):
                    workflow.run_bounded_readiness(self.args)
                hasher.assert_not_called()
            self.assertFalse(self.args.output_directory.exists())
        with patch.object(workflow,"check_configuration",side_effect=ValueError("bad SQLite")),patch.object(workflow,"sha256_stream") as hasher:
            with self.assertRaises(ValueError):workflow.run_bounded_readiness(self.args)
            hasher.assert_not_called()

    def test_ambiguous_projection_publishes_complete_report_with_measured_attrition(self):
        self.prepare(ambiguous_reference=True)
        report,status=workflow.run_bounded_readiness(self.args)
        self.assertEqual(status,0)
        self.assertEqual(report["status"],"complete")
        row=report["recordings"][0]
        self.assertEqual(row["status"],"complete")
        self.assertIsNone(row["failure_code"])
        self.assertEqual(row["stream_integrity"],self.decode["recordings"][0]["decode_check"])
        stage=row["readiness"]["exclusive_attrition"]["stages"][5]
        self.assertEqual(stage["failure_code_counts"],{"h100_reference_alignment_projection_ambiguous":1})
        self.assertEqual(row["readiness"]["complete_condition_support"]["frame_count"],1)
        self.assertEqual(json.loads((self.args.output_directory/workflow.REPORT_NAME).read_text()),report)

    def test_missing_confidence_exit_three_retains_stream_and_poison_exit_zero(self):
        self.prepare(mutate=remove_field("DrivePath","drive_path_confidences"))
        report,status=workflow.run_bounded_readiness(self.args);row=report["recordings"][0]
        self.assertEqual(status,3);self.assertIsNone(row["readiness"]);self.assertIsNotNone(row["stream_integrity"])
        self.assertEqual(row["condition_availability"],"not_assessed")

    def test_empty_values_are_complete_zero_with_usable_odometry(self):
        self.prepare(confidence=None)
        report,status=workflow.run_bounded_readiness(self.args);row=report["recordings"][0]
        self.assertEqual(status,0);self.assertTrue(row["recorded_input_causality_checked"])
        self.assertEqual(row["readiness"]["complete_condition_support"]["frame_count"],0)

    def test_global_odometry_poison_retains_geometry_and_batch_causality_false(self):
        self.prepare(invalid_odometry=True)
        report,status=workflow.run_bounded_readiness(self.args);row=report["recordings"][0]
        self.assertEqual(status,0);self.assertEqual(row["condition_availability"],"unavailable_odometry")
        self.assertEqual(row["readiness"]["sensor_geometry_support"]["frame_count"],2)
        self.assertFalse(report["recorded_input_causality_checked_for_all_recordings"])

    def test_fresh_inventory_bool_int_drift_is_fatal_without_science_or_output(self):
        self.prepare();original=workflow.read_inventory
        def drift(*args):
            result=original(*args);result["summary_offsets_present"]=1;return result
        with patch.object(workflow,"read_inventory",side_effect=drift),patch.object(reader,"check_decoding") as decoded:
            with self.assertRaisesRegex(ValueError,"readiness_preserved_inventory_mismatch"):
                workflow.run_bounded_readiness(self.args)
            decoded.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_fresh_decode_value_drift_is_fatal_even_after_science_staging(self):
        self.prepare();original=reader.check_decoding
        def drift(*args,**kw):
            value=original(*args,**kw);value["selected_payload_bytes_processed"]+=1;return value
        with patch.object(reader,"check_decoding",side_effect=drift):
            with self.assertRaisesRegex(ValueError,"readiness_preserved_decode_mismatch"):
                workflow.run_bounded_readiness(self.args)
        self.assertFalse(self.args.output_directory.exists())
        self.assertFalse(any(p.name.startswith("mpr-bounded-") for p in self.root.iterdir()))

    def test_predecessor_duplicates_nonfinite_lineage_and_bool_counts_before_hash(self):
        self.prepare();path=self.args.preserved_decode_report;raw=path.read_bytes()
        bads=[b'{"duplicate":1,"duplicate":2}',b'{"x":NaN}',b'{"x":1e999}',json.dumps({**self.decode,"technical_recording_count":True}).encode(),json.dumps({**self.decode,"selected_topics":[TOPICS[0]]}).encode(),json.dumps({**self.decode,"execution_limits":{}}).encode()]
        for bad in bads:
            path.write_bytes(bad)
            with patch.object(workflow,"sha256_stream") as hasher:
                with self.assertRaisesRegex(ValueError,"readiness_predecessor_mismatch"):workflow.run_bounded_readiness(self.args)
                hasher.assert_not_called()
            self.assertFalse(self.args.output_directory.exists())
        path.write_bytes(raw)

    def test_preserved_decode_budget_and_exact_topics_before_hash(self):
        self.prepare()
        with patch.object(workflow,"MAX_REPORT_BYTES",1),patch.object(workflow,"sha256_stream") as hasher:
            with self.assertRaisesRegex(ValueError,"report_budget_exceeded"):workflow.run_bounded_readiness(self.args)
            hasher.assert_not_called()

    def test_advertised_scientific_caps_and_inconsistent_topic_counts_before_hash(self):
        self.prepare()
        inventory=deepcopy(self.inventory);decode=deepcopy(self.decode)
        count=100_001
        for row in inventory["recordings"][0]["inventory"]["channels"]:
            if row["topic"]==TOPICS[0]:row["advertised_message_count"]=count
        for row in inventory["recordings"][0]["inventory"]["topics"]:
            if row["topic"]==TOPICS[0]:row["advertised_message_count"]=count
        inventory["recordings"][0]["inventory"]["advertised_statistics"]["message_count"]+=count-2
        checked=decode["recordings"][0]["decode_check"]
        for row in checked["channel_versions"]+checked["topics"]:
            if row["topic"]==TOPICS[0]:row.update(advertised_message_count=count,decoded_message_count=count)
        checked["decoded_selected_message_count"]+=count-2
        self.args.preserved_inventory_report.write_text(json.dumps(inventory))
        decode["preserved_inventory_report_sha256"]=hashlib.sha256(self.args.preserved_inventory_report.read_bytes()).hexdigest()
        self.args.preserved_decode_report.write_text(json.dumps(decode))
        with patch.object(workflow,"sha256_stream") as hasher:
            with self.assertRaisesRegex(ValueError,"scientific_advertised_topic_limit"):workflow.run_bounded_readiness(self.args)
            hasher.assert_not_called()
        # A contradictory topic summary is a predecessor error, not a cap result.
        inventory["recordings"][0]["inventory"]["topics"][0]["advertised_message_count"]+=1
        self.args.preserved_inventory_report.write_text(json.dumps(inventory))
        decode["preserved_inventory_report_sha256"]=hashlib.sha256(self.args.preserved_inventory_report.read_bytes()).hexdigest()
        self.args.preserved_decode_report.write_text(json.dumps(decode))
        with patch.object(workflow,"sha256_stream") as hasher:
            with self.assertRaisesRegex(ValueError,"readiness_predecessor_mismatch"):workflow.run_bounded_readiness(self.args)
            hasher.assert_not_called()
        self.args.topic=[TOPICS[0]]
        with patch.object(workflow,"sha256_stream") as hasher:
            with self.assertRaisesRegex(ValueError,"explicit_three_topics"):workflow.run_bounded_readiness(self.args)
            hasher.assert_not_called()

    def test_runtime_resource_floor_is_inconclusive_and_temp_cleanup(self):
        self.prepare();original=workflow.sha256_stream
        def hash_then_low(stream):
            digest=original(stream)
            workflow.shutil.disk_usage.return_value=SimpleNamespace(free=9*1024**3)
            return digest
        with patch.object(workflow,"sha256_stream",side_effect=hash_then_low):report,status=workflow.run_bounded_readiness(self.args)
        self.assertEqual(status,3);self.assertEqual(report["recordings"][0]["failure_code"],"scratch_free_below_runtime_floor")
        self.assertIsNone(report["recordings"][0]["stream_integrity"])

    def test_container_failure_overrides_scientific_failure_and_nulls_prefix(self):
        self.prepare();original=reader._messages;calls=0
        def failure(*args,**kw):
            nonlocal calls
            calls+=1
            if calls==3:raise MemoryError()
            return original(*args,**kw)
        with patch.object(reader,"_messages",side_effect=failure):report,status=workflow.run_bounded_readiness(self.args)
        row=report["recordings"][0]
        self.assertEqual(status,3);self.assertIsNone(row["stream_integrity"]);self.assertIsNone(row["readiness"])
        self.assertEqual(row["failure_code"],"memory_limit")
        self.assertGreater(row["reader_failure_context"]["decoded_selected_message_count"],0)

    def test_raw_and_predecessor_mutations_invalidate_in_detection_order(self):
        self.prepare();original=reader.check_decoding
        def mutate(*args,**kw):
            value=original(*args,**kw)
            other=self.root/"replacement";other.write_bytes(self.raw.read_bytes());os.replace(other,self.raw)
            for path in (self.directory/registration.SPECIFICATION_NAME,self.args.preserved_inventory_report,self.args.preserved_decode_report):
                path.write_bytes(path.read_bytes()+b" ")
            return value
        with patch.object(reader,"check_decoding",side_effect=mutate):report,status=workflow.run_bounded_readiness(self.args)
        row=report["recordings"][0]
        self.assertEqual(status,3);self.assertEqual(row["failure_code"],"file_changed_during_readiness")
        self.assertEqual(row["invalidation_codes"],["file_changed_before_report_publish","registration_changed_before_report_publish","preserved_inventory_changed_before_report_publish","preserved_decode_changed_before_report_publish"])
        for key in ("readiness","stream_integrity","binding_observations"):self.assertIsNone(row[key])

    def test_processing_deadline_is_shared_and_not_restarted_in_reader(self):
        self.prepare()
        with patch.object(workflow,"PROCESSING_SECONDS",-1):report,status=workflow.run_bounded_readiness(self.args)
        self.assertEqual(status,3);self.assertEqual(report["recordings"][0]["failure_code"],"readiness_processing_time_limit")

    def test_cli_dispatch_restores_limit_and_exposes_no_private_error_text(self):
        with patch.object(cli,"_bounded_run",return_value=({},3)) as dispatch:
            result=cli.main(["bounded-readiness","--registration-directory","unused","--scratch-directory","unused","--preserved-inventory-report","unused","--preserved-decode-report","unused","--output-directory","unused",*[v for topic in TOPICS for v in ("--topic",topic)]])
        self.assertEqual(result,3);self.assertEqual(dispatch.call_args.args[0].command,"bounded-readiness")

    def test_later_fatal_batch_drift_publishes_no_earlier_completed_recording(self):
        self.prepare(second=True);original=workflow.read_inventory;calls=0
        def drift(*args):
            nonlocal calls
            calls+=1;value=original(*args)
            if calls==2:value["summary_offsets_present"]=1
            return value
        with patch.object(workflow,"read_inventory",side_effect=drift):
            with self.assertRaisesRegex(ValueError,"readiness_preserved_inventory_mismatch"):workflow.run_bounded_readiness(self.args)
        self.assertEqual(calls,2);self.assertFalse(self.args.output_directory.exists())

    def test_earlier_batch_file_is_rechecked_before_publication(self):
        self.prepare(second=True);original=reader.check_decoding;calls=0
        def change(*a,**kw):
            nonlocal calls
            calls+=1;value=original(*a,**kw)
            if calls==2:
                other=self.root/"replacement";other.write_bytes(self.raw.read_bytes());os.replace(other,self.raw)
            return value
        with patch.object(reader,"check_decoding",side_effect=change):report,status=workflow.run_bounded_readiness(self.args)
        self.assertEqual(status,3)
        self.assertEqual(report["recordings"][0]["failure_code"],"file_changed_before_report_publish")
        self.assertIsNone(report["recordings"][0]["stream_integrity"])
        self.assertEqual(report["recordings"][1]["status"],"complete")

    def test_report_destination_cannot_mutate_immutable_registration_file_set(self):
        self.prepare();self.args.output_directory=self.directory/"child"
        with patch.object(workflow,"sha256_stream") as hasher:
            with self.assertRaisesRegex(ValueError,"readiness_output_must_not_change_registration"):workflow.run_bounded_readiness(self.args)
            hasher.assert_not_called()

    def test_exact_resource_boundaries_and_cli_limit_restoration(self):
        import resource
        self.prepare()
        for free,initial in ((workflow.INITIAL_SCRATCH_BYTES,True),(workflow.RUNTIME_SCRATCH_BYTES,False)):
            with patch.object(workflow.shutil,"disk_usage",return_value=SimpleNamespace(free=free)):
                self.assertEqual(workflow._resources(self.root,initial=initial)["scratch_free_bytes"],free)
        before=resource.getrlimit(resource.RLIMIT_AS)
        def bounded(_):
            self.assertLessEqual(resource.getrlimit(resource.RLIMIT_AS)[0],4*1024**3)
            raise ValueError("static test error")
        with patch.object(workflow,"run_bounded_readiness",side_effect=bounded):
            with self.assertRaises(ValueError):cli._bounded_run(SimpleNamespace(command="bounded-readiness"))
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS),before)
