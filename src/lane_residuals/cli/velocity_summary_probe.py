"""Run only a reviewed, pinned, summary-only development velocity probe."""
import argparse
import json

from ..io.velocity_summary_probe import run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = run(args.request, args.request_sha256, args.output)
    print(json.dumps({k: result[k] for k in ("status", "outing_id", "raw_bytes_read", "elapsed_seconds")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
