"""Freeze an original development pilot from validated cached arrays."""

import io
import os
from pathlib import Path

import numpy as np

from ..domain import cached_planner_scenarios as policy
from ..domain.artifact_registry import require
from ..io import artifact_registry as registry, development_experiment as original
from .development_experiment import protected_inputs, source_guard
from .locked_development_export import package, write


def prepare(
    *,
    project: Path,
    experiment_directory: Path,
    expected_experiment_sha256: str,
    expected_tree: str,
    expected_runtime: str,
    output_directory: Path,
) -> tuple[dict, Path]:
    """Prepare scenario inputs, retaining original profiles, identities and resets."""
    project = original.metadata_path(project)
    folder = original.resolve(project, str(experiment_directory))
    output = original.metadata_path(output_directory)
    result = output.with_name(output.name + "_results.zip")
    require(not os.path.lexists(output) and not os.path.lexists(result),
            "scenario_new_output_required_preserve_existing")
    source = source_guard(project, expected_tree, expected_runtime)
    inputs, marker = original.load_experiment(project, folder, expected_experiment_sha256)
    protected = protected_inputs(project, inputs.request) + [folder]
    registry.separate_output(output, protected)
    registry.separate_output(result, protected + [output])
    require(not any(os.path.lexists(parent / name) for parent in (output, *output.parents)
                    for name in ("experiment.json", "run_receipt.json", "scenario_manifest.private.json")),
            "scenario_output_inside_prior_evidence")
    if output.is_relative_to(project):
        require(output.is_relative_to(project / "outputs/diagnostics/private"),
                "scenario_output_inside_project_requires_private_diagnostics")
    require(marker["protocol"]["stations_m"] == policy.PROTOCOL["stations_m"],
            "scenario_original_station_contract")
    fold = sorted(marker["folds"], key=lambda row: row["validation_outing"])[0]
    matches = [b for b in inputs.blocks if b.outing_id == fold["validation_outing"]]
    require(len(matches) == 1, "scenario_unique_original_pilot_required")
    block = matches[0]
    require(len(block.y) <= 20_000, "scenario_bounded_original_pilot_required")
    rows, arrays, summary = policy.prepare_scenario_rows(block, fold)
    inputs.unchanged()
    output.mkdir(parents=True, exist_ok=False)
    try:
        write(output / "scenario_rows.private.json", rows)
        archive = io.BytesIO()
        np.savez_compressed(archive, **arrays)
        write(output / "scenario_arrays.npz", archive.getvalue())
        require(original.sha(output / "scenario_rows.private.json") == summary["rows_sha256"],
                "scenario_row_serialization_changed")
        hashes = {name: original.sha(output / name) for name in
                  ("scenario_rows.private.json", "scenario_arrays.npz")}
        inputs.unchanged()
        require(source_guard(project, expected_tree, expected_runtime) == source,
                "scenario_source_changed_during_preparation")
        report = {
            "contract_revision": policy.REVISION,
            "status": "complete_cached_spatial_scenario_preparation",
            "original_experiment_sha256": expected_experiment_sha256,
            "original_row_manifest_sha256": marker["row_manifest_sha256"],
            "original_cohort_sha256": marker["original_cohort_sha256"],
            "original_registry_sha256": marker["original_registry_sha256"],
            "latest_registry_sha256": marker["latest_registry_sha256"],
            "fold": fold,
            "protocol": policy.PROTOCOL,
            "summary": summary,
            "source": source,
            "output_files_sha256": hashes,
            "pilot_scenarios_ready": summary["eligible_rows"] > 0,
            "physical_input_availability_proven": False,
            "reference_independence_proven": False,
            "model_sampling_executed": False,
            "planner_scoring_executed": False,
            "raw_payload_opened": False,
            "final_evaluation_authorized": False,
            "new_recordings_admitted": False,
        }
        write(output / "scenario_manifest.private.json", report)
    except BaseException as exc:
        write(output / "failure.private.json", {
            "status": "incomplete_preserve_scenario_evidence",
            "exception_type": type(exc).__name__,
            "message": str(exc),
        })
        try:
            package(result, [(output, "scenarios")])
        except Exception as packaging_error:
            write(output / "packaging_failure.private.json", {"exception_type": type(packaging_error).__name__})
        raise
    try:
        package(result, [(output, "scenarios")])
    except Exception as exc:
        write(output / "packaging_failure.private.json", {"exception_type": type(exc).__name__})
        raise
    return report, result
