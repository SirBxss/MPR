"""Compatibility entry point for the withdrawn provisional-residual command."""

from .legacy.provisional_residual_cli import main

__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
