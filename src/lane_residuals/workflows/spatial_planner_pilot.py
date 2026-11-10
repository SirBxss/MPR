"""Evaluate the original held-out spatial pilot with frozen development states."""

from dataclasses import replace
from pathlib import Path
import os

import numpy as np

from ..domain.artifact_registry import require
from ..domain.spatial_planner_pilot import PROTOCOL, REVISION, score_spatial_pilot
from ..io import artifact_registry as registry, development_experiment as original
from ..io.spatial_planner_pilot import SavedSpatialModels, load_saved_models, load_scenarios
from .development_experiment import protected_inputs, source_guard
from .locked_development_export import package, write
from .spatial_planner_benchmark import draw_spatial_profiles


def draw_arms(training: np.ndarray, models: SavedSpatialModels) -> dict[str, np.ndarray]:
    """Use training rows and frozen states only, with one shared draw set per arm."""
    seed, count = PROTOCOL["sampling_seed"], PROTOCOL["draws"]
    diagonal = replace(models.gaussian, covariance=np.diag(np.diag(models.gaussian.covariance)))
    return {
        "nominal": np.zeros((1, 21)),
        "empirical": training[np.random.default_rng(seed).integers(len(training), size=count)],
        "diagonal_gaussian": draw_spatial_profiles(diagonal, sample_count=count, seed=seed),
        "full_gaussian": draw_spatial_profiles(models.gaussian, sample_count=count, seed=seed),
        "unconditional_flow_reset": draw_spatial_profiles(models.flow, sample_count=count, seed=seed),
    }


def run(*, project: Path, experiment_directory: Path, experiment_sha256: str,
        scenario_zip: Path, scenario_sha256: str, flow_zip: Path, flow_sha256: str,
        expected_tree: str, expected_runtime: str, output: Path) -> tuple[dict, Path]:
    """Score one new output directory, retaining incomplete attempts on failure."""
    project = original.metadata_path(project)
    folder = original.resolve(project, str(experiment_directory))
    scenario_zip, flow_zip, output = map(original.metadata_path, (scenario_zip, flow_zip, output))
    result = output.with_name(output.name + "_results.zip")
    partial = result.with_suffix(".zip.partial")
    require(not any(os.path.lexists(path) for path in (output, result, partial)),
            "pilot_new_output_required_preserve_existing")
    source = source_guard(project, expected_tree, expected_runtime)
    inputs, marker = original.load_experiment(project, folder, experiment_sha256)
    protected = protected_inputs(project, inputs.request) + [folder, scenario_zip, flow_zip, *inputs.watched]
    for destination in (output, result, partial):
        registry.separate_output(destination, protected)
        require(not destination.is_relative_to(project)
                or destination.is_relative_to(project / "outputs/diagnostics/private"),
                "pilot_output_inside_project_requires_private_diagnostics")
        require(not any(os.path.lexists(parent / name) for parent in destination.parents
                        for name in ("experiment.json", "run_receipt.json", "scenario_manifest.private.json",
                                     "pilot_report.private.json")), "pilot_output_inside_prior_evidence")
    fold = min(marker["folds"], key=lambda row: row["validation_outing"])
    blocks = {block.outing_id: block for block in inputs.blocks}
    held = blocks[fold["validation_outing"]]
    require(held.outing_id not in fold["training_outings"] and len(held.y) <= 20_000,
            "pilot_held_out_support")
    require(len(held.archive.raw_sha256_by_recording) == 1, "pilot_single_recording_required")
    rows, arrays = load_scenarios(scenario_zip, scenario_sha256, marker, fold, held)
    models = load_saved_models(flow_zip, flow_sha256, marker, fold, held.archive.summary_sha256)
    training = np.concatenate([blocks[outing].y for outing in fold["training_outings"]])
    require(len(training) == models.gaussian.training_rows == models.flow.training_rows,
            "pilot_model_training_count_mismatch")
    inputs.watched.update({scenario_zip: scenario_sha256, flow_zip: flow_sha256})
    inputs.unchanged()

    output.mkdir(parents=True, exist_ok=False)
    stage = "draw_frozen_states"
    try:
        print("Drawing empirical profiles and sampling saved spatial models.", flush=True)
        arms = draw_arms(training, models)
        stage = "score_fixed_planner"
        print("Scoring recorded and sampled profiles on the fixed planner and speed sensitivity.", flush=True)
        scores = score_spatial_pilot(arrays, rows, arms)
        stage = "verify_inputs"
        inputs.unchanged()
        require(source_guard(project, expected_tree, expected_runtime) == source, "pilot_source_changed")
        report = {
            "revision": REVISION,
            "status": "complete_recorded_spatial_planner_pilot",
            "protocol": PROTOCOL,
            "fold": fold,
            "source": source,
            "original_experiment_sha256": experiment_sha256,
            "scenario_zip_sha256": scenario_sha256,
            "flow_result_zip_sha256": flow_sha256,
            "saved_model_and_solver_sha256": models.hashes,
            "training_rows": len(training),
            "held_geometry_rows": len(held.archive.arrays["residuals_m"]),
            "held_complete_feature_rows": len(rows),
            "held_sequences": len(held.offsets) - 1,
            "scores": scores,
            "raw_payload_opened": False,
            "model_refitted": False,
            "speed_feature_replaced": False,
            "final_evaluation_authorized": False,
            "new_recordings_admitted": False,
        }
        stage = "publish_result"
        write(output / "pilot_report.private.json", report)
        package(partial, [(output, "pilot")])
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(partial, result)
        registry._fsync_directory(result.parent)
    except BaseException as exc:
        write(output / "failure.private.json", {
            "status": "incomplete_preserve_pilot_evidence",
            "stage": stage,
            "exception_type": type(exc).__name__,
            "message": str(exc),
        })
        raise
    try:
        partial.unlink()
    except OSError:
        print("Published result; temporary duplicate link retained.", flush=True)
    return report, result
