import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from lane_residuals.io.expanded_modeling_dataset import (
    PURPOSE,
    REQUIRED_SOURCE_FILES,
    load_expanded_modeling_dataset,
)
from lane_residuals.io.expanded_sequence_dataset import (
    ExpandedSequenceContractError,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def write_v0131_fixture(directory: Path) -> Path:
    directory.mkdir(parents=True)
    rng = np.random.default_rng(140)
    drive_ids = tuple(f"drive_{index:03d}" for index in range(1, 6))
    clean = drive_ids[:4]
    mixed = drive_ids[4:]
    frame_count_per_drive = 5
    count = len(drive_ids) * frame_count_per_drive
    frame_drives = np.repeat(drive_ids, frame_count_per_drive)
    sequence_ids = np.asarray(
        [f"{drive}_sequence_0001" for drive in frame_drives], dtype=np.str_
    )
    recording_ids = np.asarray(
        [f"recording_{index:03d}" for index in np.repeat(np.arange(1, 6), 5)],
        dtype=np.str_,
    )
    conditions = rng.normal(size=(count, 6))
    coefficients = rng.normal(scale=0.05, size=(6, 21))
    residuals = conditions @ coefficients + rng.normal(scale=0.03, size=(count, 21))
    pair_indices = np.tile(np.arange(frame_count_per_drive), len(drive_ids))
    timestamps = np.concatenate(
        [index * 10_000_000_000 + np.arange(5) * 80_000_000 for index in range(1, 6)]
    )
    basenames = np.asarray(
        [f"private_{drive}.mcap" for drive in frame_drives], dtype=np.str_
    )
    np.savez(
        directory / "expanded_profile_dataset.npz",
        conditions=conditions,
        drive_ids=frame_drives,
        eligibility=np.ones(count, dtype=np.bool_),
        estimate_message_indices=pair_indices + 100,
        exclusion_reasons=np.full(count, "", dtype=np.str_),
        mcap_basenames_private=basenames,
        pair_indices=pair_indices,
        recording_ids=recording_ids,
        residuals_m=residuals,
        sequence_ids=sequence_ids,
        speed_context_left_mcap_basenames_private=np.full(count, "", dtype=np.str_),
        speed_context_odometry_timestamps_ns_json_private=np.full(count, "[]", dtype=np.str_),
        speed_context_right_mcap_basenames_private=np.full(count, "", dtype=np.str_),
        speed_context_states=np.full(count, "recording_local", dtype=np.str_),
        stations_m=np.asarray(CANONICAL_MODEL_STATIONS_M),
        timestamps_ns_private=timestamps,
    )
    with (directory / "sequence_manifest.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("sequence_id", "drive_id", "drive_class", "frame_count"),
        )
        writer.writeheader()
        for drive_id in drive_ids:
            writer.writerow(
                {
                    "sequence_id": f"{drive_id}_sequence_0001",
                    "drive_id": drive_id,
                    "drive_class": (
                        "clean_sensor" if drive_id in clean else "mixed_source_sensor_fragment"
                    ),
                    "frame_count": frame_count_per_drive,
                }
            )
    for name in REQUIRED_SOURCE_FILES - {
        "expanded_profile_dataset.npz",
        "sequence_manifest.csv",
        "expanded_sequence_contract.json",
        "expanded_sequence_manifest.json",
        "expanded_sequence_provenance.json",
        "train_only_standardization_metadata.json",
        "v0130_parity_audit.json",
    }:
        (directory / name).write_bytes(b"fixture\n")
    contract = {
        "version": "0.13.1",
        "purpose": PURPOSE,
        "status": "complete",
        "profile_count": count,
        "sequence_count": len(drive_ids),
        "drive_count": len(drive_ids),
        "clean_drive_ids": list(clean),
        "mixed_source_drive_ids": list(mixed),
        "split_assignments_selected": False,
        "model_training_performed": False,
        "model_hyperparameters_selected": False,
    }
    manifest = {
        "version": "0.13.1",
        "purpose": PURPOSE,
        "status": "complete",
        "profile_count": count,
        "sequence_count": len(drive_ids),
        "archive_sha256": _sha256(directory / "expanded_profile_dataset.npz"),
        "split_assignments_selected": False,
        "model_training_performed": False,
    }
    (directory / "expanded_sequence_contract.json").write_text(
        json.dumps(contract), encoding="utf-8"
    )
    (directory / "expanded_sequence_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (directory / "train_only_standardization_metadata.json").write_text(
        json.dumps({"fitted": False}), encoding="utf-8"
    )
    (directory / "v0130_parity_audit.json").write_text(
        json.dumps({"fixture": True}), encoding="utf-8"
    )
    generated = {
        name: _sha256(directory / name)
        for name in REQUIRED_SOURCE_FILES - {"expanded_sequence_provenance.json"}
    }
    (directory / "expanded_sequence_provenance.json").write_text(
        json.dumps(
            {
                "version": "0.13.1",
                "purpose": PURPOSE,
                "generated_outputs_sha256": generated,
            }
        ),
        encoding="utf-8",
    )
    return directory


class ExpandedModelingDatasetTests(unittest.TestCase):
    def test_loads_primary_and_supplementary_sequences_with_frame_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_v0131_fixture(Path(directory) / "v0131")

            loaded = load_expanded_modeling_dataset(source)

            self.assertEqual(loaded.sequences.sequence_count, 5)
            self.assertEqual(loaded.sequences.frame_count, 25)
            self.assertEqual(loaded.primary.sequence_count, 4)
            self.assertEqual(loaded.primary.frame_count, 20)
            self.assertEqual(loaded.supplementary.sequence_count, 1)
            self.assertEqual(loaded.supplementary.frame_count, 5)
            self.assertTrue(
                np.all(loaded.recording_ids_by_frame[loaded.sequences.time_mask] != "")
            )

    def test_source_hash_change_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_v0131_fixture(Path(directory) / "v0131")
            with (source / "sequence_manifest.csv").open("a", encoding="utf-8") as handle:
                handle.write("changed\n")

            with self.assertRaisesRegex(
                ExpandedSequenceContractError, "provenance mismatch"
            ):
                load_expanded_modeling_dataset(source)


if __name__ == "__main__":
    unittest.main()
