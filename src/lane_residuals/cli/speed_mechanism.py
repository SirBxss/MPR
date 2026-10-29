"""Audit cached original development brackets; no raw or model operation."""
import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    from ..workflows.speed_mechanism import run
    report = run(args.project, args.request, args.request_sha256, args.output)
    print("Cached speed-mechanism status:", report["status"])
    print("No direct-speed rule evaluated, raw access, new training population or fit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
