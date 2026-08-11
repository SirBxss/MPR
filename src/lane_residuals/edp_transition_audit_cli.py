"""CLI for candidate-level EstimatedDrivePaths transition diagnostics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .edp_transition_audit import (
    DEFAULT_EDP_TRANSITION_STATIONS_M,
    EDP_SPLINE_HYPOTHESES,
    CandidateSnapshot,
    SelectedTransition,
    rank_transition_centers,
    sample_candidate_curve,
    selected_candidate_transitions,
)
from .geometry_validation import (
    GeometryValidationError,
    estimated_frame_from_message,
    generate_spline_curve,
    _spline_parameters_from_path,
)
from .mcap_io import (
    McapDependencyError,
    iter_decoded_mcap_messages,
    source_time_ns_from_message,
)
from .path_source_probe import (
    DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    ProtobufPathSemanticTuple,
    _audit_one_path,
    _joint_audit_bindings,
    _repeated_values,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _CandidateRecord:
    snapshot: CandidateSnapshot
    semantic_audit: ProtobufPathSemanticTuple = field(repr=False)
    geometry_failures: tuple[tuple[str, str], ...] = ()

    @property
    def geometry_failure_dict(self) -> dict[str, str]:
        return dict(self.geometry_failures)


@dataclass(frozen=True)
class _MessageRecord:
    message_index: int
    source_time_ns: int | None
    log_time_ns: int
    publish_time_ns: int
    schema_name: str
    message_encoding: str
    topology_source: str | None
    message_state: str
    total_path_count: int
    keep_lane_count: int
    selected_keep_lane_path_index: int | None
    selected_pairing_audit_path_index: int | None
    candidate_records: tuple[_CandidateRecord, ...] = field(default=(), repr=False)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export every EstimatedDrivePaths candidate and rank abrupt selected "
            "KEEP_LANE geometry changes under both unresolved spline hypotheses."
        )
    )
    parser.add_argument("mcap", type=Path, help="one MCAP file to inspect")
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/edp_transition_audit"),
    )
    parser.add_argument(
        "--stations-m",
        nargs="+",
        type=float,
        default=list(DEFAULT_EDP_TRANSITION_STATIONS_M),
    )
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument(
        "--transition-centers",
        nargs="*",
        type=int,
        default=None,
        help=(
            "optional EDP message indices to inspect; when omitted, the largest "
            "non-overlapping curve changes are ranked without a threshold"
        ),
    )
    parser.add_argument("--transition-window-radius", type=int, default=3)
    parser.add_argument("--max-transition-windows", type=int, default=4)
    parser.add_argument(
        "--ranking-hypothesis",
        choices=EDP_SPLINE_HYPOTHESES,
        default="curvature_delta",
    )
    parser.add_argument(
        "--estimate-topic",
        default=DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def _validate_arguments(arguments: argparse.Namespace) -> tuple[float, ...]:
    if arguments.max_step_m <= 0.0 or not math.isfinite(arguments.max_step_m):
        raise ValueError("max-step-m must be finite and positive")
    if arguments.transition_window_radius < 0:
        raise ValueError("transition-window-radius must be nonnegative")
    if arguments.max_transition_windows < 1:
        raise ValueError("max-transition-windows must be positive")
    stations = np.asarray(arguments.stations_m, dtype=np.float64)
    if (
        stations.ndim != 1
        or not len(stations)
        or not np.all(np.isfinite(stations))
        or stations[0] < 0.0
        or not np.all(np.diff(stations) > 0.0)
    ):
        raise ValueError(
            "stations-m must be finite, nonnegative, and strictly increasing"
        )
    centers = arguments.transition_centers
    if centers is not None and any(center < 0 for center in centers):
        raise ValueError("transition-centers must be nonnegative message indices")
    return tuple(float(value) for value in stations)


def _finite_float_tuple(values: Sequence[Any] | None) -> tuple[float, ...]:
    if values is None:
        return ()
    try:
        converted = tuple(float(value) for value in values)
    except (TypeError, ValueError, OverflowError):
        return ()
    return converted if all(math.isfinite(value) for value in converted) else ()


def _integer_tuple(values: Sequence[Any] | None) -> tuple[int, ...]:
    if values is None:
        return ()
    converted: list[int] = []
    try:
        for value in values:
            if isinstance(value, bool):
                return ()
            converted.append(int(value))
    except (TypeError, ValueError, OverflowError):
        return ()
    return tuple(converted)


def _metadata_fingerprint(
    *,
    role_symbol: str,
    error_symbol: str,
    lane_topology_ids: Sequence[int],
) -> str:
    payload = json.dumps(
        {
            "role": role_symbol,
            "error": error_symbol,
            "lane_topology_ids": list(lane_topology_ids),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _decode_one_estimate_message(
    decoded: Any,
    *,
    message_index: int,
    log_time_ns: int,
    publish_time_ns: int,
    schema_name: str,
    message_encoding: str,
    max_step_m: float,
    stations_m: Sequence[float],
) -> _MessageRecord:
    source_time_ns = source_time_ns_from_message(decoded)
    if (
        schema_name != DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA
        or message_encoding != "protobuf"
    ):
        return _MessageRecord(
            message_index=message_index,
            source_time_ns=source_time_ns,
            log_time_ns=log_time_ns,
            publish_time_ns=publish_time_ns,
            schema_name=schema_name,
            message_encoding=message_encoding,
            topology_source=None,
            message_state="schema_or_encoding_mismatch",
            total_path_count=0,
            keep_lane_count=0,
            selected_keep_lane_path_index=None,
            selected_pairing_audit_path_index=None,
        )

    descriptor = getattr(decoded, "DESCRIPTOR", None)
    if descriptor is None:
        return _MessageRecord(
            message_index=message_index,
            source_time_ns=source_time_ns,
            log_time_ns=log_time_ns,
            publish_time_ns=publish_time_ns,
            schema_name=schema_name,
            message_encoding=message_encoding,
            topology_source=None,
            message_state="estimate_descriptor_missing",
            total_path_count=0,
            keep_lane_count=0,
            selected_keep_lane_path_index=None,
            selected_pairing_audit_path_index=None,
        )

    bindings = _joint_audit_bindings(descriptor)
    path_values = _repeated_values(decoded, bindings.drive_paths) or []
    path_audits = tuple(
        _audit_one_path(
            path,
            message_index=message_index,
            path_index=path_index,
            bindings=bindings,
        )
        for path_index, path in enumerate(path_values)
    )
    keep_lane_indices = tuple(
        item.path_index for item in path_audits if item.is_keep_lane
    )
    selected_keep_lane_index = (
        keep_lane_indices[0] if len(keep_lane_indices) == 1 else None
    )
    try:
        frame = estimated_frame_from_message(
            decoded,
            message_index=message_index,
            log_time_ns=log_time_ns,
            publish_time_ns=publish_time_ns,
        )
    except GeometryValidationError as error:
        frame = None
        topology_source = None
        message_state = error.code
    else:
        source_time_ns = frame.source_time_ns
        topology_source = frame.topology_source
        message_state = frame.conversion_state

    selected_pairing_index = (
        selected_keep_lane_index
        if frame is not None and frame.candidate_ready
        else None
    )
    candidate_records: list[_CandidateRecord] = []
    for path_message, semantic in zip(path_values, path_audits):
        confidences = _finite_float_tuple(
            _repeated_values(path_message, bindings.drive_path_confidences)
        )
        lane_topology_ids = _integer_tuple(
            _repeated_values(path_message, bindings.lane_topology_ids)
        )
        parameters = None
        parameter_failure: str | None = None
        try:
            parameters = _spline_parameters_from_path(
                path_message,
                bindings=bindings,
            )
        except GeometryValidationError as error:
            parameter_failure = error.code

        geometries = []
        geometry_failures: dict[str, str] = {}
        if parameters is not None:
            for meaning in EDP_SPLINE_HYPOTHESES:
                try:
                    curve = generate_spline_curve(
                        parameters,
                        meaning=meaning,
                        anchor_policy="anchor_zero",
                        max_step_m=max_step_m,
                        extra_stations=stations_m,
                    )
                    geometries.append(
                        sample_candidate_curve(
                            curve,
                            message_index=message_index,
                            path_index=semantic.path_index,
                            stations_m=stations_m,
                        )
                    )
                except GeometryValidationError as error:
                    geometry_failures[meaning] = error.code
        else:
            for meaning in EDP_SPLINE_HYPOTHESES:
                geometry_failures[meaning] = parameter_failure or "parameters_unavailable"

        snapshot = CandidateSnapshot(
            message_index=message_index,
            source_time_ns=source_time_ns,
            path_index=semantic.path_index,
            topology_source=topology_source or "UNAVAILABLE_ENUM_VALUE",
            role_symbol=semantic.role_symbol,
            error_symbol=semantic.error_symbol,
            selected_unique_keep_lane=(
                semantic.path_index == selected_keep_lane_index
            ),
            selected_for_pairing_audit=(
                semantic.path_index == selected_pairing_index
            ),
            candidate_status=semantic.candidate_status,
            failure_codes=semantic.failure_codes,
            model_flag_value=semantic.model_parameters_optional_flag_value,
            lane_topology_ids=lane_topology_ids,
            confidences=confidences,
            parameters=parameters,
            geometries=tuple(geometries),
        )
        candidate_records.append(
            _CandidateRecord(
                snapshot=snapshot,
                semantic_audit=semantic,
                geometry_failures=tuple(sorted(geometry_failures.items())),
            )
        )

    return _MessageRecord(
        message_index=message_index,
        source_time_ns=source_time_ns,
        log_time_ns=log_time_ns,
        publish_time_ns=publish_time_ns,
        schema_name=schema_name,
        message_encoding=message_encoding,
        topology_source=topology_source,
        message_state=message_state,
        total_path_count=len(path_values),
        keep_lane_count=len(keep_lane_indices),
        selected_keep_lane_path_index=selected_keep_lane_index,
        selected_pairing_audit_path_index=selected_pairing_index,
        candidate_records=tuple(candidate_records),
    )


def _decode_estimate_stream(
    path: Path,
    *,
    estimate_topic: str,
    max_step_m: float,
    stations_m: Sequence[float],
) -> tuple[list[_MessageRecord], Counter[str]]:
    messages: list[_MessageRecord] = []
    states: Counter[str] = Counter()
    iterator = iter_decoded_mcap_messages(
        path,
        topics=(estimate_topic,),
        include_ros1=False,
    )
    for schema, channel, message, decoded in iterator:
        topic = str(getattr(channel, "topic", ""))
        if topic != estimate_topic:
            continue
        record = _decode_one_estimate_message(
            decoded,
            message_index=len(messages),
            log_time_ns=int(getattr(message, "log_time", 0)),
            publish_time_ns=int(getattr(message, "publish_time", 0)),
            schema_name=str(getattr(schema, "name", "")),
            message_encoding=str(getattr(channel, "message_encoding", "")).lower(),
            max_step_m=max_step_m,
            stations_m=stations_m,
        )
        messages.append(record)
        states[record.message_state] += 1
    return messages, states


def _json_value(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def _write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _candidate_row(record: _CandidateRecord) -> dict[str, Any]:
    snapshot = record.snapshot
    audit = record.semantic_audit
    parameters = snapshot.parameters
    confidence_array = np.asarray(snapshot.confidences, dtype=np.float64)
    failures = record.geometry_failure_dict
    return {
        "message_index": snapshot.message_index,
        "source_time_ns_private": snapshot.source_time_ns,
        "path_index": snapshot.path_index,
        "selected_unique_keep_lane": snapshot.selected_unique_keep_lane,
        "selected_for_pairing_audit": snapshot.selected_for_pairing_audit,
        "topology_source": snapshot.topology_source,
        "lane_role_symbol": snapshot.role_symbol,
        "drive_path_error_symbol": snapshot.error_symbol,
        "candidate_status": snapshot.candidate_status,
        "failure_codes_json": _json_value(list(snapshot.failure_codes)),
        "model_parameters_present": audit.model_parameters_present,
        "model_parameters_presence_evidence": (
            audit.model_parameters_presence_evidence
        ),
        "model_flag_present": audit.model_parameters_optional_flag_present,
        "model_flag_value": snapshot.model_flag_value,
        "model_flag_presence_evidence": (
            audit.model_parameters_optional_flag_presence_evidence
        ),
        "confirmed_stable_path_id_available": False,
        "lane_topology_ids_json_private": _json_value(
            list(snapshot.lane_topology_ids)
        ),
        "candidate_metadata_fingerprint_sha256": _metadata_fingerprint(
            role_symbol=snapshot.role_symbol,
            error_symbol=snapshot.error_symbol,
            lane_topology_ids=snapshot.lane_topology_ids,
        ),
        "drive_path_confidences_json_private": _json_value(
            list(snapshot.confidences)
        ),
        "confidence_count_observed": audit.drive_path_confidences_count,
        "confidence_values_all_finite": audit.drive_path_confidences_all_finite,
        "confidence_values_exported_count": len(snapshot.confidences),
        "confidence_min": (
            None if not len(confidence_array) else float(np.min(confidence_array))
        ),
        "confidence_mean": (
            None if not len(confidence_array) else float(np.mean(confidence_array))
        ),
        "confidence_max": (
            None if not len(confidence_array) else float(np.max(confidence_array))
        ),
        "lane_topology_ids_count_observed": audit.lane_topology_ids_count,
        "x_0_m_private": None if parameters is None else parameters.x_0,
        "y_0_m_private": None if parameters is None else parameters.y_0,
        "theta_0_rad_private": None if parameters is None else parameters.theta_0,
        "curvature_0_per_m_private": (
            None if parameters is None else parameters.curvature_0
        ),
        "segment_starts_m_json_private": _json_value(
            [] if parameters is None else parameters.segment_starts.tolist()
        ),
        "curvature_change_json_private": _json_value(
            [] if parameters is None else parameters.curvature_change.tolist()
        ),
        "interval_count": None if parameters is None else parameters.interval_count,
        "index_0": None if parameters is None else parameters.index_0,
        "index_0_explicitly_present": (
            None if parameters is None else parameters.index_0_explicitly_present
        ),
        "index_0_presence_evidence": (
            None if parameters is None else parameters.index_0_presence_evidence
        ),
        "curvature_rate_geometry_state": (
            "ready" if snapshot.geometry("curvature_rate") is not None else "not_ready"
        ),
        "curvature_rate_failure_code": failures.get("curvature_rate"),
        "curvature_delta_geometry_state": (
            "ready" if snapshot.geometry("curvature_delta") is not None else "not_ready"
        ),
        "curvature_delta_failure_code": failures.get("curvature_delta"),
    }


def _transition_row(item: SelectedTransition) -> dict[str, Any]:
    return asdict(item)


def _plot_transition_windows(
    path: Path,
    *,
    candidates: Sequence[CandidateSnapshot],
    centers: Sequence[int],
    radius: int,
) -> None:
    if not centers:
        path.unlink(missing_ok=True)
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(
        len(centers),
        len(EDP_SPLINE_HYPOTHESES),
        figsize=(13.0, 4.5 * len(centers)),
        squeeze=False,
    )
    color_map = plt.get_cmap("tab10")
    for row_index, center in enumerate(centers):
        for column_index, hypothesis in enumerate(EDP_SPLINE_HYPOTHESES):
            axis = axes[row_index, column_index]
            window_candidates = [
                item
                for item in candidates
                if abs(item.message_index - center) <= radius
                and item.geometry(hypothesis) is not None
            ]
            for item in window_candidates:
                geometry = item.geometry(hypothesis)
                assert geometry is not None
                relative = abs(item.message_index - center)
                alpha = 1.0 - 0.65 * relative / max(radius + 1, 1)
                label = None
                if item.message_index == center:
                    label = (
                        f"E{item.message_index} p{item.path_index} "
                        f"{item.role_symbol}"
                    )
                axis.plot(
                    geometry.x_m,
                    geometry.y_m,
                    color=color_map(item.path_index % 10),
                    linewidth=(2.0 if item.selected_for_pairing_audit else 0.9),
                    linestyle=("-" if item.selected_unique_keep_lane else "--"),
                    alpha=alpha,
                    label=label,
                )
                axis.scatter(
                    geometry.x_m[0],
                    geometry.y_m[0],
                    color=color_map(item.path_index % 10),
                    s=8,
                    alpha=alpha,
                )
            axis.scatter(0.0, 0.0, marker="+", color="black", s=35)
            axis.set_title(
                f"center E{center}, messages ±{radius}; {hypothesis}",
                fontsize=10,
            )
            axis.set_xlabel("provisional spline x [m]")
            axis.set_ylabel("provisional spline y [m]")
            axis.grid(True, alpha=0.25)
            axis.set_aspect("equal", adjustable="datalim")
            handles, labels = axis.get_legend_handles_labels()
            if handles:
                by_label = dict(zip(labels, handles))
                axis.legend(
                    by_label.values(),
                    by_label.keys(),
                    fontsize=7,
                    loc="best",
                )
    figure.suptitle(
        "EDP candidate transition windows: all candidates; solid = unique KEEP_LANE",
        fontsize=12,
    )
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.985))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=170)
    plt.close(figure)


def _plot_transition_metrics(
    path: Path,
    *,
    transitions: Sequence[SelectedTransition],
    centers: Sequence[int],
) -> None:
    if not transitions:
        path.unlink(missing_ok=True)
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = (
        ("sampled_position_rms_m", "raw sampled curve RMS [m]"),
        ("rigid_normalized_shape_rms_m", "rigid-normalized shape RMS [m]"),
        ("endpoint_position_jump_m", "maximum-common-station jump [m]"),
    )
    figure, axes = plt.subplots(3, 1, figsize=(12.0, 9.0), sharex=True)
    for axis, (attribute, label) in zip(axes, metrics):
        for hypothesis, color in (
            ("curvature_rate", "tab:blue"),
            ("curvature_delta", "tab:orange"),
        ):
            items = [item for item in transitions if item.hypothesis == hypothesis]
            axis.plot(
                [item.current_message_index for item in items],
                [getattr(item, attribute) for item in items],
                label=hypothesis,
                color=color,
                linewidth=1.0,
            )
        for center in centers:
            axis.axvline(center, color="black", linestyle=":", alpha=0.4)
        axis.set_ylabel(label)
        axis.grid(True, alpha=0.25)
    axes[-1].set_xlabel("current EDP message index")
    axes[0].legend(loc="upper right")
    figure.suptitle(
        "Consecutive selected KEEP_LANE changes (diagnostic ranking; no threshold)",
        fontsize=12,
    )
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.98))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=170)
    plt.close(figure)


def run_edp_transition_audit(
    arguments: argparse.Namespace,
    *,
    stations_m: Sequence[float],
) -> dict[str, Any]:
    messages, message_states = _decode_estimate_stream(
        arguments.mcap,
        estimate_topic=arguments.estimate_topic,
        max_step_m=arguments.max_step_m,
        stations_m=stations_m,
    )
    records = [
        record
        for message in messages
        for record in message.candidate_records
    ]
    candidates = [record.snapshot for record in records]
    transitions = selected_candidate_transitions(candidates)
    if arguments.transition_centers:
        centers = tuple(dict.fromkeys(arguments.transition_centers))
        center_selection_basis = "explicit_cli_message_indices"
    else:
        centers = rank_transition_centers(
            transitions,
            hypothesis=arguments.ranking_hypothesis,
            maximum_centers=arguments.max_transition_windows,
            minimum_separation_messages=(
                2 * arguments.transition_window_radius + 1
            ),
        )
        center_selection_basis = (
            "largest_non_overlapping_sampled_position_rms_without_threshold"
        )

    message_rows = [
        {
            "message_index": item.message_index,
            "source_time_ns_private": item.source_time_ns,
            "log_time_ns_private": item.log_time_ns,
            "publish_time_ns_private": item.publish_time_ns,
            "schema_name": item.schema_name,
            "message_encoding": item.message_encoding,
            "topology_source": item.topology_source,
            "message_state": item.message_state,
            "total_path_count": item.total_path_count,
            "keep_lane_count": item.keep_lane_count,
            "selected_keep_lane_path_index": item.selected_keep_lane_path_index,
            "selected_pairing_audit_path_index": (
                item.selected_pairing_audit_path_index
            ),
        }
        for item in messages
    ]
    candidate_rows = [_candidate_row(record) for record in records]
    geometry_rows = [
        {
            "message_index": snapshot.message_index,
            "source_time_ns_private": snapshot.source_time_ns,
            "path_index": snapshot.path_index,
            "selected_unique_keep_lane": snapshot.selected_unique_keep_lane,
            "selected_for_pairing_audit": snapshot.selected_for_pairing_audit,
            "lane_role_symbol": snapshot.role_symbol,
            "drive_path_error_symbol": snapshot.error_symbol,
            "hypothesis": geometry.hypothesis,
            "station_m": float(station),
            "x_m_private": float(geometry.x_m[index]),
            "y_m_private": float(geometry.y_m[index]),
            "heading_rad_private": float(geometry.heading_rad[index]),
            "curvature_per_m_private": float(geometry.curvature_per_m[index]),
        }
        for snapshot in candidates
        for geometry in snapshot.geometries
        for index, station in enumerate(geometry.stations_m)
    ]
    transition_rows = [_transition_row(item) for item in transitions]

    output = arguments.output_directory
    _write_csv(
        output / "edp_message_inventory.csv",
        tuple(message_rows[0].keys()) if message_rows else (
            "message_index",
            "source_time_ns_private",
            "log_time_ns_private",
            "publish_time_ns_private",
            "schema_name",
            "message_encoding",
            "topology_source",
            "message_state",
            "total_path_count",
            "keep_lane_count",
            "selected_keep_lane_path_index",
            "selected_pairing_audit_path_index",
        ),
        message_rows,
    )
    candidate_fields = tuple(candidate_rows[0].keys()) if candidate_rows else (
        "message_index",
        "source_time_ns_private",
        "path_index",
    )
    _write_csv(output / "edp_candidate_inventory.csv", candidate_fields, candidate_rows)
    geometry_fields = tuple(geometry_rows[0].keys()) if geometry_rows else (
        "message_index",
        "source_time_ns_private",
        "path_index",
        "selected_unique_keep_lane",
        "selected_for_pairing_audit",
        "lane_role_symbol",
        "drive_path_error_symbol",
        "hypothesis",
        "station_m",
        "x_m_private",
        "y_m_private",
        "heading_rad_private",
        "curvature_per_m_private",
    )
    _write_csv(output / "edp_candidate_geometry.csv", geometry_fields, geometry_rows)
    transition_fields = tuple(transition_rows[0].keys()) if transition_rows else tuple(
        SelectedTransition.__dataclass_fields__.keys()
    )
    _write_csv(
        output / "edp_selected_transitions.csv",
        transition_fields,
        transition_rows,
    )
    _plot_transition_windows(
        output / "edp_transition_windows.png",
        candidates=candidates,
        centers=centers,
        radius=arguments.transition_window_radius,
    )
    _plot_transition_metrics(
        output / "edp_transition_metrics.png",
        transitions=transitions,
        centers=centers,
    )

    selected_ready = [item for item in candidates if item.selected_for_pairing_audit]
    summary = {
        "version": "0.4.2",
        "purpose": "edp_candidate_and_selected_transition_diagnostic",
        "mcap_filename": arguments.mcap.name,
        "estimate_topic": arguments.estimate_topic,
        "estimate_message_count": len(messages),
        "all_candidate_count": len(candidates),
        "unique_keep_lane_candidate_count": sum(
            item.selected_unique_keep_lane for item in candidates
        ),
        "pairing_audit_selected_candidate_count": len(selected_ready),
        "message_states": dict(sorted(message_states.items())),
        "spline_hypotheses": list(EDP_SPLINE_HYPOTHESES),
        "requested_stations_m": list(stations_m),
        "selected_consecutive_pair_count": len(
            {
                (item.previous_message_index, item.current_message_index)
                for item in transitions
            }
        ),
        "selected_transition_comparison_count": len(transitions),
        "ranked_transition_centers": list(centers),
        "transition_center_selection_basis": center_selection_basis,
        "ranking_hypothesis": arguments.ranking_hypothesis,
        "transition_threshold_applied": False,
        "transition_window_radius_messages": arguments.transition_window_radius,
        "every_candidate_exported": True,
        "raw_spline_parameters_exported": True,
        "finite_candidate_confidences_exported_without_semantic_reinterpretation": True,
        "non_finite_confidence_values_replaced_by_silent_numbers": False,
        "confirmed_stable_path_identifier_available": False,
        "candidate_identity_note": (
            "lane_topology_ids and a metadata fingerprint are exported; path_index "
            "is message-local and is not treated as a stable identity"
        ),
        "driving_intention_note": (
            "the confirmed lane-role enum is exported literally; no separate "
            "driving-intention field is claimed"
        ),
        "curvature_change_semantics_confirmed": False,
        "coordinate_frame_equivalence_confirmed": False,
        "generated_final_residual_dataset": False,
        "diagnostic_is_lane_estimation_error": False,
        "next_decision": (
            "Check whether ranked curve jumps coincide with candidate index, "
            "lane_topology_ids, raw spline parameters, confidence changes, or only "
            "one curvature hypothesis. Construct an ordered multi-segment RLMB "
            "ego lane only after this EDP transition evidence is reviewed."
        ),
        "confidentiality": (
            "Outputs contain BMW-derived raw model parameters and measurements "
            "and must remain private."
        ),
    }
    _write_json(output / "edp_transition_summary.json", summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(levelname)s %(message)s",
    )
    try:
        stations_m = _validate_arguments(arguments)
        if not arguments.mcap.is_file():
            raise FileNotFoundError(f"MCAP file not found: {arguments.mcap}")
        summary = run_edp_transition_audit(arguments, stations_m=stations_m)
    except (FileNotFoundError, OSError, ValueError, McapDependencyError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "exported %d candidates and ranked %d transition windows",
        summary["all_candidate_count"],
        len(summary["ranked_transition_centers"]),
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return 0 if summary["estimate_message_count"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
