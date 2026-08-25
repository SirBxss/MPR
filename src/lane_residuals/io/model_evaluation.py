"""Strict loading of the frozen expanded-data model-evaluation baseline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..domain.model_evaluation import DriveGroupedFold
from .expanded_sequence_dataset import (
    ExpandedSequenceContractError,
    read_json_object,
    sha256_file,
)

GAUSSIAN_VERSION = "0.14.0"
GAUSSIAN_REQUIRED_FILES = frozenset(
    {
        "drive_grouped_evaluation_contract.json",
        "gaussian_grouped_evaluation.csv",
        "gaussian_grouped_station_evaluation.csv",
        "gaussian_grouped_frame_evaluation.csv",
        "gaussian_grouped_models.json",
        "gaussian_grouped_diagnostics.png",
        "gaussian_grouped_summary.json",
    }
)

AIOHMM_VERSION = "0.15.0"
AIOHMM_REQUIRED_FILES = frozenset(
    {
        "expanded_aiohmm_evaluation.csv",
        "expanded_aiohmm_station_evaluation.csv",
        "expanded_aiohmm_frame_evaluation.csv",
        "expanded_aiohmm_state_evaluation.csv",
        "expanded_aiohmm_restart_evaluation.csv",
        "expanded_aiohmm_fold_models.json",
        "expanded_aiohmm_model.json",
        "expanded_aiohmm_diagnostics.png",
        "expanded_aiohmm_summary.json",
    }
)

ONE_STATE_AR_VERSION = "0.15.1"
ONE_STATE_AR_REQUIRED_FILES = frozenset(
    {
        "one_state_ar_evaluation.csv",
        "one_state_ar_station_evaluation.csv",
        "one_state_ar_frame_evaluation.csv",
        "one_state_ar_state_evaluation.csv",
        "one_state_ar_restart_evaluation.csv",
        "one_state_ar_fold_models.json",
        "one_state_ar_model.json",
        "one_state_ar_diagnostics.png",
        "one_state_ar_summary.json",
    }
)

TWO_STATE_CONVERGENCE_VERSION = "0.15.2"
TWO_STATE_CONVERGENCE_REQUIRED_FILES = frozenset(
    {
        "two_state_convergence_evaluation.csv",
        "two_state_convergence_station_evaluation.csv",
        "two_state_convergence_frame_evaluation.csv",
        "two_state_convergence_state_evaluation.csv",
        "two_state_convergence_restart_evaluation.csv",
        "two_state_convergence_comparison.csv",
        "two_state_convergence_fold_models.json",
        "two_state_convergence_model.json",
        "two_state_convergence_diagnostics.png",
        "two_state_convergence_summary.json",
    }
)


def load_expanded_gaussian_baseline(
    directory: str | Path,
    *,
    source_files_sha256: Mapping[str, str],
    folds: Sequence[DriveGroupedFold],
) -> tuple[Mapping[str, Any], Mapping[str, Any], dict[str, str]]:
    """Validate v0.14 as the immutable comparison protocol for later models."""

    source = Path(directory)
    if not source.is_dir():
        raise FileNotFoundError(f"v0.14.0 Gaussian directory not found: {source}")
    actual = {path.name for path in source.iterdir() if path.is_file()}
    if actual != GAUSSIAN_REQUIRED_FILES:
        raise ExpandedSequenceContractError(
            "v0.14.0 Gaussian directory filename set differs from the contract"
        )
    summary = read_json_object(source / "gaussian_grouped_summary.json")
    protocol = read_json_object(source / "drive_grouped_evaluation_contract.json")
    if (
        summary.get("version") != GAUSSIAN_VERSION
        or summary.get("status") != "complete"
        or summary.get("purpose") != "expanded_drive_grouped_gaussian_rebaseline"
    ):
        raise ExpandedSequenceContractError("v0.14.0 Gaussian summary is not accepted")
    if (
        protocol.get("version") != GAUSSIAN_VERSION
        or protocol.get("status") != "complete"
        or protocol.get("purpose")
        != "leakage_safe_drive_grouped_thesis_model_evaluation_contract"
    ):
        raise ExpandedSequenceContractError("v0.14.0 evaluation protocol is not accepted")
    if summary.get("final_model_selection_authorized") is not False:
        raise ExpandedSequenceContractError("v0.14.0 cannot authorize final selection")
    if (
        summary.get("source_dataset_version") != "0.13.1"
        or summary.get("evaluation_scheme")
        != "leave_one_clean_physical_drive_out"
        or summary.get("random_frame_splits_used") is not False
        or summary.get("mixed_source_results_are_supplementary_only") is not True
        or protocol.get("fold_count") != len(folds)
        or protocol.get("untouched_final_test_drive_count") != 0
    ):
        raise ExpandedSequenceContractError("v0.14.0 evaluation policy differs")
    expected_outputs = summary.get("output_files_sha256")
    hashed_names = GAUSSIAN_REQUIRED_FILES - {"gaussian_grouped_summary.json"}
    if not isinstance(expected_outputs, Mapping) or set(expected_outputs) != hashed_names:
        raise ExpandedSequenceContractError("v0.14.0 output hash set differs")
    hashes: dict[str, str] = {}
    for name in sorted(GAUSSIAN_REQUIRED_FILES):
        digest = sha256_file(source / name)
        hashes[name] = digest
        if name != "gaussian_grouped_summary.json" and expected_outputs.get(name) != digest:
            raise ExpandedSequenceContractError(f"v0.14.0 output hash mismatch: {name}")
    expected_source = dict(
        sorted((str(key), str(value)) for key, value in source_files_sha256.items())
    )
    if (
        summary.get("source_files_sha256") != expected_source
        or protocol.get("source_files_sha256") != expected_source
    ):
        raise ExpandedSequenceContractError("v0.14.0 source lineage differs from v0.13.1")
    stored_folds = protocol.get("folds")
    expected_folds = [fold.to_dict() for fold in folds]
    if stored_folds != expected_folds:
        raise ExpandedSequenceContractError("v0.14.0 clean-drive folds or transforms differ")
    if summary.get("primary_clean_drive_ids") != [
        fold.held_out_drive_id for fold in folds
    ]:
        raise ExpandedSequenceContractError("v0.14.0 primary drive cohort differs")
    if (
        protocol.get("split_scheme") != "leave_one_clean_physical_drive_out"
        or protocol.get("random_frame_splits_permitted") is not False
        or protocol.get("same_physical_drive_may_cross_fold") is not False
        or protocol.get("supplementary_cohort", {}).get(
            "never_used_for_fit_or_primary_model_comparison"
        )
        is not True
    ):
        raise ExpandedSequenceContractError("v0.14.0 split policy differs")
    if protocol.get("primary_cross_model_metrics") != [
        "sample_mean_prediction_rmse_m",
        "mean_energy_score_m",
        "mean_normalized_sequence_energy_score_m",
        "marginal_95_coverage",
        "median_absolute_lag_one_correlation_error",
    ]:
        raise ExpandedSequenceContractError("v0.14.0 cross-model metrics differ")
    models = summary.get("models")
    if not isinstance(models, Mapping) or set(models) != {
        "unconditional_gaussian",
        "conditional_gaussian",
    }:
        raise ExpandedSequenceContractError("v0.14.0 Gaussian models are incomplete")
    monte_carlo = protocol.get("monte_carlo")
    if (
        not isinstance(monte_carlo, Mapping)
        or monte_carlo.get("common_random_numbers_across_gaussian_baselines") is not True
        or summary.get("sample_count") != monte_carlo.get("sample_count")
        or summary.get("random_seed") != monte_carlo.get("base_seed")
    ):
        raise ExpandedSequenceContractError("v0.14.0 Monte Carlo protocol differs")
    if any(
        "mean_normalized_sequence_energy_score_m"
        not in payload.get("primary_macro_drive_metrics", {})
        for payload in models.values()
    ):
        raise ExpandedSequenceContractError("v0.14.0 temporal scores are incomplete")
    return summary, protocol, hashes


def load_expanded_aiohmm_baseline(
    directory: str | Path,
    *,
    source_files_sha256: Mapping[str, str],
    gaussian_files_sha256: Mapping[str, str],
    folds: Sequence[DriveGroupedFold],
    sample_count: int,
    base_seed: int,
) -> tuple[Mapping[str, Any], dict[str, str]]:
    """Validate v0.15 as the immutable two-state comparison for AR ablations."""

    source = Path(directory)
    if not source.is_dir():
        raise FileNotFoundError(f"v0.15.0 AIOHMM directory not found: {source}")
    actual = {path.name for path in source.iterdir() if path.is_file()}
    if actual != AIOHMM_REQUIRED_FILES:
        raise ExpandedSequenceContractError(
            "v0.15.0 AIOHMM directory filename set differs from the contract"
        )
    summary = read_json_object(source / "expanded_aiohmm_summary.json")
    fold_models = read_json_object(source / "expanded_aiohmm_fold_models.json")
    if (
        summary.get("version") != AIOHMM_VERSION
        or summary.get("status") != "complete"
        or summary.get("purpose")
        != "expanded_clean_drive_autoregressive_input_output_hmm"
        or summary.get("state_count") != 2
    ):
        raise ExpandedSequenceContractError("v0.15.0 AIOHMM summary is not accepted")
    if (
        summary.get("evaluation_scheme")
        != "leave_one_clean_recording_group_out_within_one_outing"
        or summary.get("random_frame_splits_used") is not False
        or summary.get("same_folds_transforms_and_metrics_as_v0140_gaussian")
        is not True
        or summary.get("mixed_source_results_are_supplementary_only") is not True
        or summary.get("final_model_selection_authorized") is not False
        or summary.get("automatic_state_count_selection_performed") is not False
        or summary.get("held_out_drives_used_for_state_count_or_restart_selection")
        is not False
    ):
        raise ExpandedSequenceContractError("v0.15.0 evaluation policy differs")
    independence = summary.get("primary_group_independence")
    if (
        not isinstance(independence, Mapping)
        or independence.get("technical_group_count") != len(folds)
        or independence.get("independent_journey_count") != 1
        or independence.get(
            "groups_are_separated_portions_of_one_longer_same_day_outing"
        )
        is not True
        or independence.get("journey_level_generalization_estimated") is not False
    ):
        raise ExpandedSequenceContractError(
            "v0.15.0 recording-group independence declaration differs"
        )
    expected_source = dict(
        sorted((str(key), str(value)) for key, value in source_files_sha256.items())
    )
    expected_gaussian = dict(
        sorted((str(key), str(value)) for key, value in gaussian_files_sha256.items())
    )
    if (
        summary.get("source_dataset_version") != "0.13.1"
        or summary.get("source_files_sha256") != expected_source
        or summary.get("gaussian_baseline_version") != GAUSSIAN_VERSION
        or summary.get("gaussian_baseline_files_sha256") != expected_gaussian
        or summary.get("sample_count") != sample_count
        or summary.get("sampling_random_seed") != base_seed
    ):
        raise ExpandedSequenceContractError("v0.15.0 lineage or Monte Carlo protocol differs")
    expected_outputs = summary.get("output_files_sha256")
    hashed_names = AIOHMM_REQUIRED_FILES - {"expanded_aiohmm_summary.json"}
    if not isinstance(expected_outputs, Mapping) or set(expected_outputs) != hashed_names:
        raise ExpandedSequenceContractError("v0.15.0 output hash set differs")
    hashes: dict[str, str] = {}
    for name in sorted(AIOHMM_REQUIRED_FILES):
        digest = sha256_file(source / name)
        hashes[name] = digest
        if name != "expanded_aiohmm_summary.json" and expected_outputs.get(name) != digest:
            raise ExpandedSequenceContractError(f"v0.15.0 output hash mismatch: {name}")

    if (
        fold_models.get("version") != AIOHMM_VERSION
        or fold_models.get("status") != "complete"
        or fold_models.get("purpose") != "v014_clean_drive_fold_aiohmm_models"
        or fold_models.get("state_count_fixed_before_evaluation") is not True
    ):
        raise ExpandedSequenceContractError("v0.15.0 fold-model contract differs")
    stored_models = fold_models.get("models")
    if not isinstance(stored_models, Mapping) or set(stored_models) != {
        fold.fold_id for fold in folds
    }:
        raise ExpandedSequenceContractError("v0.15.0 fold model set differs")
    for fold in folds:
        payload = stored_models[fold.fold_id]
        if not isinstance(payload, Mapping):
            raise ExpandedSequenceContractError("v0.15.0 fold model must be an object")
        model = payload.get("model")
        if (
            payload.get("held_out_drive_id") != fold.held_out_drive_id
            or payload.get("training_drive_ids") != list(fold.training_drive_ids)
            or payload.get("standardizer") != fold.standardizer.to_dict()
            or payload.get("held_out_drive_not_used_for_restart_selection") is not True
            or not isinstance(model, Mapping)
            or model.get("configuration", {}).get("state_count") != 2
        ):
            raise ExpandedSequenceContractError(
                f"v0.15.0 fold or transform differs: {fold.fold_id}"
            )
    if summary.get("primary_clean_drive_ids") != [
        fold.held_out_drive_id for fold in folds
    ]:
        raise ExpandedSequenceContractError("v0.15.0 primary group cohort differs")
    return summary, hashes


def load_expanded_one_state_ar_baseline(
    directory: str | Path,
    *,
    source_files_sha256: Mapping[str, str],
    gaussian_files_sha256: Mapping[str, str],
    aiohmm_files_sha256: Mapping[str, str],
    folds: Sequence[DriveGroupedFold],
    sample_count: int,
    base_seed: int,
) -> tuple[Mapping[str, Any], dict[str, str]]:
    """Validate v0.15.1 as the immutable one-state comparison artifact."""

    source = Path(directory)
    if not source.is_dir():
        raise FileNotFoundError(
            f"v0.15.1 one-state AR directory not found: {source}"
        )
    actual = {path.name for path in source.iterdir() if path.is_file()}
    if actual != ONE_STATE_AR_REQUIRED_FILES:
        raise ExpandedSequenceContractError(
            "v0.15.1 one-state AR directory filename set differs from the contract"
        )
    summary = read_json_object(source / "one_state_ar_summary.json")
    fold_models = read_json_object(source / "one_state_ar_fold_models.json")
    if (
        summary.get("version") != ONE_STATE_AR_VERSION
        or summary.get("status") != "complete"
        or summary.get("purpose")
        != "one_state_conditional_autoregressive_gaussian_ablation"
        or summary.get("state_count") != 1
        or summary.get("latent_state_switching") is not False
        or summary.get("input_dependent_state_transitions_effective") is not False
    ):
        raise ExpandedSequenceContractError(
            "v0.15.1 one-state AR summary is not accepted"
        )
    if (
        summary.get("evaluation_scheme")
        != "leave_one_clean_recording_group_out_within_one_outing"
        or summary.get("random_frame_splits_used") is not False
        or summary.get(
            "same_folds_transforms_hyperparameters_sampling_and_metrics_as_v0150"
        )
        is not True
        or summary.get("mixed_source_results_are_supplementary_only") is not True
        or summary.get("final_model_selection_authorized") is not False
    ):
        raise ExpandedSequenceContractError(
            "v0.15.1 one-state AR evaluation policy differs"
        )
    independence = summary.get("primary_group_independence")
    if (
        not isinstance(independence, Mapping)
        or independence.get("technical_group_count") != len(folds)
        or independence.get("independent_journey_count") != 1
        or independence.get(
            "groups_are_separated_portions_of_one_longer_same_day_outing"
        )
        is not True
        or independence.get("journey_level_generalization_estimated") is not False
    ):
        raise ExpandedSequenceContractError(
            "v0.15.1 recording-group independence declaration differs"
        )
    expected_source = dict(
        sorted((str(key), str(value)) for key, value in source_files_sha256.items())
    )
    expected_gaussian = dict(
        sorted((str(key), str(value)) for key, value in gaussian_files_sha256.items())
    )
    expected_aiohmm = dict(
        sorted((str(key), str(value)) for key, value in aiohmm_files_sha256.items())
    )
    if (
        summary.get("source_dataset_version") != "0.13.1"
        or summary.get("source_files_sha256") != expected_source
        or summary.get("gaussian_baseline_version") != GAUSSIAN_VERSION
        or summary.get("gaussian_baseline_files_sha256") != expected_gaussian
        or summary.get("two_state_aiohmm_reference_version") != AIOHMM_VERSION
        or summary.get("two_state_aiohmm_reference_files_sha256")
        != expected_aiohmm
        or summary.get("sample_count") != sample_count
        or summary.get("sampling_random_seed") != base_seed
    ):
        raise ExpandedSequenceContractError(
            "v0.15.1 one-state AR lineage or Monte Carlo protocol differs"
        )
    expected_outputs = summary.get("output_files_sha256")
    hashed_names = ONE_STATE_AR_REQUIRED_FILES - {"one_state_ar_summary.json"}
    if not isinstance(expected_outputs, Mapping) or set(expected_outputs) != hashed_names:
        raise ExpandedSequenceContractError(
            "v0.15.1 one-state AR output hash set differs"
        )
    hashes: dict[str, str] = {}
    for name in sorted(ONE_STATE_AR_REQUIRED_FILES):
        digest = sha256_file(source / name)
        hashes[name] = digest
        if name != "one_state_ar_summary.json" and expected_outputs.get(name) != digest:
            raise ExpandedSequenceContractError(
                f"v0.15.1 one-state AR output hash mismatch: {name}"
            )
    if (
        fold_models.get("version") != ONE_STATE_AR_VERSION
        or fold_models.get("status") != "complete"
        or fold_models.get("purpose")
        != "v0151_clean_group_fold_one_state_ar_models"
        or fold_models.get("state_count_fixed_before_evaluation") is not True
    ):
        raise ExpandedSequenceContractError(
            "v0.15.1 one-state AR fold-model contract differs"
        )
    stored_models = fold_models.get("models")
    if not isinstance(stored_models, Mapping) or set(stored_models) != {
        fold.fold_id for fold in folds
    }:
        raise ExpandedSequenceContractError(
            "v0.15.1 one-state AR fold model set differs"
        )
    for fold in folds:
        payload = stored_models[fold.fold_id]
        if not isinstance(payload, Mapping):
            raise ExpandedSequenceContractError(
                "v0.15.1 one-state fold model must be an object"
            )
        model = payload.get("model")
        if (
            payload.get("held_out_drive_id") != fold.held_out_drive_id
            or payload.get("training_drive_ids") != list(fold.training_drive_ids)
            or payload.get("standardizer") != fold.standardizer.to_dict()
            or payload.get("held_out_drive_not_used_for_restart_selection") is not True
            or not isinstance(model, Mapping)
            or model.get("configuration", {}).get("state_count") != 1
        ):
            raise ExpandedSequenceContractError(
                f"v0.15.1 fold or transform differs: {fold.fold_id}"
            )
    if summary.get("primary_clean_drive_ids") != [
        fold.held_out_drive_id for fold in folds
    ]:
        raise ExpandedSequenceContractError(
            "v0.15.1 one-state primary group cohort differs"
        )
    return summary, hashes


def load_expanded_two_state_convergence_baseline(
    directory: str | Path,
    *,
    source_files_sha256: Mapping[str, str],
    gaussian_files_sha256: Mapping[str, str],
    aiohmm_files_sha256: Mapping[str, str],
    one_state_ar_files_sha256: Mapping[str, str],
    folds: Sequence[DriveGroupedFold],
    sample_count: int,
    base_seed: int,
) -> tuple[Mapping[str, Any], dict[str, str]]:
    """Validate the immutable v0.15.2 corrected two-state audit artifact."""

    source = Path(directory)
    if not source.is_dir():
        raise FileNotFoundError(
            f"v0.15.2 two-state convergence directory not found: {source}"
        )
    actual = {path.name for path in source.iterdir() if path.is_file()}
    if actual != TWO_STATE_CONVERGENCE_REQUIRED_FILES:
        raise ExpandedSequenceContractError(
            "v0.15.2 two-state convergence directory filename set differs "
            "from the contract"
        )

    summary = read_json_object(source / "two_state_convergence_summary.json")
    fold_models = read_json_object(
        source / "two_state_convergence_fold_models.json"
    )
    if (
        summary.get("version") != TWO_STATE_CONVERGENCE_VERSION
        or summary.get("status") != "complete"
        or summary.get("purpose")
        != "two_state_aiohmm_size_invariant_convergence_audit"
        or summary.get("state_count") != 2
        or summary.get("ar_boundary_changed") is not False
        or summary.get("new_model_family_introduced") is not False
        or summary.get("final_model_selection_authorized") is not False
    ):
        raise ExpandedSequenceContractError(
            "v0.15.2 two-state convergence summary is not accepted"
        )
    if (
        summary.get("evaluation_scheme")
        != "leave_one_clean_recording_group_out_within_one_outing"
        or summary.get("random_frame_splits_used") is not False
        or summary.get("same_folds_transforms_and_metrics_as_v0140_gaussian")
        is not True
        or summary.get("mixed_source_results_are_supplementary_only") is not True
    ):
        raise ExpandedSequenceContractError(
            "v0.15.2 two-state convergence evaluation policy differs"
        )
    independence = summary.get("primary_group_independence")
    if (
        not isinstance(independence, Mapping)
        or independence.get("technical_group_count") != len(folds)
        or independence.get("independent_journey_count") != 1
        or independence.get(
            "groups_are_separated_portions_of_one_longer_same_day_outing"
        )
        is not True
        or independence.get("journey_level_generalization_estimated") is not False
    ):
        raise ExpandedSequenceContractError(
            "v0.15.2 recording-group independence declaration differs"
        )

    expected_source = dict(
        sorted((str(key), str(value)) for key, value in source_files_sha256.items())
    )
    expected_gaussian = dict(
        sorted((str(key), str(value)) for key, value in gaussian_files_sha256.items())
    )
    expected_aiohmm = dict(
        sorted((str(key), str(value)) for key, value in aiohmm_files_sha256.items())
    )
    expected_one_state = dict(
        sorted(
            (str(key), str(value))
            for key, value in one_state_ar_files_sha256.items()
        )
    )
    if (
        summary.get("source_dataset_version") != "0.13.1"
        or summary.get("source_files_sha256") != expected_source
        or summary.get("gaussian_baseline_version") != GAUSSIAN_VERSION
        or summary.get("gaussian_baseline_files_sha256") != expected_gaussian
        or summary.get("reference_two_state_aiohmm_version") != AIOHMM_VERSION
        or summary.get("reference_two_state_aiohmm_files_sha256")
        != expected_aiohmm
        or summary.get("one_state_ar_reference_version") != ONE_STATE_AR_VERSION
        or summary.get("one_state_ar_reference_files_sha256")
        != expected_one_state
        or summary.get("sample_count") != sample_count
        or summary.get("sampling_random_seed") != base_seed
    ):
        raise ExpandedSequenceContractError(
            "v0.15.2 lineage or Monte Carlo protocol differs"
        )

    expected_outputs = summary.get("output_files_sha256")
    hashed_names = TWO_STATE_CONVERGENCE_REQUIRED_FILES - {
        "two_state_convergence_summary.json"
    }
    if not isinstance(expected_outputs, Mapping) or set(expected_outputs) != hashed_names:
        raise ExpandedSequenceContractError(
            "v0.15.2 output hash set differs"
        )
    hashes: dict[str, str] = {}
    for name in sorted(TWO_STATE_CONVERGENCE_REQUIRED_FILES):
        digest = sha256_file(source / name)
        hashes[name] = digest
        if (
            name != "two_state_convergence_summary.json"
            and expected_outputs.get(name) != digest
        ):
            raise ExpandedSequenceContractError(
                f"v0.15.2 output hash mismatch: {name}"
            )

    if (
        fold_models.get("version") != TWO_STATE_CONVERGENCE_VERSION
        or fold_models.get("status") != "complete"
        or fold_models.get("purpose")
        != "v0152_clean_group_fold_two_state_convergence_models"
        or fold_models.get("state_count_fixed_before_evaluation") is not True
    ):
        raise ExpandedSequenceContractError(
            "v0.15.2 fold-model contract differs"
        )
    stored_models = fold_models.get("models")
    if not isinstance(stored_models, Mapping) or set(stored_models) != {
        fold.fold_id for fold in folds
    }:
        raise ExpandedSequenceContractError(
            "v0.15.2 fold model set differs"
        )
    for fold in folds:
        payload = stored_models[fold.fold_id]
        if not isinstance(payload, Mapping):
            raise ExpandedSequenceContractError(
                "v0.15.2 fold model must be an object"
            )
        model = payload.get("model")
        if (
            payload.get("held_out_drive_id") != fold.held_out_drive_id
            or payload.get("training_drive_ids") != list(fold.training_drive_ids)
            or payload.get("standardizer") != fold.standardizer.to_dict()
            or payload.get("held_out_drive_not_used_for_restart_selection") is not True
            or not isinstance(model, Mapping)
            or model.get("configuration", {}).get("state_count") != 2
        ):
            raise ExpandedSequenceContractError(
                f"v0.15.2 fold or transform differs: {fold.fold_id}"
            )
    if summary.get("primary_clean_drive_ids") != [
        fold.held_out_drive_id for fold in folds
    ]:
        raise ExpandedSequenceContractError(
            "v0.15.2 primary group cohort differs"
        )
    return summary, hashes


__all__ = [
    "AIOHMM_REQUIRED_FILES",
    "AIOHMM_VERSION",
    "GAUSSIAN_REQUIRED_FILES",
    "GAUSSIAN_VERSION",
    "ONE_STATE_AR_REQUIRED_FILES",
    "ONE_STATE_AR_VERSION",
    "TWO_STATE_CONVERGENCE_REQUIRED_FILES",
    "TWO_STATE_CONVERGENCE_VERSION",
    "load_expanded_aiohmm_baseline",
    "load_expanded_gaussian_baseline",
    "load_expanded_one_state_ar_baseline",
    "load_expanded_two_state_convergence_baseline",
]
