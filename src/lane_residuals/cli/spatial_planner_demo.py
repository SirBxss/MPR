"""Run the spatial planner benchmark with generated training and replay data."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from ..domain.reference_planner import ReferencePlannerConfig
from ..domain.spatial_planner_response import (
    STATIONS_M,
    SpatialPlannerScenario,
    build_spatial_response,
)
from ..modeling.matched_flow import MatchedFlow, fit_matched_flow
from ..modeling.matched_gaussian import MatchedGaussian, fit_matched_gaussian
from ..workflows.spatial_planner_benchmark import benchmark_spatial_profiles, draw_spatial_profiles


SYNTHETIC_SEED = 20261106
DRAW_COUNT = 128


def _fixture(seed: int, count: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    s = np.asarray(STATIONS_M) / 100.0
    offset = rng.normal(0, 0.10, (count, 1))
    heading = rng.normal(0, 0.18, (count, 1))
    bend = rng.standard_t(4, (count, 1)) * 0.12
    return offset + heading * s + bend * s**2 + rng.normal(0, 0.02, (count, len(s)))


def run_demo() -> dict:
    """Fit and restore synthetic states via the native Gaussian and flow APIs."""
    training = _fixture(SYNTHETIC_SEED, 512)
    replay = _fixture(SYNTHETIC_SEED + 1, 96)
    conditions = np.zeros((len(training), 6))
    gaussian = fit_matched_gaussian(training, conditions, mode="unconditional_gaussian")
    base = fit_matched_gaussian(training, conditions, mode="conditional_gaussian")
    block = SimpleNamespace(
        outing_id="synthetic_training",
        x=conditions,
        y=training,
        offsets=np.arange(len(training) + 1),
    )
    flow, fit = fit_matched_flow(base, [block], mode="unconditional", seed=SYNTHETIC_SEED + 2)
    gaussian = MatchedGaussian.from_dict(gaussian.to_dict())
    flow = MatchedFlow.from_dict(flow.to_dict())
    rng = np.random.default_rng(SYNTHETIC_SEED + 3)
    rng_gaussian = np.random.default_rng(SYNTHETIC_SEED + 4)
    physical_scale = gaussian.residual_scale
    diagonal_std = np.sqrt(np.diag(gaussian.covariance)) * physical_scale
    physical_mean = gaussian.predict_mean(np.zeros((1, 6)))[0]
    draws = {
        "empirical": training[rng.integers(len(training), size=DRAW_COUNT)],
        "diagonal_gaussian": physical_mean + rng_gaussian.standard_normal((DRAW_COUNT, 21)) * diagonal_std,
        "full_gaussian": draw_spatial_profiles(gaussian, sample_count=DRAW_COUNT, seed=SYNTHETIC_SEED + 4),
        "unconditional_flow": draw_spatial_profiles(flow, sample_count=DRAW_COUNT, seed=SYNTHETIC_SEED + 4),
    }
    config = ReferencePlannerConfig()
    scenarios = []
    for speed in (15.0, 25.0):
        scenario = SpatialPlannerScenario(speed_mps=speed, dt_s=0.1)
        response = build_spatial_response(scenario, config)
        scenarios.append({
            "inputs": asdict(scenario),
            "lookahead_m": float(response.distances_m[-1]),
            "first_curvature_gain_by_station_per_m2": response.curvature_response[:, 0].tolist(),
            "benchmark": benchmark_spatial_profiles(response, replay, draws),
        })
    return {
        "scope": "synthetic_single_plan_engineering_fixture",
        "seed": SYNTHETIC_SEED,
        "stations_m": list(STATIONS_M),
        "training_profiles": len(training),
        "flow_epochs": fit["epochs_completed"],
        "flow_solver": "heun",
        "flow_steps": 128,
        "planner": asdict(config),
        "scenarios": scenarios,
    }


def _plot(report: dict, path: Path) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(8.5, 4.6), layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots()
    for case in report["scenarios"]:
        speed = case["inputs"]["speed_mps"]
        axes.plot(report["stations_m"], case["first_curvature_gain_by_station_per_m2"],
                  marker="o", markersize=3, label=f"{speed:g} m/s")
    axes.axhline(0, color="#888888", lw=0.8)
    axes.set(title="First planner command sensitivity to spatial disagreement",
             xlabel="Residual station (m)", ylabel="Curvature change per metre of residual (1/m²)")
    axes.grid(alpha=0.25)
    axes.legend(frameon=False)
    figure.supxlabel("Synthetic geometry and motion. One fixed planner solve per input.", fontsize=9)
    figure.savefig(path, dpi=150)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory for the synthetic report")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    report = run_demo()
    (args.output / "synthetic_spatial_planner.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8",
    )
    _plot(report, args.output / "synthetic_spatial_sensitivity.png")
    print(f"Synthetic spatial planner benchmark complete: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
