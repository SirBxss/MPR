"""Separately reviewed exploratory batch02 extraction, with an allocation cap."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from collections.abc import Sequence

PROCESS_ADDRESS_SPACE_BYTES = 4 * 1024**3


def _bounded_run(arguments):
    import resource
    previous = resource.getrlimit(resource.RLIMIT_AS)
    soft = PROCESS_ADDRESS_SPACE_BYTES if previous[0] == resource.RLIM_INFINITY else min(previous[0], PROCESS_ADDRESS_SPACE_BYTES)
    resource.setrlimit(resource.RLIMIT_AS, (soft, previous[1]))
    try:
        from ..workflows.exploratory_residuals import run_exploratory_residuals
        return run_exploratory_residuals(arguments)
    finally:
        resource.setrlimit(resource.RLIMIT_AS, previous)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract exploratory batch02 EDP/RLMB profiles after focused review; no fit or outing admission.")
    parser.add_argument("mcap_root", type=Path)
    for name in ("registration", "container-context", "preserved-feasibility-report", "preserved-diagnostics-report", "scratch-directory", "output-directory"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    arguments = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, arguments.log_level), format="%(levelname)s %(message)s")
    try:
        _, status = _bounded_run(arguments)
        return status
    except MemoryError:
        logging.error("memory_limit: incomplete extraction; no data conclusion")
        return 2
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError) as error:
        logging.error("%s", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
