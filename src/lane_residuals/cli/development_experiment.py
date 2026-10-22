"""CLI for preparation and explicitly adopted fixed Gaussian development fits."""

import argparse
from pathlib import Path

from ..workflows import development_experiment as workflow


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation",choices=("prepare","train"))
    parser.add_argument("--project-root",type=Path,required=True)
    parser.add_argument("--expected-consumer-tree",required=True)
    parser.add_argument("--expected-consumer-runtime",required=True)
    parser.add_argument("--request",type=Path)
    parser.add_argument("--expected-request-sha256")
    parser.add_argument("--experiment-directory",type=Path)
    parser.add_argument("--expected-experiment-sha256")
    parser.add_argument("--authorization",type=Path)
    parser.add_argument("--expected-authorization-sha256")
    args = parser.parse_args(argv)
    common = dict(project=args.project_root,expected_tree=args.expected_consumer_tree,expected_runtime=args.expected_consumer_runtime)
    try:
        if args.operation == "prepare":
            if args.request is None or args.expected_request_sha256 is None or any(v is not None for v in
                (args.experiment_directory,args.expected_experiment_sha256,args.authorization,args.expected_authorization_sha256)):
                parser.error("prepare requires only request and request digest")
            manifest,pin = workflow.prepare(**common,request_path=args.request,expected_request_sha256=args.expected_request_sha256)
            print(manifest["status"],"experiment SHA-256:",pin)
            return 0
        if args.request is not None or args.expected_request_sha256 is not None or any(v is None for v in
            (args.experiment_directory,args.expected_experiment_sha256,args.authorization,args.expected_authorization_sha256)):
            parser.error("train requires experiment, authorization and both digests")
        return workflow.train(**common,experiment_directory=args.experiment_directory,
            expected_experiment_sha256=args.expected_experiment_sha256,authorization_path=args.authorization,
            expected_authorization_sha256=args.expected_authorization_sha256)
    except (ValueError,OSError,KeyError) as exc:
        print("Stopped:",str(exc),"Preserve all existing evidence; do not edit pins or retry a started attempt.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
