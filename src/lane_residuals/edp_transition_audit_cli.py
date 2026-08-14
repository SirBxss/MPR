"""Compatibility module forwarding to the categorized EDP-transition workflow."""

from .workflows import edp_transitions as _implementation

globals().update(
    {name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")}
)

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
