"""Fixed Matplotlib panels; original support, never counterfactual recovery."""
from pathlib import Path


def plot(output, report):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    outings = report["outings"]
    x = list(range(len(outings)))
    labels = [o["outing_id"]+(" *" if o["previously_examined_case"] else "") for o in outings]
    fig, axes = plt.subplots(3, 1, figsize=(12, 11), constrained_layout=True)
    bottom = [0]*len(outings)
    for key, label, color in (("original_matched_complete_rows", "Original matched complete", "#23866c"),
            ("geometry_with_only_future_source_speed_failure", "Geometry ready; only future-speed failure", "#bb614b"),
            ("other_rows", "Other retained candidates", "#9aa6b2")):
        values = [o[key] for o in outings]
        axes[0].bar(x, values, bottom=bottom, label=label, color=color)
        bottom = [a+b for a, b in zip(bottom, values)]
    axes[0].set_ylabel("Original retained candidate rows")
    axes[0].legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1))
    bottom = [0]*len(outings)
    for key, label, color in (("complete_equal", "Complete + endpoint equality", "#23866c"),
            ("incomplete_unequal", "Incomplete + endpoint inequality", "#60758c"),
            ("complete_unequal", "Complete without equality", "#c39735"),
            ("incomplete_equal", "Incomplete despite equality", "#8662a1"),
            (None, "Bracket not assessable", "#b6b6b6")):
        values = [o["stratum_assessable_complete_endpoint_table"][key] if key else sum(o["stratum_not_assessable_counts"].values()) for o in outings]
        axes[1].bar(x, values, bottom=bottom, label=label, color=color)
        bottom = [a+b for a,b in zip(bottom, values)]
    axes[1].set_ylabel("Geometry ready; no declared\nestimate-feature failure")
    axes[1].legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1))
    if all(o["stratum_assessable_complete_endpoint_table"][k] == 0
           for o in outings for k in ("complete_unequal", "incomplete_equal")):
        axes[1].text(0.01, 0.98, "Both mismatch cells: 0 in every outing",
            transform=axes[1].transAxes, va="top", fontsize=8,
            bbox={"facecolor": "white", "alpha": .9, "edgecolor": "none"})
    spans = [o["original_matched_support"]["maximum_complete_sequence_duration_ns"]/1e9 for o in outings]
    axes[2].bar(x, spans, color="#60758c")
    for i, span in enumerate(spans):
        axes[2].text(i, span, f"{span:.2f}s", ha="center", va="bottom", fontsize=9)
    axes[2].set_ylim(0, max(1, max(spans, default=0)*1.25))
    axes[2].set_ylabel("Original maximum complete\nsequence span (s)")
    for ax in axes:
        ax.set_xticks(x, labels, fontsize=9)
        ax.grid(axis="y", alpha=.2)
    axes[2].set_xlabel("Original locked development outing (* previously examined mechanism case)")
    fig.suptitle("Cached speed-fragmentation mechanism audit\nDescriptive development evidence · No direct-speed recovery or feature adoption", fontsize=13)
    output = Path(output)
    fig.savefig(output/"speed_mechanism.png", dpi=160)
    fig.savefig(output/"speed_mechanism.pdf")
    plt.close(fig)
