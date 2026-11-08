"""Compare distributions of fixed planner responses to single profiles."""

import numpy as np
from numpy.typing import NDArray

from ..domain.spatial_planner_response import STATIONS_M, SpatialPlannerResponse
from ..modeling.matched_flow import MatchedFlow, sample_matched_flow
from ..modeling.matched_gaussian import MatchedGaussian


def draw_spatial_profiles(
    model: MatchedGaussian | MatchedFlow, *, sample_count: int, seed: int
) -> NDArray[np.float64]:
    """Use an unconditional native sampler in physical metres without history."""
    conditions = np.zeros((1, 6))
    if isinstance(model, MatchedGaussian) and model.mode == "unconditional_gaussian":
        return model.sample(conditions, sample_count=sample_count, seed=seed)[:, 0]
    if isinstance(model, MatchedFlow) and model.mode == "unconditional":
        return sample_matched_flow(
            model, conditions, np.array([0, 1]), sample_count=sample_count,
            seed=seed, steps=128, solver="heun",
        )[:, 0]
    raise ValueError("this spatial benchmark requires an unconditional matched state")


def _crps(draws: NDArray[np.float64], observed: NDArray[np.float64]) -> float:
    """Mean scalar CRPS of a discrete sample law on separate replay targets."""
    ordered = np.sort(draws)
    count = len(ordered)
    splits = np.arange(1, count)
    # Each adjacent gap occurs in every pair that straddles that gap.
    half_pair_distance = float(np.diff(ordered) @ (splits * (count - splits))) / count**2
    return float(np.mean(np.abs(ordered[:, None] - observed)) - half_pair_distance)


def _summary(values: NDArray[np.float64]) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "p95_absolute": float(np.quantile(np.abs(values), 0.95)),
    }


def benchmark_spatial_profiles(
    response: SpatialPlannerResponse,
    replay_profiles_m: NDArray[np.float64],
    sampled_arms: dict[str, NDArray[np.float64]],
) -> dict:
    """Compare sampled and recorded planner outcomes within one fixed scenario.

    Callers establish outing, row and model provenance separately. The sample
    ensemble for each arm is shared across the replay observations of this
    fixed scenario, as appropriate for unconditional spatial distributions.
    """
    replay = np.asarray(replay_profiles_m, dtype=np.float64)
    if replay.ndim != 2 or not len(replay):
        raise ValueError("replay profiles require a nonempty two dimensional array")
    if not sampled_arms or {"nominal", "replay"} & sampled_arms.keys():
        raise ValueError("sampled arm names must be distinct from the control names")
    arrays = {name: np.asarray(value, dtype=np.float64) for name, value in sampled_arms.items()}
    if any(value.ndim != 2 or len(value) < 4 for value in arrays.values()):
        raise ValueError("each sampled arm requires at least four profiles")
    draw_counts = {len(value) for value in arrays.values()}
    if len(draw_counts) != 1:
        raise ValueError("sampled arms require a common draw count")

    observed = response.evaluate(replay)
    nominal = np.zeros((1, len(STATIONS_M)))
    results = {
        "replay": {metric: _summary(values) for metric, values in observed.items()},
    }
    for name, profiles in {"nominal": nominal, **arrays}.items():
        results[name] = {
            metric: {**_summary(values), "crps_vs_replay": _crps(values, observed[metric])}
            for metric, values in response.evaluate(profiles).items()
        }
    return {
        "replay_count": len(replay),
        "draws_per_sampled_arm": draw_counts.pop(),
        "arms": results,
    }
