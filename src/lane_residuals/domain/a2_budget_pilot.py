"""Training-panel support and score arithmetic for the fixed a2 budget pilot."""

from dataclasses import dataclass
from statistics import mean

import numpy as np

from . import planner_parameter_selection as a2
from .artifact_registry import require
from ..modeling.matched_one_state_ar import MAX_PADDED_FRAMES, MAX_SAMPLED_PADDED_FRAMES

REVISION = "a2-calibration-budget-pilot-v1"
BUDGETS = (1, 3, 5)
ARMS = ("empirical", "one_state_ar")
CADENCE_NS = 20_000_000
NOMINAL_PEAK_LIMIT = (3.0, 5.0)
DRAWS = a2.PROTOCOL["draws"]
PREFIX = a2.PROTOCOL["prefix_draws"]
SEED = a2.PROTOCOL["seed"]
PROTOCOL = {
    "budgets": list(BUDGETS), "arms": list(ARMS), "cadence_tolerance_ns": CADENCE_NS,
    "contexts_per_outing": a2.CONTEXTS_PER_OUTING, "draws": DRAWS, "prefix_draws": PREFIX, "seed": SEED,
    "a2_revision": a2.REVISION, "nominal_gate": a2.PROTOCOL["nominal_gate"],
    "constant_nominal_limits": list(NOMINAL_PEAK_LIMIT), "descriptive_margin": .02,
    "unit": "whole_labelled_outings_with_shared_calibration_covariates",
    "reported_regret": "audit_loss_of_selected_candidate_minus_five_outing_empirical_selected_loss",
}


@dataclass(frozen=True)
class Sequence:
    outing: str
    index: int
    start: int
    stop: int
    intervals_ns: tuple[int, ...]

    @property
    def length(self) -> int:
        return self.stop - self.start

    def record(self) -> dict:
        return {"outing_id": self.outing, "sequence_index": self.index, "start_row": self.start,
                "stop_row": self.stop, "frame_count": self.length, "interval_ns": list(self.intervals_ns)}

    def intervals(self) -> np.ndarray:
        return np.asarray(self.intervals_ns) / 1e9


def eligible_sequences(outing: str, times: list[str], offsets: np.ndarray, speeds: np.ndarray) -> list[Sequence]:
    require(len(times) == len(speeds) == offsets[-1]
            and all(type(t) is str and t.isascii() and t.isdecimal() for t in times),
            "budget_original_source_clock_shape")
    stamps = [int(t) for t in times]
    require(all(t <= np.iinfo(np.int64).max for t in stamps), "budget_original_source_clock_range")
    sequences = []
    for index, (start, stop) in enumerate(zip(offsets[:-1], offsets[1:])):
        lo, hi = int(start), int(stop)
        intervals = tuple(stamps[row + 1] - stamps[row] for row in range(lo, hi - 1))
        require(all(dt > 0 for dt in intervals), "budget_original_clock_order")
        if (hi - lo >= 3 and np.all((speeds[lo:hi] >= a2.BASE.minimum_speed_mps) & (speeds[lo:hi] <= 40.))
                and all(a2.BASE.minimum_dt_s * 1e9 <= dt <= a2.BASE.maximum_dt_s * 1e9 for dt in intervals)):
            sequences.append(Sequence(outing, index, lo, hi, intervals))
    return sequences


def spread(sequences: list[Sequence], count: int) -> list[Sequence]:
    if not sequences or count == 0:
        return []
    indices = np.floor(np.linspace(0, len(sequences) - 1, min(len(sequences), count))).astype(int)
    return [sequences[i] for i in indices]


def donor_windows(target: Sequence, candidates: list[Sequence]) -> list[tuple[int, ...]]:
    """Eligible starts by donor sequence. Each window stays within an original reset."""
    result = []
    for donor in candidates:
        if donor.length < target.length:
            continue
        clock = np.lib.stride_tricks.sliding_window_view(np.asarray(donor.intervals_ns), target.length - 1)
        hits = np.flatnonzero(np.all(np.abs(clock - target.intervals_ns) <= CADENCE_NS, axis=1))
        if len(hits):
            result.append(tuple(int(start) + donor.start for start in hits))
    return result


@dataclass(frozen=True)
class Panel:
    contexts: tuple[Sequence, ...]
    # Entries follow the context order. Values preserve outing and donor-sequence strata.
    donors: tuple[dict[str, list[tuple[int, ...]]], ...]
    support: dict


def build_panel(eligible: dict[str, list[Sequence]]) -> Panel:
    ids = sorted(eligible)
    require(len(ids) == BUDGETS[-1], "budget_calibration_outing_count")
    contexts, donors, coverage = [], [], []
    for outing in ids:
        for target in spread(eligible[outing], a2.CONTEXTS_PER_OUTING):
            windows = {donor: donor_windows(target, eligible[donor]) for donor in ids}
            windows = {donor: found for donor, found in windows.items() if found}
            counts = {
                str(budget): sum(len(starts) for donor in ids[:budget] for starts in windows.get(donor, []))
                for budget in BUDGETS
            }
            common = all(counts.values())
            coverage.append({**target.record(), "windows_by_budget": counts, "common_support": common})
            if common:
                contexts.append(target)
                donors.append(windows)
    support = {
        "eligible_sequences_by_outing": {oid: len(eligible[oid]) for oid in ids},
        "common_contexts_by_outing": {oid: sum(s.outing == oid for s in contexts) for oid in ids},
        "context_coverage": coverage,
    }
    return Panel(tuple(contexts), tuple(donors), support)


def panel_layout(panel: Panel, covariates: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    offsets = np.cumsum([0, *(s.length for s in panel.contexts)])
    conditions = np.concatenate([covariates[s.outing][s.start:s.stop] for s in panel.contexts])
    return conditions, offsets


def training_counts(offsets: dict[str, np.ndarray], outings: tuple[str, ...] | list[str]) -> dict:
    lengths = np.concatenate([np.diff(offsets[oid]) for oid in outings])
    return {"outing_ids": list(outings), "frames": int(lengths.sum()), "sequences": len(lengths),
            "transitions": int(lengths.sum()) - len(lengths), "padded_frames": len(lengths) * int(lengths.max())}


def native_fit_supported(counts: dict) -> bool:
    return counts["frames"] >= 8 and counts["transitions"] > 0 and counts["padded_frames"] <= MAX_PADDED_FRAMES


def nominal_panel(panel: Panel, covariates: dict[str, np.ndarray], offsets: dict[str, np.ndarray]) -> dict:
    """Recheck a2's nominal gates without a model or residual draw."""
    ids = sorted(covariates)
    issues = []
    if any(count < a2.CONTEXTS_PER_OUTING for count in panel.support["eligible_sequences_by_outing"].values()):
        issues.append("a2_context_quota_unavailable")
    if any(count == 0 for count in panel.support["common_contexts_by_outing"].values()):
        issues.append("empty_common_donor_support_for_outing")
    budgets = {}
    for budget in BUDGETS:
        budgets[str(budget)] = training_counts(offsets, ids[:budget])
        if not native_fit_supported(budgets[str(budget)]):
            issues.append(f"budget_{budget}_native_fit_support_or_resource_bound")
    if panel.contexts and DRAWS * len(panel.contexts) * max(s.length for s in panel.contexts) > MAX_SAMPLED_PADDED_FRAMES:
        issues.append("native_sampling_resource_bound")
    result = {"support": panel.support, "budgets": budgets, "feasible_candidates": [], "reasons": issues}
    if issues:
        return result
    values = np.empty((len(a2.CANDIDATES), len(panel.contexts), len(a2.TASKS)))
    reference_peaks = []
    for index, context in enumerate(panel.contexts):
        speed = covariates[context.outing][context.start:context.stop, 0]
        zeros = np.zeros((1, context.length, 21))
        for candidate in range(len(a2.CANDIDATES)):
            nominal = a2.rollout_costs(zeros, speed, context.intervals(), candidate, a2.TASKS)
            values[candidate, index] = nominal["tracking"][0]
            if candidate == a2.DEFAULT:
                reference_peaks.append([float(nominal["peak_acceleration"].max()), float(nominal["peak_jerk"].max())])
    feasible, evidence = a2.feasible_candidates(values, a2.nominal_probes(), [s.outing for s in panel.contexts],
                                                 PROTOCOL["nominal_gate"])
    peaks = np.max(reference_peaks, axis=0)
    if np.any(peaks > NOMINAL_PEAK_LIMIT):
        issues.append("a2_reference_nominal_envelope_failed")
    if np.count_nonzero(feasible) < 2:
        issues.append("fewer_than_two_a2_nominal_candidates")
    return {**result, "nominal": evidence, "reference_nominal_peak_acceleration_and_jerk": peaks.tolist(),
            "feasible_candidates": np.flatnonzero(feasible).tolist()}


def empirical_profiles(panel: Panel, training: dict[str, np.ndarray]) -> np.ndarray:
    """Sample balanced donor outings, sequences and then windows at native clocks."""
    rng = np.random.default_rng(SEED)
    parts = []
    for target, by_outing in zip(panel.contexts, panel.donors):
        eligible = [oid for oid in sorted(training) if oid in by_outing]
        require(bool(eligible), "budget_panel_outside_common_support")
        draws = []
        for _ in range(DRAWS):
            outing = eligible[rng.integers(len(eligible))]
            sequences = by_outing[outing]
            spans = sequences[rng.integers(len(sequences))]
            start = spans[rng.integers(len(spans))]
            draws.append(training[outing][start:start + target.length])
        parts.append(np.stack(draws))
    return np.concatenate(parts, axis=1)


def choose(losses: np.ndarray, feasible: list[int]) -> int:
    best = min(losses[i] for i in feasible)
    order = [a2.DEFAULT] + [i for i in range(len(a2.CANDIDATES)) if i != a2.DEFAULT]
    return next(i for i in order if i in feasible and losses[i] <= best + a2.PROTOCOL["numerical_tie_tolerance"])


def selection_score(profiles: np.ndarray, panel: Panel, conditions: np.ndarray,
                    offsets: np.ndarray, feasible: list[int]) -> dict:
    require(profiles.shape == (DRAWS, len(conditions), 21) and np.isfinite(profiles).all(),
            "budget_expected_finite_draws")
    components = np.empty((2, len(a2.CANDIDATES), len(panel.contexts), len(a2.COMPONENTS)))
    for candidate in range(len(a2.CANDIDATES)):
        for index, context in enumerate(panel.contexts):
            lo, hi = offsets[index:index + 2]
            result = a2.rollout_costs(profiles[:, lo:hi], conditions[lo:hi, 0], context.intervals(), candidate, a2.TASKS)
            for row, count in enumerate((DRAWS, PREFIX)):
                components[row, candidate, index] = [result[k][:count].mean() for k in a2.COMPONENTS]
    ids = np.array([context.outing for context in panel.contexts])
    averages = np.mean([components[:, :, ids == oid].mean(axis=2) for oid in sorted(set(ids))], axis=0)
    full, prefix = (choose(result[:, -1], feasible) for result in averages)
    chosen = {
        "candidate": full, "draws_32_candidate": prefix, "prefix_agrees": full == prefix,
        "component_order": list(a2.COMPONENTS), "candidate_macro_components": averages[0].tolist(),
        "prefix_candidate_macro_components": averages[1].tolist(),
    }
    chosen["runner_up_loss_gap"] = min(averages[0, c, -1] for c in feasible if c != full) - averages[0, full, -1]
    return chosen


def audit_scores(residuals: np.ndarray, speeds: np.ndarray, sequences: list[Sequence], choices: dict) -> dict:
    evaluated = a2.evaluate_held(residuals, speeds, [sequence.record() for sequence in sequences])
    benchmark = evaluated["candidate_mean_metrics"][choices["5"]["empirical"]["candidate"]]["loss"]
    nominal_best = np.asarray(evaluated["nominal_tracking_by_sequence_candidate_task"]).mean(axis=(0, 2))
    comparisons = {}
    for budget, panels in choices.items():
        metrics = {}
        for method, selection in panels.items():
            candidate = selection["candidate"]
            observed = evaluated["candidate_mean_metrics"][candidate]
            nominal_peaks = np.asarray(evaluated["nominal_peaks_by_sequence_candidate"])[:, candidate]
            metrics[method] = {
                "candidate": candidate, "observed": observed, "loss_minus_full_empirical": observed["loss"] - benchmark,
                "within_descriptive_band": observed["loss"] <= benchmark * (1 + PROTOCOL["descriptive_margin"]),
                "nominal_tracking_exceeds_allowance": bool(nominal_best[candidate] > nominal_best.min() * (1 + PROTOCOL["nominal_gate"]) + 1e-12),
                "nominal_envelope_violating_sequences": int(np.count_nonzero(np.any(nominal_peaks > NOMINAL_PEAK_LIMIT, axis=1))),
            }
        comparisons[budget] = {
            "methods": metrics,
            "ar_minus_equal_budget_empirical": metrics["one_state_ar"]["observed"]["loss"] - metrics["empirical"]["observed"]["loss"],
        }
    return {"reference_full_empirical_loss": benchmark, "comparisons": comparisons, "fixed_grid_audit": evaluated}
