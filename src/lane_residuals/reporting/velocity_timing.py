"""Matplotlib figures for the fixed local diagnostic; no generated imagery."""
from pathlib import Path

from ..domain.velocity_timing import TOPICS


def plot(output, records, screens, report):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    output = Path(output)
    start = int(report["window_start_log_ns"])
    end = int(report["window_end_log_ns"])
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), constrained_layout=True)
    for i, topic in enumerate(TOPICS):
        selected = [r for r in records if r["topic"] == topic and r["value"] is not None and start <= int(r["log_ns"]) < end]
        axes[i].scatter([(int(r["log_ns"])-start)/1e9 for r in selected], [r["value"] for r in selected], s=8)
        axes[i].set_title(topic, fontsize=10)
        axes[i].set_ylabel("Native value\n(semantics unadopted)")
    rows = [r for r in screens if r["topic"] == TOPICS[0] and r["old_speed_mps"] is not None]
    axes[2].scatter([(int(r["edp_log_ns"])-start)/1e9 for r in rows], [r["old_speed_mps"] for r in rows], s=10, color="#555555")
    axes[2].set_title("Accepted old speed — only originally complete frames", fontsize=10)
    axes[2].set_ylabel("Old speed (m/s)")
    for ax in axes:
        ax.grid(alpha=.2)
        ax.set_xlim(0, (end-start)/1e9)
        ax.set_xlabel("Recorded log time from fixed window start (s)")
    fig.suptitle("Local velocity observations — no feature adoption or physical availability claim", fontsize=12)
    fig.savefig(output/"01_velocity_observations.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), constrained_layout=True)
    for i, topic in enumerate(TOPICS):
        rows = [r for r in screens if r["topic"] == topic]
        x = [(int(r["edp_log_ns"])-start)/1e9 for r in rows]
        axes[0].scatter(x, [i+int(r["local_hypothetical_complete"])*.3 for r in rows], s=15,
            label=topic.rsplit("/", 1)[-1]+" (raised = screen met)")
    old = [r for r in screens if r["topic"] == TOPICS[0]]
    axes[0].scatter([(int(r["edp_log_ns"])-start)/1e9 for r in old], [2+int(r["old_complete"])*.3 for r in old],
        s=15, color="#555555", label="Original complete mask")
    axes[0].set_yticks([])
    axes[0].legend(fontsize=8, loc="upper right")
    axes[0].set_xlabel("Recorded log time from fixed window start (s)")
    labels, spans = ["Original"], [report["analysis"]["local_original_complete"]["maximum_span_s"]]
    for topic in TOPICS:
        labels.append(topic.rsplit("/", 1)[-1]+"\nhypothetical screen")
        spans.append(report["analysis"]["topics"][topic]["local_hypothetical_complete_under_screen"]["maximum_span_s"])
    axes[1].bar(labels, spans, color=["#555555", "#247ba0", "#e39b30"])
    for i, span in enumerate(spans):
        axes[1].annotate(f"{span:.2f}", (i, span), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=9)
    axes[1].set_ylabel("Maximum local sequence span (s)")
    axes[1].grid(axis="y", alpha=.2)
    fig.suptitle("Fixed 100 ms recorded-clock screen — exploratory, local, unadopted", fontsize=12)
    fig.savefig(output/"02_local_support_screen.png", dpi=160)
    plt.close(fig)
