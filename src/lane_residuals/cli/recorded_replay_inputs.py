"""Describe or verify the recorded geometry of one original development row."""

import argparse
import json
from pathlib import Path

from ..workflows import recorded_replay_inputs as workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    describe = actions.add_parser("describe", help="Print a private evidence form without opening the MCAP.")
    verify = actions.add_parser("verify", help="Check the original recorded row and write a private receipt.")
    for action in (describe, verify):
        action.add_argument("--project", type=Path, required=True)
        action.add_argument("--experiment", type=Path, required=True)
        action.add_argument("--experiment-sha256", required=True)
        action.add_argument("--outing", required=True)
        action.add_argument("--matched-row", type=int, required=True)
    for option in ("source", "evidence", "scratch", "output"):
        verify.add_argument("--" + option, type=Path, required=True)
    for option in ("evidence-sha256", "expected-tree", "expected-runtime"):
        verify.add_argument("--" + option, required=True)
    arguments = vars(parser.parse_args(argv))
    if arguments.pop("action") == "describe":
        print(json.dumps(workflow.describe(**arguments), indent=2, allow_nan=False))
        return 0
    report = workflow.run(**arguments)
    print(report["status"])
    return 0 if report["status"] == "recorded_frame_geometry_verified" else 3


if __name__ == "__main__":
    raise SystemExit(main())
