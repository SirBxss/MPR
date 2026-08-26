"""Freeze the reviewed v0.15.3 one-state model for planner development."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..domain.sequence_dataset import SequenceStandardizer
from ..io.expanded_sequence_dataset import read_csv_rows, read_json_object
from ..io.model_evaluation import ONE_STATE_AR_REQUIRED_FILES
from ..io.reports import write_strict_json
from ..modeling.aiohmm import AutoregressiveInputOutputHMM
from ..modeling.development_residual import (
    DEVELOPMENT_MODEL_VERSION,
    SELECTED_DEVELOPMENT_AR_CEILING,
)
from .expanded_ar_boundary import (
    AR_BOUNDARY_TOLERANCE,
    FITTED_AR_CEILINGS,
    REFERENCE_AR_CEILING,
    _model_id,
)
from .sequence_contract import ensure_empty_output_directory, sha256_file

VERSION = DEVELOPMENT_MODEL_VERSION
REFERENCE_VERSION = "0.15.1"
BOUNDARY_AUDIT_VERSION = "0.15.3"
MODEL_FILENAME = "development_residual_model.json"
SUMMARY_FILENAME = "development_model_freeze_summary.json"

AR_BOUNDARY_ROOT_FILES = frozenset(
    {
        "ar_boundary_model_comparison.csv",
        "ar_boundary_fold_comparison.csv",
        "ar_boundary_station_comparison.csv",
        "ar_boundary_sensitivity_diagnostics.png",
        "ar_boundary_sensitivity_summary.json",
    }
)


def _hash_files(directory: Path, paths: set[str]) -> dict[str, str]:
    return {
        name: sha256_file(directory / name)
        for name in sorted(paths)
    }


def _validate_v0151_reference(
    directory: Path,
) -> tuple[Mapping[str, Any], dict[str, str]]:
    if not directory.is_dir():
        raise FileNotFoundError(f"v0.15.1 one-state directory not found: {directory}")
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != ONE_STATE_AR_REQUIRED_FILES:
        raise ValueError("v0.15.1 one-state directory filename set differs")
    summary = read_json_object(directory / "one_state_ar_summary.json")
    if (
        summary.get("version") != REFERENCE_VERSION
        or summary.get("status") != "complete"
        or summary.get("purpose")
        != "one_state_conditional_autoregressive_gaussian_ablation"
        or summary.get("state_count") != 1
        or summary.get("latent_state_switching") is not False
        or summary.get("final_model_selection_authorized") is not False
    ):
        raise ValueError("v0.15.1 one-state reference is not accepted")
    expected_hashes = summary.get("output_files_sha256")
    hashed_names = set(ONE_STATE_AR_REQUIRED_FILES) - {"one_state_ar_summary.json"}
    if not isinstance(expected_hashes, Mapping) or set(expected_hashes) != hashed_names:
        raise ValueError("v0.15.1 one-state output hash set differs")
    hashes = _hash_files(directory, set(ONE_STATE_AR_REQUIRED_FILES))
    for name in sorted(hashed_names):
        if expected_hashes.get(name) != hashes[name]:
            raise ValueError(f"v0.15.1 one-state output hash mismatch: {name}")
    return summary, hashes


def _validate_audit_hashes(
    directory: Path,
    summary: Mapping[str, Any],
) -> dict[str, str]:
    expected = summary.get("output_files_sha256")
    if not isinstance(expected, Mapping):
        raise ValueError("v0.15.3 output hashes are missing")
    actual_paths = {
        str(path.relative_to(directory).as_posix())
        for path in directory.rglob("*")
        if path.is_file() and path.name != "ar_boundary_sensitivity_summary.json"
    }
    if set(expected) != actual_paths:
        raise ValueError("v0.15.3 output hash path set differs")
    hashes = _hash_files(directory, actual_paths)
    for name, digest in hashes.items():
        if expected.get(name) != digest:
            raise ValueError(f"v0.15.3 output hash mismatch: {name}")
    hashes["ar_boundary_sensitivity_summary.json"] = sha256_file(
        directory / "ar_boundary_sensitivity_summary.json"
    )
    return hashes


def _normalized_model_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    configuration = result.get("configuration")
    if not isinstance(configuration, dict):
        raise ValueError("candidate model configuration is missing")
    configuration["maximum_absolute_autoregression"] = (
        "normalized_for_cross_ceiling_identity_check"
    )
    return result


def _validate_candidate(
    directory: Path,
    *,
    ceiling: float,
    reference_hashes: Mapping[str, str],
) -> tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    SequenceStandardizer,
    AutoregressiveInputOutputHMM,
]:
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != ONE_STATE_AR_REQUIRED_FILES:
        raise ValueError(f"v0.15.3 candidate filename set differs: {ceiling}")
    summary = read_json_object(directory / "one_state_ar_summary.json")
    model_bundle = read_json_object(directory / "one_state_ar_model.json")
    if (
        summary.get("version") != BOUNDARY_AUDIT_VERSION
        or summary.get("status") != "complete"
        or summary.get("purpose")
        != "one_state_ar_boundary_sensitivity_candidate"
        or summary.get("state_count") != 1
        or summary.get("latent_state_switching") is not False
        or summary.get("failed_restart_count") != 0
        or summary.get("selected_fit_nonconvergence_count") != 0
        or summary.get("one_state_ar_reference_files_sha256")
        != dict(reference_hashes)
    ):
        raise ValueError(f"v0.15.3 candidate summary is not accepted: {ceiling}")
    difference = summary.get("only_configuration_difference_from_v0151")
    expected_difference = {
        "maximum_absolute_autoregression": {
            "v0151": REFERENCE_AR_CEILING,
            "candidate": ceiling,
        }
    }
    if difference != expected_difference:
        raise ValueError(f"v0.15.3 candidate changed more than its cap: {ceiling}")
    if (
        model_bundle.get("version") != BOUNDARY_AUDIT_VERSION
        or model_bundle.get("status") != "complete"
        or model_bundle.get("role")
        != "descriptive_all_clean_development_fit_after_cross_validation"
        or model_bundle.get("not_an_untouched_final_model") is not True
    ):
        raise ValueError(f"v0.15.3 candidate model bundle differs: {ceiling}")
    standardizer_payload = model_bundle.get("standardizer")
    model_payload = model_bundle.get("model")
    if not isinstance(standardizer_payload, Mapping) or not isinstance(
        model_payload, Mapping
    ):
        raise ValueError(f"v0.15.3 candidate model is missing: {ceiling}")
    standardizer = SequenceStandardizer.from_dict(standardizer_payload)
    model = AutoregressiveInputOutputHMM.from_dict(model_payload)
    if (
        model.config.state_count != 1
        or model.config.input_dependent_transitions is not False
        or not np.isclose(
            model.config.maximum_absolute_autoregression,
            ceiling,
            rtol=0.0,
            atol=1e-12,
        )
        or not model.is_fitted
        or model.to_dict().get("converged") is not True
    ):
        raise ValueError(f"v0.15.3 candidate fitted model differs: {ceiling}")
    return summary, model_bundle, standardizer, model


def _comparison_rows(directory: Path) -> dict[str, Mapping[str, Any]]:
    rows = read_csv_rows(directory / "ar_boundary_model_comparison.csv")
    indexed = {str(row["model_id"]): row for row in rows}
    required = {
        _model_id(REFERENCE_AR_CEILING),
        _model_id(SELECTED_DEVELOPMENT_AR_CEILING),
    }
    if not required <= set(indexed):
        raise ValueError("v0.15.3 comparison is missing freeze variants")
    return {name: indexed[name] for name in sorted(required)}


def _binding_stations(directory: Path, model_id: str) -> list[float]:
    rows = read_csv_rows(directory / "ar_boundary_station_comparison.csv")
    return [
        float(row["station_m"])
        for row in rows
        if row.get("model_id") == model_id
        and str(row.get("candidate_cap_binding_station", "")).lower() == "true"
    ]


def run_development_model_freeze(
    *,
    one_state_ar_directory: Path,
    ar_boundary_directory: Path,
    output_directory: Path,
) -> tuple[dict[str, Any], int]:
    """Freeze the 0.99 all-clean fit without refitting or metric selection."""

    reference_summary, reference_hashes = _validate_v0151_reference(
        one_state_ar_directory
    )
    if not ar_boundary_directory.is_dir():
        raise FileNotFoundError(
            f"v0.15.3 AR-boundary directory not found: {ar_boundary_directory}"
        )
    root_entries = {path.name for path in ar_boundary_directory.iterdir()}
    if root_entries != {*AR_BOUNDARY_ROOT_FILES, "candidates"}:
        raise ValueError("v0.15.3 AR-boundary root filename set differs")
    audit_summary = read_json_object(
        ar_boundary_directory / "ar_boundary_sensitivity_summary.json"
    )
    if (
        audit_summary.get("version") != BOUNDARY_AUDIT_VERSION
        or audit_summary.get("status") != "complete"
        or audit_summary.get("purpose")
        != "one_state_ar_boundary_sensitivity_audit"
        or audit_summary.get("reference_ar_ceiling") != REFERENCE_AR_CEILING
        or audit_summary.get("fitted_candidate_ar_ceilings")
        != list(FITTED_AR_CEILINGS)
        or audit_summary.get("development_supported_ar_ceilings") != []
        or audit_summary.get("smallest_development_supported_ar_ceiling")
        is not None
        or audit_summary.get("development_result_classification")
        != "no_higher_ar_ceiling_passes_all_predeclared_checks"
        or audit_summary.get("ar_ceiling_selected_after_held_out_evaluation")
        is not False
        or audit_summary.get("final_model_selection_authorized") is not False
        or audit_summary.get("planner_model_frozen") is not False
        or audit_summary.get("one_state_ar_reference_files_sha256")
        != reference_hashes
    ):
        raise ValueError("v0.15.3 AR-boundary audit is not accepted")
    audit_hashes = _validate_audit_hashes(ar_boundary_directory, audit_summary)

    candidate_root = ar_boundary_directory / "candidates"
    expected_candidate_names = {_model_id(value) for value in FITTED_AR_CEILINGS}
    if {path.name for path in candidate_root.iterdir()} != expected_candidate_names:
        raise ValueError("v0.15.3 candidate directory set differs")
    candidates: dict[
        float,
        tuple[
            Mapping[str, Any],
            Mapping[str, Any],
            SequenceStandardizer,
            AutoregressiveInputOutputHMM,
        ],
    ] = {}
    for ceiling in FITTED_AR_CEILINGS:
        candidates[ceiling] = _validate_candidate(
            candidate_root / _model_id(ceiling),
            ceiling=ceiling,
            reference_hashes=reference_hashes,
        )

    selected_summary, selected_bundle, selected_standardizer, selected_model = (
        candidates[SELECTED_DEVELOPMENT_AR_CEILING]
    )
    normalized_models = {
        ceiling: _normalized_model_payload(bundle[1]["model"])
        for ceiling, bundle in candidates.items()
    }
    selected_normalized = normalized_models[SELECTED_DEVELOPMENT_AR_CEILING]
    if any(payload != selected_normalized for payload in normalized_models.values()):
        raise ValueError("higher-ceiling fitted models are not identical")
    if any(
        bundle[2].to_dict() != selected_standardizer.to_dict()
        for bundle in candidates.values()
    ):
        raise ValueError("higher-ceiling standardizers differ")
    maximum_fitted_ar = float(
        np.max(np.abs(selected_model.autoregressive_coefficients))
    )
    if maximum_fitted_ar >= (
        SELECTED_DEVELOPMENT_AR_CEILING - AR_BOUNDARY_TOLERANCE
    ):
        raise ValueError("selected 0.99 development model still touches its AR cap")

    decisions = audit_summary.get("predeclared_development_decisions")
    selected_decision = (
        decisions.get(_model_id(SELECTED_DEVELOPMENT_AR_CEILING))
        if isinstance(decisions, Mapping)
        else None
    )
    if (
        not isinstance(selected_decision, Mapping)
        or selected_decision.get("all_predeclared_development_checks_passed")
        is not False
    ):
        raise ValueError("v0.15.3 strict decision for the 0.99 cap is missing")

    comparison = _comparison_rows(ar_boundary_directory)
    reference_binding = _binding_stations(
        ar_boundary_directory, _model_id(REFERENCE_AR_CEILING)
    )
    selected_binding = _binding_stations(
        ar_boundary_directory, _model_id(SELECTED_DEVELOPMENT_AR_CEILING)
    )
    if selected_binding:
        raise ValueError("selected 0.99 model has a binding station")

    model_payload = selected_bundle["model"]
    bundle_payload: dict[str, Any] = {
        "schema_version": VERSION,
        "status": "complete",
        "purpose": "development_residual_model_for_planner_experiments",
        "model_family": "one_state_conditional_autoregressive_gaussian",
        "selected_ar_ceiling": SELECTED_DEVELOPMENT_AR_CEILING,
        "retained_reference_ar_ceiling": REFERENCE_AR_CEILING,
        "selection_basis": (
            "smallest_tested_nonbinding_ceiling_above_the_identical_interior_optimum"
        ),
        "selected_after_held_out_performance_evaluation": False,
        "strict_v0153_performance_gate_passed": False,
        "strict_v0153_performance_gate_result": dict(selected_decision),
        "higher_ceiling_fits_identical_except_configured_ceiling": True,
        "maximum_fitted_absolute_autoregression": maximum_fitted_ar,
        "development_planner_model_frozen": True,
        "final_model_selection_authorized": False,
        "journey_level_generalization_estimated": False,
        "untouched_final_test_drive_count": 0,
        "source_dataset_version": "0.13.1",
        "source_one_state_reference_version": REFERENCE_VERSION,
        "source_ar_boundary_audit_version": BOUNDARY_AUDIT_VERSION,
        "source_one_state_reference_files_sha256": reference_hashes,
        "source_ar_boundary_audit_files_sha256": audit_hashes,
        "residual_contract": {
            "stations_m": list(selected_standardizer.stations_m),
            "unit": "m",
            "definition": (
                "EDP estimate minus spatially aligned RLMB pseudo-reference, "
                "projected onto the pseudo-reference left unit normal"
            ),
            "positive_direction": (
                "left of the pseudo-reference with respect to increasing station"
            ),
            "reference_role": "RLMB pseudo-reference, not physical ground truth",
        },
        "condition_contract": {
            "feature_names_in_required_order": list(
                selected_standardizer.feature_names
            ),
            "input_units": "physical",
            "standardization": "bundled_all_clean_development_transform",
            "future_or_pseudo_reference_features_permitted": False,
        },
        "temporal_sampling_contract": {
            "sampling": "free_running_generated_history",
            "dependency_order": 1,
            "sequence_start": "training_marginal_conditional_gaussian_reset_prior",
            "reset_at_each_input_sequence": True,
            "independent_frame_sampling_permitted": False,
            "time_model": "discrete_step_with_nonconstant_observed_frame_interval",
        },
        "standardizer": selected_standardizer.to_dict(),
        "model": model_payload,
        "scientific_limitations": [
            (
                "Development-only fit from four technical groups within one "
                "same-day outing."
            ),
            "No untouched final journey was available for model selection.",
            "The strict v0.15.3 performance gates did not support a higher ceiling.",
            "The 0.99 cap is frozen only to release the binding 0.98 constraint.",
            (
                "RLMB is a pseudo-reference and retains documented "
                "source/timing limitations."
            ),
            "Near-field undercoverage remains after releasing the AR cap.",
            "Planner benefit has not yet been evaluated.",
        ],
        "confidentiality": "Model parameters derive from private BMW measurements.",
    }

    ensure_empty_output_directory(output_directory)
    model_path = output_directory / MODEL_FILENAME
    write_strict_json(model_path, bundle_payload)
    summary: dict[str, Any] = {
        "version": VERSION,
        "status": "complete",
        "purpose": "development_residual_model_freeze",
        "selected_model_file": MODEL_FILENAME,
        "selected_model_sha256": sha256_file(model_path),
        "selected_ar_ceiling": SELECTED_DEVELOPMENT_AR_CEILING,
        "retained_reference_ar_ceiling": REFERENCE_AR_CEILING,
        "selection_basis": bundle_payload["selection_basis"],
        "performance_selected": False,
        "strict_v0153_performance_gate_passed": False,
        "maximum_fitted_absolute_autoregression": maximum_fitted_ar,
        "reference_binding_stations_m": reference_binding,
        "reference_cap_binding_observed": bool(reference_binding),
        "selected_binding_stations_m": selected_binding,
        "higher_ceiling_fits_identical_except_configured_ceiling": True,
        "reported_freeze_variants": comparison,
        "development_planner_model_frozen": True,
        "final_model_selection_authorized": False,
        "journey_level_generalization_estimated": False,
        "planner_benefit_evaluated": False,
        "next_phase": "sample_frozen_residual_sequences_for_planner_evaluation",
        "source_one_state_reference_files_sha256": reference_hashes,
        "source_ar_boundary_audit_files_sha256": audit_hashes,
        "source_candidate_summary": {
            "version": selected_summary["version"],
            "model_id": _model_id(SELECTED_DEVELOPMENT_AR_CEILING),
        },
        "confidentiality": "Model parameters derive from private BMW measurements.",
    }
    write_strict_json(output_directory / SUMMARY_FILENAME, summary)
    return summary, 0


__all__ = [
    "AR_BOUNDARY_ROOT_FILES",
    "MODEL_FILENAME",
    "SUMMARY_FILENAME",
    "VERSION",
    "run_development_model_freeze",
]
