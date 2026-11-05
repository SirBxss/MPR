"""Reproducible Python comparison, one point per held out outing."""
from pathlib import Path

import numpy as np


def plot_comparison(rows: list[dict], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = sorted({r["model"] for r in rows})
    keys = ("mean_normalized_sequence_energy_score_m", "mean_marginal_crps_m", "median_absolute_lag_one_correlation_error")
    labels = ("Sequence energy score [m]", "Marginal CRPS [m]", "Lag one correlation error")
    with plt.rc_context({"font.size": 10}):
        fig, axes = plt.subplots(1, 3, figsize=(16, 7), layout="constrained")
        try:
            for ax, key, label in zip(axes, keys, labels):
                for i, name in enumerate(names):
                    values = [r["metrics"][key] for r in rows if r["model"] == name and r["metrics"][key] is not None]
                    if values:
                        ax.scatter(i+np.linspace(-.12, .12, len(values)), values, alpha=.65, s=24)
                        ax.scatter([i], [np.mean(values)], marker="D", color="black", s=40)
                ax.set_xticks(range(len(names)), [n.replace("_", " ") for n in names], rotation=55, ha="right")
                ax.set_ylabel(label)
                ax.grid(axis="y", alpha=.25)
                ax.set_title("Lower is better")
            fig.suptitle("Matched development comparison\nPoints: outings. Black diamonds: equal outing means. Short temporal support only.")
            fig.savefig(path, dpi=160)
        finally:
            plt.close(fig)
