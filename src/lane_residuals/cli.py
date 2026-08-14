"""Compatibility entry point for the legacy v0.3.x association command."""

from .legacy.association_cli import main

__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
