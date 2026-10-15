from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from lane_residuals.io import recording_readiness_resources as resources


class ReadinessResourcesTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)

    def workspace(self,deadline=None):
        return resources.Workspace(self.root,lambda:None,resources.Observations(),time.monotonic()+60 if deadline is None else deadline)

    def test_exact_pragmas_and_exactly_two_owned_files(self):
        resources.check_configuration(self.root)
        self.assertEqual(list(self.root.iterdir()),[])
        with self.workspace() as workspace:
            self.assertEqual({p.name for p in workspace.directory.iterdir()},{"index.sqlite","science.sqlite"})
            for connection in (workspace.index,workspace.science):
                expected={"journal_mode":"off","synchronous":0,"temp_store":2,"mmap_size":0,"page_size":4096,"cache_size":-8192}
                for key,value in expected.items():self.assertEqual(connection.execute("PRAGMA "+key).fetchone()[0],value)
                connection.execute("CREATE TABLE test (value)");connection.execute("INSERT INTO test VALUES (1)")
            workspace.checkpoint()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_sidecar_failure_even_when_main_databases_are_small_and_cleanup(self):
        with self.assertRaisesRegex(ValueError,"readiness_unexpected_scratch_file"):
            with self.workspace() as workspace:
                (workspace.directory/"science.sqlite-wal").write_bytes(b"not allowed")
                workspace.checkpoint()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_allocated_main_and_combined_byte_limits_are_checked(self):
        with self.workspace() as workspace:
            workspace.science.execute("CREATE TABLE test (value)")
            with patch.object(resources,"MAX_SCIENCE_BYTES",1):
                with self.assertRaisesRegex(ValueError,"readiness_database_limit"):workspace.checkpoint()
            with patch.object(resources,"MAX_COMBINED_BYTES",1):
                with self.assertRaisesRegex(ValueError,"readiness_database_limit"):workspace.checkpoint()

    def test_shared_deadline_and_low_resource_callback_stop_then_cleanup(self):
        with self.assertRaisesRegex(ValueError,"readiness_processing_time_limit"):
            with self.workspace(time.monotonic()-1):pass
        with self.workspace() as workspace:
            workspace.resource_check=lambda:(_ for _ in ()).throw(MemoryError())
            with self.assertRaises(MemoryError):workspace.checkpoint()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_preflight_configuration_is_verified_not_only_requested(self):
        class Unsupported:
            def execute(self,*_):return self
            def fetchone(self):return ("wal",)
        with self.assertRaisesRegex(ValueError,"readiness_sqlite_configuration_unsupported"):
            resources.configure(Unsupported(),resources.MAX_SCIENCE_BYTES)

    def test_sqlite_memory_or_full_failures_use_static_codes(self):
        self.assertEqual(resources.scientific_failure(sqlite3.OperationalError("out of memory PRIVATE")),"memory_limit")
        self.assertEqual(resources.scientific_failure(sqlite3.OperationalError("database or disk is full PRIVATE")),"readiness_database_limit")
        self.assertEqual(resources.scientific_failure(MemoryError()),"memory_limit")

    def test_nonoverlapping_phases_null_unentered_and_checkpoint_rss(self):
        obs=resources.Observations()
        with patch.object(resources.time,"monotonic",side_effect=(1.,3.,8.)),patch.object(resources,"_snapshot",side_effect=({"process_resident_memory_bytes":10},{"process_resident_memory_bytes":20},{"process_resident_memory_bytes":15})):
            obs.phase("raw_hash");obs.phase("fresh_summary");summary=obs.summary()
        self.assertEqual(summary["elapsed_seconds"]["raw_hash"],2.)
        self.assertEqual(summary["elapsed_seconds"]["fresh_summary"],5.)
        self.assertIsNone(summary["elapsed_seconds"]["selected_decode"])
        self.assertEqual(summary["peak_resident_memory_bytes"],20)
