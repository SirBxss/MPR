"""CLI for the separately reviewed batch02 recording-level feasibility pilot."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from collections.abc import Sequence

PROCESS_ADDRESS_SPACE_BYTES = 4 * 1024**3


def _bounded_run(arguments):
    # Apply the Linux allocation cap before importing NumPy/decoder modules.
    # Do not raise an existing stricter limit or alter the hard limit.
    import resource
    previous = resource.getrlimit(resource.RLIMIT_AS)
    soft = PROCESS_ADDRESS_SPACE_BYTES if previous[0] == resource.RLIM_INFINITY else min(previous[0], PROCESS_ADDRESS_SPACE_BYTES)
    resource.setrlimit(resource.RLIMIT_AS, (soft, previous[1]))
    try:
        from ..workflows.recording_pair_feasibility import run_recording_pair_feasibility
        return run_recording_pair_feasibility(arguments)
    finally:
        resource.setrlimit(resource.RLIMIT_AS, previous)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit batch02 EDP/RLMB geometry without declaring independent outings.")
    parser.add_argument("mcap_root", type=Path)
    parser.add_argument("--registration", required=True, type=Path)
    parser.add_argument("--container-context", required=True, type=Path)
    parser.add_argument("--scratch-directory", required=True, type=Path,
                        help="existing local-disk directory for temporary geometry; at least 10 GiB free")
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    arguments = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, arguments.log_level), format="%(levelname)s %(message)s")
    try:
        report, status = _bounded_run(arguments)
    except MemoryError:
        logging.error("memory_limit: incomplete execution; no negative geometry conclusion")
        return 2
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError) as error:
        logging.error("%s", error)
        return 2
    logging.info("Recording audit %s; no outing identities or roles assigned", report["status"])
    return status


if __name__ == "__main__":
    raise SystemExit(main())
