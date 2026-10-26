"""Seal verified merged-source evidence or run one bounded velocity pilot."""
import argparse
import hashlib
from pathlib import Path

from ..io import velocity_review_gate
from ..workflows.velocity_timing_pilot import run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser("seal", help="Metadata only; requires actual successful CI and merged main")
    operate = commands.add_parser("run", help="Verify sealed source again, then one fixed development pilot")
    for command in (seal, operate):
        command.add_argument("--project", required=True, type=Path)
        command.add_argument("--request", required=True, type=Path)
        command.add_argument("--request-sha256", required=True)
        command.add_argument("--expected-runtime-sha256", required=True)
    seal.add_argument("--review-note", required=True, type=Path)
    seal.add_argument("--independent-review-go", action="store_true")
    seal.add_argument("--output", required=True, type=Path)
    operate.add_argument("--gate", required=True, type=Path)
    operate.add_argument("--gate-sha256", required=True)
    operate.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    # Role/lineage checks also apply to metadata sealing; no raw file is touched.
    from ..io.velocity_timing_pilot import load_request
    load_request(args.request, args.request_sha256)
    if args.command == "seal":
        pin = velocity_review_gate.seal(args.project, args.expected_runtime_sha256, args.request_sha256,
            args.review_note, args.output, independent_review_go=args.independent_review_go)
        print("Metadata source gate SHA-256:", pin)
    else:
        import resource
        limit = 4*1024**3
        _, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (min(limit, hard) if hard != resource.RLIM_INFINITY else limit, hard))
        result = run(project=args.project, request_path=args.request, request_sha256=args.request_sha256,
            gate_path=args.gate, gate_sha256=args.gate_sha256, expected_runtime=args.expected_runtime_sha256, output=args.output)
        print("Pilot status:", result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
