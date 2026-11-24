"""One-frame recorded input preflight with a private reproducibility receipt."""

from __future__ import annotations

import os
from pathlib import Path

from ..domain.artifact_registry import RegistryError, require
from ..domain.geometry_validation import GeometryValidationError
from ..io import artifact_registry as registry, development_experiment as original
from ..io.numeric_export_inputs import read_json
from ..io.recorded_replay_inputs import (
    ReplayFrame, frame_evidence_template, recover_frame, select_frame, validate_frame_evidence,
)
from ..io.recording_readiness_resources import scientific_failure
from .bounded_recording_readiness import _resources
from .development_experiment import protected_inputs, source_guard
from .locked_development_export import write

REVISION = "recorded-replay-one-frame-inputs-v2"


def load_frame(
    project: Path, experiment: Path, experiment_sha256: str, outing: str, matched_row: int
) -> tuple[original.ExperimentInputs, ReplayFrame]:
    project = original.metadata_path(project)
    experiment = original.resolve(project, str(experiment))
    inputs, _ = original.load_experiment(project, experiment, experiment_sha256)
    return inputs, select_frame(inputs, outing, matched_row)


def describe(project: Path, experiment: Path, experiment_sha256: str, outing: str, matched_row: int) -> dict:
    """Prepare a private frame-evidence form using sealed metadata only."""
    inputs, frame = load_frame(project, experiment, experiment_sha256, outing, matched_row)
    inputs.unchanged()
    return frame_evidence_template(frame)


def run(
    *, source: Path, project: Path, experiment: Path, experiment_sha256: str, outing: str,
    matched_row: int, evidence: Path, evidence_sha256: str, scratch: Path, output: Path,
    expected_tree: str, expected_runtime: str,
) -> dict:
    """Publish one geometry receipt after native replay and input stability checks."""
    source = original.metadata_path(source)
    project = original.metadata_path(project)
    evidence = original.metadata_path(evidence)
    scratch = original.metadata_path(scratch)
    source_identity = source_guard(source, expected_tree, expected_runtime)
    inputs, frame = load_frame(project, experiment, experiment_sha256, outing, matched_row)
    declared, digest, _ = read_json(evidence, maximum=64 * 1024)
    require(digest == evidence_sha256, "replay_frame_evidence_digest_mismatch")
    origin, qualifier = validate_frame_evidence(declared, frame)
    protected = protected_inputs(project, inputs.request) + [
        original.resolve(project, str(experiment)), evidence, frame.raw_path,
    ]
    output = original.metadata_path(output)
    require(output.name.endswith(".private.json") and output.parent.is_dir()
            and not os.path.lexists(output), "replay_new_private_receipt_required")
    registry.separate_output(output, protected)
    registry.separate_output(scratch, protected + [output])
    for checkout in {source, project}:
        if output.is_relative_to(checkout):
            require(output.is_relative_to(checkout / "outputs/diagnostics/private"),
                    "replay_private_diagnostic_location_required")
    require(scratch.is_dir(), "replay_scratch_directory_required")
    _resources(scratch, initial=True)
    report = {
        "revision": REVISION, "source": source_identity, "experiment_sha256": experiment_sha256,
        "frame_evidence_sha256": digest, "row": frame.identity,
        "original_sequence_matched_row_bounds": [frame.sequence_start, frame.sequence_stop],
        "physical_frame_basis": "owner_evidence_declaration",
        "frame_and_pose_evidence_reference": declared["frame_and_pose_evidence_reference"],
        "path_frame": declared["path_frame"], "odometry_frame": declared["odometry_frame"],
        "original_speed_mps": frame.original_speed_mps,
    }
    try:
        geometry, odometry = recover_frame(
            frame, origin, scratch, lambda: _resources(scratch), qualifier_binding=qualifier,
        )
    except GeometryValidationError as error:
        status = (
            "recorded_frame_inconclusive"
            if error.code in {"replay_archive_alignment_mismatch", "replay_archived_residual_invalid"}
            else "recorded_frame_unsupported"
        )
        report.update(status=status, failure_code=error.code)
    except Exception as error:
        # Use static diagnostics for I/O and decoder exceptions.
        report.update(status="recorded_frame_inconclusive", failure_code=(
            str(error) if isinstance(error, RegistryError) else scientific_failure(error)
        ))
    else:
        report.update(
            status="recorded_frame_geometry_verified",
            nominal_reference_points_m=geometry.reference_points_m.tolist(),
            residual_stations_from_rear_axle_m=geometry.residual_stations_from_ego_m.tolist(),
            residual_anchor_station_m=geometry.residual_anchor_station_m,
            rear_axle_reference_station_m=geometry.ego_reference_station_m,
            initial_lateral_error_m=geometry.initial_lateral_error_m,
            initial_heading_error_rad=geometry.initial_heading_error_rad,
            odometry=odometry,
        )
    try:
        inputs.unchanged()
        require(read_json(evidence, maximum=64 * 1024)[1] == digest, "replay_frame_evidence_changed")
        require(source_guard(source, expected_tree, expected_runtime) == source_identity, "replay_source_changed")
    except Exception as error:
        # Invalidate computed geometry if any input changed before publication.
        report = {
            "revision": REVISION, "source": source_identity, "experiment_sha256": experiment_sha256,
            "frame_evidence_sha256": digest, "row": frame.identity,
            "status": "recorded_frame_inconclusive", "failure_code": (
                str(error) if isinstance(error, RegistryError) else scientific_failure(error)
            ),
        }
    write(output, report)
    return report
