"""Build the v0.13.0 quality-gated expanded sensor-topology sequences."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from ..domain.expanded_sequence_dataset import (
    DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS,
    EXPECTED_TOPOLOGY_SOURCE,
    MAXIMUM_ANCHOR_DISTANCE_M,
    PURPOSE,
    VERSION,
    ExpandedProfile,
    ExpandedSequence,
    ProfileEligibilityEvidence,
    SequenceBreakEvidence,
    cross_mcap_stitchable,
    evaluate_profile_eligibility,
    sequence_break_reasons,
    standardization_contract,
)
from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M, ResidualObservation
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from ..io.expanded_sequence_dataset import (
    ExpandedSequenceContractError,
    load_expanded_sequence_inputs,
    residual_profiles_by_pair,
    sha256_file,
    validate_profile_archive,
    write_deterministic_npz,
)
from ..io.odometry import DEFAULT_ODOMETRY_TOPIC
from ..io.reports import write_csv_rows, write_strict_json
from .conditional_features import (
    DEFAULT_ESTIMATE_TOPIC,
    ODOMETRY_SPEED_SOURCE,
    ManifestRecording,
    _extract_recording_features,
    _resolve_mcap_files,
)


LOGGER = logging.getLogger(__name__)
DEFAULT_MAXIMUM_ODOMETRY_INTERPOLATION_GAP_MS = 50.0

PROFILE_AUDIT_FIELDS = (
    "recording_id", "drive_id", "mcap_basename_private", "pair_index",
    "estimate_message_index", "estimate_source_time_ns_private",
    "topology_source_name", "h100_aligned_eligible", "station_count",
    "anchor_distance_m", "anchor_heading_delta_rad", "estimator_state",
    "estimate_geometry_state", "estimate_geometry_failure_code",
    "map_geometry_state", "map_geometry_failure_code", "feature_state",
    "finite_residuals", "finite_features", "profile_eligible", "exclusion_reasons",
    "sequence_id",
)
SEQUENCE_MANIFEST_FIELDS = (
    "sequence_id", "drive_id", "drive_class", "start_reasons", "frame_count",
    "recording_count", "mcap_count", "recording_ids_json", "mcap_basenames_json_private",
    "first_timestamp_ns_private", "last_timestamp_ns_private", "duration_s",
    "crosses_mcap", "minimum_interval_ms", "median_interval_ms", "maximum_interval_ms",
)
DRIVE_SUMMARY_FIELDS = (
    "drive_id", "drive_class", "recording_count", "candidate_message_count",
    "eligible_profile_count", "excluded_profile_count", "sequence_count",
    "cross_mcap_sequence_count", "stitched_boundary_count", "topology_source_counts_json",
    "exclusion_reason_counts_json", "anchor_distance_q50_m", "anchor_distance_q95_m",
    "anchor_distance_max_m", "absolute_anchor_heading_q50_rad",
    "absolute_anchor_heading_q95_rad", "absolute_anchor_heading_max_rad",
)
STITCH_FIELDS = (
    "drive_id", "left_recording_id", "right_recording_id",
    "left_mcap_basename_private", "right_mcap_basename_private",
    "inventory_boundary_accepted", "left_endpoint_sensor_h100",
    "right_endpoint_sensor_h100", "immediately_eligible_boundary_candidate",
    "left_endpoint_profile_eligible", "right_endpoint_profile_eligible",
    "timestamp_gap_ms", "timestamp_continuity_passes", "stitched",
    "rejection_reasons",
)
EXCLUSION_FIELDS = ("exclusion_reason", "profile_count", "recording_count", "drive_count")


def _strict_bool(value: Any) -> bool:
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ExpandedSequenceContractError(f"strict boolean required, got {value!r}")


def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _quantile(values: Sequence[float], q: float) -> float | None:
    return None if not values else float(np.quantile(np.asarray(values), q))


def _ensure_empty(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError(f"output directory must be new and empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _feature_rows(
    *,
    mcap_inputs: Sequence[Path],
    manifest: Mapping[str, Any],
    pair_rows: Sequence[Mapping[str, Any]],
    profiles: Mapping[tuple[str, int], np.ndarray],
    estimate_topic: str,
    odometry_topic: str,
    maximum_odometry_gap_ns: int,
    max_step_m: float,
) -> tuple[dict[tuple[str, int], dict[str, Any]], Counter[str]]:
    resolved = _resolve_mcap_files(mcap_inputs)
    pairs_by_key = {
        (row["recording_id"], int(row["pair_index"])): row for row in pair_rows
    }
    observations: dict[str, list[ResidualObservation]] = defaultdict(list)
    recordings: list[ManifestRecording] = []
    manifest_basenames: set[str] = set()
    for raw in manifest["recordings"]:
        recording_id, drive_id = raw["recording_id"], raw["drive_id"]
        basename = raw["mcap_filename_private"]
        path = resolved.get(basename)
        if path is None:
            raise FileNotFoundError(f"manifest MCAP not resolved: {basename}")
        recordings.append(ManifestRecording(recording_id, drive_id, basename, path))
        manifest_basenames.add(basename)
    if set(resolved) != manifest_basenames:
        raise ExpandedSequenceContractError("raw MCAP inputs differ from exact manifest")
    for key, residuals in profiles.items():
        row = pairs_by_key.get(key)
        if row is None:
            raise ExpandedSequenceContractError(f"H100 station profile lacks pair row: {key}")
        observations[key[0]].append(
            ResidualObservation(
                recording_id=key[0], drive_id=row["drive_id"],
                pair_index=int(row["pair_index"]),
                estimate_message_index=int(row["estimate_message_index"]),
                map_message_index=int(row["map_message_index"]),
                estimate_source_time_ns_private=int(row["estimate_source_time_ns_private"]),
                map_source_time_ns_private=int(row["map_source_time_ns_private"]),
                source_delta_ms=float(row["source_delta_ms"]), residuals_m=residuals,
            )
        )
    feature_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    failures: Counter[str] = Counter()
    for index, recording in enumerate(recordings, 1):
        LOGGER.info("extracting v0.9 conditions %d/%d: %s", index, len(recordings), recording.recording_id)
        result = _extract_recording_features(
            recording, observations.get(recording.recording_id, ()),
            estimate_topic=estimate_topic, speed_source=ODOMETRY_SPEED_SOURCE,
            speed_topic="", odometry_topic=odometry_topic,
            maximum_speed_interpolation_gap_ns=0,
            maximum_odometry_interpolation_gap_ns=maximum_odometry_gap_ns,
            max_step_m=max_step_m,
        )
        failures.update(result.failure_counts)
        for row in result.rows:
            feature_by_key[(row["recording_id"], int(row["pair_index"]))] = row
    return feature_by_key, failures


def _make_audit_rows(
    messages: Sequence[Mapping[str, Any]],
    residual_profiles: Mapping[tuple[str, int], np.ndarray],
    features: Mapping[tuple[str, int], Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, int], ExpandedProfile]]:
    audit_rows: list[dict[str, Any]] = []
    eligible: dict[tuple[str, int], ExpandedProfile] = {}
    for message in messages:
        pair_raw = message.get("pair_index", "")
        pair_index = int(pair_raw) if pair_raw != "" else -1
        key = (message["recording_id"], pair_index)
        residuals = residual_profiles.get(key)
        feature = features.get(key)
        condition_values = None
        if feature is not None and feature.get("feature_state") == "ready":
            condition_values = np.asarray([float(feature[name]) for name in BMW_CONDITION_FEATURE_NAMES])
        anchor = _optional_float(message.get("anchor_distance_m"))
        heading = _optional_float(message.get("anchor_heading_delta_rad"))
        source_delta = _optional_float(message.get("source_delta_ms"))
        evidence = ProfileEligibilityEvidence(
            topology_source_name=message["topology_source_name"],
            h100_aligned_eligible=_strict_bool(message["h100_aligned_eligible"]),
            station_grid_m=(CANONICAL_MODEL_STATIONS_M if residuals is not None else ()),
            residuals_m=(residuals if residuals is not None else ()),
            anchor_distance_m=anchor, anchor_heading_delta_rad=heading,
            source_delta_ms=source_delta, estimator_state=message["estimator_state"],
            estimate_geometry_state=message.get("estimate_geometry_state", ""),
            estimate_geometry_failure_code=message.get("estimate_geometry_failure_code") or None,
            map_geometry_state=message.get("map_geometry_state", ""),
            map_geometry_failure_code=message.get("map_geometry_failure_code") or None,
            feature_state=("not_ready" if feature is None else feature["feature_state"]),
            features=condition_values,
        )
        result = evaluate_profile_eligibility(evidence)
        row = {
            "recording_id": message["recording_id"], "drive_id": message["drive_id"],
            "mcap_basename_private": message["mcap_basename_private"],
            "pair_index": pair_raw, "estimate_message_index": message["message_index"],
            "estimate_source_time_ns_private": message["source_time_ns_private"],
            "topology_source_name": message["topology_source_name"],
            "h100_aligned_eligible": message["h100_aligned_eligible"],
            "station_count": 0 if residuals is None else len(residuals),
            "anchor_distance_m": anchor, "anchor_heading_delta_rad": heading,
            "estimator_state": message["estimator_state"],
            "estimate_geometry_state": message.get("estimate_geometry_state"),
            "estimate_geometry_failure_code": message.get("estimate_geometry_failure_code"),
            "map_geometry_state": message.get("map_geometry_state"),
            "map_geometry_failure_code": message.get("map_geometry_failure_code"),
            "feature_state": "not_ready" if feature is None else feature["feature_state"],
            "finite_residuals": residuals is not None and np.all(np.isfinite(residuals)),
            "finite_features": condition_values is not None and np.all(np.isfinite(condition_values)),
            "profile_eligible": result.eligible,
            "exclusion_reasons": ";".join(result.exclusion_reasons), "sequence_id": "",
        }
        audit_rows.append(row)
        if result.eligible:
            assert residuals is not None and condition_values is not None
            eligible[key] = ExpandedProfile(
                recording_id=message["recording_id"], drive_id=message["drive_id"],
                mcap_basename_private=message["mcap_basename_private"],
                pair_index=pair_index, estimate_message_index=int(message["message_index"]),
                estimate_source_time_ns_private=int(message["source_time_ns_private"]),
                topology_source_name=message["topology_source_name"],
                anchor_distance_m=float(anchor), anchor_heading_delta_rad=float(heading),
                residuals_m=residuals, conditions=condition_values,
            )
    return audit_rows, eligible


def _build_sequences_and_stitch_audit(
    audit_rows: list[dict[str, Any]],
    eligible: Mapping[tuple[str, int], ExpandedProfile],
    continuity_rows: Sequence[Mapping[str, Any]],
    *,
    maximum_gap_ms: float,
) -> tuple[list[ExpandedSequence], list[dict[str, Any]]]:
    continuity = {
        (row["left_recording_id"], row["right_recording_id"]): row
        for row in continuity_rows
    }
    by_recording: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in audit_rows:
        by_recording[row["recording_id"]].append(row)
    stitch_rows: list[dict[str, Any]] = []
    for (left_id, right_id), boundary in continuity.items():
        left, right = by_recording[left_id][-1], by_recording[right_id][0]
        left_pre = left["topology_source_name"] == EXPECTED_TOPOLOGY_SOURCE and _strict_bool(left["h100_aligned_eligible"])
        right_pre = right["topology_source_name"] == EXPECTED_TOPOLOGY_SOURCE and _strict_bool(right["h100_aligned_eligible"])
        left_ok, right_ok = bool(left["profile_eligible"]), bool(right["profile_eligible"])
        gap_ns = int(right["estimate_source_time_ns_private"]) - int(left["estimate_source_time_ns_private"])
        evidence = SequenceBreakEvidence(
            same_physical_drive=left["drive_id"] == right["drive_id"],
            topology_source_changed=left["topology_source_name"] != right["topology_source_name"],
            previous_eligible=left_ok, current_eligible=right_ok,
            current_anchor_gate_failed="anchor_distance_exceeds_1m" in right["exclusion_reasons"],
            timestamp_gap_ns=gap_ns, crosses_mcap_boundary=True,
            mcap_boundary_accepted=_strict_bool(boundary["stitchable"]),
        )
        stitched = cross_mcap_stitchable(evidence, maximum_contiguous_gap_ms=maximum_gap_ms)
        stitch_rows.append({
            "drive_id": left["drive_id"], "left_recording_id": left_id,
            "right_recording_id": right_id,
            "left_mcap_basename_private": left["mcap_basename_private"],
            "right_mcap_basename_private": right["mcap_basename_private"],
            "inventory_boundary_accepted": boundary["stitchable"],
            "left_endpoint_sensor_h100": left_pre, "right_endpoint_sensor_h100": right_pre,
            "immediately_eligible_boundary_candidate": left_pre and right_pre,
            "left_endpoint_profile_eligible": left_ok, "right_endpoint_profile_eligible": right_ok,
            "timestamp_gap_ms": gap_ns / 1e6,
            "timestamp_continuity_passes": 0 < gap_ns <= maximum_gap_ms * 1e6,
            "stitched": stitched,
            "rejection_reasons": ";".join(sequence_break_reasons(evidence, maximum_contiguous_gap_ms=maximum_gap_ms)),
        })

    boundary_by_pair = {(row["left_recording_id"], row["right_recording_id"]): row for row in stitch_rows}
    sequences: list[ExpandedSequence] = []
    active: list[ExpandedProfile] = []
    active_reasons: tuple[str, ...] = ("physical_drive_start",)
    drive_sequence_counts: Counter[str] = Counter()
    previous_row: dict[str, Any] | None = None

    def close() -> None:
        nonlocal active
        if not active:
            return
        drive = active[0].drive_id
        drive_sequence_counts[drive] += 1
        sequence_id = f"{drive}_sequence_{drive_sequence_counts[drive]:04d}"
        sequence = ExpandedSequence(sequence_id, drive, active_reasons, tuple(active))
        sequences.append(sequence)
        for frame in active:
            # keys are unique because every message/pair is recording-local.
            next(row for row in audit_rows if row["recording_id"] == frame.recording_id and str(row["pair_index"]) == str(frame.pair_index))["sequence_id"] = sequence_id
        active = []

    for row in audit_rows:
        key = (row["recording_id"], int(row["pair_index"])) if row["pair_index"] != "" else None
        profile = None if key is None else eligible.get(key)
        reasons: tuple[str, ...] = ()
        if previous_row is not None:
            crosses = row["recording_id"] != previous_row["recording_id"]
            boundary = boundary_by_pair.get((previous_row["recording_id"], row["recording_id"])) if crosses else None
            gap_ns = int(row["estimate_source_time_ns_private"]) - int(previous_row["estimate_source_time_ns_private"])
            evidence = SequenceBreakEvidence(
                same_physical_drive=row["drive_id"] == previous_row["drive_id"],
                topology_source_changed=row["topology_source_name"] != previous_row["topology_source_name"],
                previous_eligible=bool(previous_row["profile_eligible"]),
                current_eligible=bool(row["profile_eligible"]),
                current_anchor_gate_failed="anchor_distance_exceeds_1m" in row["exclusion_reasons"],
                timestamp_gap_ns=gap_ns, crosses_mcap_boundary=crosses,
                mcap_boundary_accepted=(None if not crosses else boundary is not None and _strict_bool(boundary["inventory_boundary_accepted"])),
            )
            reasons = sequence_break_reasons(evidence, maximum_contiguous_gap_ms=maximum_gap_ms)
        if reasons:
            close()
        if profile is not None:
            if not active:
                active_reasons = reasons or (("physical_drive_start",) if previous_row is None or row["drive_id"] != previous_row["drive_id"] else ("eligible_run_start",))
            active.append(profile)
        previous_row = row
    close()
    return sequences, stitch_rows


def run_expanded_sequence_dataset(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Build physical-unit profiles and quality-gated session sequences."""

    maximum_gap_ms = float(arguments.maximum_contiguous_gap_ms)
    odometry_gap_ms = float(arguments.maximum_odometry_interpolation_gap_ms)
    if not math.isfinite(maximum_gap_ms) or maximum_gap_ms <= 0:
        raise ValueError("maximum-contiguous-gap-ms must be finite and positive")
    if not math.isfinite(odometry_gap_ms) or odometry_gap_ms < 0:
        raise ValueError("maximum-odometry-interpolation-gap-ms must be finite and nonnegative")
    inputs = load_expanded_sequence_inputs(
        alignment_directory=arguments.alignment_directory,
        topology_audit_directory=arguments.topology_audit_directory,
        expected_file_count=arguments.expected_file_count,
    )
    residual_profiles = residual_profiles_by_pair(inputs.station_rows)
    features, feature_failures = _feature_rows(
        mcap_inputs=arguments.mcap, manifest=inputs.alignment_manifest,
        pair_rows=inputs.alignment_pair_rows, profiles=residual_profiles,
        estimate_topic=arguments.estimate_topic, odometry_topic=arguments.odometry_topic,
        maximum_odometry_gap_ns=int(round(odometry_gap_ms * 1e6)),
        max_step_m=arguments.max_step_m,
    )
    audit_rows, eligible = _make_audit_rows(
        inputs.topology_message_rows, residual_profiles, features
    )
    sequences, stitch_rows = _build_sequences_and_stitch_audit(
        audit_rows, eligible, inputs.continuity_rows, maximum_gap_ms=maximum_gap_ms
    )
    _ensure_empty(arguments.output_directory)

    sequence_rows = []
    for sequence in sequences:
        timestamps = np.asarray([frame.estimate_source_time_ns_private for frame in sequence.frames], dtype=np.int64)
        intervals = np.diff(timestamps).astype(float) / 1e6
        recordings = list(dict.fromkeys(frame.recording_id for frame in sequence.frames))
        mcaps = list(dict.fromkeys(frame.mcap_basename_private for frame in sequence.frames))
        sequence_rows.append({
            "sequence_id": sequence.sequence_id, "drive_id": sequence.drive_id,
            "drive_class": "clean_sensor" if sequence.drive_id in {"drive_001", "drive_002", "drive_003", "drive_004"} else "mixed_source_sensor_fragment",
            "start_reasons": ";".join(sequence.start_reasons), "frame_count": sequence.length,
            "recording_count": len(recordings), "mcap_count": len(mcaps),
            "recording_ids_json": json.dumps(recordings, separators=(",", ":")),
            "mcap_basenames_json_private": json.dumps(mcaps, separators=(",", ":")),
            "first_timestamp_ns_private": int(timestamps[0]), "last_timestamp_ns_private": int(timestamps[-1]),
            "duration_s": (timestamps[-1] - timestamps[0]) / 1e9,
            "crosses_mcap": sequence.crosses_mcap,
            "minimum_interval_ms": None if not len(intervals) else float(np.min(intervals)),
            "median_interval_ms": None if not len(intervals) else float(np.median(intervals)),
            "maximum_interval_ms": None if not len(intervals) else float(np.max(intervals)),
        })

    drive_rows = []
    for drive in sorted({row["drive_id"] for row in audit_rows}):
        rows = [row for row in audit_rows if row["drive_id"] == drive]
        selected = [row for row in rows if row["profile_eligible"]]
        drive_sequences = [sequence for sequence in sequences if sequence.drive_id == drive]
        anchors = [float(row["anchor_distance_m"]) for row in selected]
        headings = [abs(float(row["anchor_heading_delta_rad"])) for row in selected]
        reasons = Counter(reason for row in rows for reason in row["exclusion_reasons"].split(";") if reason)
        drive_rows.append({
            "drive_id": drive,
            "drive_class": "clean_sensor" if drive in {"drive_001", "drive_002", "drive_003", "drive_004"} else "mixed_source_sensor_fragment",
            "recording_count": len({row["recording_id"] for row in rows}),
            "candidate_message_count": len(rows), "eligible_profile_count": len(selected),
            "excluded_profile_count": len(rows) - len(selected), "sequence_count": len(drive_sequences),
            "cross_mcap_sequence_count": sum(sequence.crosses_mcap for sequence in drive_sequences),
            "stitched_boundary_count": sum(_strict_bool(row["stitched"]) for row in stitch_rows if row["drive_id"] == drive),
            "topology_source_counts_json": json.dumps(dict(sorted(Counter(row["topology_source_name"] for row in rows).items())), separators=(",", ":")),
            "exclusion_reason_counts_json": json.dumps(dict(sorted(reasons.items())), separators=(",", ":")),
            "anchor_distance_q50_m": _quantile(anchors, .5), "anchor_distance_q95_m": _quantile(anchors, .95),
            "anchor_distance_max_m": None if not anchors else max(anchors),
            "absolute_anchor_heading_q50_rad": _quantile(headings, .5),
            "absolute_anchor_heading_q95_rad": _quantile(headings, .95),
            "absolute_anchor_heading_max_rad": None if not headings else max(headings),
        })

    all_reasons = sorted({reason for row in audit_rows for reason in row["exclusion_reasons"].split(";") if reason})
    exclusion_rows = [
        {
            "exclusion_reason": reason,
            "profile_count": sum(reason in row["exclusion_reasons"].split(";") for row in audit_rows),
            "recording_count": len({row["recording_id"] for row in audit_rows if reason in row["exclusion_reasons"].split(";")}),
            "drive_count": len({row["drive_id"] for row in audit_rows if reason in row["exclusion_reasons"].split(";")}),
        }
        for reason in all_reasons
    ]

    profiles = [frame for sequence in sequences for frame in sequence.frames]
    arrays = {
        "residuals_m": np.stack([frame.residuals_m for frame in profiles]),
        "conditions": np.stack([frame.conditions for frame in profiles]),
        "timestamps_ns_private": np.asarray([frame.estimate_source_time_ns_private for frame in profiles], dtype=np.int64),
        "recording_ids": np.asarray([frame.recording_id for frame in profiles]),
        "drive_ids": np.asarray([frame.drive_id for frame in profiles]),
        "mcap_basenames_private": np.asarray([frame.mcap_basename_private for frame in profiles]),
        "sequence_ids": np.asarray([sequence.sequence_id for sequence in sequences for _ in sequence.frames]),
        "pair_indices": np.asarray([frame.pair_index for frame in profiles], dtype=np.int64),
        "estimate_message_indices": np.asarray([frame.estimate_message_index for frame in profiles], dtype=np.int64),
        "stations_m": np.asarray(CANONICAL_MODEL_STATIONS_M, dtype=np.float64),
        "eligibility": np.ones(len(profiles), dtype=np.bool_),
        "exclusion_reasons": np.asarray(["" for _ in profiles]),
    }
    archive = arguments.output_directory / "expanded_profile_dataset.npz"
    write_deterministic_npz(archive, arrays)
    validate_profile_archive(archive)
    write_csv_rows(arguments.output_directory / "profile_eligibility_audit.csv", PROFILE_AUDIT_FIELDS, audit_rows)
    write_csv_rows(arguments.output_directory / "sequence_manifest.csv", SEQUENCE_MANIFEST_FIELDS, sequence_rows)
    write_csv_rows(arguments.output_directory / "sequence_summary_by_drive.csv", DRIVE_SUMMARY_FIELDS, drive_rows)
    write_csv_rows(arguments.output_directory / "cross_mcap_stitching_audit.csv", STITCH_FIELDS, stitch_rows)
    write_csv_rows(arguments.output_directory / "exclusion_reason_summary.csv", EXCLUSION_FIELDS, exclusion_rows)

    immediate_count = sum(_strict_bool(row["immediately_eligible_boundary_candidate"]) for row in stitch_rows)
    summary = {
        "version": VERSION, "purpose": PURPOSE, "status": "complete", "blockers": [],
        "profile_count": len(profiles), "candidate_message_count": len(audit_rows),
        "excluded_message_count": len(audit_rows) - len(profiles), "sequence_count": len(sequences),
        "recording_count": len({frame.recording_id for frame in profiles}),
        "drive_count": len({frame.drive_id for frame in profiles}),
        "clean_drive_ids": ["drive_001", "drive_002", "drive_003", "drive_004"],
        "mixed_source_drive_ids": ["drive_005", "drive_006", "drive_007", "drive_008"],
        "profile_eligibility": {
            "required_topology_source": EXPECTED_TOPOLOGY_SOURCE,
            "h100_required": True, "exact_station_count": 21,
            "station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
            "maximum_anchor_distance_m_inclusive": MAXIMUM_ANCHOR_DISTANCE_M,
            "anchor_distance_rule_basis": "pre_model_geometric_validity_not_model_performance",
            "anchor_heading_threshold_applied": False,
            "valid_estimator_and_geometry_required": True, "finite_values_required": True,
        },
        "recording_038_h100_anchor_gate_exclusion_count": sum(
            row["recording_id"] == "recording_038" and _strict_bool(row["h100_aligned_eligible"])
            and "anchor_distance_exceeds_1m" in row["exclusion_reasons"] for row in audit_rows
        ),
        "maximum_contiguous_gap_ms": maximum_gap_ms,
        "cross_mcap_boundary_count": len(stitch_rows),
        "immediately_eligible_cross_mcap_boundary_candidate_count": immediate_count,
        "independently_reconciles_expected_candidate_count_17": immediate_count == 17,
        "stitched_cross_mcap_boundary_count": sum(_strict_bool(row["stitched"]) for row in stitch_rows),
        "standardization": standardization_contract(),
        "split_assignments_selected": False, "model_hyperparameters_selected": False,
        "model_training_performed": False,
        "feature_contract": {"schema": "bmw_condition_schema_v1", "names": list(BMW_CONDITION_FEATURE_NAMES), "shape": [len(profiles), 6]},
        "residual_contract": {"shape": [len(profiles), 21], "stations_m": list(CANONICAL_MODEL_STATIONS_M)},
        "feature_extraction": {
            "speed_source": ODOMETRY_SPEED_SOURCE,
            "maximum_odometry_interpolation_gap_ms": odometry_gap_ms,
            "recording_local": True, "cross_mcap_feature_extraction": False,
            "failure_counts": dict(sorted(feature_failures.items())),
        },
        "source_files_sha256": inputs.source_files_sha256,
    }
    write_strict_json(arguments.output_directory / "expanded_sequence_contract.json", summary)
    return summary, 0


__all__ = [
    "DRIVE_SUMMARY_FIELDS", "EXCLUSION_FIELDS", "PROFILE_AUDIT_FIELDS",
    "SEQUENCE_MANIFEST_FIELDS", "STITCH_FIELDS", "run_expanded_sequence_dataset",
]
