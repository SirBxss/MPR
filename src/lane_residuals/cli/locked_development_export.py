"""Execute one externally pinned, reviewed private development-export plan."""

import argparse
import json
from pathlib import Path
import resource


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project-root", "plan"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("expected-plan-sha256", "expected-consumer-tree", "expected-consumer-runtime"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    old = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3 if old[0] == resource.RLIM_INFINITY else min(old[0], 4 * 1024**3), old[1]))
    try:
        from ..workflows.locked_development_export import execute
        return execute(project_root=args.project_root, plan_path=args.plan, expected_plan_sha256=args.expected_plan_sha256,
                       expected_consumer_tree=args.expected_consumer_tree, expected_consumer_runtime=args.expected_consumer_runtime)
    except (Exception, KeyboardInterrupt) as exc:
        print(json.dumps({"status": "stopped_preserve_evidence", "failure_code": getattr(exc, "code", type(exc).__name__),
                          "model_admission_authorized": False}))
        return 130 if isinstance(exc, KeyboardInterrupt) else 2
    finally:
        resource.setrlimit(resource.RLIMIT_AS, old)


if __name__ == "__main__":
    raise SystemExit(main())
