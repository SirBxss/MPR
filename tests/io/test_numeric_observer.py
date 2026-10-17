"""Observation position/failure tests around an actual unchanged ScientificSink."""

from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from lane_residuals.domain.recording_ingestion import RecordingIngestionError
from lane_residuals.io.bounded_recording_readiness import ScientificSink
from lane_residuals.io.numeric_residuals import NumericObserver
from lane_residuals.io.recording_readiness_resources import Observations, Workspace
from tests.io.bounded_readiness_fixture import messages, T


class ObserverTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        observations = Observations()
        self.workspace = Workspace(Path(temporary.name), lambda: None, observations, time.monotonic()+1800)
        self.workspace.__enter__();self.addCleanup(self.workspace.__exit__, None, None, None)
        self.sink = ScientificSink(self.workspace)
        self.observer = NumericObserver(self.sink)
        self.observer.selected = {1: {"topic": "/adp/estimated_drive_paths"}}
        self.message = messages()[0]

    def test_uses_sink_position_and_same_object_once_with_duplicate_source_clocks(self):
        self.sink.geometry.times["estimate"].extend([T, T])
        def staged(channel, log, publish, decoded):
            self.assertIs(decoded, self.message)
            self.assertEqual((channel, log, publish), (1, 4, 5))
            self.sink.geometry.times["estimate"].append(T)
        with patch.object(self.sink, "consume", side_effect=staged) as delegated:
            self.observer.consume(1, 4, 5, self.message)
        delegated.assert_called_once()
        self.assertEqual(self.sink.db.execute("SELECT position,confidence_count FROM numeric_observations").fetchall(), [(2, 40)])

    def test_wrong_append_count_or_clock_never_attaches_to_a_neighbor(self):
        for appended in ([], [T+1], [T, T]):
            with self.subTest(appended=appended):
                self.sink.geometry.times["estimate"].clear()
                with patch.object(self.sink, "consume", side_effect=lambda *a: self.sink.geometry.times["estimate"].extend(appended)):
                    self.observer.consume(1, 4, 5, self.message)
        self.assertEqual(self.sink.db.execute("SELECT count(*) FROM numeric_observations").fetchone()[0], 0)
        self.assertEqual(self.observer.failures, {"numeric_observer_alignment_mismatch": 3})

    def test_missing_clock_is_unavailable_even_if_sink_stages_missing_clock(self):
        self.message.ClearField("time_stamp")
        # Proto3 scalar zero is a real source clock, so use a genuinely absent source accessor.
        with patch("lane_residuals.io.numeric_residuals.source_time_ns_from_message", return_value=None), patch.object(self.sink, "consume", side_effect=lambda *a: self.sink.geometry.times["estimate"].append(None)):
            self.observer.consume(1, 4, 5, self.message)
        self.assertEqual(self.observer.failures, {"numeric_observer_metadata_unavailable": 1})

    def test_one_first_failure_per_message_even_when_alignment_also_fails(self):
        with patch("lane_residuals.io.numeric_residuals._metadata", side_effect=AttributeError()), patch.object(self.sink, "consume"):
            self.observer.consume(1, 4, 5, self.message)
        self.assertEqual(self.observer.failures, {"numeric_observer_metadata_unavailable": 1})

    def test_observer_storage_failure_propagates_without_harmless_counter(self):
        self.sink.db.execute("DROP TABLE numeric_observations")
        with patch.object(self.sink, "consume", side_effect=lambda *a: self.sink.geometry.times["estimate"].append(T)):
            with self.assertRaises(sqlite3.Error):self.observer.consume(1, 4, 5, self.message)
        self.assertEqual(self.observer.failures, {})

    def test_real_sink_exception_is_not_caught_as_metadata_failure(self):
        for error in (MemoryError(), RecordingIngestionError("readiness_processing_time_limit"), sqlite3.OperationalError("full")):
            with patch.object(self.sink, "consume", side_effect=error):
                with self.assertRaises(type(error)):self.observer.consume(1, 4, 5, self.message)
        self.assertEqual(self.observer.failures, {})
