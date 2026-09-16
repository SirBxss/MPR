"""Thin command adapters for the supported v0.4.5 interfaces.

``main`` preserves the historical ``lane_residuals.cli:main`` association
entry point while categorized commands live in sibling modules.
"""

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Load the historical association CLI only when its entry point runs."""

    from ..legacy.association_cli import main as association_main

    return association_main(argv)

__all__ = ["main"]
