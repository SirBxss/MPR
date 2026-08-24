"""v0.15.1 one-state conditional-AR ablation on the frozen model protocol."""

from __future__ import annotations

import argparse
from typing import Any

from .expanded_aiohmm import (
    ExpandedAutoregressiveExperiment,
    _run_expanded_autoregressive,
)

VERSION = "0.15.1"

EXPERIMENT = ExpandedAutoregressiveExperiment(
    version=VERSION,
    output_prefix="one_state_ar",
    expected_state_count=1,
    purpose="one_state_conditional_autoregressive_gaussian_ablation",
    fold_models_purpose="v0151_clean_group_fold_one_state_ar_models",
    state_count_rationale=(
        "predeclared_one_state_ablation_to_isolate_autoregression_from_latent_switching"
    ),
    plot_subtitle=(
        "One-state conditional AR ablation; no latent state switching is present"
    ),
    candidate_label="one_state_ar",
    comparison_key="one_state_ar_minus_conditional_gaussian_primary_macro_deltas",
    next_phase=(
        "compare_v0151_with_v014_and_v015_before_any_new_model_family_or_feature_expansion"
    ),
    scientific_limitations=(
        (
            "The four clean technical groups are separated portions of one "
            "longer same-day outing, not four independent journeys."
        ),
        "Leave-one-group-out results do not estimate journey-level generalization.",
        (
            "One state is a diagnostic ablation of the v0.15 emission equation, "
            "not a newly tuned thesis model family."
        ),
        (
            "Observed-history joint density and free-running generation are both "
            "valid but answer different questions."
        ),
        (
            "RLMB remains a pseudo-reference and independence from the EDP "
            "topology source is unknown."
        ),
        "Sample metrics retain finite Monte Carlo error under the recorded seed.",
    ),
    requires_two_state_reference=True,
)


def run_expanded_ar_ablation(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], int]:
    """Compare one-state AR with the frozen Gaussian and two-state results."""

    return _run_expanded_autoregressive(arguments, experiment=EXPERIMENT)


__all__ = ["EXPERIMENT", "VERSION", "run_expanded_ar_ablation"]
