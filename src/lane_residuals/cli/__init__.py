"""Thin command adapters for the supported v0.4.5 interfaces.

``main`` preserves the historical ``lane_residuals.cli:main`` association
entry point while categorized commands live in sibling modules.
"""

from ..legacy.association_cli import main

__all__ = ["main"]
