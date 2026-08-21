import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from lane_residuals.io.topology_semantics import (
    INVENTORY_LINEAGE_FILES,
    sha256_file,
    validate_alignment_lineage,
    validate_inventory_lineage,
)


class TopologySemanticsIOTests(unittest.TestCase):
    def _inventory(self, root: Path) -> tuple[Path, dict[str, str]]:
        directory = root / "inventory"
        directory.mkdir()
        for name in INVENTORY_LINEAGE_FILES:
            (directory / name).write_bytes(b"placeholder\n")
        (directory / "corpus_inventory_summary.json").write_text(
            json.dumps({
                "version": "0.12.1", "status": "complete",
                "exact_drive_map_coverage": True, "mcap_file_count": 2,
                "unusable_file_count": 0, "physical_drive_count": 8,
                "provisional_continuous_block_count": 8,
                "rejected_boundary_count": 0, "stitchable_boundary_count": -6,
                "duplicate_count": 0, "empty_file_count": 0,
                "unreadable_file_count": 0,
                "required_topic_schema_failure_count": 0,
            }), encoding="utf-8"
        )
        (directory / "proposed_session_groups.json").write_text(
            json.dumps({"cross_mcap_sequence_stitching_performed": False}),
            encoding="utf-8",
        )
        _, _, hashes = validate_inventory_lineage(directory, expected_file_count=2)
        return directory, hashes

    def _alignment(
        self, root: Path, inventory_hashes: dict[str, str], drive_hash: str
    ) -> Path:
        directory = root / "alignment"
        directory.mkdir()
        contract = {
            "version": "0.5.2",
            "purpose": "exact_manifest_projection_based_reference_alignment_validation",
            "alignment_semantics": "v0.5.0_native_spatial_projection",
            "explicit_ego_pose_motion_compensation_applied": False,
            "source_delta_used_numerically_for_alignment": False,
            "accepted_for_modeling": True,
        }
        summary = {
            **contract, "status": "complete", "resolved_file_count": 2,
            "failed_recording_count": 0, "blockers": [],
            "mutual_nearest_pair_count": 1,
        }
        manifest = {**contract, "status": "complete"}
        (directory / "alignment_batch_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (directory / "batch_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (directory / "alignment_pair_audit.csv").write_text(
            "recording_id,estimate_message_index\nrecording_001,0\n", encoding="utf-8"
        )
        generated = {
            name: sha256_file(directory / name)
            for name in (
                "alignment_batch_summary.json", "batch_manifest.json",
                "alignment_pair_audit.csv",
            )
        }
        source_hashes = {
            "drive_map_private_json": drive_hash,
            **{name: inventory_hashes[name] for name in (
                "corpus_inventory_summary.json", "recording_continuity.csv",
                "proposed_session_groups.json",
            )},
        }
        provenance = {
            **contract, "generated_batch_outputs_sha256": generated,
            "source_files_sha256": source_hashes,
        }
        (directory / "batch_output_provenance.json").write_text(
            json.dumps(provenance), encoding="utf-8"
        )
        return directory

    def test_v052_alignment_and_v0121_inventory_hashes_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, hashes = self._inventory(root)
            drive_hash = hashlib.sha256(b"map").hexdigest()
            alignment = self._alignment(root, hashes, drive_hash)
            manifest, rows, output_hashes = validate_alignment_lineage(
                alignment, expected_file_count=2, inventory_hashes=hashes,
                drive_map_hash=drive_hash,
            )
            self.assertEqual(manifest["version"], "0.5.2")
            self.assertEqual(len(rows), 1)
            self.assertIn("alignment_pair_audit.csv", output_hashes)

            (alignment / "alignment_pair_audit.csv").write_text(
                "recording_id,estimate_message_index\nrecording_001,9\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                validate_alignment_lineage(
                    alignment, expected_file_count=2, inventory_hashes=hashes,
                    drive_map_hash=drive_hash,
                )


if __name__ == "__main__":
    unittest.main()
