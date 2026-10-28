"""Audit source ties in a pinned cached timing return; diagnostic only."""
import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-zip", required=True, type=Path)
    parser.add_argument("--result-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    from ..workflows.velocity_source_ties import run
    result = run(args.result_zip, args.result_sha256, args.output)
    print("Cached source-tie status:", result["status"])
    print("Same selected update; post-hoc diagnostic only; no speed feature adopted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
