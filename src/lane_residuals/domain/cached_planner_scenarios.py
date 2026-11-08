"""Fixed spatial perturbation context on original complete feature rows."""

from dataclasses import asdict
import hashlib
import json

import numpy as np

from .reference_planner import ReferencePlannerConfig
from .sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from .spatial_planner_response import STATIONS_M


REVISION = "v0.19.29-cached-spatial-scenarios-2026-11-08-a1"
DT_S = 0.1
PROTOCOL = {
    "question": "incremental_spatial_response_relative_to_identical_nominal_plan",
    "pilot_selection": "lexicographically_first_original_development_outing",
    "row_selection": "every_original_complete_feature_row_retained_in_original_order",
    "scenario_dt_s": DT_S,
    "dt_interpretation": "fixed_prediction_grid_not_measured_replanning_cadence",
    "initial_state": "zero_incremental_state_from_common_nominal_plan",
    "baseline_cancellation": "same_affine_dynamics_state_and_previous_input_in_both_plans",
    "reference": "original_sensor_EDP_minus_RLMB_fusion_pseudo_residuals",
    "stations_m": list(STATIONS_M),
    "planner": asdict(ReferencePlannerConfig()),
    "speed": "original_complete_row_feature_without_replacement_or_interpolation",
    "eligibility": ["speed_at_least_minimum", "lookahead_at_most_100m"],
    "comparison_stage": "scenario_preparation_without_model_sampling_or_planner_scoring",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def prepare_scenario_rows(block, fold: dict) -> tuple[list[dict], dict, dict]:
    """Retain every admitted identity and explicitly mask unsuitable speeds."""
    arrays = block.archive.arrays
    indices = arrays["conditioned_profile_indices"]
    profiles = np.asarray(block.y)
    conditions = np.asarray(block.x)
    offsets = np.asarray(block.offsets)
    _require(tuple(BMW_CONDITION_FEATURE_NAMES)[0] == "speed_mps", "unexpected speed feature position")
    _require(profiles.shape == (len(indices), 21) and conditions.shape == (len(indices), 6)
             and len(indices) > 0 and np.isfinite(profiles).all() and np.isfinite(conditions).all(),
             "scenario original matched shapes and values required")
    _require(np.array_equal(arrays["stations_m"], STATIONS_M), "scenario station grid differs")
    _require(fold["validation_outing"] == block.outing_id
             and block.outing_id not in fold["training_outings"], "scenario held out outing mismatch")
    _require(offsets[0] == 0 and offsets[-1] == len(indices)
             and np.all(np.diff(offsets) > 0), "scenario sequence resets differ")
    speed = conditions[:, 0].copy()
    config = ReferencePlannerConfig()
    lookahead = speed * DT_S * config.horizon_steps
    eligible = (speed >= config.minimum_speed_mps) & (lookahead <= STATIONS_M[-1])
    rows = []
    seen = set()
    identity_fields = ("recording_id", "candidate_index", "pair_index", "estimate_message_index",
                       "reference_message_index", "estimate_source_time_ns_decimal",
                       "reference_source_time_ns_decimal")
    for matched_row, profile_row in enumerate(indices):
        identity = {}
        for name in identity_fields:
            value = arrays[name][profile_row]
            identity[name] = str(value) if name == "recording_id" or name.endswith("_decimal") else int(value)
        raw = block.archive.raw_sha256_by_recording[identity["recording_id"]]
        key = (raw, identity["candidate_index"], identity["pair_index"])
        _require(key not in seen, "scenario duplicate frame identity")
        seen.add(key)
        if speed[matched_row] < config.minimum_speed_mps:
            status = "speed_below_planner_minimum"
        elif lookahead[matched_row] > STATIONS_M[-1]:
            status = "lookahead_exceeds_100m"
        else:
            status = "eligible"
        rows.append({
            "matched_row": matched_row,
            "geometry_profile_row": int(profile_row),
            "outing_id": block.outing_id,
            "archive_sha256": block.archive.summary_sha256,
            "raw_sha256": raw,
            **identity,
            "original_speed_mps": float(speed[matched_row]),
            "lookahead_m": float(lookahead[matched_row]),
            "status": status,
        })
    encoded = (json.dumps(rows, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    result = {
        "residuals_m": profiles.copy(),
        "speed_mps": speed,
        "eligible": eligible,
        "matched_row": np.arange(len(indices), dtype=np.int64),
        "geometry_profile_row": indices.copy(),
        "conditioned_sequence_offsets": offsets.copy(),
        "stations_m": np.asarray(STATIONS_M),
    }
    counts = {name: sum(r["status"] == name for r in rows)
              for name in ("eligible", "speed_below_planner_minimum", "lookahead_exceeds_100m")}
    summary = {
        "original_complete_rows": len(indices),
        "eligible_rows": counts["eligible"],
        "status_counts": counts,
        "rows_sha256": hashlib.sha256(encoded).hexdigest(),
        "source_archive_sha256": block.archive.summary_sha256,
        "nominal_reference_xy_in_archive": False,
        "observed_vehicle_initial_state_in_archive": False,
        "reference_association": "validated_original_100m_extraction_and_exact_frame_identifiers",
        "initial_state_semantics": PROTOCOL["initial_state"],
    }
    return rows, result, summary
