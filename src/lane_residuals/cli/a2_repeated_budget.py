"""Verify shared metadata support for the repeated a2 budget comparison."""

import argparse
from pathlib import Path

from ..workflows import a2_repeated_budget as workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("source", "project", "experiment", "output", "preflight", "rate-receipt"):
        parser.add_argument("--" + option, type=Path, required=True)
    for option in ("preflight-sha256", "rate-receipt-sha256", "experiment-sha256",
                   "archive-set-sha256", "expected-tree", "expected-runtime"):
        parser.add_argument("--" + option, required=True)
    args = vars(parser.parse_args(argv))
    report = workflow.preflight(**args)
    result = report["support"]
    print(report["status"])
    print("Private receipt", args["output"] / workflow.RECEIPT)
    print("Common contexts", result["common_context_count"], "of", result["parent_context_count"])
    print("Common contexts per outing (sorted)", sorted(result["common_contexts_by_outing"].values()))
    for budget in report["protocol"]["budgets"]:
        rows = [row for row in result["subsets"] if row["budget"] == budget]
        counts = [row["supported_context_count"] for row in rows]
        print("Outing budget", budget, "subsets", len(rows), "supported parent contexts", min(counts), "to", max(counts))
    print("Fixed weights failing common-panel gates",
          [row["curvature_rate_weight"] for row in report["nominal_fixed_grid"] if row["nominal_gate_failures"]])
    print("Stop reasons", result["reasons"])
    return 0 if report["status"] == workflow.READY else 3


if __name__ == "__main__":
    raise SystemExit(main())
