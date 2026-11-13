"""Evaluate a predeclared short temporal planner pilot using saved AR states."""

from pathlib import Path
import os
import hashlib

import numpy as np

from ..domain import temporal_planner_pilot as policy
from ..domain.artifact_registry import require
from ..io import artifact_registry as registry, development_experiment as original
from ..io.temporal_planner_pilot import TemporalModels, accepted_spatial, load_models
from ..modeling.matched_one_state_ar import MAX_SAMPLED_PADDED_FRAMES
from .development_experiment import protected_inputs, source_guard
from .locked_development_export import package, write


def draw_arms(training: np.ndarray, conditions: np.ndarray, offsets: np.ndarray, models: TemporalModels) -> dict[str, np.ndarray]:
    """Sample the frozen laws without passing held residuals to any sampler."""
    count, seed = policy.PROTOCOL["draws"], policy.PROTOCOL["sampling_seed"]
    stationary = models.stationary.sample(conditions, offsets, sample_count=count, seed=seed)
    one_state = models.one_state.sample(conditions, offsets, sample_count=count, seed=seed)
    return assemble_arms(
        np.zeros((1, len(conditions), 21)),
        training[np.random.default_rng(seed).integers(len(training), size=(count, len(conditions)))],
        models.gaussian.sample(conditions, sample_count=count, seed=seed),
        stationary, one_state, offsets,
    )


def assemble_arms(nominal, empirical, gaussian, stationary, one_state, offsets) -> dict[str, np.ndarray]:
    """Construct matched finite marginal controls from complete native draws."""
    seed = policy.PROTOCOL["permutation_seed"]
    return dict(nominal=nominal, empirical=empirical, conditional_gaussian=gaussian,
                stationary_ar=stationary, stationary_ar_permuted=policy.permute_draws(stationary, offsets, seed),
                one_state_ar=one_state, one_state_ar_permuted=policy.permute_draws(one_state, offsets, seed))


def run(*, project: Path, manifest_path: Path, manifest_pin: str, one_state_zip: Path, spatial_zip: Path,
        expected_tree: str, expected_runtime: str, output: Path, preflight_only: bool = False) -> tuple[dict, Path | None]:
    """Verify native cached support and states before the first temporal score."""
    project, manifest_path, one_state_zip, spatial_zip, output = map(
        original.metadata_path, (project, manifest_path, one_state_zip, spatial_zip, output))
    result, partial = output.with_name(output.name + "_results.zip"), output.with_name(output.name + "_results.zip.partial")
    source = source_guard(project, expected_tree, expected_runtime)
    plan, _ = original.pinned_json(manifest_path, manifest_pin)
    require(set(plan) == {"revision", "protocol", "original_experiment_directory", "original_experiment_sha256",
                         "one_state_experiment_directory", "one_state_experiment_sha256", "one_state_result_sha256",
                         "accepted_spatial_result_sha256", "accepted_spatial_tree", "fold", "saved_model_sha256",
                         "expected_support", "scenario_rows_sha256"}
            and plan["revision"] == policy.REVISION and plan["protocol"] == policy.PROTOCOL,
            "temporal_pilot_sealed_manifest_contract")
    folder = original.resolve(project, plan["original_experiment_directory"])
    inputs, marker = original.load_experiment(project, folder, plan["original_experiment_sha256"])
    fold = min(marker["folds"], key=lambda value: value["validation_outing"])
    require(fold == plan["fold"], "temporal_pilot_frozen_original_fold")
    held = next(block for block in inputs.blocks if block.outing_id == fold["validation_outing"])
    require(len(held.archive.raw_sha256_by_recording) == 1 and len(held.y) <= 20_000,
            "temporal_pilot_single_bounded_recording_required")
    rows, arrays, records, support = policy.prepare(held, fold)
    require(support["eligible_sequences"] > 0, "temporal_pilot_no_supported_sequences")
    row_pin = hashlib.sha256(original.encoded(rows)).hexdigest()
    require(support == plan["expected_support"] and row_pin == plan["scenario_rows_sha256"],
            "temporal_pilot_reviewed_support_mismatch")
    require(policy.PROTOCOL["draws"] * len(held.offsets[:-1]) * int(np.diff(held.offsets).max())
            <= MAX_SAMPLED_PADDED_FRAMES, "temporal_pilot_native_sampling_budget")
    one_directory = original.resolve(project, plan["one_state_experiment_directory"])
    one_inputs, models = load_models(project, one_directory, plan["one_state_experiment_sha256"],
                                       one_state_zip, plan["one_state_result_sha256"], marker, fold)
    require(models.hashes == plan["saved_model_sha256"], "temporal_pilot_reviewed_model_pins")
    accepted_spatial(spatial_zip, plan["accepted_spatial_result_sha256"], plan, marker, fold)
    training = np.concatenate([b.y for b in inputs.blocks if b.outing_id in fold["training_outings"]])
    require(len(training) == models.gaussian.training_rows, "temporal_pilot_training_partition")
    watched = {manifest_path: manifest_pin, one_state_zip: plan["one_state_result_sha256"],
               spatial_zip: plan["accepted_spatial_result_sha256"]}
    inputs.watched.update(watched)

    def unchanged():
        inputs.unchanged()
        one_inputs.unchanged()
        require(source_guard(project, expected_tree, expected_runtime) == source, "temporal_pilot_source_changed")

    protected = protected_inputs(project, inputs.request) + [folder, one_directory, *inputs.watched]
    protected += list(one_inputs.watched) + list(one_inputs.temporal_inputs.watched)
    for path in (output, result, partial):
        require(not os.path.lexists(path), "temporal_pilot_new_output_required")
        registry.separate_output(path, protected)
        require(not path.is_relative_to(project) or path.is_relative_to(project / "outputs/diagnostics/private"),
                "temporal_pilot_output_requires_private_diagnostics")
        require(not any(os.path.lexists(parent / name) for parent in path.parents for name in
                        ("experiment.json", "run_receipt.json", "replication_manifest.private.json",
                         "temporal_manifest.private.json", "pilot_report.private.json")),
                "temporal_pilot_output_inside_prior_evidence")
    unchanged()
    receipt = dict(revision=policy.REVISION, source=source, manifest_sha256=manifest_pin,
                   fold=fold, support=support, training_rows=len(training), saved_model_sha256=models.hashes,
                   scenario_rows_sha256=row_pin,
                   raw_payload_opened=False, model_refitted=False, final_evaluation_authorized=False,
                   new_recordings_admitted=False)
    if preflight_only:
        return dict(receipt, status="verified_temporal_pilot_inputs_no_scores"), None

    output.mkdir(parents=True, exist_ok=False)
    stage = "preserve_manifest"
    try:
        write(output / "temporal_manifest.private.json", plan)
        write(output / "sequences.private.json", records)
        stage = "sample_frozen_temporal_laws"
        print("Sampling frozen AR laws on original complete rows.", flush=True)
        arms = draw_arms(training, held.x, held.offsets, models)
        stage = "score_short_temporal_sequences"
        scores = policy.score(arrays, records, arms)
        write(output / "scores.private.json", scores)
        prefix = policy.PROTOCOL["prefix_draws"]
        prefix_arms = assemble_arms(arms["nominal"], arms["empirical"][:prefix],
                                   arms["conditional_gaussian"][:prefix], arms["stationary_ar"][:prefix],
                                   arms["one_state_ar"][:prefix], held.offsets)
        prefix_scores = policy.score(arrays, records, prefix_arms)
        stage = "verify_inputs"
        unchanged()
        report = dict(receipt, status="complete_short_temporal_planner_pilot", protocol=policy.PROTOCOL,
                      scores={k: v for k, v in scores.items() if k != "sequence_scores"},
                      prefix_scores={k: v for k, v in prefix_scores.items() if k != "sequence_scores"})
        write(output / "temporal_report.private.json", report)
        stage = "package_result"
        package(partial, [(output, "temporal")])
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(partial, result)
        registry._fsync_directory(result.parent)
    except BaseException as exc:
        write(output / "failure.private.json", dict(stage=stage, exception_type=type(exc).__name__, message=str(exc)))
        raise
    try:
        partial.unlink()
    except OSError:
        print("Published result; temporary duplicate link retained.", flush=True)
    return report, result
