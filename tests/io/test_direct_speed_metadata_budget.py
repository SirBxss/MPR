"""Schema heavy synthetic metadata reproduces the redundant pass failure."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lane_residuals.io import velocity_timing_pilot as pilot
from lane_residuals.io import direct_speed_study as study
from lane_residuals.io.recording_inventory import read_inventory
from tests.io.velocity_timing_fixture import recording, LOG


def schema_heavy_recording():
    from mcap.reader import SeekingReader
    from mcap.writer import Writer, CompressionType
    reader = SeekingReader(BytesIO(recording("NONE")))
    summary = reader.get_summary()
    stream = BytesIO()
    writer = Writer(stream,compression=CompressionType.NONE,chunk_size=1,enable_crcs=True)
    writer.start()
    schemas = {key:writer.register_schema(s.name,s.encoding,s.data) for key,s in summary.schemas.items()}
    for i in range(4):
        writer.register_schema("SyntheticUnused"+str(i),"opaque",bytes([i])*512*1024)
    channels = {key:writer.register_channel(c.topic,c.message_encoding,schemas.get(c.schema_id,0))
        for key,c in summary.channels.items()}
    for _,channel,message in reader.iter_messages():
        writer.add_message(channels[channel.id],message.log_time,message.data,message.publish_time)
    writer.finish()
    return stream.getvalue()


class MetadataBudgetTests(unittest.TestCase):
    def setUp(self):
        try:
            pilot.decoder.check_dependencies()
        except (ImportError,ValueError):
            self.skipTest("optional MCAP extras not installed")
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = schema_heavy_recording()
        self.inventory = read_inventory(BytesIO(self.raw),len(self.raw))
        self.window = (LOG-10**9,LOG+13*10**9)

    def legacy_plan(self, **kwargs):
        return pilot.prepare_window(BytesIO(self.raw),len(self.raw),self.inventory,self.window,self.root,**kwargs)

    def test_validation_reuses_one_decoder_pass_with_original_byte_cost(self):
        baseline = self.legacy_plan()["summary"]["metadata_bytes_read"]
        # Enough for the reviewed inventory/decoder/index plan, but not another
        # complete read of the large unused schema group.
        limit = baseline+1024**2
        with patch.dict(pilot.LIMITS,metadata_read_bytes=limit), \
                patch.object(pilot.decoder,"_decompress",side_effect=AssertionError("payload during planning")):
            prepared = study.prepare(BytesIO(self.raw),len(self.raw),self.inventory,self.window,self.root)
            self.assertEqual(prepared["summary"]["metadata_bytes_read"],baseline)
            self.assertEqual(prepared["summary"]["decoder_schema_pass_count"],1)
            self.assertEqual(len(prepared["summary"]["descriptor_bindings"]),2)
            # This is precisely the old extra traversal. It still fails under
            # that same budget: the fix removed work rather than raising limits.
            meter = prepared["metered"]
            with self.assertRaisesRegex(ValueError,"pilot_read_budget"):
                groups = pilot.decoder._groups(meter,len(self.raw),meter.deadline)
                pilot.decoder._decoders(meter,groups,prepared["selected"],prepared["schemas"],meter.deadline)
        self.assertEqual(pilot.LIMITS["metadata_read_bytes"],128*1024**2)

    def test_insufficient_original_budget_still_fails_without_payload(self):
        baseline = self.legacy_plan()["summary"]["metadata_bytes_read"]
        with patch.dict(pilot.LIMITS,metadata_read_bytes=baseline-1), \
                patch.object(pilot.decoder,"_decompress",side_effect=AssertionError("payload during planning")):
            with self.assertRaisesRegex(ValueError,"pilot_read_budget"):
                study.prepare(BytesIO(self.raw),len(self.raw),self.inventory,self.window,self.root)

    def test_observer_can_refuse_before_indexing_or_payload(self):
        def refuse(*_):
            raise ValueError("synthetic_descriptor_refusal")
        with patch.object(pilot.decoder,"_stage_indexes",side_effect=AssertionError("indexing before descriptor check")), \
                patch.object(pilot.decoder,"_decompress",side_effect=AssertionError("payload during planning")):
            with self.assertRaisesRegex(ValueError,"synthetic_descriptor_refusal"):
                self.legacy_plan(descriptor_observer=refuse)

    def test_default_reader_and_observed_reader_decode_identical_updates(self):
        baseline = self.legacy_plan()
        observed = study.prepare(BytesIO(self.raw),len(self.raw),self.inventory,self.window,self.root)
        baseline_records,baseline_report = pilot.decode_prepared(baseline)
        observed_records,observed_report = pilot.decode_prepared(observed)
        self.assertEqual(baseline_records,observed_records)
        self.assertEqual(len(observed_records),6)
        for key in ("window_chunks","expanded_chunk_bytes","decoded_selected_messages_in_touched_chunks",
                "messages_retained_in_padded_log_window","nonzero_chunk_crcs_checked"):
            self.assertEqual(baseline_report[key],observed_report[key])
