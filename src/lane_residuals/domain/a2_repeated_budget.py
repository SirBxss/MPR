"""Metadata design of a paired whole-outing calibration budget comparison."""

from collections import Counter
from itertools import combinations

from . import a2_budget_pilot as pilot, a2_rate_design as rate
from .artifact_registry import require

REVISION = "a2-repeated-rate-budget-support-v1"
CANDIDATES = (1, 2, 3, 4, 5, 6)
CONFIGS = rate.CONFIGS + rate.UPPER_CONFIGS
PROTOCOL = {
    "budgets": list(pilot.BUDGETS),
    "arms": list(pilot.ARMS),
    "candidate_indices": list(CANDIDATES),
    "rate_weights": [CONFIGS[i].weight_curvature_rate for i in CANDIDATES],
    "subset_rule": "all_whole_outing_subsets_in_sorted_order_for_each_budget",
    "panel_rule": "intersection_of_all_subset_donor_support_on_pinned_pr60_contexts",
    "cadence_tolerance_ns": pilot.CADENCE_NS,
    "minimum_contexts_per_outing": 1,
    "nominal_tracking_anchor": rate.PROTOCOL["tracking_reference"],
    "nominal_tracking_allowance": rate.PROTOCOL["tracking_allowance"],
    "nominal_peak_limits": rate.PROTOCOL["nominal_peak_limits"],
    "nominal_passive_probe_fraction": rate.PROTOCOL["passive_probe_tracking_fraction"],
    "sampling_resource_check_draws": pilot.DRAWS,
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
    subsets = []
    common_indices = set(range(len(panel.contexts)))
    for budget in pilot.BUDGETS:
        for subset in combinations(outings, budget):
            counts = [sum(row[outing] for outing in subset) for row in windows]
            supported = [i for i, count in enumerate(counts) if count]
            common_indices.intersection_update(supported)
            training = pilot.training_counts(offsets, subset)
            subsets.append({
                "budget": budget, **training,
                "native_fit_resources_supported": pilot.native_fit_supported(training),
                "supported_context_count": len(supported), "windows_by_context": counts,
            })
    indices = sorted(common_indices)
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
        "padded_sample_frames": padded_sample_frames, "reasons": reasons,
    }
    return pilot.Panel(contexts, donors, support), support
