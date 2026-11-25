"""Inspect one original development row for recorded replay feasibility."""

import argparse
import json
from pathlib import Path

from ..workflows import recorded_replay_inputs as workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    describe = actions.add_parser("describe", help="Print a private evidence form without opening the MCAP.")
    verify = actions.add_parser("verify", help="Check the original recorded row and write a private receipt.")
    census = actions.add_parser("qualifier-census", help="Count original odometry qualifier wire encodings.")
    for action in (describe, verify, census):
        action.add_argument("--project", type=Path, required=True)
        action.add_argument("--experiment", type=Path, required=True)
        action.add_argument("--experiment-sha256", required=True)
        action.add_argument("--outing", required=True)
        action.add_argument("--matched-row", type=int, required=True)
    for action in (verify, census):
        for option in ("source", "evidence", "scratch", "output"):
            action.add_argument("--" + option, type=Path, required=True)
        for option in ("evidence-sha256", "expected-tree", "expected-runtime"):
            action.add_argument("--" + option, required=True)
    census.add_argument("--available-symbol", required=True)
    arguments = vars(parser.parse_args(argv))
    action = arguments.pop("action")
    if action == "describe":
        print(json.dumps(workflow.describe(**arguments), indent=2, allow_nan=False))
        return 0
    if action == "qualifier-census":
        report = workflow.census(**arguments)
        success = "recorded_odometry_census_complete"
    else:
        report = workflow.run(**arguments)
        success = "recorded_frame_geometry_verified"
    print(report["status"])
    return 0 if report["status"] == success else 3


if __name__ == "__main__":
    raise SystemExit(main())
