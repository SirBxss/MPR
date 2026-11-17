"""Bounded local recovery tasks and prospective planner parameter selection."""

from dataclasses import asdict, replace
from functools import lru_cache
from statistics import mean

import numpy as np

from .artifact_registry import require
from .reference_planner import ReferencePlannerConfig, plan_reference_step
from .spatial_planner_response import STATIONS_M
from . import temporal_planner_pilot as temporal

REVISION = "v0.19.34-planner-parameter-selection-a1"
BASE = ReferencePlannerConfig()
SCALES = (.25, 1., 4.)
CANDIDATES = tuple((a, b) for a in SCALES for b in SCALES)
DEFAULT = CANDIDATES.index((1., 1.))
TASKS = np.array([[.3, 0., 0.], [-.3, 0., 0.], [0., .015, 0.], [0., -.015, 0.]])
TASKS.setflags(write=False)
ARMS = ("zero_disturbance", "empirical", "unconditional_gaussian", "conditional_gaussian",
        "stationary_ar", "one_state_ar", "unconditional_flow", "conditional_flow")
METRICS = ("tracking", "acceleration", "jerk", "loss", "lateral_exceedance", "acceleration_exceedance", "jerk_exceedance")
CONTEXTS_PER_OUTING = 12
PROTOCOL = {
    "planner_base": asdict(BASE), "prediction_dt_s": .1,
    "candidate_scales_curvature_and_rate": [list(v) for v in CANDIDATES],
    "default_candidate_index": DEFAULT, "initial_tasks": TASKS.tolist(),
    "contexts_per_training_outing": CONTEXTS_PER_OUTING,
    "context_selection": "floor_linspace_first_to_last_eligible_original_sequences_in_source_order",
    "support": "whole_original_temporal_eligible_sequences_at_least_three_frames",
    "draws": 64, "prefix_draws": 32, "seed": 193401,
    "metric_order": list(METRICS), "selector_order": list(ARMS),
    "flow_solver": "heun", "flow_steps": 128,
    "normalization": {"lateral_m": .3, "heading_rad": .03, "acceleration_mps2": 3., "jerk_mps3": 5.},
    "tracking": "mean_over_observed_states_after_initial_of_normalized_lateral_squared_plus_heading_squared",
    "acceleration": "mean_over_all_observed_commands_of_normalized_incremental_acceleration_squared",
    "jerk": "mean_over_observed_command_transitions_of_normalized_acceleration_difference_per_source_dt_squared",
    "loss": "tracking_plus_acceleration_plus_jerk_equal_normalized_weights",
    "tail_diagnostics": "draw_task_fraction_peak_future_lateral_gt_1m_peak_acceleration_gt_3_peak_jerk_gt_5",
    "nominal_gate": .10, "nominal_gate_sensitivities": [.05, .10, .20],
    "nominal_probes": {"speeds_mps": [10., 20., 30.], "frames": 26, "dt_s": .1,
                       "scope": "synthetic_zero_disturbance_tracking_only_no_error_law_extrapolation"},
    "nominal_gate_rule": "every_training_context_and_nominal_probe_task_tracking_at_most_one_plus_gate_times_default_plus_1e-12",
    "selection_weighting": "equal_tasks_and_draws_then_equal_sequences_within_training_outing_then_equal_training_outings",
    "selection": "minimum_predicted_loss_over_shared_nominal_feasible_grid_ties_within_1e-12_default_first_then_index",
    "evaluation": "all_supported_held_sequences_equal_weight_four_tasks_observed_residuals_only_after_choices_frozen",
    "primary": "held_outing_mean_loss_one_state_AR_selected_minus_zero_disturbance_selected",
    "primary_rule": "negative_seven_outing_macro_and_at_least_four_negative_outings",
    "nominal_adoption_requirement": "primary_AR_choice_passes_same_10_percent_nominal_requirement_on_every_held_task",
    "oracle": "retrospective_held_minimum_on_training_feasible_candidates_never_used_for_selection",
    "scope": "prospective_development_local_error_recovery_simulator_not_physical_replay_or_final_test",
}


def config(index: int) -> ReferencePlannerConfig:
    """Vary only correction effort and correction smoothness in the fixed grid."""
    require(type(index) is int and 0 <= index < len(CANDIDATES), "parameter_selection_candidate")
    effort, rate = CANDIDATES[index]
    return replace(BASE, weight_curvature=BASE.weight_curvature*effort,
                   weight_curvature_rate=BASE.weight_curvature_rate*rate)


@lru_cache(maxsize=8192)
def control_map(index: int, speed: float) -> tuple[np.ndarray, np.ndarray]:
    """Compute the native Riccati first control map for 21 profile coordinates.

    Propagating the linear term as a 3 by 21 matrix gives all station gains
    in one backward recursion instead of 24 separate native unit solves.
    """
    cfg = config(index)
    require(np.isfinite(speed) and cfg.minimum_speed_mps <= speed <= 40., "parameter_selection_speed")
    d = speed*.1
    distances = d*(np.arange(cfg.horizon_steps)+1)
    interpolation = np.column_stack([np.interp(distances, STATIONS_M, unit) for unit in np.eye(21)])
    a = np.array([[1., d, 0.], [0., 1., 0.], [0., 0., 0.]])
    b = np.array([0., d, 1.])
    q = np.diag([2*cfg.weight_lateral, 2*cfg.weight_heading, 0.])
    r = np.diag([0., 0., 2*cfg.weight_curvature_rate])
    cross = np.array([0., 0., -2*cfg.weight_curvature_rate])
    p, v = np.zeros((3, 3)), np.zeros((3, 21))
    for reverse_index, weights in enumerate(interpolation[::-1]):
        mult = cfg.terminal_multiplier if reverse_index == 0 else 1.
        combined = p + mult*q
        linear = v.copy()
        linear[0] -= 2*mult*cfg.weight_lateral*weights
        h = 2*(cfg.weight_curvature+cfg.weight_curvature_rate) + b@combined@b
        term = b@combined@a + cross
        gain, offset = term/h, (b@linear)/h
        p = r + a.T@combined@a - np.outer(term, gain)
        p = .5*(p+p.T)
        v = a.T@linear - np.outer(term, offset)
    state_map, profile_map = -gain, -offset
    state_map.setflags(write=False); profile_map.setflags(write=False)
    return state_map, profile_map


def response_costs(profiles: np.ndarray, speeds: np.ndarray, intervals: np.ndarray, candidate: int) -> dict:
    """Return [draw, task] costs of the true local state under exogenous errors."""
    y, speeds, intervals = map(lambda v: np.asarray(v, dtype=float), (profiles, speeds, intervals))
    require(y.ndim == 3 and y.shape[1:] == (len(speeds), 21) and len(y) > 0 and len(speeds) >= 3,
            "parameter_selection_sequence_shape")
    require(intervals.shape == (len(speeds)-1,) and np.isfinite(y).all() and np.isfinite(intervals).all()
            and np.all((intervals >= BASE.minimum_dt_s) & (intervals <= BASE.maximum_dt_s)),
            "parameter_selection_sequence_intervals")
    state = np.broadcast_to(TASKS, (len(y), *TASKS.shape)).copy()
    tracking = np.zeros(state.shape[:2]); acceleration = tracking.copy(); jerk = tracking.copy()
    max_lateral = tracking.copy(); max_acceleration = tracking.copy(); max_jerk = tracking.copy()
    previous_acceleration = None
    for t, speed in enumerate(speeds):
        k, g = control_map(candidate, float(speed))
        command = state@k + (y[:, t]@g)[:, None]
        acc = speed**2*command
        acceleration += (acc/3.)**2
        max_acceleration = np.maximum(max_acceleration, np.abs(acc))
        if t:
            tracking += (state[..., 0]/.3)**2 + (state[..., 1]/.03)**2
            max_lateral = np.maximum(max_lateral, np.abs(state[..., 0]))
            rate = (acc-previous_acceleration)/intervals[t-1]
            jerk += (rate/5.)**2
            max_jerk = np.maximum(max_jerk, np.abs(rate))
        previous_acceleration = acc
        if t < len(intervals):
            state = temporal.propagate(state, command, float(speed), float(intervals[t]))
    tracking /= len(speeds)-1; acceleration /= len(speeds); jerk /= len(speeds)-1
    result = dict(tracking=tracking, acceleration=acceleration, jerk=jerk,
                  loss=tracking+acceleration+jerk,
                  lateral_exceedance=(max_lateral > 1.).astype(float),
                  acceleration_exceedance=(max_acceleration > 3.).astype(float),
                  jerk_exceedance=(max_jerk > 5.).astype(float))
    require(all(np.isfinite(v).all() for v in result.values()), "parameter_selection_nonfinite_cost")
    return result


def contexts(block, fold: dict) -> tuple[dict, list[dict], dict]:
    """Classify whole original sequences before outcome based parameter selection."""
    _, arrays, records, support = temporal.prepare(block, fold)
    kept = [r for r in records if r["status"] == "eligible" and r["frame_count"] >= 3]
    require(bool(kept), "parameter_selection_empty_support")
    return arrays, kept, support


def select_context_indices(records: list[dict]) -> list[int]:
    """Choose a fixed metadata-only spread, without reading residual magnitudes."""
    require(len(records) >= CONTEXTS_PER_OUTING, "parameter_selection_training_context_support")
    return np.floor(np.linspace(0, len(records)-1, CONTEXTS_PER_OUTING)).astype(int).tolist()


def context_descriptors(records_by_outing: dict[str, list[dict]], training_outings: list[str]) -> list[dict]:
    """Pack whole training sequences without changing their clocks or history."""
    result, cursor = [], 0
    for outing in training_outings:
        eligible = [r for r in records_by_outing[outing] if r["status"] == "eligible" and r["frame_count"] >= 3]
        for index in select_context_indices(eligible):
            row = eligible[index]
            size = row["frame_count"]
            result.append(dict(outing_id=outing, original_sequence_index=row["sequence_index"],
                original_start_row=row["start_row"], original_stop_row=row["stop_row"],
                start_row=cursor, stop_row=cursor+size, frame_count=size,
                source_start_ns_decimal=row["source_start_ns_decimal"], interval_ns=row["interval_ns"]))
            cursor += size
    return result


@lru_cache(maxsize=1)
def nominal_probes() -> np.ndarray:
    """Test longer nominal recovery without extending sampled error sequences."""
    spec = PROTOCOL["nominal_probes"]
    values = np.empty((len(CANDIDATES), len(spec["speeds_mps"]), len(TASKS)))
    for candidate in range(len(CANDIDATES)):
        for index, speed in enumerate(spec["speeds_mps"]):
            values[candidate, index] = response_costs(np.zeros((1, spec["frames"], 21)),
                np.full(spec["frames"], speed), np.full(spec["frames"]-1, spec["dt_s"]), candidate)["tracking"][0]
    values.setflags(write=False)
    return values


def engineering_screen() -> dict:
    """Check synthetic native parity and rejection of an unresponsive control."""
    rng = np.random.default_rng(193400)
    maximum, cases = 0., 0
    for candidate in range(9):
        for speed in PROTOCOL["nominal_probes"]["speeds_mps"]:
            k, g = control_map(candidate, speed)
            for _ in range(4):
                state = rng.normal(size=3)*np.array([.3, .02, .001])
                profile = rng.normal(0, .1, 21)
                native = plan_reference_step(lateral_error_m=state[0], heading_error_rad=state[1],
                    previous_curvature_correction_per_m=state[2], residual_profile_m=profile,
                    stations_m=np.asarray(STATIONS_M), speed_mps=speed, dt_s=.1, config=config(candidate))
                maximum = max(maximum, abs(float(state@k+profile@g)-native.curvature_correction_per_m))
                cases += 1
    require(maximum <= 1e-10, "parameter_selection_native_map_parity")
    probes = nominal_probes()
    unresponsive = []
    for speed in PROTOCOL["nominal_probes"]["speeds_mps"]:
        state = TASKS.copy()
        terms = []
        for _ in range(PROTOCOL["nominal_probes"]["frames"]-1):
            state = temporal.propagate(state, np.zeros(4), speed, .1)
            terms.append((state[:,0]/.3)**2+(state[:,1]/.03)**2)
        unresponsive.append(np.mean(terms, axis=0))
    require(np.any(np.asarray(unresponsive) > 1.1*probes[DEFAULT]+1e-12),
            "parameter_selection_nominal_gate_cannot_reject_unresponsive_control")
    return dict(status="passed_synthetic_parameter_selection_engineering_screen", cases=cases,
                maximum_command_difference_per_m=maximum, unresponsive_nominal_control_rejected=True,
                nominal_probe_tracking=probes.tolist(), unresponsive_nominal_tracking=np.asarray(unresponsive).tolist())


def grid_costs(arms: dict[str, np.ndarray], speeds: np.ndarray, records: list[dict]) -> dict:
    """Evaluate every candidate on the same ensembles and local initial tasks.

    The per-sequence arm means preserve both 64 and 32 draw results. No draws
    are regenerated for a different candidate, nominal gate or prefix.
    """
    require(tuple(arms) == ARMS and len(arms[ARMS[0]]) == 1
            and all(len(arms[a]) == PROTOCOL["draws"] for a in ARMS[1:]), "parameter_selection_fixed_arms")
    require(all(v.shape[1:] == (len(speeds), 21) and np.isfinite(v).all() for v in arms.values()),
            "parameter_selection_draw_shapes")
    joined = np.concatenate(list(arms.values()))
    offsets = np.cumsum([0]+[len(v) for v in arms.values()])
    costs = np.empty((len(CANDIDATES), len(ARMS), 2, len(records), len(METRICS)))
    nominal = np.empty((len(CANDIDATES), len(records), len(TASKS)))
    for candidate in range(len(CANDIDATES)):
        for index, record in enumerate(records):
            lo, hi = record["start_row"], record["stop_row"]
            values = response_costs(joined[:, lo:hi], speeds[lo:hi], np.array(record["interval_ns"])/1e9, candidate)
            nominal[candidate, index] = values["tracking"][0]
            for arm_index in range(len(ARMS)):
                start, stop = offsets[arm_index:arm_index+2]
                for prefix_index, count in enumerate((PROTOCOL["draws"], PROTOCOL["prefix_draws"])):
                    end = min(stop, start+count)
                    costs[candidate, arm_index, prefix_index, index] = [values[m][start:end].mean() for m in METRICS]
    return dict(costs=costs, nominal_tracking=nominal, nominal_probe_tracking=nominal_probes())


def select_parameters(grid: dict, outing_ids: list[str]) -> dict:
    """Freeze choices using training context forecasts and a shared nominal gate."""
    costs, nominal, probes = grid["costs"], grid["nominal_tracking"], grid["nominal_probe_tracking"]
    require(costs.shape == (9, 8, 2, len(outing_ids), len(METRICS))
            and nominal.shape == (9, len(outing_ids), 4) and probes.shape == (9, 3, 4)
            and np.isfinite(costs).all() and np.isfinite(nominal).all()
            and np.isfinite(probes).all(), "parameter_selection_grid_shape")
    groups = sorted(set(outing_ids))
    require(len(groups) == 6 and all(outing_ids.count(i) == CONTEXTS_PER_OUTING for i in groups),
            "parameter_selection_balanced_training_contexts")
    group_metrics = np.stack([costs[..., np.array(outing_ids) == i, :].mean(axis=3) for i in groups], axis=3)
    predicted = group_metrics.mean(axis=3)
    priority = [DEFAULT] + [i for i in range(9) if i != DEFAULT]
    settings = {}
    for gate in PROTOCOL["nominal_gate_sensitivities"]:
        feasible = np.all(nominal <= (1+gate)*nominal[DEFAULT]+1e-12, axis=(1, 2))
        feasible &= np.all(probes <= (1+gate)*probes[DEFAULT]+1e-12, axis=(1, 2))
        require(feasible[DEFAULT], "parameter_selection_default_must_be_feasible")
        for prefix_index, count in enumerate((64, 32)):
            chosen = {}
            for arm_index, arm in enumerate(ARMS):
                losses = predicted[:, arm_index, prefix_index, METRICS.index("loss")]
                best = losses[feasible].min()
                chosen[arm] = next(i for i in priority if feasible[i] and losses[i] <= best+1e-12)
            settings[f"draws_{count}_gate_{gate:.2f}"] = dict(gate_fraction=gate, draws=count,
                feasible_candidates=np.flatnonzero(feasible).tolist(), selected_candidates=chosen)
    return dict(settings=settings, training_outing_ids=groups,
                predicted_metrics_by_training_outing=group_metrics.tolist(),
                predicted_macro_metrics=predicted.tolist(), nominal_tracking_by_context_task=nominal.tolist(),
                nominal_probe_tracking=probes.tolist())


def evaluate_held(residuals: np.ndarray, speeds: np.ndarray, records: list[dict]) -> dict:
    """Score the fixed grid on observed held residuals after choices are written."""
    scored, nominal = [], []
    for record in records:
        lo, hi = record["start_row"], record["stop_row"]
        values, gates = [], []
        for candidate in range(9):
            args = dict(speeds=speeds[lo:hi], intervals=np.array(record["interval_ns"])/1e9, candidate=candidate)
            observed = response_costs(residuals[None, lo:hi], **args)
            clean = response_costs(np.zeros((1, hi-lo, 21)), **args)
            values.append({metric: float(observed[metric].mean()) for metric in METRICS})
            gates.append(clean["tracking"][0].tolist())
        scored.append(dict(sequence_index=record["sequence_index"], frame_count=hi-lo, candidate_metrics=values))
        nominal.append(gates)
    means = [{m: mean(r["candidate_metrics"][c][m] for r in scored) for m in METRICS} for c in range(9)]
    return dict(sequence_scores=scored, candidate_mean_metrics=means,
                nominal_tracking_by_sequence_candidate_task=nominal)


def compare_choices(selection: dict, held: dict) -> dict:
    """Assess all frozen choices and a labelled retrospective grid oracle."""
    nominal = np.array(held["nominal_tracking_by_sequence_candidate_task"])
    summaries = {}
    for name, setting in selection["settings"].items():
        chosen = dict(fixed_default=DEFAULT, **setting["selected_candidates"])
        costs = held["candidate_mean_metrics"]
        oracle = min(costs[i]["loss"] for i in setting["feasible_candidates"])
        methods = {}
        for method, index in chosen.items():
            violations = nominal[:, index] > (1+setting["gate_fraction"])*nominal[:, DEFAULT]+1e-12
            methods[method] = dict(candidate=index, metrics=costs[index],
                regret_vs_training_feasible_grid_oracle=costs[index]["loss"]-oracle,
                nominal_violating_sequence_tasks=int(violations.sum()), assessed_sequence_tasks=int(violations.size))
        summaries[name] = dict(methods=methods, retrospective_grid_oracle_loss=oracle,
            primary_AR_minus_zero=methods["one_state_ar"]["metrics"]["loss"]-methods["zero_disturbance"]["metrics"]["loss"])
    return summaries


def summarize(folds: dict[str, dict]) -> dict:
    """Report equal outing development results and all prespecified sensitivities."""
    require(len(folds) == 7, "parameter_selection_seven_folds_required")
    result = {}
    for setting in next(iter(folds.values())):
        methods = next(iter(folds.values()))[setting]["methods"]
        values = [f[setting]["primary_AR_minus_zero"] for f in folds.values()]
        result[setting] = dict(outing_count=7, primary_AR_minus_zero_macro=mean(values),
            negative_outings=sum(v < 0 for v in values), positive_outings=sum(v > 0 for v in values),
            tied_outings=sum(v == 0 for v in values), minimum_difference=min(values), maximum_difference=max(values),
            methods={m: dict(macro_metrics={k: mean(f[setting]["methods"][m]["metrics"][k] for f in folds.values()) for k in METRICS},
                macro_regret=mean(f[setting]["methods"][m]["regret_vs_training_feasible_grid_oracle"] for f in folds.values()),
                nominal_violating_sequence_tasks=sum(f[setting]["methods"][m]["nominal_violating_sequence_tasks"] for f in folds.values()))
                for m in methods})
    main = result["draws_64_gate_0.10"]
    risk_passes = main["primary_AR_minus_zero_macro"] < 0 and main["negative_outings"] >= 4
    nominal_passes = main["methods"]["one_state_ar"]["nominal_violating_sequence_tasks"] == 0
    return dict(settings=result, descriptive_primary_risk_improves=risk_passes,
                primary_held_nominal_requirement_passes=nominal_passes,
                development_recommendation_supported=risk_passes and nominal_passes)
