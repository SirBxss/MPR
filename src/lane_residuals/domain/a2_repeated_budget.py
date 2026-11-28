"""Metadata design of a paired whole-outing calibration budget comparison."""

from collections import Counter
from itertools import combinations

from . import a2_budget_pilot as pilot, a2_rate_design as rate
from .artifact_registry import require

REVISION = "a2-repeated-rate-budget-support-v2"
PROTOCOL = {
    "budgets": list(pilot.BUDGETS),
    "arms": list(pilot.ARMS),
    "candidate_rule": "feasible_rate_indices_from_pinned_and_replayed_upper_design",
    "subset_rule": "all_whole_outing_subsets_in_sorted_order_for_each_budget",
    "panel_rule": "intersection_of_all_subset_donor_support_on_pinned_pr60_contexts",
    "cadence_tolerance_ns": pilot.CADENCE_NS,
    "minimum_contexts_per_outing": 1,
    "nominal_tracking_anchor": "original_nine_curvature_grid_best_per_outing_on_common_panel",
    "nominal_tracking_allowance": rate.PROTOCOL["tracking_allowance"],
    "nominal_peak_limits": rate.PROTOCOL["nominal_peak_limits"],
    "nominal_passive_probe_fraction": rate.PROTOCOL["passive_probe_tracking_fraction"],
    "empirical_self_donation": "permitted_with_exact_replay_exposure_reported",
    "sampling_resource_check_draws": pilot.DRAWS,
}


def _self_windows(context: pilot.Sequence, donors: dict) -> int:
    """The only exact self window of this whole sequence starts at its original first row."""
    return sum(context.start in starts for starts in donors.get(context.outing, []))


def _length_histograms(contexts: tuple[pilot.Sequence, ...], outings: list[str]) -> dict:
    by_outing = {oid: Counter() for oid in outings}
    for context in contexts:
        by_outing[context.outing][str(context.length)] += 1
    return {oid: dict(counts) for oid, counts in by_outing.items()}


def _self_exposure(counts: list[int], exact: list[int]) -> dict:
    total = sum(counts)
    eligible = sum(exact)
    return {
        "eligible_self_windows": eligible, "total_eligible_windows": total,
        "share_of_eligible_windows": eligible / total if total else None,
        "self_only_context_count": sum(count == n == 1 for count, n in zip(counts, exact)),
    }


def support_panel(panel: pilot.Panel, offsets: dict) -> tuple[pilot.Panel, dict]:
    """Enumerate support without sampling or reading labels."""
    outings = sorted(offsets)
    require(len(outings) == pilot.BUDGETS[-1] and len(panel.contexts) == len(panel.donors)
            and {context.outing for context in panel.contexts} == set(outings),
            "repeated_budget_calibration_panel")
    windows = [
        {outing: sum(map(len, donors.get(outing, []))) for outing in outings}
        for donors in panel.donors
    ]
    self_windows = [_self_windows(context, donors) for context, donors in zip(panel.contexts, panel.donors)]
    require(all(count <= 1 for count in self_windows), "repeated_budget_duplicate_self_window")
    subsets = []
    common_indices = set(range(len(panel.contexts)))
    for budget in pilot.BUDGETS:
        for subset in combinations(outings, budget):
            counts = [sum(row[outing] for outing in subset) for row in windows]
            self_counts = [n if context.outing in subset else 0 for context, n in zip(panel.contexts, self_windows)]
            supported = [i for i, count in enumerate(counts) if count]
            common_indices.intersection_update(supported)
            training = pilot.training_counts(offsets, subset)
            subsets.append({
                "budget": budget, **training,
                "native_fit_resources_supported": pilot.native_fit_supported(training),
                "supported_context_count": len(supported), "windows_by_context": counts,
                "parent_panel_self_donation": _self_exposure(counts, self_counts),
            })
    indices = sorted(common_indices)
    for subset in subsets:
        counts = [subset["windows_by_context"][i] for i in indices]
        exact = [self_windows[i] if panel.contexts[i].outing in subset["outing_ids"] else 0 for i in indices]
        subset["common_panel_self_donation"] = _self_exposure(counts, exact)
    contexts = tuple(panel.contexts[i] for i in indices)
    donors = tuple(panel.donors[i] for i in indices)
    by_outing = Counter(context.outing for context in contexts)
    counts = {outing: by_outing[outing] for outing in outings}
    reasons = []
    if any(count < PROTOCOL["minimum_contexts_per_outing"] for count in counts.values()):
        reasons.append("missing_common_contexts_for_calibration_outing")
    if any(not row["native_fit_resources_supported"] for row in subsets):
        reasons.append("subset_native_fit_support_or_resource_bound")
    padded_sample_frames = pilot.DRAWS * len(contexts) * max((s.length for s in contexts), default=0)
    if padded_sample_frames > pilot.MAX_SAMPLED_PADDED_FRAMES:
        reasons.append("common_panel_native_sampling_resource_bound")
    support = {
        "parent_context_count": len(panel.contexts), "common_context_count": len(contexts),
        "common_context_indices": indices, "common_contexts_by_outing": counts,
        "common_contexts": [context.record() for context in contexts],
        "subsets": subsets, "per_context_donor_windows_by_outing": windows,
        "exact_replay_by_parent_context": [
            {"own_outing_self_window_present": bool(n),
             "own_outing_support_self_only": n == row[context.outing] == 1}
            for context, n, row in zip(panel.contexts, self_windows, windows)
        ],
        "parent_frame_length_histograms_by_outing": _length_histograms(panel.contexts, outings),
        "common_frame_length_histograms_by_outing": _length_histograms(contexts, outings),
        "padded_sample_frames": padded_sample_frames, "reasons": reasons,
    }
    return pilot.Panel(contexts, donors, support), support
