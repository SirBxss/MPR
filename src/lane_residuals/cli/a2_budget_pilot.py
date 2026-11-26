"""Run preflight, calibration selection or the frozen-choice inner audit."""

import argparse
from pathlib import Path

from ..workflows import a2_budget_pilot as workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("preflight", "select", "audit"))
    for option in ("source", "project", "experiment", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    for option in ("experiment-sha256", "archive-set-sha256", "expected-tree", "expected-runtime"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--receipt-sha256", help="Pin the preceding receipt for select or audit.")
    args = vars(parser.parse_args(argv))
    stage, pin = args.pop("stage"), args.pop("receipt_sha256")
    if (stage == "preflight") != (pin is None):
        parser.error("--receipt-sha256 is required for select and audit")
    if stage == "preflight":
        result, expected = workflow.preflight(**args), workflow.READY
    elif stage == "select":
        result, expected = workflow.select(preflight_sha256=pin, **args), workflow.FROZEN
    else:
        result, expected = workflow.audit(choices_sha256=pin, **args), workflow.COMPLETE
    print(result["status"])
    return 0 if result["status"] == expected else 3


if __name__ == "__main__":
    raise SystemExit(main())
