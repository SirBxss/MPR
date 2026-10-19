"""Create or verify an outcome-blind generic physical-outing cohort lock."""

import argparse
import json
from pathlib import Path
import resource


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    for name in ("project-root", "registry-directory", "session-declaration", "cohort-manifest", "output-directory"):
        create.add_argument("--" + name, type=Path, required=True)
    for name in ("expected-registry-sha256", "expected-session-declaration-sha256", "expected-cohort-manifest-sha256"):
        create.add_argument("--" + name, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--cohort-directory", type=Path, required=True)
    verify.add_argument("--expected-cohort-sha256", required=True)
    verify.add_argument("--registry-directory", type=Path, required=True)
    args = parser.parse_args(argv)
    old = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3 if old[0] == resource.RLIM_INFINITY else min(old[0], 4 * 1024**3), old[1]))
    try:
        from ..io.generic_cohort import create_cohort, load_cohort
        if args.action == "create":
            result, pin = create_cohort(**{k: v for k, v in vars(args).items() if k != "action"})
            print(json.dumps({"status": result["status"], "cohort_sha256": pin,
                              "model_admission_authorized": False}, sort_keys=True))
            return 0 if result["status"] == "complete" else 3
        result = load_cohort(args.cohort_directory, args.expected_cohort_sha256, args.registry_directory)
        print(json.dumps({"status": result["status"], "verification": "complete", "model_admission_authorized": False}, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "failure_code": getattr(exc, "code", type(exc).__name__)}))
        return 2
    finally:
        resource.setrlimit(resource.RLIMIT_AS, old)


if __name__ == "__main__":
    raise SystemExit(main())
