"""Compare saved direct speeds and original odometry brackets without raw access."""
import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-zip",required=True,type=Path)
    parser.add_argument("--result-sha256",required=True)
    parser.add_argument("--output",required=True,type=Path)
    args = parser.parse_args(argv)
    from ..workflows.speed_disagreement import run
    result = run(args.result_zip,args.result_sha256,args.output)
    print("Cached disagreement status:",result["status"])
    print("Descriptive only. No speed correction, training export or feature adoption.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
