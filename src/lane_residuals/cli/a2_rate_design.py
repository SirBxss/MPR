"""Check a fixed steering-rate axis using the pinned a2 calibration panel."""

import argparse
from pathlib import Path

from ..workflows.a2_rate_design import EXTENSION_RECEIPT, RECEIPT, run_design


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("source", "project", "experiment", "output", "preflight"):
        parser.add_argument("--" + option, type=Path, required=True)
    for option in ("preflight-sha256", "experiment-sha256", "archive-set-sha256", "expected-tree", "expected-runtime"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--previous-design", type=Path, help="PR 61 owner receipt for the bounded upper search")
    parser.add_argument("--previous-design-sha256", help="SHA-256 of the PR 61 owner receipt")
    args = vars(parser.parse_args(argv))
    extend = args["previous_design"] is not None
    if extend != (args["previous_design_sha256"] is not None):
        parser.error("--previous-design and --previous-design-sha256 must be supplied together")
    report = run_design(**args)
    result = report["design"]
    print(report["status"])
    print("Private receipt", args["output"] / (EXTENSION_RECEIPT if extend else RECEIPT))
    print("Common contexts", result["context_count"])
    print("Feasible rate weights", [result["candidates"][i]["curvature_rate_weight"]
                                    for i in result["feasible_candidates"]])
    print("Nominal finding", result["finding"])
    for candidate in result["candidates"]:
        print("Rate weight", candidate["curvature_rate_weight"],
              "gate failures", candidate["nominal_gate_failures"])
    print("Nominal diagnostic choice", result["nominal_choice_diagnostic"]["choice"]
          if result["nominal_choice_diagnostic"] else None)
    print("Nominal trade-off pairs (better tracking, lower jerk)",
          [(row["better_tracking"], row["lower_jerk"]) for row in result["nominal_tradeoffs"]])
    for row in result["synthetic_covariance_probes"]:
        print("Synthetic probe", row["rho"], row["sigma_m"], "choice", row["choice"],
              "within 2%", row["near_optimal_candidates"], "runner-up gap", row["runner_up_gap"])
    if extend:
        print("Upper stop", result["upper_stop"])
        for row in [result["nominal_choice_diagnostic"], *result["synthetic_covariance_probes"]]:
            if row is not None:
                print("Choice boundaries", row.get("rho"), row.get("sigma_m"),
                      result["candidates"][row["choice"]]["curvature_rate_weight"],
                      row["lower_boundary"], row["upper_boundary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
