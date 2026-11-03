"""Python plots of unchanged cached values and fixed bracket associations."""
from ..domain.direct_speed_study import AGREEMENT_LIMITS


def plot(output, rows):
    import matplotlib.pyplot as plt
    candidate = "/adp/velocity_vehicle_longitudinal"
    outings = list(dict.fromkeys(r["outing_id"] for r in rows))
    fig,axes = plt.subplots(len(outings),2,figsize=(12,3.5*len(outings)),squeeze=False)
    bound = AGREEMENT_LIMITS["maximum_absolute_difference_mps"]
    for line,outing in zip(axes,outings):
        selected = [r for r in rows if r["outing_id"] == outing and r["topic"] == candidate]
        origin = int(selected[0]["edp_source_ns"])
        for ax in line:
            ax.axhspan(-bound,bound,color="gray",alpha=.1)
            ax.axhline(0,color="gray",linewidth=.7)
            ax.grid(alpha=.2)
        for equal,color,label in ((True,"#D78117","Equal source time"),(False,"#137C66","Earlier source time")):
            local = [r for r in selected if r["shared_original_complete"] and r["source_equal"] is equal]
            line[0].scatter([(int(r["edp_source_ns"])-origin)/1e9 for r in local],
                [r["candidate_minus_old_mps"] for r in local],label=label,color=color,s=22)
            known = [r for r in local if r["previous_interpolation_fraction"] is not None]
            line[1].scatter([r["previous_interpolation_fraction"] for r in known],
                [r["candidate_minus_old_mps"] for r in known],label=label,color=color,s=22)
        line[0].set(xlabel="Elapsed EDP source time (s)",ylabel="Candidate minus original (m/s)",title=outing+" shared rows")
        line[1].set(xlabel="Original previous pose interpolation fraction",ylabel="Candidate minus original (m/s)",
            title="Bracket association, not a causal explanation",xlim=(-.05,1.05))
    axes[0,0].legend(fontsize=8)
    fig.suptitle("Cached disagreement: original values, masks and comparison limit",fontsize=14)
    fig.tight_layout()
    for suffix in ("png","pdf"):
        fig.savefig(output/("speed_disagreement."+suffix),bbox_inches="tight",dpi=160)
    plt.close(fig)
