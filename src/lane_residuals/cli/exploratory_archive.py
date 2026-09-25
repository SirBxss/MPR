"""Read-only validation of the one published batch02 exploratory archive."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from ..io.exploratory_archive import load_exploratory_archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate published v0.19.2 batch02 output; no split or fit")
    parser.add_argument("output_directory", type=Path, help="Directory containing the three unzipped output files")
    args = parser.parse_args(argv)
    try:
        result = load_exploratory_archive(args.output_directory)
    except (OSError, ValueError, KeyError, TypeError) as error:
        logging.error("%s", error)
        return 2
    support = result.summary["support"]
    print(json.dumps({"contract_revision": result.summary["contract_revision"],
                      "geometric_profile_count": support["geometric_profile_count"],
                      "conditioned_profile_count": support["conditioned_profile_count"],
                      "conditioned_transition_count": support["conditioned_transition_count"],
                      "outing_count": None, "model_fitted": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
