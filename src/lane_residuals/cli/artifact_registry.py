"""Import or verify a private, raw-free engineering registry; never fit a model."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("import")
    create.add_argument("--manifest", type=Path, required=True)
    create.add_argument("--project-root", type=Path, required=True)
    create.add_argument("--output-directory", type=Path, required=True)
    create.add_argument("--previous-directory", type=Path)
    create.add_argument("--expected-previous-sha256")
    create.add_argument("--observe-cache", action="store_true", help="Stat raw paths only; never open/hash payloads.")
    verify = sub.add_parser("verify")
    verify.add_argument("--registry-directory", type=Path, required=True)
    verify.add_argument("--expected-registry-sha256", required=True)
    args = parser.parse_args(argv)
    import resource
    previous = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3 if previous[0] == resource.RLIM_INFINITY else min(previous[0], 4*1024**3), previous[1]))
    try:
        from ..io.artifact_registry import import_evidence, load_registry
        if args.command == "import":
            metadata, pin = import_evidence(args.manifest, project_root=args.project_root, output_directory=args.output_directory,
                previous_directory=args.previous_directory, expected_previous_sha256=args.expected_previous_sha256, observe_cache=args.observe_cache)
        else:
            metadata, _, _ = load_registry(args.registry_directory, args.expected_registry_sha256)
            pin = args.expected_registry_sha256
        print(json.dumps({"status": "complete_engineering_registry", "registry_sha256": pin,
            "unique_raw_identity_count": len(metadata["records"]), "model_admission_authorized": False,
            "roles_assigned": False, "raw_cache_deletion_authorized": False}, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "failure_code": getattr(exc, "code", "registry_validation_failed"),
            "model_admission_authorized": False}, sort_keys=True))
        return 2
    finally:
        resource.setrlimit(resource.RLIMIT_AS, previous)


if __name__ == "__main__":
    raise SystemExit(main())
