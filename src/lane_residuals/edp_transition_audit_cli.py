"""Compatibility-only facade for the categorized EDP-transition command."""

from .cli import edp_transitions as _command
from .workflows import edp_transitions as _workflow

globals().update(
    {name: getattr(_workflow, name) for name in dir(_workflow) if not name.startswith("__")}
)
_parser = _command._parser
main = _command.main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
