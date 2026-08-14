"""Compatibility module forwarding to the categorized reference workflow."""

from .cli import reference as _command
from .workflows import reference as _workflow

globals().update(
    {name: getattr(_workflow, name) for name in dir(_workflow) if not name.startswith("__")}
)
_parser = _command._parser
main = _command.main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
