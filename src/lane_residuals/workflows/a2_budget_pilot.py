"""Stage the a2 budget pilot with immutable, externally pinned receipts."""

from dataclasses import asdict
import os
from pathlib import Path
import resource
import time

import numpy as np

from ..domain import a2_budget_pilot as pilot
from ..domain import planner_parameter_selection as a2
from ..domain.artifact_registry import require
from ..io import a2_budget_pilot as reader, artifact_registry as registry, development_experiment as original
from ..io.numeric_export_inputs import equal as equal_json
from ..io.recording_ingestion import file_state
from ..modeling.matched_gaussian import fit_matched_gaussian
from ..modeling.matched_one_state_ar import OneStateAR, fit_one_state_ar
from .development_experiment import source_guard
from .locked_development_export import write

PREFLIGHT = "preflight.private.json"
CHOICES = "choices_frozen.private.json"
AUDIT = "audit.private.json"
READY = "a2_budget_preflight_ready"
FROZEN = "a2_budget_choices_frozen"
COMPLETE = "a2_budget_inner_audit_complete"


def _setup(args):
    source, project, experiment, output = (original.metadata_path(args[key])
                                           for key in ("source", "project", "experiment", "output"))
    source_identity = source_guard(source, args["expected_tree"], args["expected_runtime"])
    inputs = reader.load_pinned_inputs(project, experiment, args["experiment_sha256"], args["archive_set_sha256"])
    registry.separate_output(output, inputs.protected)
    for checkout in (source, project):
        require(not output.is_relative_to(checkout) or output.is_relative_to(checkout / "outputs/diagnostics/private"),
                "budget_private_output_location")
    return inputs, output, source_identity


def _recheck(args, source_identity, watched):
    current = source_guard(args["source"], args["expected_tree"], args["expected_runtime"])
    require(current == source_identity, "budget_source_or_runtime_changed")
    require(all(file_state(path) == before for path, before in watched.items()), "budget_input_changed")


def _roles(inputs):
    return {
        "outer_held_outing": inputs.outer_held, "inner_audit_outing": inputs.audit,
        "calibration_outings": [row.outing_id for row in inputs.calibration],
        "numeric_sha256_by_non_outer_outing": {
            row.outing_id: row.numeric_sha256 for row in (*inputs.calibration, inputs.audit_outing)
        },
    }


def _sequence_metadata(spec, values):
    return pilot.eligible_sequences(spec.outing_id, spec.rows["estimate_source_time_ns_decimal"],
                                    spec.offsets, values[:, 0])


def _preflight_plan(inputs):
    covariates, eligible, watched = {}, {}, {}
    for spec in inputs.calibration:
        values, watched[spec.archive] = reader.open_accepted_outing(spec, labels=False)
        covariates[spec.outing_id] = values
        eligible[spec.outing_id] = _sequence_metadata(spec, values)
    panel = pilot.build_panel(eligible)
    design = pilot.nominal_panel(panel, covariates, {spec.outing_id: spec.offsets for spec in inputs.calibration})
    design["panel_donor_index_sha256"] = reader.value_sha256(
        [{"sequence": context.record(), "donor_starts": donors} for context, donors in zip(panel.contexts, panel.donors)]
    )
    return design, panel, covariates, watched


def _preflight_receipt(inputs, source_identity, design):
    return {
        "revision": pilot.REVISION, "protocol": pilot.PROTOCOL,
        "status": "a2_budget_preflight_stopped" if design["reasons"] else READY,
        "source": source_identity, "experiment_sha256": inputs.experiment_sha256,
        "accepted_archive_set_sha256": inputs.archive_set_sha256, "roles": _roles(inputs), "design": design,
        "residual_arrays_decoded": False, "model_fit_attempted": False, "outer_held_numeric_opened": False,
        "inner_audit_numeric_opened": False,
    }


def preflight(**args):
    inputs, output, source = _setup(args)
    output.mkdir(mode=0o700, exist_ok=False)
    design, _, _, watched = _preflight_plan(inputs)
    _recheck(args, source, watched)
    report = _preflight_receipt(inputs, source, design)
    write(output / PREFLIGHT, report)
    return report


def _fit_panel(blocks, conditions, offsets, output):
    observations = np.concatenate([block.y for block in blocks])
    training_conditions = np.concatenate([block.x for block in blocks])
    start = time.perf_counter()
    base = fit_matched_gaussian(observations, training_conditions, mode="conditional_gaussian")
    model, fit = fit_one_state_ar(base, blocks)
    model_record = {"state": model.to_dict(), "fit_report": asdict(fit)}
    write(output, model_record)
    restored = OneStateAR.from_dict(model_record["state"])
    metadata = {
        "fit_seconds_including_state_round_trip": time.perf_counter() - start,
        "native_converged": bool(model_record["state"]["legacy_model"]["converged"]),
        "fit_warnings": list(fit.warnings), "fit_state_sha256": original.sha(output),
    }
    if not metadata["native_converged"]:
        return None, metadata
    start = time.perf_counter()
    profiles = restored.sample(conditions, offsets, sample_count=pilot.DRAWS, seed=pilot.SEED)
    metadata["sampling_seconds"] = time.perf_counter() - start
    return profiles, metadata


def _score(profiles, panel, conditions, offsets, feasible):
    start = time.perf_counter()
    score = pilot.selection_score(profiles, panel, conditions, offsets, feasible)
    return {**score, "rollout_seconds": time.perf_counter() - start, "status": "selected"}


def select(*, preflight_sha256, **args):
    inputs, output, source = _setup(args)
    predecessor, _ = original.pinned_json(output / PREFLIGHT, preflight_sha256)
    require(predecessor["status"] == READY, "budget_ready_preflight_required")
    attempts = output / "selection_attempt.private"
    attempts.mkdir(mode=0o700, exist_ok=False)
    design, panel, covariates, watched = _preflight_plan(inputs)
    equal_json(predecessor, _preflight_receipt(inputs, source, design), "budget_preflight_plan_changed")
    _recheck(args, source, watched)
    conditions, offsets = pilot.panel_layout(panel, covariates)
    feasible = design["feasible_candidates"]
    completed, failures, blocks = {}, [], []
    selection_started = time.perf_counter()
    for budget in pilot.BUDGETS:
        # Extend the nested subset just before its fit. Only the five calibration objects are reachable.
        for spec in inputs.calibration[len(blocks):budget]:
            block, state = reader.open_accepted_outing(spec, labels=True)
            require(state == watched[spec.archive], "budget_numeric_input_changed_since_preflight")
            blocks.append(block)
        start = time.perf_counter()
        empirical = pilot.empirical_profiles(panel, {block.outing_id: block.y for block in blocks})
        empirical_seconds = time.perf_counter() - start
        empirical_score = _score(empirical, panel, conditions, offsets, feasible)
        del empirical
        empirical_score["sampling_seconds"] = empirical_seconds
        write(attempts / f"budget_{budget}_empirical.private.json", empirical_score)
        fit_started = time.perf_counter()
        try:
            draws, fit_details = _fit_panel(blocks, conditions, offsets, attempts / f"budget_{budget}_ar_state.private.json")
            if draws is None:
                ar_score = {"status": "fit_not_converged", **fit_details}
            else:
                ar_score = {**_score(draws, panel, conditions, offsets, feasible), **fit_details}
                del draws
        except (ValueError, RuntimeError, ArithmeticError, np.linalg.LinAlgError) as error:
            ar_score = {"status": "fit_or_sampling_failed", "failure_type": type(error).__name__,
                        "attempt_seconds": time.perf_counter() - fit_started}
        write(attempts / f"budget_{budget}_one_state_ar.private.json", ar_score)
        if ar_score["status"] != "selected":
            failures.append(budget)
        completed[str(budget)] = {"one_state_ar": ar_score, "empirical": empirical_score}
        _recheck(args, source, watched)
        original.pinned_json(output / PREFLIGHT, preflight_sha256)
    report = {
        "revision": pilot.REVISION, "status": "a2_budget_selection_incomplete" if failures else FROZEN,
        "source": source, "experiment_sha256": inputs.experiment_sha256,
        "accepted_archive_set_sha256": inputs.archive_set_sha256, "roles": _roles(inputs),
        "preflight_sha256": preflight_sha256, "feasible_candidates": feasible,
        "budget_counts": design["budgets"], "choices": completed, "failed_ar_budgets": failures,
        "fit_pipeline_attempt_count": len(pilot.BUDGETS), "selection_wall_seconds": time.perf_counter() - selection_started,
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "outer_held_numeric_opened": False, "inner_audit_numeric_opened": False,
    }
    write(output / CHOICES, report)
    return report


def audit(*, choices_sha256, **args):
    inputs, output, source = _setup(args)
    choices, _ = original.pinned_json(output / CHOICES, choices_sha256)
    require(choices["revision"] == pilot.REVISION and choices["status"] == FROZEN
            and choices["source"] == source and choices["roles"] == _roles(inputs)
            and choices["experiment_sha256"] == inputs.experiment_sha256
            and choices["accepted_archive_set_sha256"] == inputs.archive_set_sha256
            and choices["outer_held_numeric_opened"] is False and choices["inner_audit_numeric_opened"] is False,
            "budget_complete_frozen_choices_required")
    before, _ = original.pinned_json(output / PREFLIGHT, choices["preflight_sha256"])
    require(before["status"] == READY and before["roles"] == choices["roles"] and before["source"] == source
            and before["design"]["feasible_candidates"] == choices["feasible_candidates"]
            and before["design"]["budgets"] == choices["budget_counts"], "budget_frozen_choice_predecessor")
    require(set(choices["choices"]) == {str(b) for b in pilot.BUDGETS}, "budget_all_budget_choices_required")
    for budget, arms in choices["choices"].items():
        require(set(arms) == set(pilot.ARMS), "budget_both_arms_required")
        for method, selection in arms.items():
            require(selection["status"] == "selected" and selection["candidate"] in choices["feasible_candidates"],
                    "budget_selected_candidate_invalid")
            original.pinned_json(
                output / "selection_attempt.private" / f"budget_{budget}_{method}.private.json",
                reader.value_sha256(selection),
            )
    attempt = output / "audit_attempt.private"
    attempt.mkdir(mode=0o700, exist_ok=False)
    start = time.perf_counter()
    spec = inputs.audit_outing
    values, state = reader.open_accepted_outing(spec, labels=False)
    sequences = pilot.spread(_sequence_metadata(spec, values), a2.CONTEXTS_PER_OUTING)
    write(attempt / "audit_contexts.private.json", {
        "choices_sha256": choices_sha256, "selected_audit_sequences": [s.record() for s in sequences],
    })
    report = {
        "revision": pilot.REVISION, "source": source, "choices_sha256": choices_sha256,
        "audit_outing": inputs.audit, "audit_sequences": len(sequences), "audit_frames": sum(s.length for s in sequences),
        "scope": "one_inner_development_audit_outing", "outer_held_numeric_opened": False,
        "inner_audit_numeric_opened": True,
    }
    if not sequences:
        report.update(status="a2_budget_audit_no_supported_sequences", inner_audit_residuals_decoded=False)
    else:
        block, labelled_state = reader.open_accepted_outing(spec, labels=True)
        require(labelled_state == state, "budget_inner_audit_input_changed")
        report.update(status=COMPLETE, inner_audit_residuals_decoded=True,
                      **pilot.audit_scores(block.y, values[:, 0], sequences, choices["choices"]))
    report["wall_seconds"] = time.perf_counter() - start
    report["process_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    _recheck(args, source, {spec.archive: state})
    original.pinned_json(output / CHOICES, choices_sha256)
    require(not os.path.lexists(output / AUDIT), "budget_existing_audit_receipt")
    write(output / AUDIT, report)
    return report
