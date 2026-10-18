"""Validate one separately pinned generic development archive without raw access."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path


def add_lineage_arguments(parser):
    for name in ("registration-directory", "preserved-inventory-report", "preserved-decode-report",
            "preserved-readiness-report", "exposure-authorization"):
        parser.add_argument("--"+name, required=True, type=Path)
    parser.add_argument("--expected-readiness-sha256", required=True)
    parser.add_argument("--expected-exposure-authorization-sha256", required=True)
    parser.add_argument("--topic", action="append", required=True, help="Repeat exactly EDP, RLMB and odometry; no selection override.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    add_lineage_arguments(parser)
    parser.add_argument("--export-directory", required=True, type=Path)
    parser.add_argument("--expected-summary-sha256", required=True)
    parser.add_argument("--validation-receipt", required=True, type=Path)
    arguments = parser.parse_args(argv)
    import resource
    previous = resource.getrlimit(resource.RLIMIT_AS)
    soft = 4*1024**3 if previous[0] == resource.RLIM_INFINITY else min(previous[0], 4*1024**3)
    resource.setrlimit(resource.RLIMIT_AS, (soft, previous[1]))
    try:
        from ..workflows.numeric_export import run_validation
        return run_validation(arguments)[1]
    except Exception:
        logging.error("numeric_validation_failed; no success receipt")
        return 2
    finally:
        resource.setrlimit(resource.RLIMIT_AS, previous)


if __name__ == "__main__":
    raise SystemExit(main())
