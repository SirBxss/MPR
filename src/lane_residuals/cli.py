"""Command-line entry point for the first real-MCAP MPR experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np

from .gaussian import fit_gaussian_residual_model
from .mcap_io import McapDependencyError
from .plotting import (
    plot_gaussian_residual_model,
    plot_lane_association_audit,
    plot_mcap_dataset_diagnostics,
)
from .preprocessing import (
    DEFAULT_AUDIT_HORIZONS,
    DEFAULT_ESTIMATE_TOPIC,
    DEFAULT_REFERENCE_TOPIC,
    FrameRejection,
    build_residual_dataset_from_mcap,
    save_residual_dataset,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Decode map- and sensor-based road topics, audit lane association "
            "and horizon coverage, calculate residuals, and optionally fit a "
            "descriptive Gaussian."
        )
    )
    parser.add_argument("mcap_file", type=Path)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs") / "mcap_v032",
    )
    parser.add_argument(
        "--reference-topic",
        default=DEFAULT_REFERENCE_TOPIC,
    )
    parser.add_argument(
        "--estimate-topic",
        default=DEFAULT_ESTIMATE_TOPIC,
    )
    parser.add_argument("--station-start", type=float, default=0.0)
    parser.add_argument("--station-stop", type=float, default=50.0)
    parser.add_argument("--station-step", type=float, default=5.0)
    parser.add_argument("--max-samples", type=int, default=100)
    parser.add_argument("--max-time-delta-ms", type=float, default=50.0)
    parser.add_argument(
        "--time-basis",
        choices=("log", "source"),
        default="source",
        help="Timestamp used for pairing; source time is the v0.3.2 default.",
    )
    parser.add_argument(
        "--audit-horizons",
        type=float,
        nargs="+",
        default=list(DEFAULT_AUDIT_HORIZONS),
        metavar="M",
        help="Forward horizons used for geometric coverage counts.",
    )
    parser.add_argument(
        "--association-examples",
        type=int,
        default=6,
        help="Maximum labelled candidate-pair panels to retain.",
    )
    parser.add_argument(
        "--max-projection-distance-m",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--max-absolute-residual-m",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--regularization",
        type=float,
        default=1e-6,
        help="Gaussian diagonal covariance regularization in m^2.",
    )
    parser.add_argument(
        "--fit-gaussian",
        action="store_true",
        help=(
            "Opt in to the descriptive Gaussian only after lane association "
            "has been inspected. The v0.3.2 audit does not fit it by default."
        ),
    )
    parser.add_argument(
        "--assume-same-frame",
        action="store_true",
        help=(
            "Confirm that both selected road topics use the same local "
            "coordinate frame. Processing is blocked without this confirmation."
        ),
    )
    return parser


def _stations(start: float, stop: float, step: float) -> np.ndarray:
    if not all(np.isfinite(value) for value in (start, stop, step)):
        raise ValueError("station values must be finite")
    if step <= 0.0 or stop < start:
        raise ValueError("station step must be positive and stop must be >= start")
    stations = np.arange(start, stop + 0.5 * step, step, dtype=np.float64)
    if stations[-1] > stop + 1e-9:
        stations = stations[:-1]
    if len(stations) == 0:
        raise ValueError("station configuration produces no stations")
    return stations


def main(argv: Sequence[str] | None = None) -> int:
    """Run the v0.3.2 MCAP lane-association and residual checkpoint."""

    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        stations = _stations(
            arguments.station_start,
            arguments.station_stop,
            arguments.station_step,
        )
        dataset = build_residual_dataset_from_mcap(
            arguments.mcap_file,
            assume_same_frame=arguments.assume_same_frame,
            reference_topic=arguments.reference_topic,
            estimate_topic=arguments.estimate_topic,
            stations=stations,
            max_delta_ms=arguments.max_time_delta_ms,
            time_basis=arguments.time_basis,
            max_samples=arguments.max_samples,
            max_projection_distance_m=arguments.max_projection_distance_m,
            max_absolute_residual_m=arguments.max_absolute_residual_m,
            audit_horizons_m=arguments.audit_horizons,
            n_association_examples=arguments.association_examples,
        )
    except (FileNotFoundError, ValueError, FrameRejection, McapDependencyError) as error:
        parser.exit(2, f"error: {error}\n")

    output_directory = arguments.output_directory
    output_directory.mkdir(parents=True, exist_ok=True)
    written = save_residual_dataset(dataset, output_directory)

    diagnostics, _ = plot_mcap_dataset_diagnostics(dataset)
    diagnostics_path = output_directory / "mcap_diagnostics.png"
    diagnostics.savefig(diagnostics_path, dpi=160)
    plt.close(diagnostics)
    written["diagnostics"] = diagnostics_path

    if dataset.association_examples:
        association_figure, _ = plot_lane_association_audit(dataset)
        association_path = output_directory / "lane_association_audit.png"
        association_figure.savefig(association_path, dpi=160)
        plt.close(association_figure)
        written["lane_association_audit"] = association_path

    model_summary: dict[str, object] | None = None
    if arguments.fit_gaussian and len(dataset.residuals) >= 2:
        model = fit_gaussian_residual_model(
            dataset.residuals,
            regularization=arguments.regularization,
        )
        model_path = output_directory / "gaussian_model.npz"
        np.savez_compressed(
            model_path,
            mean=model.mean,
            covariance=model.covariance,
            n_training_samples=np.asarray(model.n_training_samples),
            regularization=np.asarray(model.regularization),
        )
        gaussian_figure, _ = plot_gaussian_residual_model(
            model,
            dataset.stations,
            observed_residuals=dataset.residuals,
        )
        gaussian_path = output_directory / "gaussian_diagnostics.png"
        gaussian_figure.savefig(gaussian_path, dpi=160)
        plt.close(gaussian_figure)
        written["gaussian_model"] = model_path
        written["gaussian_diagnostics"] = gaussian_path

        model_summary = {
            "fit_interpretation": (
                "descriptive in-sample fit only; this is not held-out evaluation"
            ),
            "n_training_samples": model.n_training_samples,
            "dimension": model.dimension,
            "regularization_m2": model.regularization,
            "in_sample_negative_log_likelihood": model.negative_log_likelihood(
                dataset.residuals
            ),
        }
        model_summary_path = output_directory / "gaussian_summary.json"
        with model_summary_path.open("w", encoding="utf-8") as stream:
            json.dump(model_summary, stream, indent=2)
            stream.write("\n")
        written["gaussian_summary"] = model_summary_path
    elif arguments.fit_gaussian:
        print(
            "Gaussian not fitted: at least two accepted residual vectors are required."
        )

    print(json.dumps(dataset.report.to_dict(), indent=2))
    if model_summary is not None:
        print(json.dumps(model_summary, indent=2))
    print("Written files:")
    for name, path in written.items():
        print(f"  {name}: {path}")
    print(
        "Interpretation: sensor-based versus map-based discrepancy; "
        "the map topic is not confirmed ground truth."
    )
    print(
        "Confidentiality: derived files and figures remain local under outputs/."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
