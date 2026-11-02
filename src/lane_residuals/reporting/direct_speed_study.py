"""Matplotlib diagnostics for bounded windows and a cached population check."""
from pathlib import Path


def plot(output, report, stations):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    output = Path(output)
    cases = report["cases"]
    fig,axes = plt.subplots(3,1,figsize=(12,10),constrained_layout=True)
    labels,primary,secondary,old,pspan,sspan,ospan,bias,rms = [],[],[],[],[],[],[],[],[]
    for case in cases:
        for topic,item in case["analysis"]["topics"].items():
            labels.append(case["outing_id"]+"\n"+topic.rsplit("/",1)[-1])
            a,b = item["rules"]["primary"],item["rules"]["strict_source_secondary"]
            n = item["geometry_without_estimate_failure_rows"]
            primary.append(a["stratum_coverage"]);secondary.append(b["stratum_coverage"])
            old.append(case["analysis"]["original_support"]["frames"]/n if n else None)
            pspan.append(a["support"]["maximum_span_s"]);sspan.append(b["support"]["maximum_span_s"])
            ospan.append(case["analysis"]["original_support"]["maximum_span_s"])
            comparison = a["agreement_on_original_complete_rows"]
            bias.append(comparison["bias_mps"]);rms.append(comparison["rms_difference_mps"])
    x = list(range(len(labels)))
    for values,name,offset,color in ((old,"Original",-.24,"#929aa1"),(primary,"Primary",0,"#23866c"),(secondary,"Strict-source secondary",.24,"#60758c")):
        axes[0].bar([i+offset for i in x],[float("nan") if v is None else v for v in values],width=.23,label=name,color=color)
    axes[0].axhline(.95,ls="--",color="#bb614b",label="Predeclared 95% target")
    axes[0].set_ylim(0,1.08);axes[0].set_ylabel("Window stratum coverage")
    for values,name in ((ospan,"Original"),(pspan,"Primary"),(sspan,"Strict-source secondary")):
        axes[1].plot(x,values,"o-",label=name)
    axes[1].axhline(5,ls="--",color="#bb614b",label="Predeclared 5 s target")
    axes[1].set_ylabel("Maximum window run span (s)")
    axes[2].plot(x,[float("nan") if v is None else v for v in bias],"o",label="Primary direct minus old: mean")
    axes[2].plot(x,[float("nan") if v is None else v for v in rms],"s",label="Primary RMS difference")
    axes[2].axhline(0,color="grey",lw=.7);axes[2].set_ylabel("Paired speed difference (m/s)")
    for ax in axes:
        ax.set_xticks(x,labels,fontsize=8);ax.legend(loc="upper left",bbox_to_anchor=(1.01,1),fontsize=8);ax.grid(axis="y",alpha=.2)
    fig.suptitle("Bounded development windows · recorded-clock diagnostics\nNo feature adoption or cohort-wide recovery claim")
    for suffix in ("png","pdf"):
        fig.savefig(output/("direct_speed_windows."+suffix),dpi=160)
    plt.close(fig)
    fig,ax = plt.subplots(figsize=(11,5),constrained_layout=True)
    for outing in sorted({r["outing_id"] for r in stations}):
        rows = [r for r in stations if r["outing_id"] == outing]
        ax.plot([r["station_m"] for r in rows],[float("nan") if r["future_only_minus_complete_mean_m"] is None else r["future_only_minus_complete_mean_m"] for r in rows],label=outing)
    ax.axhline(0,color="grey",lw=.7);ax.set_xlabel("H100 station (m)");ax.set_ylabel("Mean residual: future-only minus complete (m)")
    ax.legend(loc="upper left",bbox_to_anchor=(1.01,1),fontsize=8);ax.grid(alpha=.2)
    ax.set_title("Cached within-outing population comparison\nDescriptive differences; no frame-independence or model-impact claim")
    for suffix in ("png","pdf"):
        fig.savefig(output/("cached_population_difference."+suffix),dpi=160)
    plt.close(fig)
