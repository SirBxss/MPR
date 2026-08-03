"""Corpus-level CLI for fail-closed direct-path geometry validation."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from .geometry_validation import (
    DEFAULT_COMPARATOR_TOPIC,
    DecodedRecording,
    EstimatedFrameAudit,
    GeometryValidationError,
    HypothesisMetrics,
    SplineCurve,
    audit_counts,
    compare_curve_to_comparator,
    contiguous_state_runs,
    decode_recording_messages,
    generate_spline_hypotheses,
    metrics_to_dict,
    state_transition_counts,
    synchronize_estimate_and_comparator,
)
from .mcap_io import McapDependencyError, iter_decoded_mcap_messages
from .path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC

LOGGER = logging.getLogger(__name__)


@dataclass
class _RecordingResult:
    recording_id: str
    session_id: str
    source_path: Path
    status: str
    error_code: str | None
    decoded: DecodedRecording | None
    synchronization: Any | None
    sensitivity_counts: dict[str, int]
    generated_curves: dict[tuple[int, str], SplineCurve]
    generation_failures: dict[tuple[int, str], str]
    metrics: list[tuple[int, int, HypothesisMetrics]]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit estimator availability across a corpus, generate explicitly "
            "labelled spline hypotheses for strict candidates, and compare them "
            "diagnostically with /em/road/ego_lane_path. No residual training "
            "dataset or Gaussian model is produced."
        )
    )
    parser.add_argument(
        "mcap_inputs",
        nargs="+",
        type=Path,
        help="MCAP files or directories containing MCAP files.",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs") / "mcap_v038",
    )
    parser.add_argument(
        "--session-map",
        type=Path,
        help=(
            "Optional JSON object mapping each MCAP basename to a real session "
            "label. Labels are replaced with opaque session IDs in outputs."
        ),
    )
    parser.add_argument(
        "--expected-file-count",
        type=int,
        default=10,
        help="Expected corpus size; mismatch makes the corpus incomplete.",
    )
    parser.add_argument(
        "--max-messages-per-topic",
        type=int,
        help="Diagnostic sampling only; omission performs a complete scan.",
    )
    parser.add_argument(
        "--comparison-max-delta-ms",
        type=float,
        default=20.0,
        help="Diagnostic source-time tolerance used for geometry comparison.",
    )
    parser.add_argument(
        "--sync-sensitivity-ms",
        type=float,
        nargs="+",
        default=(5.0, 10.0, 20.0, 50.0),
    )
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument(
        "--minimum-common-coverage-m",
        type=float,
        default=20.0,
    )
    parser.add_argument(
        "--include-explicit-index-anchor",
        action="store_true",
        help=(
            "Also evaluate the index anchor, but only when index_0 is explicitly "
            "present. Implicit proto defaults remain blocked."
        ),
    )
    parser.add_argument(
        "--assume-same-frame",
        action="store_true",
        help=(
            "Explicitly confirm that raw estimate and comparator coordinates may "
            "be compared without fitted alignment."
        ),
    )
    parser.add_argument(
        "--absolute-lateral-rms-tolerance-m",
        type=float,
        help="Required only to permit a geometrically_preferred label.",
    )
    parser.add_argument(
        "--absolute-heading-p95-tolerance-rad",
        type=float,
        help="Required only to permit a geometrically_preferred label.",
    )
    parser.add_argument(
        "--max-overlays-per-recording",
        type=int,
        default=8,
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def _resolve_mcap_files(inputs: Sequence[Path]) -> tuple[Path, ...]:
    paths: dict[Path, None] = {}
    for raw in inputs:
        candidate = raw.expanduser()
        if candidate.is_file():
            if candidate.suffix.lower() != ".mcap":
                raise ValueError(f"input is not an MCAP file: {candidate}")
            paths[candidate.resolve()] = None
        elif candidate.is_dir():
            for path in candidate.rglob("*.mcap"):
                if path.is_file():
                    paths[path.resolve()] = None
        else:
            raise FileNotFoundError(f"MCAP input not found: {candidate}")
    if not paths:
        raise ValueError("no MCAP files were resolved")
    return tuple(sorted(paths, key=lambda path: str(path).casefold()))


def _load_session_map(path: Path | None, files: Sequence[Path]) -> tuple[dict[Path, str], bool]:
    if path is None:
        return {file: "session_unassigned" for file in files}, False
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, Mapping) or not all(
        isinstance(key, str) and isinstance(value, str) and value
        for key, value in payload.items()
    ):
        raise ValueError("session map must be a JSON object of basename: label")
    basenames = [file.name for file in files]
    if len(set(basenames)) != len(basenames):
        raise ValueError("duplicate MCAP basenames make the session map ambiguous")
    missing = sorted(name for name in basenames if name not in payload)
    extra = sorted(name for name in payload if name not in set(basenames))
    if missing or extra:
        raise ValueError(
            "session map must match resolved basenames exactly; "
            f"missing={missing}, extra={extra}"
        )
    labels = sorted({str(payload[name]) for name in basenames})
    opaque = {label: f"session_{index:03d}" for index, label in enumerate(labels, 1)}
    return {file: opaque[str(payload[file.name])] for file in files}, True


def _process_recording(
    path: Path,
    *,
    recording_id: str,
    session_id: str,
    arguments: argparse.Namespace,
) -> _RecordingResult:
    LOGGER.info("Processing %s", recording_id)
    try:
        decoded_messages = iter_decoded_mcap_messages(
            path,
            topics=(DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC, DEFAULT_COMPARATOR_TOPIC),
            include_ros1=True,
        )
        decoded = decode_recording_messages(
            decoded_messages,
            max_messages_per_topic=arguments.max_messages_per_topic,
        )
    except (
        FileNotFoundError,
        ValueError,
        GeometryValidationError,
        McapDependencyError,
        OSError,
    ) as error:
        LOGGER.error("%s failed: %s", recording_id, error)
        return _RecordingResult(
            recording_id=recording_id,
            session_id=session_id,
            source_path=path,
            status="file_failed",
            error_code=getattr(error, "code", type(error).__name__),
            decoded=None,
            synchronization=None,
            sensitivity_counts={},
            generated_curves={},
            generation_failures={},
            metrics=[],
        )

    synchronization = synchronize_estimate_and_comparator(
        decoded.estimated_frames,
        decoded.comparator_frames,
        max_delta_ms=arguments.comparison_max_delta_ms,
    )
    sensitivity_counts = {
        f"{tolerance:g}": len(
            synchronize_estimate_and_comparator(
                decoded.estimated_frames,
                decoded.comparator_frames,
                max_delta_ms=tolerance,
            ).pairs
        )
        for tolerance in arguments.sync_sensitivity_ms
    }
    estimate_by_index = {
        frame.message_index: frame for frame in decoded.estimated_frames
    }
    comparator_by_index = {
        frame.message_index: frame for frame in decoded.comparator_frames
    }
    curves: dict[tuple[int, str], SplineCurve] = {}
    failures: dict[tuple[int, str], str] = {}
    metrics: list[tuple[int, int, HypothesisMetrics]] = []

    for estimate in decoded.estimated_frames:
        if not estimate.candidate_ready:
            continue
        generated, generation_failures = generate_spline_hypotheses(
            estimate.candidate,
            include_explicit_index_anchor=arguments.include_explicit_index_anchor,
            max_step_m=arguments.max_step_m,
        )
        for curve in generated:
            curves[(estimate.message_index, curve.hypothesis)] = curve
        for hypothesis, code in generation_failures:
            failures[(estimate.message_index, hypothesis)] = code

    if arguments.assume_same_frame:
        for pair in synchronization.pairs:
            estimate = estimate_by_index[pair.estimate_index]
            comparator = comparator_by_index[pair.comparator_index]
            if not estimate.candidate_ready or comparator.geometry is None:
                continue
            for (message_index, _), curve in curves.items():
                if message_index != estimate.message_index:
                    continue
                result = compare_curve_to_comparator(
                    curve,
                    comparator.geometry,
                    minimum_common_coverage_m=arguments.minimum_common_coverage_m,
                )
                metrics.append(
                    (estimate.message_index, comparator.message_index, result)
                )

    status = "completed" if decoded.scan_complete else "completed_partial_scan"
    return _RecordingResult(
        recording_id=recording_id,
        session_id=session_id,
        source_path=path,
        status=status,
        error_code=None,
        decoded=decoded,
        synchronization=synchronization,
        sensitivity_counts=sensitivity_counts,
        generated_curves=curves,
        generation_failures=failures,
        metrics=metrics,
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _relative_seconds(frames: Sequence[Any]) -> dict[int, float | None]:
    timestamps = [frame.source_time_ns for frame in frames if frame.source_time_ns is not None]
    origin = min(timestamps) if timestamps else None
    return {
        frame.message_index: (
            None
            if frame.source_time_ns is None or origin is None
            else (int(frame.source_time_ns) - int(origin)) / 1_000_000_000.0
        )
        for frame in frames
    }


def _duplicate_flags(
    results: Sequence[_RecordingResult],
    *,
    sessions_confirmed: bool,
) -> tuple[dict[tuple[str, int], str], set[tuple[str, int]]]:
    """Identify duplicate chunk-boundary frames without exposing timestamps."""

    if not sessions_confirmed:
        return {}, set()
    groups: dict[tuple[str, int], list[tuple[str, EstimatedFrameAudit]]] = defaultdict(list)
    for result in results:
        if result.decoded is None:
            continue
        for frame in result.decoded.estimated_frames:
            if frame.source_time_ns is not None:
                groups[(result.session_id, int(frame.source_time_ns))].append(
                    (result.recording_id, frame)
                )
    duplicates: dict[tuple[str, int], str] = {}
    conflicts: set[tuple[str, int]] = set()
    for entries in groups.values():
        recording_ids = {recording_id for recording_id, _ in entries}
        if len(entries) < 2 or len(recording_ids) < 2:
            continue
        entries.sort(key=lambda item: (item[0], item[1].message_index))
        signatures = {
            (
                frame.payload_fingerprint
            )
            for _, frame in entries
        }
        fingerprints_available = all(
            frame.payload_fingerprint is not None for _, frame in entries
        )
        if fingerprints_available and len(signatures) == 1:
            canonical_recording, canonical_frame = entries[0]
            canonical = f"{canonical_recording}:{canonical_frame.message_index}"
            for recording_id, frame in entries[1:]:
                duplicates[(recording_id, frame.message_index)] = canonical
        else:
            conflicts.update(
                (recording_id, frame.message_index)
                for recording_id, frame in entries
            )
    return duplicates, conflicts


def _frame_rows(
    results: Sequence[_RecordingResult],
    *,
    duplicate_flags: Mapping[tuple[str, int], str],
    conflict_flags: set[tuple[str, int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if result.decoded is None:
            continue
        relative = _relative_seconds(result.decoded.estimated_frames)
        paired = {
            pair.estimate_index: pair for pair in result.synchronization.pairs
        }
        ambiguous = set(result.synchronization.ambiguous_estimate_indices)
        for frame in result.decoded.estimated_frames:
            if frame.message_index in paired:
                sync_state = "paired"
                delta_ms = paired[frame.message_index].source_delta_ns / 1_000_000.0
            elif frame.message_index in ambiguous:
                sync_state = "ambiguous"
                delta_ms = None
            elif frame.source_time_ns is None:
                sync_state = "timestamp_missing"
                delta_ms = None
            else:
                sync_state = "unmatched"
                delta_ms = None
            rows.append(
                {
                    "recording_id": result.recording_id,
                    "session_id": result.session_id,
                    "message_index": frame.message_index,
                    "relative_recording_time_s": relative[frame.message_index],
                    "estimator_state": frame.estimator_state,
                    "estimator_error": frame.keep_lane_error,
                    "conversion_state": frame.conversion_state,
                    "interval_count": frame.interval_count,
                    "total_path_count": frame.total_path_count,
                    "keep_lane_count": frame.keep_lane_count,
                    "synchronization_state": sync_state,
                    "source_delta_ms": delta_ms,
                    "duplicate_of": duplicate_flags.get(
                        (result.recording_id, frame.message_index)
                    ),
                    "timestamp_conflict": (
                        (result.recording_id, frame.message_index) in conflict_flags
                    ),
                }
            )
    return rows


def _synchronization_rows(results: Sequence[_RecordingResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if result.decoded is None:
            continue
        estimate_relative = _relative_seconds(result.decoded.estimated_frames)
        paired = {pair.estimate_index: pair for pair in result.synchronization.pairs}
        ambiguous = set(result.synchronization.ambiguous_estimate_indices)
        comparator_states = {
            frame.message_index: frame.state for frame in result.decoded.comparator_frames
        }
        for frame in result.decoded.estimated_frames:
            pair = paired.get(frame.message_index)
            rows.append(
                {
                    "recording_id": result.recording_id,
                    "session_id": result.session_id,
                    "estimate_message_index": frame.message_index,
                    "relative_recording_time_s": estimate_relative[frame.message_index],
                    "state": (
                        "paired"
                        if pair is not None
                        else "ambiguous"
                        if frame.message_index in ambiguous
                        else "timestamp_missing"
                        if frame.source_time_ns is None
                        else "unmatched"
                    ),
                    "comparator_message_index": (
                        None if pair is None else pair.comparator_index
                    ),
                    "comparator_state": (
                        None
                        if pair is None
                        else comparator_states.get(pair.comparator_index)
                    ),
                    "source_delta_ms": (
                        None if pair is None else pair.source_delta_ns / 1_000_000.0
                    ),
                    "log_delta_ms": (
                        None if pair is None else pair.log_delta_ns / 1_000_000.0
                    ),
                }
            )
    return rows


def _metric_rows(
    results: Sequence[_RecordingResult],
    *,
    duplicate_flags: Mapping[tuple[str, int], str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        estimate_source_times = (
            {}
            if result.decoded is None
            else {
                frame.message_index: frame.source_time_ns
                for frame in result.decoded.estimated_frames
            }
        )
        for estimate_index, comparator_index, metric in result.metrics:
            rows.append(
                {
                    "recording_id": result.recording_id,
                    "session_id": result.session_id,
                    "estimate_message_index": estimate_index,
                    "comparator_message_index": comparator_index,
                    "duplicate_source_frame": (
                        (result.recording_id, estimate_index) in duplicate_flags
                    ),
                    # Internal ordering evidence. CSV field selection deliberately
                    # omits it, so absolute source time never leaves the process.
                    "_source_time_ns": estimate_source_times.get(estimate_index),
                    **metrics_to_dict(metric),
                }
            )
        for (estimate_index, hypothesis), code in sorted(result.generation_failures.items()):
            rows.append(
                {
                    "recording_id": result.recording_id,
                    "session_id": result.session_id,
                    "estimate_message_index": estimate_index,
                    "comparator_message_index": None,
                    "hypothesis": hypothesis,
                    "status": "generation_failed",
                    "failure_code": code,
                    "duplicate_source_frame": (
                        (result.recording_id, estimate_index) in duplicate_flags
                    ),
                    "_source_time_ns": estimate_source_times.get(estimate_index),
                }
            )
    return rows


def _duplicate_gap_rows(
    results: Sequence[_RecordingResult],
    *,
    sessions_confirmed: bool,
) -> list[dict[str, Any]]:
    if not sessions_confirmed:
        return []
    rows: list[dict[str, Any]] = []
    by_session: dict[
        str,
        dict[str, list[tuple[int, str, Any]]],
    ] = defaultdict(lambda: defaultdict(list))
    for result in results:
        if result.decoded is None:
            continue
        for frame in result.decoded.estimated_frames:
            if frame.source_time_ns is not None:
                by_session[result.session_id]["estimate"].append(
                    (int(frame.source_time_ns), result.recording_id, frame)
                )
        for frame in result.decoded.comparator_frames:
            if frame.source_time_ns is not None:
                by_session[result.session_id]["comparator"].append(
                    (int(frame.source_time_ns), result.recording_id, frame)
                )
    for session_id, streams in sorted(by_session.items()):
        for stream_name, entries in sorted(streams.items()):
            entries.sort(key=lambda item: (item[0], item[1], item[2].message_index))
            origin = entries[0][0] if entries else 0
            positive_deltas = [
                right[0] - left[0]
                for left, right in pairwise(entries)
                if right[0] > left[0]
            ]
            median_delta = (
                float(np.median(positive_deltas)) if positive_deltas else None
            )
            for left, right in pairwise(entries):
                delta = right[0] - left[0]
                relative = (right[0] - origin) / 1_000_000_000.0
                if delta == 0 and left[1] != right[1]:
                    left_signature = left[2].payload_fingerprint
                    right_signature = right[2].payload_fingerprint
                    rows.append(
                        {
                            "session_id": session_id,
                            "stream": stream_name,
                            "event": (
                                "duplicate_timestamp_same_signature"
                                if left_signature is not None
                                and left_signature == right_signature
                                else "conflicting_same_timestamp"
                            ),
                            "left_recording_id": left[1],
                            "right_recording_id": right[1],
                            "relative_session_time_s": relative,
                            "delta_ms": 0.0,
                        }
                    )
                elif median_delta is not None and delta > 3.0 * median_delta:
                    rows.append(
                        {
                            "session_id": session_id,
                            "stream": stream_name,
                            "event": "timestamp_gap",
                            "left_recording_id": left[1],
                            "right_recording_id": right[1],
                            "relative_session_time_s": relative,
                            "delta_ms": delta / 1_000_000.0,
                        }
                    )
    return rows


def _block_bootstrap_ci(values: Sequence[float], *, seed: int, block: int = 10,
                        repetitions: int = 2000) -> tuple[float, float] | None:
    array = np.asarray(values, dtype=np.float64)
    if len(array) < max(20, block * 2):
        return None
    rng = np.random.default_rng(seed)
    starts = np.arange(max(1, len(array) - block + 1))
    samples = np.empty(repetitions, dtype=np.float64)
    for repetition in range(repetitions):
        pieces: list[np.ndarray] = []
        while sum(len(piece) for piece in pieces) < len(array):
            start = int(rng.choice(starts))
            pieces.append(array[start : start + block])
        sample = np.concatenate(pieces)[: len(array)]
        samples[repetition] = float(np.median(sample))
    return float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def _semantic_decision(
    metric_rows: Sequence[Mapping[str, Any]],
    *,
    sessions_confirmed: bool,
    lateral_tolerance: float | None,
    heading_tolerance: float | None,
) -> dict[str, Any]:
    hypotheses = (
        "curvature_rate__anchor_zero",
        "curvature_delta__anchor_zero",
    )
    complete = [
        row
        for row in metric_rows
        if row.get("status") == "comparison_completed"
        and row.get("hypothesis") in hypotheses
        and not row.get("duplicate_source_frame", False)
    ]
    paired: dict[tuple[str, str, int], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in complete:
        key = (
            str(row["session_id"]),
            str(row["recording_id"]),
            int(row["estimate_message_index"]),
        )
        paired[key][str(row["hypothesis"])] = row
    paired = {key: value for key, value in paired.items() if len(value) == 2}
    sessions = sorted({key[0] for key in paired})
    evidence: dict[str, Any] = {}
    candidate_passes = {hypothesis: True for hypothesis in hypotheses}
    for session_number, session in enumerate(sessions):
        entries = sorted(
            (value for key, value in paired.items() if key[0] == session),
            key=lambda value: (
                int(next(iter(value.values())).get("_source_time_ns") or 0),
                str(next(iter(value.values()))["recording_id"]),
                int(next(iter(value.values()))["estimate_message_index"]),
            ),
        )
        session_payload: dict[str, Any] = {"paired_frames": len(entries)}
        rate_values = np.asarray(
            [entry[hypotheses[0]]["lateral_rms_m"] for entry in entries],
            dtype=np.float64,
        )
        delta_values = np.asarray(
            [entry[hypotheses[1]]["lateral_rms_m"] for entry in entries],
            dtype=np.float64,
        )
        difference = rate_values - delta_values
        ci = _block_bootstrap_ci(difference, seed=20260803 + session_number)
        session_payload["paired_median_rate_minus_delta_rms_m"] = (
            None if not len(difference) else float(np.median(difference))
        )
        session_payload["block_bootstrap_95pct_ci_m"] = (
            None if ci is None else list(ci)
        )
        for index, hypothesis in enumerate(hypotheses):
            own = rate_values if index == 0 else delta_values
            alternative = delta_values if index == 0 else rate_values
            rows = [entry[hypothesis] for entry in entries]
            win_rate = float(np.mean(own < alternative)) if len(own) else 0.0
            median_own = float(np.median(own)) if len(own) else None
            median_alt = float(np.median(alternative)) if len(alternative) else None
            median_heading = (
                float(np.median([row["heading_p95_abs_rad"] for row in rows]))
                if rows
                else None
            )
            median_coverage = (
                float(np.median([row["common_coverage_m"] for row in rows]))
                if rows
                else None
            )
            alternative_rows = [
                entry[hypotheses[1 - index]] for entry in entries
            ]
            alternative_heading = (
                float(np.median([row["heading_p95_abs_rad"] for row in alternative_rows]))
                if alternative_rows
                else None
            )
            alternative_coverage = (
                float(np.median([row["common_coverage_m"] for row in alternative_rows]))
                if alternative_rows
                else None
            )
            ci_excludes_zero = bool(
                ci is not None
                and ((index == 0 and ci[1] < 0.0) or (index == 1 and ci[0] > 0.0))
            )
            passes = bool(
                len(entries) >= 20
                and win_rate >= 0.80
                and median_own is not None
                and median_alt is not None
                and median_own <= 0.5 * median_alt
                and median_heading is not None
                and alternative_heading is not None
                and median_heading <= 1.1 * alternative_heading
                and median_coverage is not None
                and alternative_coverage is not None
                and median_coverage >= 0.9 * alternative_coverage
                and ci_excludes_zero
                and lateral_tolerance is not None
                and heading_tolerance is not None
                and median_own <= lateral_tolerance
                and median_heading <= heading_tolerance
            )
            candidate_passes[hypothesis] &= passes
            session_payload[hypothesis] = {
                "win_rate": win_rate,
                "median_lateral_rms_m": median_own,
                "median_heading_p95_rad": median_heading,
                "median_common_coverage_m": median_coverage,
                "passes_predeclared_gate": passes,
            }
        evidence[session] = session_payload

    eligible_sessions = sessions_confirmed and len(sessions) >= 2
    passing = [hypothesis for hypothesis, value in candidate_passes.items() if value]
    decision = passing[0] if eligible_sessions and len(passing) == 1 else None
    return {
        "status": (
            "geometrically_preferred" if decision is not None else "hypothesis_unresolved"
        ),
        "geometrically_preferred_hypothesis": decision,
        "authoritative_semantics_confirmed": False,
        "sessions_confirmed": sessions_confirmed,
        "eligible_session_count": len(sessions),
        "absolute_tolerances_predeclared": (
            lateral_tolerance is not None and heading_tolerance is not None
        ),
        "session_evidence": evidence,
    }


def _distribution(values: Sequence[float]) -> dict[str, float | None]:
    array = np.asarray(values, dtype=np.float64)
    if len(array) == 0:
        return {
            "median": None,
            "p95": None,
            "p99": None,
            "maximum": None,
        }
    absolute = np.abs(array)
    return {
        "median": float(np.median(array)),
        "p95": float(np.percentile(absolute, 95)),
        "p99": float(np.percentile(absolute, 99)),
        "maximum": float(np.max(absolute)),
    }


def _synchronization_diagnostics(
    results: Sequence[_RecordingResult],
) -> dict[str, Any]:
    """Summarize timestamp scale, offsets, drift and sensitivity per file."""

    payload: dict[str, Any] = {}
    for result in results:
        if result.decoded is None or result.synchronization is None:
            continue
        pairs = result.synchronization.pairs
        estimate_by_index = {
            frame.message_index: frame for frame in result.decoded.estimated_frames
        }
        source_delta_ms = [pair.source_delta_ns / 1_000_000.0 for pair in pairs]
        log_delta_ms = [pair.log_delta_ns / 1_000_000.0 for pair in pairs]
        relative_seconds: list[float] = []
        if pairs:
            origin = min(
                int(estimate_by_index[pair.estimate_index].source_time_ns)
                for pair in pairs
            )
            relative_seconds = [
                (
                    int(estimate_by_index[pair.estimate_index].source_time_ns)
                    - origin
                )
                / 1_000_000_000.0
                for pair in pairs
            ]
        if len(relative_seconds) >= 2 and np.ptp(relative_seconds) > 0.0:
            drift = float(np.polyfit(relative_seconds, source_delta_ms, 1)[0])
        else:
            drift = None

        estimates = [
            frame
            for frame in result.decoded.estimated_frames
            if frame.source_time_ns is not None
        ]
        estimates.sort(key=lambda frame: int(frame.source_time_ns))
        source_steps = [
            (int(right.source_time_ns) - int(left.source_time_ns)) / 1_000_000.0
            for left, right in pairwise(estimates)
            if int(right.source_time_ns) > int(left.source_time_ns)
        ]
        log_steps = [
            (right.log_time_ns - left.log_time_ns) / 1_000_000.0
            for left, right in pairwise(estimates)
            if right.log_time_ns > left.log_time_ns
        ]
        median_source_step = float(np.median(source_steps)) if source_steps else None
        median_log_step = float(np.median(log_steps)) if log_steps else None
        increment_ratio = (
            None
            if median_source_step is None
            or median_log_step is None
            or median_log_step == 0.0
            else median_source_step / median_log_step
        )
        payload[result.recording_id] = {
            "paired_messages": len(pairs),
            "ambiguous_estimate_messages": len(
                result.synchronization.ambiguous_estimate_indices
            ),
            "unmatched_estimate_messages": len(
                result.synchronization.unmatched_estimate_indices
            ),
            "source_delta_ms": _distribution(source_delta_ms),
            "log_delta_ms": _distribution(log_delta_ms),
            "source_delta_drift_ms_per_s": drift,
            "median_estimate_source_step_ms": median_source_step,
            "median_estimate_log_step_ms": median_log_step,
            "source_to_log_increment_ratio": increment_ratio,
            "sensitivity_pair_counts": result.sensitivity_counts,
        }
    return payload


def _plot_overlays(
    result: _RecordingResult,
    output_directory: Path,
    *,
    maximum: int,
) -> int:
    if maximum <= 0 or result.decoded is None or not result.metrics:
        return 0
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        LOGGER.warning("matplotlib unavailable; overlays skipped")
        return 0
    completed_pairs = sorted(
        {
            (estimate, comparator)
            for estimate, comparator, metric in result.metrics
            if metric.status == "comparison_completed"
        }
    )
    if not completed_pairs:
        return 0
    estimate_by_index = {
        frame.message_index: frame for frame in result.decoded.estimated_frames
    }
    preferred_positions: list[int] = [0, len(completed_pairs) - 1]
    # Include at least one example for every observed spline length.
    represented_intervals: set[int] = set()
    for position, (estimate_index, _) in enumerate(completed_pairs):
        interval_count = estimate_by_index[estimate_index].interval_count
        if interval_count is not None and interval_count not in represented_intervals:
            preferred_positions.append(position)
            represented_intervals.add(interval_count)
    # Include both edges of each converter-ready run so regime transitions are
    # visible instead of selecting only the long final valid block.
    ready_indices = [
        frame.message_index
        for frame in result.decoded.estimated_frames
        if frame.candidate_ready
    ]
    if ready_indices:
        run_edges = {ready_indices[0], ready_indices[-1]}
        for left, right in pairwise(ready_indices):
            if right != left + 1:
                run_edges.update((left, right))
        pair_position_by_estimate = {
            estimate_index: position
            for position, (estimate_index, _) in enumerate(completed_pairs)
        }
        preferred_positions.extend(
            pair_position_by_estimate[index]
            for index in sorted(run_edges)
            if index in pair_position_by_estimate
        )
    evenly_spaced = np.linspace(
        0,
        len(completed_pairs) - 1,
        min(maximum, len(completed_pairs)),
    ).astype(int)
    preferred_positions.extend(map(int, evenly_spaced))
    selected_positions: list[int] = []
    for position in preferred_positions:
        if position not in selected_positions:
            selected_positions.append(position)
        if len(selected_positions) >= maximum:
            break
    positions = np.asarray(sorted(selected_positions), dtype=int)
    comparator_by_index = {
        frame.message_index: frame for frame in result.decoded.comparator_frames
    }
    overlay_directory = output_directory / "validation_overlays" / result.recording_id
    overlay_directory.mkdir(parents=True, exist_ok=True)
    written = 0
    for output_index, position in enumerate(positions):
        estimate_index, comparator_index = completed_pairs[int(position)]
        comparator = comparator_by_index[comparator_index]
        if comparator.geometry is None:
            continue
        fig, axis = plt.subplots(figsize=(8, 5))
        axis.plot(
            comparator.geometry.x,
            comparator.geometry.y,
            color="black",
            linewidth=2.2,
            label="ego-lane comparator (not ground truth)",
        )
        for hypothesis, color in (
            ("curvature_rate__anchor_zero", "tab:blue"),
            ("curvature_delta__anchor_zero", "tab:orange"),
        ):
            curve = result.generated_curves.get((estimate_index, hypothesis))
            if curve is not None:
                axis.plot(curve.x, curve.y, color=color, label=hypothesis)
        axis.set_aspect("equal", adjustable="datalim")
        axis.set_xlabel("x [unverified shared frame]")
        axis.set_ylabel("y [unverified shared frame]")
        axis.set_title(
            f"{result.recording_id}, diagnostic pair {output_index:03d}\n"
            "No fitted alignment, scaling, reflection, or station shift"
        )
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(overlay_directory / f"pair_{output_index:03d}.png", dpi=160)
        plt.close(fig)
        written += 1
    return written


def _write_outputs(
    results: Sequence[_RecordingResult],
    *,
    output_directory: Path,
    sessions_confirmed: bool,
    arguments: argparse.Namespace,
) -> dict[str, Any]:
    output_directory.mkdir(parents=True, exist_ok=True)
    duplicate_flags, conflict_flags = _duplicate_flags(
        results,
        sessions_confirmed=sessions_confirmed,
    )
    frame_rows = _frame_rows(
        results,
        duplicate_flags=duplicate_flags,
        conflict_flags=conflict_flags,
    )
    sync_rows = _synchronization_rows(results)
    metric_rows = _metric_rows(results, duplicate_flags=duplicate_flags)
    duplicate_rows = _duplicate_gap_rows(results, sessions_confirmed=sessions_confirmed)

    _write_csv(
        output_directory / "frame_states.csv",
        (
            "recording_id",
            "session_id",
            "message_index",
            "relative_recording_time_s",
            "estimator_state",
            "estimator_error",
            "conversion_state",
            "interval_count",
            "total_path_count",
            "keep_lane_count",
            "synchronization_state",
            "source_delta_ms",
            "duplicate_of",
            "timestamp_conflict",
        ),
        frame_rows,
    )
    _write_csv(
        output_directory / "synchronization_audit.csv",
        (
            "recording_id",
            "session_id",
            "estimate_message_index",
            "relative_recording_time_s",
            "state",
            "comparator_message_index",
            "comparator_state",
            "source_delta_ms",
            "log_delta_ms",
        ),
        sync_rows,
    )
    metric_fields = [
        "recording_id",
        "session_id",
        "estimate_message_index",
        "comparator_message_index",
        "hypothesis",
        "status",
        "failure_code",
        "common_coverage_m",
        "station_count",
        "lateral_rms_m",
        "lateral_median_abs_m",
        "lateral_p95_abs_m",
        "lateral_max_abs_m",
        "along_track_rms_m",
        "heading_rms_rad",
        "heading_p95_abs_rad",
        "curvature_rms_per_m",
        "endpoint_position_error_m",
        "initial_position_error_m",
        "initial_heading_error_rad",
        "initial_curvature_error_per_m",
        "symmetric_chamfer_m",
        "symmetric_hausdorff_m",
        "projection_monotonic_fraction",
        "maximum_abs_curvature_per_m",
        "maximum_abs_curvature_rate_per_m2",
        "self_intersection_detected",
        "duplicate_source_frame",
    ]
    _write_csv(output_directory / "hypothesis_metrics.csv", metric_fields, metric_rows)
    _write_csv(
        output_directory / "duplicate_gap_audit.csv",
        (
            "session_id",
            "stream",
            "event",
            "left_recording_id",
            "right_recording_id",
            "relative_session_time_s",
            "delta_ms",
        ),
        duplicate_rows,
    )

    manifest_records: list[dict[str, Any]] = []
    all_estimate_hashes: set[str] = set()
    all_comparator_hashes: set[str] = set()
    aggregate_estimator = Counter()
    aggregate_conversion = Counter()
    runs_payload: dict[str, Any] = {}
    availability_by_recording: dict[str, Any] = {}
    session_estimator_counts: dict[str, Counter[str]] = defaultdict(Counter)
    session_conversion_counts: dict[str, Counter[str]] = defaultdict(Counter)
    transitions = Counter()
    overlay_count = 0
    session_frames: dict[str, list[tuple[int, EstimatedFrameAudit]]] = defaultdict(list)
    for result in results:
        if result.decoded is None:
            manifest_records.append(
                {
                    "recording_id": result.recording_id,
                    "session_id": result.session_id,
                    "status": result.status,
                    "error_code": result.error_code,
                }
            )
            continue
        unique_frames = [
            frame
            for frame in result.decoded.estimated_frames
            if (result.recording_id, frame.message_index) not in duplicate_flags
        ]
        counts = audit_counts(unique_frames)
        aggregate_estimator.update(counts["estimator_states"])
        aggregate_conversion.update(counts["conversion_states"])
        availability_by_recording[result.recording_id] = audit_counts(
            result.decoded.estimated_frames
        )
        session_estimator_counts[result.session_id].update(counts["estimator_states"])
        session_conversion_counts[result.session_id].update(counts["conversion_states"])
        session_frames[result.session_id].extend(
            (int(frame.source_time_ns), frame)
            for frame in unique_frames
            if frame.source_time_ns is not None
        )
        all_estimate_hashes.update(result.decoded.estimate_schema_fingerprints)
        all_comparator_hashes.update(result.decoded.comparator_schema_fingerprints)
        runs_payload[result.recording_id] = [
            {"state": state, "message_count": length}
            for state, length in contiguous_state_runs(result.decoded.estimated_frames)
        ]
        transitions.update(
            (source, target)
            for source, target, count in state_transition_counts(result.decoded.estimated_frames)
            for _ in range(count)
        )
        manifest_records.append(
            {
                "recording_id": result.recording_id,
                "session_id": result.session_id,
                "status": result.status,
                "scan_complete": result.decoded.scan_complete,
                "decoded_estimate_messages": len(result.decoded.estimated_frames),
                "decoded_comparator_messages": len(result.decoded.comparator_frames),
                "estimate_schema_fingerprints": list(result.decoded.estimate_schema_fingerprints),
                "comparator_schema_fingerprints": list(result.decoded.comparator_schema_fingerprints),
                "sync_sensitivity_pair_counts": result.sensitivity_counts,
            }
        )
        if arguments.assume_same_frame:
            overlay_count += _plot_overlays(
                result,
                output_directory,
                maximum=arguments.max_overlays_per_recording,
            )

    file_count_matches = len(results) == arguments.expected_file_count
    files_succeeded = all(result.decoded is not None for result in results)
    scans_complete = all(
        result.decoded is not None and result.decoded.scan_complete for result in results
    )
    schema_consistent = len(all_estimate_hashes) == 1 and len(all_comparator_hashes) == 1
    conflicting_timestamps = any(
        row["event"] == "conflicting_same_timestamp" for row in duplicate_rows
    )
    files_have_required_topics = all(
        result.decoded is not None
        and len(result.decoded.estimated_frames) > 0
        and len(result.decoded.comparator_frames) > 0
        for result in results
    )
    corpus_complete = bool(
        file_count_matches
        and files_succeeded
        and scans_complete
        and sessions_confirmed
        and files_have_required_topics
        and schema_consistent
        and not conflicting_timestamps
    )
    manifest = {
        "purpose": "semantic_geometry_validation",
        "package_version": "0.3.8",
        "corpus_status": "complete" if corpus_complete else "incomplete",
        "requested_file_count": arguments.expected_file_count,
        "resolved_file_count": len(results),
        "file_count_matches": file_count_matches,
        "sessions_confirmed": sessions_confirmed,
        "required_topics_present_in_every_file": files_have_required_topics,
        "schema_consistent_across_files": schema_consistent,
        "estimate_schema_fingerprints": sorted(all_estimate_hashes),
        "comparator_schema_fingerprints": sorted(all_comparator_hashes),
        "records": manifest_records,
        "privacy": {
            "source_filenames_exported": False,
            "absolute_timestamps_exported": False,
            "raw_coordinates_exported_in_tables_or_json": False,
            "overlays_contain_confidential_geometry": overlay_count > 0,
        },
    }
    _write_json(output_directory / "corpus_manifest.json", manifest)

    availability = {
        "purpose": "estimator_availability_audit",
        "decoded_estimate_messages": len(frame_rows),
        "unique_estimate_messages": len(frame_rows) - len(duplicate_flags),
        "duplicate_estimate_messages": len(duplicate_flags),
        "estimator_states": dict(sorted(aggregate_estimator.items())),
        "conversion_states": dict(sorted(aggregate_conversion.items())),
        "counts_by_recording_raw": availability_by_recording,
        "counts_by_session_unique": {
            session_id: {
                "estimator_states": dict(sorted(session_estimator_counts[session_id].items())),
                "conversion_states": dict(sorted(session_conversion_counts[session_id].items())),
            }
            for session_id in sorted(session_estimator_counts)
        },
        "counts_reconcile": (
            sum(aggregate_estimator.values())
            == len(frame_rows) - len(duplicate_flags)
        ),
        "contiguous_runs_by_recording": runs_payload,
        "contiguous_runs_by_session_unique": {
            session_id: [
                {"state": state, "message_count": length}
                for state, length in contiguous_state_runs(
                    [
                        frame
                        for _, frame in sorted(
                            session_frames[session_id],
                            key=lambda item: item[0],
                        )
                    ]
                )
            ]
            for session_id in sorted(session_frames)
        },
        "transition_matrix_within_recordings": [
            {"from": source, "to": target, "count": count}
            for (source, target), count in sorted(transitions.items())
        ],
        "transition_matrix_within_sessions_unique": {
            session_id: [
                {"from": source, "to": target, "count": count}
                for source, target, count in state_transition_counts(
                    [
                        frame
                        for _, frame in sorted(
                            session_frames[session_id],
                            key=lambda item: item[0],
                        )
                    ]
                )
            ]
            for session_id in sorted(session_frames)
        },
        "selection_bias_warning": (
            "geometry rows are conditional on estimator availability; reported-error "
            "frames are retained and must not be silently removed from the denominator"
        ),
    }
    _write_json(output_directory / "availability_summary.json", availability)

    decision = _semantic_decision(
        metric_rows,
        sessions_confirmed=sessions_confirmed,
        lateral_tolerance=arguments.absolute_lateral_rms_tolerance_m,
        heading_tolerance=arguments.absolute_heading_p95_tolerance_rad,
    )
    semantic_summary = {
        "purpose": "semantic_geometry_validation",
        "training_eligible": False,
        "ground_truth_confirmed": False,
        "comparator_independence_confirmed": False,
        "comparator_label": "ego_lane_path comparator (not ground truth)",
        "same_frame_operator_confirmation": arguments.assume_same_frame,
        "motion_compensation_confirmed": False,
        "timestamp_tolerance_authoritative": False,
        "comparison_tolerance_ms": arguments.comparison_max_delta_ms,
        "synchronization_diagnostics_by_recording": (
            _synchronization_diagnostics(results)
        ),
        "hypotheses": {
            "curvature_rate__anchor_zero": (
                "segment_starts are boundaries; initial state is at s=0; "
                "curvature_change is d(kappa)/ds"
            ),
            "curvature_delta__anchor_zero": (
                "segment_starts are boundaries; initial state is at s=0; "
                "curvature_change is total delta-kappa per interval"
            ),
        },
        "index_anchor_warning": (
            "index_0 anchor is evaluated only when explicitly present; an implicit "
            "Protobuf zero default is not accepted as semantic evidence"
        ),
        "generated_curve_count": sum(len(result.generated_curves) for result in results),
        "generation_failure_count": sum(len(result.generation_failures) for result in results),
        "completed_comparison_rows": sum(
            row.get("status") == "comparison_completed" for row in metric_rows
        ),
        "overlay_count": overlay_count,
        "decision": decision,
        "prohibited_outputs": {
            "training_residuals_exported": False,
            "gaussian_fitted": False,
            "likelihood_reported": False,
            "train_test_split_created": False,
            "planner_performance_claimed": False,
        },
        "next_gate": (
            "Review stratified overlays and per-session hypothesis stability, then "
            "obtain authoritative spline, frame, unit, timestamp, and signal-lineage "
            "documentation before creating residuals."
        ),
    }
    _write_json(output_directory / "semantic_validation_summary.json", semantic_summary)
    return {
        "corpus_complete": corpus_complete,
        "resolved_file_count": len(results),
        "decoded_estimate_messages_raw": len(frame_rows),
        "decoded_estimate_messages_unique": len(frame_rows) - len(duplicate_flags),
        "duplicate_estimate_messages": len(duplicate_flags),
        "candidate_ready_messages": aggregate_conversion.get("candidate_ready", 0),
        "semantic_decision": decision["status"],
        "output_directory": output_directory,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )
    if arguments.expected_file_count < 1:
        parser.error("--expected-file-count must be positive")
    if arguments.max_overlays_per_recording < 0:
        parser.error("--max-overlays-per-recording must be nonnegative")
    if not math.isfinite(arguments.comparison_max_delta_ms) or arguments.comparison_max_delta_ms < 0:
        parser.error("--comparison-max-delta-ms must be finite and nonnegative")
    if not math.isfinite(arguments.max_step_m) or arguments.max_step_m <= 0:
        parser.error("--max-step-m must be finite and positive")
    if not math.isfinite(arguments.minimum_common_coverage_m) or arguments.minimum_common_coverage_m <= 0:
        parser.error("--minimum-common-coverage-m must be finite and positive")
    for value in arguments.sync_sensitivity_ms:
        if not math.isfinite(value) or value < 0:
            parser.error("--sync-sensitivity-ms values must be finite and nonnegative")
    for option, value in (
        ("--absolute-lateral-rms-tolerance-m", arguments.absolute_lateral_rms_tolerance_m),
        ("--absolute-heading-p95-tolerance-rad", arguments.absolute_heading_p95_tolerance_rad),
    ):
        if value is not None and (not math.isfinite(value) or value <= 0):
            parser.error(f"{option} must be finite and positive")
    try:
        files = _resolve_mcap_files(arguments.mcap_inputs)
        session_ids, sessions_confirmed = _load_session_map(
            arguments.session_map,
            files,
        )
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")

    results = [
        _process_recording(
            path,
            recording_id=f"recording_{index:03d}",
            session_id=session_ids[path],
            arguments=arguments,
        )
        for index, path in enumerate(files, 1)
    ]
    try:
        summary = _write_outputs(
            results,
            output_directory=arguments.output_directory,
            sessions_confirmed=sessions_confirmed,
            arguments=arguments,
        )
    except (ValueError, OSError, GeometryValidationError) as error:
        parser.exit(2, f"error while saving validation audit: {error}\n")

    print(f"Semantic validation outputs: {summary['output_directory']}")
    print(
        "Estimate messages audited: "
        f"{summary['decoded_estimate_messages_raw']} raw / "
        f"{summary['decoded_estimate_messages_unique']} unique; "
        "strict geometry candidates: "
        f"{summary['candidate_ready_messages']}"
    )
    print(
        "Semantic decision: "
        f"{summary['semantic_decision']}. "
        "Training remains prohibited in v0.3.8."
    )
    return 0 if summary["corpus_complete"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
