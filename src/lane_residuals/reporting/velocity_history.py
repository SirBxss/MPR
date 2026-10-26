"""Python plots with explicit hypothesis and local-support labels."""
from pathlib import Path

from ..domain.velocity_timing import TOPICS


def plot(output, screens, report):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    start = int(report["window_start_log_ns"])
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    for column, topic in enumerate(TOPICS):
        rows = [r for r in screens if r["topic"] == topic]
        x = [(int(r["edp_log_ns"])-start)/1e9 for r in rows]
        ax = axes[0, column]
        for key, label, color in [("approved_latest_log_source_age_ns", "Approved latest log ≤ EDP", "#bd4d38"),
            ("source_age_ns", "Post hoc latest log < EDP", "#23866c")]:
            points = [(t, int(r[key])/1e6) for t, r in zip(x, rows) if r[key] is not None]
            ax.scatter([p[0] for p in points], [p[1] for p in points], s=14, label=label, color=color)
        ax.axhline(0, color="#555555", linewidth=1)
        ax.set_title(topic.rsplit("/", 1)[-1], fontsize=11)
        ax.set_ylabel("EDP source − update source (ms)")
        ax.legend(fontsize=8)
        ax = axes[1, column]
        for i, (key, label, color) in enumerate([("original_local_complete", "Original complete", "#526b87"),
            ("approved_latest_log_hypothetical_complete", "Approved latest ≤ log", "#bd4d38"),
            ("local_hypothetical_complete", "Post hoc strict < log", "#23866c")]):
            ax.scatter(x, [i]*len(rows), s=7, color="#e0e5e8", marker="s")
            ax.scatter([t for t, r in zip(x, rows) if r[key]], [i]*sum(bool(r[key]) for r in rows), s=20, color=color, marker="s")
        ax.set_yticks(range(3), ["Original complete", "Approved latest ≤ log", "Post hoc strict < log"])
        ax.invert_yaxis()
        for ax in axes[:, column]:
            ax.set_xlabel("Recorded log seconds from fixed window start")
            ax.grid(axis="x", alpha=.2)
    fig.suptitle("Cached history hypothesis — one fixed development window\nPost hoc; no adopted speed feature, training dataset or physical-availability proof", fontsize=13)
    output = Path(output)
    fig.savefig(output/"history_comparison.png", dpi=160)
    fig.savefig(output/"history_comparison.pdf")
    plt.close(fig)
