"""Prepare a cached original development pilot for spatial planner comparison."""

import argparse
import logging
from pathlib import Path

from ..workflows.cached_planner_scenarios import prepare


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--experiment-directory", type=Path, required=True)
    parser.add_argument("--expected-experiment-sha256", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--expected-runtime", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report, result = prepare(
            project=args.project,
            experiment_directory=args.experiment_directory,
            expected_experiment_sha256=args.expected_experiment_sha256,
            expected_tree=args.expected_tree,
            expected_runtime=args.expected_runtime,
            output_directory=args.output,
        )
        print("Cached spatial scenario preparation:", report["summary"]["eligible_rows"],
              "eligible of", report["summary"]["original_complete_rows"], "original matched rows")
        print("Pilot outing:", report["fold"]["validation_outing"])
        print("Result ZIP:", result)
        return 0
    except KeyboardInterrupt:
        logging.error("Interrupted; preserve any partial scenario evidence")
        return 130
    except (ValueError, OSError) as exc:
        logging.error("%s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
