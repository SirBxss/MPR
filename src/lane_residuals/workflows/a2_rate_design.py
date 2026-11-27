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
PR60_TREE = "fbd7345cb8e267d6c68fecd34bf29c7c03707fa8"
PR60_RUNTIME = "9fa1358c8eda33c66183367ff20bf31f5463a6681504a2046dc4bc9cd8aed744"


def run_design(*, preflight: Path, preflight_sha256: str, **args) -> dict:
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
    inputs, output, source = prior._setup(args)
    registry.separate_output(output, (preflight.parent,))
    output.mkdir(mode=0o700, exist_ok=False)
    old_design, panel, covariates, watched = prior._preflight_plan(inputs)
    equal_json(old_design, receipt["design"], "rate_design_pr60_panel_parity")
    equal_json(prior._roles(inputs), receipt["roles"], "rate_design_pr60_role_parity")
    result = rate.diagnose(panel, covariates, old_design["nominal"])
    default_tracking = np.asarray(result["candidates"][rate.DEFAULT]["components_by_outing"])[:, 0]
    require(np.allclose(default_tracking, old_design["nominal"]["nominal_tracking_by_outing"][a2.DEFAULT],
                        rtol=1e-12, atol=1e-12), "rate_design_reference_parity")
    prior._recheck(args, source, {**watched, preflight: state})
    report = {
        "status": COMPLETE, "revision": rate.REVISION, "protocol": rate.PROTOCOL, "source": source,
        "pr60_preflight_sha256": preflight_sha256, "experiment_sha256": inputs.experiment_sha256,
        "accepted_archive_set_sha256": inputs.archive_set_sha256,
        "panel_donor_index_sha256": old_design["panel_donor_index_sha256"],
        "design": result, "residual_arrays_decoded": False, "model_fit_attempted": False,
        "inner_audit_numeric_opened": False, "outer_held_numeric_opened": False,
        "calibration_budget_selection_authorized": False,
    }
    write(output / RECEIPT, report)
    return report
