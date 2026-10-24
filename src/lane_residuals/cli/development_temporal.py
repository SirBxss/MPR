"""Prepare or run the separately adopted matched stationary AR control."""
import argparse
from pathlib import Path

from ..workflows import development_temporal as workflow


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
    a = parser.parse_args(argv)
    common = dict(project=a.project_root,expected_tree=a.expected_consumer_tree,expected_runtime=a.expected_consumer_runtime)
    try:
        if a.operation == "prepare":
            if a.request is None or a.expected_request_sha256 is None or any(v is not None for v in
                    (a.experiment_directory,a.expected_experiment_sha256,a.authorization,a.expected_authorization_sha256)):
                parser.error("prepare requires only request and digest")
            manifest,pin = workflow.prepare(**common,request_path=a.request,expected_request_sha256=a.expected_request_sha256)
            print(manifest["status"],"experiment SHA-256:",pin)
            return 0
        if a.request is not None or a.expected_request_sha256 is not None or any(v is None for v in
                (a.experiment_directory,a.expected_experiment_sha256,a.authorization,a.expected_authorization_sha256)):
            parser.error("train requires experiment, authorization and both digests")
        return workflow.train(**common,experiment_directory=a.experiment_directory,expected_experiment_sha256=a.expected_experiment_sha256,
            authorization_path=a.authorization,expected_authorization_sha256=a.expected_authorization_sha256)
    except (ValueError,OSError,KeyError) as exc:
        print("Stopped:",str(exc),"Preserve every input, claim and attempt; do not retry or edit pins.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
