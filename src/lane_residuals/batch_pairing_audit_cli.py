"""Compatibility-only facade for the categorized batch-pairing command."""

from .cli import batch_pairing as _command
from .workflows import batch_pairing as _workflow

globals().update(
    {name: getattr(_workflow, name) for name in dir(_workflow) if not name.startswith("__")}
)
_parser = _command._parser
main = _command.main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
