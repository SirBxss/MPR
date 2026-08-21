import argparse
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lane_residuals.domain.corpus_inventory import McapInventoryRecord, TopicCompatibility
from lane_residuals.workflows.corpus_inventory import load_drive_map_pairs, run_corpus_inventory


NAMES = (
    "2025-05-27_12-00-00_2025-05-27_12-00-20_MCAP_000307.mcap",
    "2025-05-27_12-00-20_2025-05-27_12-00-40_MCAP_000398.mcap",
)


def _compatible_topics() -> tuple[TopicCompatibility, ...]:
    return tuple(
        TopicCompatibility(
            role=role,
            topic=topic,
            expected_schema_name=schema,
            present=True,
            message_count=10,
            schema_names=(schema,),
            schema_encodings=("protobuf",),
            message_encodings=("protobuf",),
        )
        for role, topic, schema in (
            ("estimate", "/adp/estimated_drive_paths", "Adp.Perception.EstimatedDrivePaths"),
            ("map", "/adp/road_lane_map_based", "Adp.Perception.Road"),
            ("odometry", "/adp/odometry", "Adp.OdometryState"),
        )
    )


def _fake_inspection(path: Path, *, root: Path, recording_id: str, drive_id: str | None, **_):
    index = NAMES.index(path.name)
    source_start = 1_000_000_000 if index == 0 else 2_080_000_000
    source_end = 2_000_000_000 if index == 0 else 3_080_000_000
    internal_start = 1_000_000_000 if index == 0 else 2_010_000_000
    internal_end = 2_000_000_000 if index == 0 else 3_010_000_000
    return McapInventoryRecord(
        path=str(path.resolve()),
        basename=path.name,
        relative_path=str(path.resolve().relative_to(root.resolve())),
        recording_id=recording_id,
        drive_id=drive_id,
        file_size_bytes=path.stat().st_size,
        sha256=f"{index + 1:064x}",
        readable=True,
        empty=False,
        internal_start_log_time_ns=internal_start,
        internal_end_log_time_ns=internal_end,
        first_estimate_source_time_ns=source_start,
        last_estimate_source_time_ns=source_end,
        estimate_source_timestamp_count=10,
        estimate_missing_source_timestamp_count=0,
        estimate_source_timestamps_strictly_increasing=True,
        filename_start=f"2025-05-27T12:00:{index * 20:02d}",
        filename_end=f"2025-05-27T12:00:{(index + 1) * 20:02d}",
        filename_duration_ms=20_000.0,
        mcap_identifier=(307, 398)[index],
        filename_internal_time_disagreement=True,
        topics=_compatible_topics(),
        failure_codes=("filename_internal_duration_disagreement",),
    )


class CorpusInventoryWorkflowTests(unittest.TestCase):
    @staticmethod
    def _fixture(root: Path) -> tuple[Path, Path]:
        corpus = root / "corpus"
        (corpus / "nested").mkdir(parents=True)
        (corpus / NAMES[0]).write_bytes(b"first")
        (corpus / "nested" / NAMES[1]).write_bytes(b"second")
        drive_map = root / "sessions.private.json"
        drive_map.write_text(
            json.dumps({NAMES[0]: "physical-secret", NAMES[1]: "physical-secret"}),
            encoding="utf-8",
        )
        return corpus, drive_map

    def test_duplicate_json_keys_are_preserved_for_exact_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.json"
            path.write_text('{"a.mcap": "one", "a.mcap": "two"}', encoding="utf-8")
            self.assertEqual(
                load_drive_map_pairs(path),
                (("a.mcap", "one"), ("a.mcap", "two")),
            )

    def test_outputs_are_deterministic_and_identifier_jump_does_not_reject(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, drive_map = self._fixture(root)
            outputs = (root / "out-a", root / "out-b")
            summaries = []
            with patch(
                "lane_residuals.workflows.corpus_inventory.inspect_mcap_for_inventory",
                side_effect=_fake_inspection,
            ):
                for output in outputs:
                    summary, status = run_corpus_inventory(
                        argparse.Namespace(
                            mcap_root=corpus,
                            drive_map=drive_map,
                            output_directory=output,
                            maximum_source_gap_ms=200.0,
                        )
                    )
                    self.assertEqual(status, 0)
                    summaries.append(summary)
            expected = {
                "mcap_inventory.csv",
                "topic_compatibility.csv",
                "recording_continuity.csv",
                "proposed_session_groups.json",
                "corpus_inventory_summary.json",
                "corpus_inventory_diagnostics.png",
            }
            self.assertEqual({path.name for path in outputs[0].iterdir()}, expected)
            self.assertEqual(summaries[0], summaries[1])
            for name in expected:
                self.assertEqual((outputs[0] / name).read_bytes(), (outputs[1] / name).read_bytes())
            self.assertEqual(summaries[0]["provisional_continuous_block_count"], 1)
            self.assertEqual(summaries[0]["stitchable_boundary_count"], 1)
            with (outputs[0] / "mcap_inventory.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                inventory_rows = list(csv.DictReader(handle))
            self.assertEqual(
                inventory_rows[0]["failure_codes"],
                "filename_internal_duration_disagreement",
            )
            self.assertEqual(inventory_rows[0]["exclusion_codes"], "")

    def test_missing_drive_map_entry_writes_fail_closed_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, drive_map = self._fixture(root)
            drive_map.write_text(json.dumps({NAMES[0]: "physical-secret"}), encoding="utf-8")
            output = root / "out"
            with patch(
                "lane_residuals.workflows.corpus_inventory.inspect_mcap_for_inventory",
                side_effect=_fake_inspection,
            ):
                summary, status = run_corpus_inventory(
                    argparse.Namespace(
                        mcap_root=corpus,
                        drive_map=drive_map,
                        output_directory=output,
                        maximum_source_gap_ms=200.0,
                    )
                )
            self.assertEqual(status, 3)
            self.assertEqual(summary["status"], "incomplete")
            self.assertFalse(summary["exact_drive_map_coverage"])
            self.assertEqual(summary["drive_map_coverage_failures"]["missing_basenames"], [NAMES[1]])
            self.assertTrue((output / "mcap_inventory.csv").is_file())


if __name__ == "__main__":
    unittest.main()
