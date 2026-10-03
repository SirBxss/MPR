"""Register arbitrary new MCAPs, then audit development-only readiness."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import logging
from pathlib import Path

PROCESS_ADDRESS_SPACE_BYTES = 4 * 1024**3


def _bounded_run(arguments):
    import resource
    previous = resource.getrlimit(resource.RLIMIT_AS)
    soft = PROCESS_ADDRESS_SPACE_BYTES if previous[0] == resource.RLIM_INFINITY else min(previous[0], PROCESS_ADDRESS_SPACE_BYTES)
    resource.setrlimit(resource.RLIMIT_AS, (soft, previous[1]))
    try:
        from ..workflows.recording_ingestion import run_prepare, run_readiness, run_registration
        return {"prepare": run_prepare, "register": run_registration, "audit": run_readiness}[arguments.command](arguments)
    finally:
        resource.setrlimit(resource.RLIMIT_AS, previous)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Development-only MCAP registration and bounded EDP/RLMB/input readiness; no residual export or fit.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="Create a one-recording development declaration with unknown evidence set to null.")
    prepare.add_argument("--mcap-file", required=True, type=Path)
    prepare.add_argument("--batch-id", required=True)
    prepare.add_argument("--recording-id", required=True)
    prepare.add_argument("--merged-input-mcap-count", type=int)
    prepare.add_argument("--source-recording-id")
    prepare.add_argument("--export-settings")
    prepare.add_argument("--output-specification", required=True, type=Path)
    registration = subparsers.add_parser("register", help="Hash files and preserve source declarations; no payload decoding.")
    registration.add_argument("--specification", required=True, type=Path)
    audit = subparsers.add_parser("audit", help="Audit indexed metadata, geometry and causal-input support after implementation review.")
    audit.add_argument("--registration-directory", required=True, type=Path)
    audit.add_argument("--scratch-directory", required=True, type=Path)
    audit.add_argument("--preserved-readiness-report", type=Path,
                       help="Preserve and reconcile an inconclusive ZstdError predecessor for a reviewed successor audit.")
    for command in (prepare, registration, audit):
        if command is not prepare:
            command.add_argument("--output-directory", required=True, type=Path)
        command.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    arguments = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, arguments.log_level), format="%(levelname)s %(message)s")
    try:
        _, status = _bounded_run(arguments)
        return status
    except MemoryError:
        logging.error("memory_limit; no completed audit")
        return 2
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError) as error:
        # Never print decoder exceptions, raw paths, source locators or payloads.
        from ..domain.recording_ingestion import RecordingIngestionError
        code = error.code if isinstance(error, RecordingIngestionError) else type(error).__name__
        logging.error("%s; no completed audit (see the runbook and preserve existing outputs)", code)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
