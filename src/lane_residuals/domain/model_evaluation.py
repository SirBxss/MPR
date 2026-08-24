"""Leakage-safe physical-drive evaluation contracts for thesis models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .sequence_dataset import PaddedSequenceDataset, SequenceStandardizer


@dataclass(frozen=True)
class DriveGroupedFold:
    """One leave-one-physical-drive-out development fold."""

    fold_id: str
    held_out_drive_id: str
    training_drive_ids: tuple[str, ...]
    training_sequence_ids: tuple[str, ...]
    test_sequence_ids: tuple[str, ...]
    training_frame_count: int
    test_frame_count: int
    standardizer: SequenceStandardizer

    def __post_init__(self) -> None:
        if not self.fold_id or not self.held_out_drive_id:
            raise ValueError("fold identifiers must be nonempty")
        if (
            not self.training_drive_ids
            or self.held_out_drive_id in self.training_drive_ids
            or len(set(self.training_drive_ids)) != len(self.training_drive_ids)
        ):
            raise ValueError("fold training drives are invalid")
        if not self.training_sequence_ids or not self.test_sequence_ids:
            raise ValueError("fold sequence assignments must be nonempty")
        if set(self.training_sequence_ids) & set(self.test_sequence_ids):
            raise ValueError("fold training and test sequences overlap")
        if self.training_frame_count < 2 or self.test_frame_count < 2:
            raise ValueError("fold frame counts are insufficient")
        if self.standardizer.train_drive_ids != self.training_drive_ids:
            raise ValueError("fold standardizer uses different training drives")
        if self.standardizer.training_frame_count != self.training_frame_count:
            raise ValueError("fold standardizer training count differs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "fold_id": self.fold_id,
            "held_out_drive_id": self.held_out_drive_id,
            "training_drive_ids": list(self.training_drive_ids),
            "training_sequence_ids": list(self.training_sequence_ids),
            "test_sequence_ids": list(self.test_sequence_ids),
            "training_frame_count": self.training_frame_count,
            "test_frame_count": self.test_frame_count,
            "standardizer": self.standardizer.to_dict(),
        }


def build_leave_one_drive_out_folds(
    dataset: PaddedSequenceDataset,
    *,
    primary_drive_ids: Sequence[str],
) -> tuple[DriveGroupedFold, ...]:
    """Build deterministic folds and fit transforms on training drives only."""

    if dataset.standardized:
        raise ValueError("drive folds require a physical-unit dataset")
    drives = tuple(sorted(str(value) for value in primary_drive_ids))
    if len(drives) < 3 or len(set(drives)) != len(drives) or any(not value for value in drives):
        raise ValueError("primary evaluation requires at least three unique drives")
    unknown = sorted(set(drives) - set(dataset.drive_ids.tolist()))
    if unknown:
        raise ValueError(f"unknown primary drive IDs: {unknown}")
    primary = dataset.select_drive_ids(drives)
    all_sequences = set(primary.sequence_ids.tolist())
    folds: list[DriveGroupedFold] = []
    tested_sequences: set[str] = set()
    for held_out in drives:
        training_drives = tuple(value for value in drives if value != held_out)
        training = primary.select_drive_ids(training_drives)
        test = primary.select_drive_ids((held_out,))
        standardizer = SequenceStandardizer.fit(
            primary,
            train_drive_ids=training_drives,
        )
        fold = DriveGroupedFold(
            fold_id=f"hold_out_{held_out}",
            held_out_drive_id=held_out,
            training_drive_ids=training_drives,
            training_sequence_ids=tuple(sorted(training.sequence_ids.tolist())),
            test_sequence_ids=tuple(sorted(test.sequence_ids.tolist())),
            training_frame_count=training.frame_count,
            test_frame_count=test.frame_count,
            standardizer=standardizer,
        )
        folds.append(fold)
        tested_sequences.update(fold.test_sequence_ids)
    if tested_sequences != all_sequences:
        raise ValueError("drive folds do not test every primary sequence exactly once")
    return tuple(folds)


__all__ = ["DriveGroupedFold", "build_leave_one_drive_out_folds"]
