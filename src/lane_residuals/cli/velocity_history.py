"""Replay a pinned completed timing ZIP; no raw decode or model fitting."""
import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-zip", required=True, type=Path)
    parser.add_argument("--result-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    from ..workflows.velocity_history import run
    result = run(args.result_zip, args.result_sha256, args.output)
    print("Cached history status:", result["status"])
    print("Post-hoc diagnostic only; no raw operation or training feature adopted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
