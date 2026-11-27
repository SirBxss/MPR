"""Metadata-only design diagnostics and a declared synthetic decision fixture.

No learned state, measured residual, held outcome or model draw enters here.
Variable-length sequences occupy separate blocks in the flip-bound operator.
"""

from functools import lru_cache

import numpy as np

from .artifact_registry import require
from . import planner_parameter_selection as policy
from .reference_planner import ReferencePlannerConfig


def quadratic_map(speeds: tuple[float, ...], intervals: tuple[float, ...], candidate: int) -> np.ndarray:
    return quadratic_map_for_config(speeds, intervals, policy.config(candidate))


@lru_cache(maxsize=24)
def quadratic_map_for_config(speeds: tuple[float, ...], intervals: tuple[float, ...],
                             cfg: ReferencePlannerConfig) -> np.ndarray:
    """Return M with zero-state quadratic loss y' M y, in row/station order."""
    length = len(speeds)
    require(3 <= length <= policy.PROTOCOL["design_diagnostic"]["maximum_frames"]
            and len(intervals) == length-1, "parameter_design_quadratic_budget")
    require(np.isfinite(speeds).all() and np.isfinite(intervals).all()
            and all(cfg.minimum_speed_mps <= v <= 40. for v in speeds)
            and all(cfg.minimum_dt_s <= dt <= cfg.maximum_dt_s for dt in intervals),
            "parameter_design_clock_or_speed")
    size = 21*length
    state = np.zeros((3,size)); matrix = np.zeros((size,size)); previous = None
    for t,speed in enumerate(speeds):
        k,g = policy.control_map_for_config(cfg,float(speed))
        command = k@state
        command[t*21:(t+1)*21] += g
        acceleration = speed**2*command
        matrix += np.outer(acceleration,acceleration)/(9*length)
        if t:
            matrix += np.outer(state[0],state[0])/(.03**2*(length-1))
            matrix += np.outer(state[1],state[1])/(.003**2*(length-1))
            jerk = (acceleration-previous)/intervals[t-1]
            matrix += np.outer(jerk,jerk)/(25*(length-1))
        previous = acceleration
        if t < length-1:
            distance = speed*intervals[t]
            state = np.array([state[0]+distance*state[1], state[1]+distance*command, command])
    matrix = .5*(matrix+matrix.T)
    require(np.isfinite(matrix).all(), "parameter_design_nonfinite_quadratic")
    matrix.setflags(write=False)
    return matrix


@lru_cache(maxsize=64)
def unit_covariance(length: int, rho: float) -> np.ndarray:
    """Unit marginal variance: spatial exp(30 m), per-frame stationary AR rho."""
    spec = policy.PROTOCOL["design_diagnostic"]
    require(type(length) is int and 3 <= length <= spec["maximum_frames"] and np.isfinite(rho) and abs(rho) < 1.,
            "parameter_design_covariance_contract")
    station = np.arange(0,101,5)
    spatial = np.exp(-np.abs(station[:,None]-station)/spec["spatial_length_m"])
    temporal = rho**np.abs(np.arange(length)[:,None]-np.arange(length))
    result = np.kron(temporal,spatial)
    result.setflags(write=False)
    return result


@lru_cache(maxsize=1024)
def metadata_moments(speeds: tuple[float, ...], intervals: tuple[float, ...], candidate: int) -> tuple:
    """Cache only small nominal summaries and synthetic covariance traces."""
    values = policy.rollout_costs(np.zeros((1,len(speeds),21)),np.array(speeds),np.array(intervals),candidate,policy.TASKS)
    matrix = quadratic_map(speeds,intervals,candidate)
    traces = tuple(float(np.sum(matrix*unit_covariance(len(speeds),rho)))
                   for rho in policy.PROTOCOL["design_diagnostic"]["synthetic_rhos"])
    return (tuple(float(values[m].mean()) for m in policy.COMPONENTS),
            tuple(values["tracking"][0].tolist()),
            (float(values["peak_acceleration"].max()),float(values["peak_jerk"].max())),traces)


@lru_cache(maxsize=4096)
def flip_eigenvalue(speeds: tuple[float, ...], intervals: tuple[float, ...], zero: int, candidate: int) -> float:
    """Largest eigenvalue of M_zero-M_candidate for one original sequence."""
    return float(np.linalg.eigvalsh(quadratic_map(speeds,intervals,zero)-quadratic_map(speeds,intervals,candidate))[-1])


def choose(losses: np.ndarray, feasible: np.ndarray) -> int:
    """Use exactly the selector's tie rule on a law-independent candidate set."""
    require(feasible.any(), "parameter_design_empty_feasible_set")
    priority = [policy.DEFAULT]+[i for i in range(9) if i != policy.DEFAULT]
    best = losses[feasible].min()
    return next(i for i in priority if feasible[i] and losses[i] <= best+policy.PROTOCOL["numerical_tie_tolerance"])


def design_diagnostics(speeds: np.ndarray, records: list[dict]) -> dict:
    """Assess training metadata before any real model sampling or held solving."""
    ids = [r["outing_id"] for r in records]
    groups = sorted(set(ids))
    require(len(groups) == 6 and all(ids.count(g) == 12 for g in groups), "parameter_design_context_groups")
    require(np.isfinite(speeds).all(), "parameter_design_finite_speeds")
    keys = [(tuple(float(v) for v in speeds[r["start_row"]:r["stop_row"]]),
             tuple(float(v)/1e9 for v in r["interval_ns"])) for r in records]
    summaries = [[metadata_moments(v,dt,c) for v,dt in keys] for c in range(9)]
    nominal = np.array([[r[0] for r in rows] for rows in summaries])
    tracking = np.array([[r[1] for r in rows] for rows in summaries])
    peaks = np.array([[r[2] for r in rows] for rows in summaries])
    traces = np.array([[r[3] for r in rows] for rows in summaries])
    # Quotas are balanced, so each block has weight1/72. Do not average
    # differently sized quadratic matrices as if their coordinates matched.
    weights = np.array([1/(len(groups)*ids.count(g)) for g in ids])
    nominal_loss = np.einsum('cn,n->c',nominal[:,:,3],weights)
    trace_mean = np.einsum('cnr,n->cr',traces,weights)
    settings = {}
    spec = policy.PROTOCOL["design_diagnostic"]
    for gate in policy.PROTOCOL["nominal_gate_sensitivities"]:
        feasible,details = policy.feasible_candidates(tracking,policy.nominal_probes(),ids,gate)
        entry = dict(feasible_candidates=np.flatnonzero(feasible).tolist(),nominal_diagnostics=details)
        if not feasible.any():
            entry.update(zero_choice=None,flip_bounds=[],synthetic_choices=[])
        else:
            zero = choose(nominal_loss,feasible)
            bounds = []
            for candidate in np.flatnonzero(feasible):
                candidate = int(candidate)
                if candidate == zero:continue
                eigenvalues = [float(w*flip_eigenvalue(v,dt,zero,candidate)) for w,(v,dt) in zip(weights,keys)]
                maximum = max(eigenvalues);gap = max(0.,float(nominal_loss[candidate]-nominal_loss[zero]))
                energy = gap/maximum if maximum > 1e-12 else None
                rms = float(np.sqrt(energy/(21*sum(len(v) for v,_ in keys)))) if energy is not None else None
                bounds.append(dict(candidate=candidate,nominal_gap=gap,maximum_weighted_block_eigenvalue=maximum,
                    minimum_total_second_moment=energy,minimum_global_per_element_rms_m=rms,
                    bound_scope="optimally_aligned_energy_in_weighted_block_operator_not_plausible_law_guarantee"))
            synthetic = []
            for index,rho in enumerate(spec["synthetic_rhos"]):
                for sigma in spec["synthetic_sigmas_m"]:
                    losses = nominal_loss+sigma**2*trace_mean[:,index]
                    synthetic.append(dict(rho=rho,sigma_m=sigma,choice=choose(losses,feasible),expected_losses=losses.tolist()))
            entry.update(zero_choice=zero,zero_choice_at_axis_edge=zero in (0,8),flip_bounds=bounds,synthetic_choices=synthetic)
        settings[f"gate_{gate:.2f}"] = entry
    main = settings[f"gate_{policy.PROTOCOL['nominal_gate']:.2f}"]
    reasons = []
    if len(main["feasible_candidates"]) < 2:reasons.append("primary_feasible_set_has_fewer_than_two_candidates")
    if any(not e["feasible_candidates"] for e in settings.values()):reasons.append("sensitivity_feasible_set_empty")
    if not any(s["choice"] != main["zero_choice"] for s in main["synthetic_choices"]):
        reasons.append("declared_synthetic_moments_never_change_primary_choice")
    if not any(b["minimum_global_per_element_rms_m"] is not None and b["minimum_global_per_element_rms_m"] <= spec["maximum_flip_rms_m"] for b in main["flip_bounds"]):
        reasons.append("no_flip_bound_within_declared_rms_budget")
    baseline_peaks = peaks[policy.DEFAULT].max(axis=0)
    if baseline_peaks[0] > 3. or baseline_peaks[1] > 5.:reasons.append("nominal_baseline_outside_training_context_envelope")
    return dict(informative=not reasons,reasons=reasons,settings=settings,scope="training_metadata_and_synthetic_covariances_only",
        nominal_components_by_context=nominal.tolist(),component_order=list(policy.COMPONENTS),
        nominal_peak_acceleration_jerk_by_context=peaks.tolist(),synthetic_unit_covariance_traces_by_context=traces.tolist(),
        nominal_macro_loss=nominal_loss.tolist(),baseline_peak_acceleration_mps2=float(baseline_peaks[0]),
        baseline_peak_jerk_mps3=float(baseline_peaks[1]),quadratic_block_weights=weights.tolist(),
        total_profile_coordinates=21*sum(len(v) for v,_ in keys))


@lru_cache(maxsize=1)
def synthetic_power_screen() -> dict:
    """Finite fixed-seed choice sensitivity, not a significance/power guarantee."""
    spec = policy.PROTOCOL["design_diagnostic"]
    keys = [(tuple([speed]*8),tuple([.1]*7)) for speed in (10.,20.,30.)]
    nominal = np.array([[metadata_moments(v,dt,c)[0][3] for v,dt in keys] for c in range(9)]).mean(axis=1)
    tracking = np.array([[metadata_moments(v,dt,c)[1] for v,dt in keys] for c in range(9)])
    tracking = np.tile(tracking,(1,24,1))
    ids = [str(g) for g in range(6) for _ in range(12)]
    feasible,_ = policy.feasible_candidates(tracking,policy.nominal_probes(),ids,policy.PROTOCOL["nominal_gate"])
    zero = choose(nominal,feasible)
    scenarios = []
    for rho in spec["synthetic_rhos"]:
        covariance = unit_covariance(8,rho)
        factor = np.linalg.cholesky(covariance)
        expected = np.array([np.mean([np.sum(quadratic_map(v,dt,c)*covariance) for v,dt in keys]) for c in range(9)])
        estimates = []
        for repeat in range(spec["power_repeats"]):
            rng = np.random.default_rng(spec["power_seed"]+repeat)
            draws = rng.normal(size=(64,168))@factor.T
            estimates.append(np.array([[np.mean(np.einsum('bi,bi->b',draws[:count]@quadratic_map(v,dt,c),draws[:count]))
                for v,dt in keys] for count in (64,32) for c in range(9)]).reshape(2,9,3).mean(axis=2))
        for sigma in spec["synthetic_sigmas_m"]:
            choices = [[choose(nominal+sigma**2*e[prefix],feasible) for prefix in (0,1)] for e in estimates]
            scenarios.append(dict(rho=rho,sigma_m=sigma,exact_moment_choice=choose(nominal+sigma**2*expected,feasible),
                exact_expected_losses=(nominal+sigma**2*expected).tolist(),
                choices_64_32=choices,changed_fraction_64=float(np.mean([c[0] != zero for c in choices])),
                prefix_choice_agreement=float(np.mean([c[0] == c[1] for c in choices]))))
    qualifying = sum(s["changed_fraction_64"] >= spec["power_minimum_changed_fraction"] for s in scenarios)
    return dict(passed=zero not in (0,8) and qualifying >= 2,zero_choice=zero,
        feasible_candidates=np.flatnonzero(feasible).tolist(),nominal_losses=nominal.tolist(),
        scenarios=scenarios,qualifying_scenarios=qualifying,repeats=spec["power_repeats"],
        scope="fixed_synthetic_gaussian_family_choice_frequency_not_BMW_result_or_statistical_test_power")
