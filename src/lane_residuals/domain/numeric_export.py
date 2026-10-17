"""Fixed v0.19.12 development archive policy; no admission or model fitting."""

from __future__ import annotations

from collections import Counter
import math
import re
from types import MappingProxyType

import numpy as np

from .exploratory_residuals import sequence_layout
from .recording_ingestion import RecordingIngestionError
from .residual_dataset import CANONICAL_MODEL_STATIONS_M
from .sequence_dataset import BMW_CONDITION_FEATURE_NAMES

REVISION = "v0.19.12-generic-development-numeric-export-2026-10-17-a3"
VALIDATION_REVISION = "v0.19.12-generic-numeric-validation-2026-10-17-a3"
AUTHORIZATION_REVISION = "v0.19.12-development-exposure-authorization-2026-10-17-a3"
AUTHORIZATION_PURPOSE = "explicit_numeric_export_and_permanent_development_reservation"
PURPOSE = "development_only_recording_local_edp_rlmb_numeric_export"
EXPOSURE_POLICY = "permanent_development_reservation_and_numeric_exposure_v01912_a3"
ACCEPTED_READINESS_SOURCE = "069e1095426bd82f675af093356e699868306d2fa297a8a27b7e058295d062b7"
MAX_EDP = 100_000
MAX_AUDIT_BYTES = 256 * 1024**2
MAX_SUMMARY_BYTES = 64 * 1024**2
MAX_NPZ_BYTES = 128 * 1024**2
PUBLICATION_SECONDS = 300
ARTIFACT_RESERVE_BYTES = 1024**3
AUTHORIZATION_BYTES = 65_536
SUMMARY = "numeric_export.json"
AUDIT = "candidate_audit.json"
ARCHIVE = "residuals.npz"
ATTESTATIONS = frozenset({"explicit_numeric_export_selection", "permanently_reserve_linked_outings_for_development",
    "prospective_final_candidates_excluded", "pipeline_scope_label_is_not_exposure_authorization"})
AUTHORIZATION_FIELDS = frozenset({"contract_revision", "purpose", "batch_id", "registration_sha256",
    "source_specification_sha256", "preserved_readiness_report_sha256", "authorized_raw_sha256", "attestations"})
NUMERIC_ESTIMATE_ADMISSION_POLICY_V01912 = MappingProxyType({
    "policy_id": "v0.19.12-numeric-through-v0.19.11-sink-a2",
    "mechanism": "unchanged_v01911_scientific_sink", "structural_legacy_v1": True,
    "flag_absent_v2_root_file_sha256": ("dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4",
        "604f854d430cf394693b4fe8944b8bbd12d10959e33935e716d65955a0b2ab9a"),
    "historical_defaults_unchanged": True,
})
CONFIDENCE_SEMANTICS = {"assumed_bucket_size_m": 5.0,
    "provenance_status": "assumed_unconfirmed_implementation_constant", "applies_to": "all_admitted_estimate_roots",
    "basis": "interface names detail::kConfidenceScoreBucketSize; numeric value not source-traced"}
EXPOSURE = {"status": "permanently_development_only", "final_test_eligible": False,
    "applies_to": "recording_and_any_linked_physical_outing"}
OBSERVER_CODES = frozenset({"numeric_observer_metadata_unavailable", "numeric_observer_alignment_mismatch"})
ARRAY_DTYPES = {"stations_m": "<f8", "condition_names": "<U48", "residuals_m": "<f8", "recording_id": "<U48",
    "candidate_index": "<i8", "pair_index": "<i8", "estimate_message_index": "<i8", "reference_message_index": "<i8",
    "estimate_source_time_ns_decimal": "<U20", "reference_source_time_ns_decimal": "<U20",
    "geometry_sequence_offsets": "<i8", "conditioned_profile_indices": "<i8", "conditions": "<f8",
    "conditioned_sequence_offsets": "<i8"}
SUPPORT_FIELDS = frozenset({"geometric_profile_count", "conditioned_profile_count", "geometry_sequences",
    "conditioned_sequences", "geometry_transition_count", "conditioned_transition_count"})
RECORDING_FIELDS = frozenset({"recording_id", "raw_sha256", "size_bytes", "source_declaration_status", "status", "failure_code",
    "invalidation_codes", "reader_failure_context", "binding_observations", "stream_integrity", "readiness",
    "condition_availability", "recorded_input_causality_checked", "readiness_matches_preserved", "execution_observations",
    "candidate_start", "candidate_stop", "residual_failure_counts", "support", "outcome_exposure", "observer_failure_counts"})
SUMMARY_FIELDS = frozenset({"contract_revision", "purpose", "status", "failure_code", "batch_id", "registration_sha256",
    "source_specification_sha256", "preserved_inventory_report_sha256", "preserved_decode_report_sha256",
    "preserved_readiness_report_sha256", "preserved_readiness_contract_revision", "preserved_readiness_runtime_source_sha256",
    "runtime_versions", "exposure_authorization_sha256", "runtime_source_sha256", "reader_implementation",
    "scientific_policy_revision", "estimate_admission_policy", "confidence_bucket_semantics", "outcome_exposure_policy",
    "schema_semantics_basis", "schema_semantics_deployed_producer_retraced", "resources_at_start", "execution_limits",
    "technical_recording_count", "independent_outing_count", "roles_assigned", "cohort_lock_created", "model_fitted",
    "standardizers_fitted", "residuals_exported", "numeric_conditions_exported", "recorded_input_causality_checked_for_all_recordings",
    "physical_input_availability_proven", "reference_independence_proven", "raw_cache_deletion_authorized",
    "pre_residual_candidate_count", "pre_residual_complete_condition_count", "condition_failure_counts",
    "residual_failure_counts", "support", "recordings", "artifacts_sha256", "interpretation"})
AUDIT_FIELDS = frozenset({"recording_id", "candidate_index", "pair_index", "estimate_message_index", "reference_message_index",
    "estimate_source_time_ns_decimal_private", "reference_source_time_ns_decimal_private", "estimate_log_time_ns_decimal_private",
    "estimate_publish_time_ns_decimal_private", "signed_reference_minus_estimate_ns_decimal", "condition_failure_codes",
    "speed_bracket_evidence", "residual_failure_code", "estimate_file_descriptor_sha256", "confidence_vector_length",
    "estimate_native_station_end_m", "anchor_distance_m", "reference_anchor_station_m", "residual_available", "conditions_available"})
SPEED_FIELDS = frozenset({"previous_lower_timestamp_ns_decimal_private", "previous_upper_timestamp_ns_decimal_private",
    "current_lower_timestamp_ns_decimal_private", "current_upper_timestamp_ns_decimal_private",
    "maximum_input_log_time_ns_decimal_private", "maximum_input_publish_time_ns_decimal_private",
    "minimum_input_log_time_ns_decimal_private"})


def require(condition, code="numeric_export_invalid"):
    if not condition:
        raise RecordingIngestionError(code)


def admission_policy():
    return {**NUMERIC_ESTIMATE_ADMISSION_POLICY_V01912,
        "flag_absent_v2_root_file_sha256": list(NUMERIC_ESTIMATE_ADMISSION_POLICY_V01912["flag_absent_v2_root_file_sha256"])}


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected))


def integer(value, maximum=2**63-1):
    require(type(value) is int and 0 <= value <= maximum)
    return value


def digest(value):
    require(type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None)
    return value


def decimal(value, *, signed=False):
    require(type(value) is str and len(value) <= 21 and re.fullmatch(r"-?(0|[1-9][0-9]*)" if signed else r"0|[1-9][0-9]*", value) is not None)
    number = int(value)
    require(str(number) == value and (-(2**64-1) <= number < 2**64 if signed else 0 <= number < 2**64))
    return number


def histogram(value, allowed=None):
    require(type(value) is dict)
    for key, count in value.items():
        require(type(key) is str and bool(key) and (allowed is None or key in allowed))
        integer(count)
        require(count > 0)


def finite(value):
    require(type(value) in (int, float) and math.isfinite(value))
    return value


def build_numeric_archive(candidates):
    """Use frozen sequence rules with a separate U48 generic-ID consumer."""
    profiles = [r for r in candidates if r["residuals_m"] is not None]
    for row in profiles:
        require(type(row["recording_id"]) is str and re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", row["recording_id"]) is not None)
        for side in ("estimate", "reference"):
            integer(row[f"{side}_source_time_ns_private"], 2**64-1)
    indices = [i for i, row in enumerate(profiles) if row["conditions"] is not None]
    conditioned = [profiles[i] for i in indices]
    go, gs = sequence_layout(profiles)
    co, cs = sequence_layout(conditioned)
    values = {"stations_m": CANONICAL_MODEL_STATIONS_M, "condition_names": BMW_CONDITION_FEATURE_NAMES,
        "residuals_m": [r["residuals_m"] for r in profiles], "recording_id": [r["recording_id"] for r in profiles],
        **{k: [r[k] for r in profiles] for k in ("candidate_index", "pair_index", "estimate_message_index", "reference_message_index")},
        **{f"{s}_source_time_ns_decimal": [str(r[f"{s}_source_time_ns_private"]) for r in profiles] for s in ("estimate", "reference")},
        "geometry_sequence_offsets": go, "conditioned_sequence_offsets": co, "conditioned_profile_indices": indices,
        "conditions": [r["conditions"] for r in conditioned]}
    arrays = {name: np.asarray(value, dtype=ARRAY_DTYPES[name], order="C") for name, value in values.items()}
    arrays["residuals_m"] = arrays["residuals_m"].reshape(-1, 21)
    arrays["conditions"] = arrays["conditions"].reshape(-1, 6)
    require(np.isfinite(arrays["residuals_m"]).all() and np.isfinite(arrays["conditions"]).all())
    support = {"geometric_profile_count": len(profiles), "conditioned_profile_count": len(conditioned),
        "geometry_sequences": gs, "conditioned_sequences": cs,
        "geometry_transition_count": sum(s["transition_count"] for s in gs),
        "conditioned_transition_count": sum(s["transition_count"] for s in cs)}
    return arrays, support


def audit_row(row):
    result = {k: row[k] for k in ("recording_id", "candidate_index", "pair_index", "estimate_message_index",
        "reference_message_index", "condition_failure_codes", "residual_failure_code", "estimate_file_descriptor_sha256",
        "confidence_vector_length", "estimate_native_station_end_m", "anchor_distance_m", "reference_anchor_station_m")}
    for side in ("estimate_source_time", "reference_source_time", "estimate_log_time", "estimate_publish_time"):
        result[f"{side}_ns_decimal_private"] = str(row[f"{side}_ns_private"])
    result["signed_reference_minus_estimate_ns_decimal"] = str(row["signed_reference_minus_estimate_ns"])
    result["speed_bracket_evidence"] = {key.replace("_ns_private", "_ns_decimal_private"): str(value)
        for key, value in row["speed_bracket_evidence"].items()}
    result["residual_available"] = row["residuals_m"] is not None
    result["conditions_available"] = row["conditions"] is not None
    keys(result, AUDIT_FIELDS)
    return result


def failures(rows, field):
    return dict(sorted(Counter(code for row in rows for code in (
        row[field] if isinstance(row[field], list) else [row[field]] if row[field] is not None else [])).items()))
