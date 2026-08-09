"""Fail-closed compatibility shim for the withdrawn provisional-GT workflow."""

from __future__ import annotations

import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Reject the obsolete ego-lane-as-ground-truth command.

    Version 0.3.9 was scientifically revised after determining that the fused
    ego-lane path is not confirmed ground truth.  The replacement command is
    ``python -m lane_residuals.reference_audit_cli``.
    """

    _ = argv
    print(
        "BLOCKED: the provisional-GT residual extractor was withdrawn. "
        "Run `python -m lane_residuals.reference_audit_cli --help` and audit "
        "direct-map and pose-plus-centerline reference candidates first.",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
