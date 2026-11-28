"""Check whether repeated whole-outing subsets share a usable calibration panel."""

from pathlib import Path

from ..domain import a2_budget_pilot as pilot, a2_rate_design as rate, a2_repeated_budget as support
from ..domain.artifact_registry import require
from ..io import a2_budget_pilot as reader, artifact_registry as registry, development_experiment as original
from ..io.numeric_export_inputs import equal as equal_json
from ..io.recording_ingestion import file_state
from . import a2_budget_pilot as prior, a2_rate_design as rate_workflow
from .locked_development_export import write

RECEIPT = "repeated_budget_support.private.json"
READY = "a2_repeated_budget_support_ready"
STOPPED = "a2_repeated_budget_support_stopped"
PR62_TREE = "1a0df357a161dafd9b0907601e74800166c02e3b"
PR62_RUNTIME = "abd702ab2388ac215ac5796cc513fc9dea738c5f03ecc5b29e28251133d3e396"


def _load_receipts(preflight, preflight_sha256, rate_receipt, rate_receipt_sha256, args):
    preflight = original.metadata_path(preflight)
    rate_receipt = original.metadata_path(rate_receipt)
    watched = {path: file_state(path) for path in (preflight, rate_receipt)}
    original_plan, _ = original.pinned_json(preflight, preflight_sha256)
    previous, _ = original.pinned_json(rate_receipt, rate_receipt_sha256)
    require(original_plan["status"] == prior.READY and original_plan["revision"] == pilot.REVISION
            and original_plan["source"]["consumer_git_tree"] == rate_workflow.PR60_TREE
            and original_plan["source"]["consumer_runtime_source_sha256"] == rate_workflow.PR60_RUNTIME
            and original_plan["experiment_sha256"] == previous["experiment_sha256"] == args["experiment_sha256"]
            and original_plan["accepted_archive_set_sha256"] == previous["accepted_archive_set_sha256"]
            == args["archive_set_sha256"] and previous["pr60_preflight_sha256"] == preflight_sha256,
            "repeated_budget_receipt_lineage")
    require(previous["status"] == rate_workflow.EXTENSION_COMPLETE
            and previous["revision"] == rate_workflow.EXTENSION_REVISION
            and previous["source"]["consumer_git_tree"] == PR62_TREE
            and previous["source"]["consumer_runtime_source_sha256"] == PR62_RUNTIME
            and all(previous[field] is False for field in (
                "calibration_budget_selection_authorized", "residual_arrays_decoded", "model_fit_attempted",
                "outer_held_numeric_opened", "inner_audit_numeric_opened")),
            "repeated_budget_pr62_design_contract")
    candidates = previous["design"]["feasible_candidates"]
    require(type(candidates) is list and len(candidates) >= 2
            and all(type(i) is int and 0 <= i < len(rate.CONFIGS) + len(rate.UPPER_CONFIGS) for i in candidates)
            and candidates == sorted(set(candidates)), "repeated_budget_pr62_candidate_contract")
    equal_json(original_plan["protocol"], pilot.PROTOCOL, "repeated_budget_pr60_protocol")
    equal_json(previous["protocol"], rate.EXTENSION_PROTOCOL, "repeated_budget_pr62_protocol")
    return original_plan, previous, watched


def preflight(*, preflight: Path, preflight_sha256: str, rate_receipt: Path,
              rate_receipt_sha256: str, **args) -> dict:
    """Bind the prior receipts, then use the existing allowlisted metadata reader."""
    original_plan, previous, watched_receipts = _load_receipts(
        preflight, preflight_sha256, rate_receipt, rate_receipt_sha256, args,
    )
    inputs, output, source = prior._setup(args)
    registry.separate_output(output, [path.parent for path in watched_receipts])
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    equal_json(previous["source"]["consumer_runtime_versions"], source["consumer_runtime_versions"],
               "repeated_budget_pr62_runtime_versions")
    design, panel, covariates, watched = prior._preflight_plan(inputs)
    equal_json(design, original_plan["design"], "repeated_budget_pr60_panel_parity")
    equal_json(prior._roles(inputs), original_plan["roles"], "repeated_budget_pr60_role_parity")
    require(design["panel_donor_index_sha256"] == previous["panel_donor_index_sha256"],
            "repeated_budget_pr62_panel_identity")
    replayed = rate.diagnose(panel, covariates, design["nominal"], extend_upper=True)
    equal_json(replayed, previous["design"], "repeated_budget_pr62_design_parity")
    candidates = tuple(replayed["feasible_candidates"])
    common, findings = support.support_panel(panel, {spec.outing_id: spec.offsets for spec in inputs.calibration})
    original_anchor = design["nominal"]
    tracking_anchors = {
        "outing_ids": original_anchor["training_outing_ids"],
        "pr60_full_panel": original_anchor["grid_best_tracking_by_outing"],
        "common_panel": None,
    }
    nominal, nominal_original = [], []
    if all(findings["common_contexts_by_outing"].values()):
        _, common_anchor, _ = pilot.nominal_curvature_grid(common, covariates)
        tracking_anchors["common_panel"] = common_anchor["grid_best_tracking_by_outing"]
        nominal = rate.check_nominal_candidates(common, covariates, common_anchor, candidates)
        nominal_original = rate.check_nominal_candidates(common, covariates, original_anchor, candidates)
        if any(row["nominal_gate_failures"] for row in nominal):
            findings["reasons"].append("fixed_rate_grid_fails_on_common_panel")
    common_panel_pin = reader.value_sha256(
        [{"sequence": context.record(), "donor_starts": donors}
         for context, donors in zip(common.contexts, common.donors)]
    )
    prior._recheck(args, source, {**watched, **watched_receipts})
    report = {
        "revision": support.REVISION, "protocol": support.PROTOCOL, "source": source,
        "status": STOPPED if findings["reasons"] else READY,
        "experiment_sha256": inputs.experiment_sha256, "accepted_archive_set_sha256": inputs.archive_set_sha256,
        "pr60_preflight_sha256": preflight_sha256, "pr62_rate_receipt_sha256": rate_receipt_sha256,
        "pr60_panel_donor_index_sha256": design["panel_donor_index_sha256"],
        "common_panel_sha256": common_panel_pin, "support": findings,
        "fixed_rate_candidate_indices": list(candidates), "nominal_tracking_anchors": tracking_anchors,
        "nominal_fixed_grid": nominal, "nominal_fixed_grid_original_anchor": nominal_original,
        "residual_arrays_decoded": False, "model_fit_attempted": False, "inner_audit_numeric_opened": False,
        "outer_held_numeric_opened": False, "calibration_budget_selection_authorized": False,
    }
    # Exclusive even for a scientific stop, after source and receipt parity succeeds.
    output.mkdir(mode=0o700, exist_ok=False)
    write(output / RECEIPT, report)
    return report
