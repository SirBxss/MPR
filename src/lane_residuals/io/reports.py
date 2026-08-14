"""Stable CSV and strict-JSON serialization used by diagnostic workflows."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


def write_csv_rows(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
    *,
    extrasaction: str = "raise",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction=extrasaction)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def write_strict_json(
    path: Path,
    payload: Any,
    *,
    sort_keys: bool = True,
) -> None:
    """Write portable JSON and reject non-finite numeric values."""

    serialized = json.dumps(
        payload,
        indent=2,
        sort_keys=sort_keys,
        allow_nan=False,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(serialized)
        handle.write("\n")


def write_csv_rows_ignoring_extras(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
) -> None:
    """Write the legacy geometry/reference CSV policy unchanged."""
    write_csv_rows(path, fieldnames, rows, extrasaction="ignore")


def write_strict_json_insertion_order(path: Path, payload: Any) -> None:
    """Write strict JSON while retaining insertion order."""
    write_strict_json(path, payload, sort_keys=False)
