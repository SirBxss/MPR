"""Run the steering-rate design on the pinned PR60 calibration context panel."""

from pathlib import Path

import numpy as np

from ..domain import a2_rate_design as rate, a2_budget_pilot as budget, planner_parameter_selection as a2
from ..domain.artifact_registry import require
from ..io import artifact_registry as registry, development_experiment as original
from ..io.numeric_export_inputs import equal as equal_json
from ..io.recording_ingestion import file_state
from . import a2_budget_pilot as prior
from .locked_development_export import write

RECEIPT = "rate_design.private.json"
COMPLETE = "a2_rate_design_complete"
EXTENSION_RECEIPT = "rate_design_upper.private.json"
EXTENSION_COMPLETE = "a2_rate_design_upper_complete"
EXTENSION_REVISION = "a2-steering-rate-upper-bracket-v1"
PR60_TREE = "fbd7345cb8e267d6c68fecd34bf29c7c03707fa8"
PR60_RUNTIME = "9fa1358c8eda33c66183367ff20bf31f5463a6681504a2046dc4bc9cd8aed744"
PR61_TREE = "5c4ee4e6d3c31f5caccd8ff71848b40fecc9db12"
PR61_RUNTIME = "01f328d4d5364439e2d7bf5ad7e913aae6da8fcac1d8543ed9e4a70e6f7ba988"


def _validate_extension_receipt(previous: dict, source: dict, args: dict, preflight_sha256: str) -> None:
    require(previous["status"] == COMPLETE and previous["revision"] == rate.REVISION
            and previous["source"]["consumer_git_tree"] == PR61_TREE
            and previous["source"]["consumer_runtime_source_sha256"] == PR61_RUNTIME
            and previous["experiment_sha256"] == args["experiment_sha256"]
            and previous["accepted_archive_set_sha256"] == args["archive_set_sha256"]
            and previous["pr60_preflight_sha256"] == preflight_sha256,
            "rate_design_pr61_receipt_lineage")
    equal_json(source["consumer_runtime_versions"], previous["source"]["consumer_runtime_versions"],
               "rate_design_pr61_runtime_versions")
    equal_json(previous["protocol"], rate.PROTOCOL, "rate_design_pr61_receipt_protocol")


def _check_extension_trigger(original_design: dict) -> None:
    last_index = len(rate.CONFIGS) - 1
    require(any(row["choice"] == last_index
                and len(row["near_optimal_candidates"]) < len(original_design["feasible_candidates"])
                for row in original_design["synthetic_covariance_probes"]),
            "rate_design_pr61_no_material_upper_edge_choice")


def run_design(*, preflight: Path, preflight_sha256: str, previous_design: Path | None = None,
               previous_design_sha256: str | None = None, **args) -> dict:
    """Require exact preflight lineage and metadata replay before writing a fresh receipt."""
    preflight = original.metadata_path(preflight)
    state = file_state(preflight)
    receipt, _ = original.pinned_json(preflight, preflight_sha256)
    require(receipt["status"] == prior.READY and receipt["revision"] == budget.REVISION
            and receipt["source"]["consumer_git_tree"] == PR60_TREE
            and receipt["source"]["consumer_runtime_source_sha256"] == PR60_RUNTIME
            and receipt["experiment_sha256"] == args["experiment_sha256"]
            and receipt["accepted_archive_set_sha256"] == args["archive_set_sha256"],
            "rate_design_pr60_preflight_lineage")
    equal_json(receipt["protocol"], budget.PROTOCOL, "rate_design_pr60_preflight_protocol")
    extend = previous_design is not None
    require(extend == (previous_design_sha256 is not None), "rate_design_pr61_receipt_and_pin_required")
    protected = [preflight.parent]
    watched_receipts = {preflight: state}
    if extend:
        previous_design = original.metadata_path(previous_design)
        watched_receipts[previous_design] = file_state(previous_design)
        previous, _ = original.pinned_json(previous_design, previous_design_sha256)
        protected.append(previous_design.parent)
    inputs, output, source = prior._setup(args)
    registry.separate_output(output, protected)
    if extend:
        _validate_extension_receipt(previous, source, args, preflight_sha256)
    output.mkdir(mode=0o700, exist_ok=False)
    old_design, panel, covariates, watched = prior._preflight_plan(inputs)
    equal_json(old_design, receipt["design"], "rate_design_pr60_panel_parity")
    equal_json(prior._roles(inputs), receipt["roles"], "rate_design_pr60_role_parity")
    result = rate.diagnose(panel, covariates, old_design["nominal"])
    default_tracking = np.asarray(result["candidates"][rate.DEFAULT]["components_by_outing"])[:, 0]
    require(np.allclose(default_tracking, old_design["nominal"]["nominal_tracking_by_outing"][a2.DEFAULT],
                        rtol=1e-12, atol=1e-12), "rate_design_reference_parity")
    panel_sha256 = old_design["panel_donor_index_sha256"]
    if extend:
        require(previous["panel_donor_index_sha256"] == panel_sha256, "rate_design_pr61_panel_identity")
        equal_json(result, previous["design"], "rate_design_pr61_bracket_parity")
        _check_extension_trigger(result)
        result = rate.diagnose(panel, covariates, old_design["nominal"], extend_upper=True)
    prior._recheck(args, source, {**watched, **watched_receipts})
    report = {
        "status": EXTENSION_COMPLETE if extend else COMPLETE,
        "revision": EXTENSION_REVISION if extend else rate.REVISION,
        "protocol": rate.EXTENSION_PROTOCOL if extend else rate.PROTOCOL,
        "source": source,
        "pr60_preflight_sha256": preflight_sha256, "experiment_sha256": inputs.experiment_sha256,
        "accepted_archive_set_sha256": inputs.archive_set_sha256,
        "panel_donor_index_sha256": panel_sha256,
        "design": result, "residual_arrays_decoded": False, "model_fit_attempted": False,
        "inner_audit_numeric_opened": False, "outer_held_numeric_opened": False,
        "calibration_budget_selection_authorized": False,
    }
    if extend:
        report["pr61_design_sha256"] = previous_design_sha256
    write(output / (EXTENSION_RECEIPT if extend else RECEIPT), report)
    return report
