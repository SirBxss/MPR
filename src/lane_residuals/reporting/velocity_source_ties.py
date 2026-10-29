"""Matplotlib figures for paired source ties, preserving clock qualifications."""
from pathlib import Path

from ..domain.velocity_timing import TOPICS


def plot(output, screens, report):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    start = int(report["window_start_log_ns"])
    selections = (
        ("original_complete", "Original complete", "original_local_complete", "#60758c"),
        ("approved_latest_log", "Prior pilot: log ≤ EDP", "approved_latest_log_hypothetical_complete", "#bb614b"),
        ("primary_source_at_or_before", "Primary: log < EDP, source ≤ EDP", "local_hypothetical_complete", "#23866c"),
        ("secondary_source_strictly_before", "Secondary: same update, source < EDP", "strict_source_local_hypothetical_complete", "#8662a1"),
    )
    fig, axes = plt.subplots(3, 2, figsize=(14, 10), constrained_layout=True)
    for column, topic in enumerate(TOPICS):
        rows = [r for r in screens if r["topic"] == topic]
        x = [(int(r["edp_log_ns"])-start)/1e9 for r in rows]
        ax = axes[0, column]
        for equal, label, color in ((False, "Selected source differs", "#23866c"), (True, "Selected source equals EDP", "#8662a1")):
            points = [(t, int(r["source_age_ns"])/1e6) for t, r in zip(x, rows)
                if r["source_age_ns"] is not None and r["selected_source_time_equal_to_edp"] == equal]
            ax.scatter([p[0] for p in points], [p[1] for p in points], s=14, label=label, color=color)
        ax.axhline(0, color="#555555", linewidth=.8)
        ax.set_title(topic.rsplit("/", 1)[-1], fontsize=11)
        ax.set_ylabel("EDP source − selected source (ms)")
        ax.legend(fontsize=8)
        ax = axes[1, column]
        for i, (_, label, key, color) in enumerate(selections):
            ax.scatter(x, [i]*len(rows), s=8, color="#dfe4e8", marker="s")
            retained = [t for t, r in zip(x, rows) if r[key]]
            ax.scatter(retained, [i]*len(retained), s=18, color=color, marker="s")
        ax.set_yticks(range(len(selections)), [s[1] for s in selections], fontsize=9)
        ax.invert_yaxis()
        for ax in axes[:2, column]:
            ax.set_xlabel("Recorded log seconds from fixed window start")
            ax.grid(axis="x", alpha=.2)
        ax = axes[2, column]
        for i, (key, label, _, color) in enumerate(selections):
            stat = next(s for s in report["support_comparison"] if s["selection"] == key and s["topic"] in ("both", topic))
            span = stat["maximum_span_s"]
            ax.barh(i, span, color=color)
            ax.text(span+.1, i, f'{span:.2f}s · {stat["frames"]} frames / {stat["sequences"]} runs', va="center", fontsize=8)
        ax.set_yticks(range(len(selections)), [s[1] for s in selections], fontsize=9)
        ax.invert_yaxis()
        maximum = max(s["maximum_span_s"] for s in report["support_comparison"])
        ax.set_xlim(0, max(1, maximum*1.5))
        ax.set_xlabel("Longest uninterrupted EDP source-time span (s)")
        ax.grid(axis="x", alpha=.2)
    fig.suptitle("Source-tie sensitivity — one cached development window\nSame selected update · Post hoc · Recorded clocks; no producer or availability proof", fontsize=13)
    output = Path(output)
    fig.savefig(output/"source_tie_comparison.png", dpi=160)
    fig.savefig(output/"source_tie_comparison.pdf")
    plt.close(fig)
