#!/usr/bin/env python3
"""Audit EstimatedDrivePaths.topology_source in one or more MCAP files.

This diagnostic intentionally reads the top-level protobuf field directly from
the wire payload. It therefore does not require BMW-generated ``*_pb2.py``
modules or ``mcap-protobuf-support``.

Codebase evidence used by this diagnostic:

* topic: ``/adp/estimated_drive_paths``
* message: ``Adp.Perception.EstimatedDrivePaths``
* top-level ``topology_source`` protobuf field number: 5
* enum values: 0=Unknown, 1=Croc, 2=Odometry, 3=LaneMap,
  4=SensorTopology

Install the only required package with::

    python -m pip install mcap

Example::

    python count_topology_source.py /path/to/folder/with/mcaps \
        --output-dir outputs/topology_source_audit

The input may be one or more MCAP files and/or directories. Directories are
searched recursively. The script writes CSV, JSON, and text reports.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence


DEFAULT_TOPIC = "/adp/estimated_drive_paths"
DEFAULT_FIELD_NUMBER = 5
TOPOLOGY_SOURCE_NAMES = {
    0: "kUnknown",
    1: "kCroc",
    2: "kOdometry",
    3: "kLaneMap",
    4: "kSensorTopology",
}


class ProtobufWireError(ValueError):
    """Raised when a payload is not a structurally valid protobuf message."""


@dataclass
class FileAudit:
    """Counts and diagnostics for one MCAP file."""

    file: str
    total_topic_messages: int = 0
    parsed_messages: int = 0
    explicit_counts: dict[int, int] = field(
        default_factory=lambda: {value: 0 for value in range(5)}
    )
    missing_wire_field: int = 0
    other_values: dict[int, int] = field(default_factory=dict)
    parse_failures: int = 0
    duplicate_field_messages: int = 0
    schema_names: list[str] = field(default_factory=list)
    schema_encodings: list[str] = field(default_factory=list)
    message_encodings: list[str] = field(default_factory=list)
    first_errors: list[str] = field(default_factory=list)

    @property
    def effective_count_0(self) -> int:
        """Proto scalar default: an omitted enum field has effective value zero."""

        return self.explicit_counts[0] + self.missing_wire_field

    def effective_count(self, value: int) -> int:
        if value == 0:
            return self.effective_count_0
        return self.explicit_counts[value]

    def classified_messages(self) -> int:
        return (
            sum(self.explicit_counts.values())
            + self.missing_wire_field
            + sum(self.other_values.values())
            + self.parse_failures
        )


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    """Read one unsigned protobuf varint and return ``(value, new_offset)``."""

    value = 0
    shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
    if offset >= len(data):
        raise ProtobufWireError("truncated varint")
    raise ProtobufWireError("varint is longer than 10 bytes")


def _require_available(data: bytes, offset: int, size: int) -> int:
    new_offset = offset + size
    if size < 0 or new_offset > len(data):
        raise ProtobufWireError("field extends beyond end of payload")
    return new_offset


def _skip_group(data: bytes, offset: int, start_field_number: int) -> int:
    """Skip a deprecated protobuf group, including nested groups."""

    while offset < len(data):
        key, offset = _read_varint(data, offset)
        field_number = key >> 3
        wire_type = key & 0x07
        if field_number == 0:
            raise ProtobufWireError("protobuf field number zero is invalid")
        if wire_type == 4:
            if field_number != start_field_number:
                raise ProtobufWireError("mismatched end-group field number")
            return offset
        offset = _skip_value(data, offset, field_number, wire_type)
    raise ProtobufWireError("unterminated protobuf group")


def _skip_value(
    data: bytes, offset: int, field_number: int, wire_type: int
) -> int:
    if wire_type == 0:  # varint
        _, offset = _read_varint(data, offset)
        return offset
    if wire_type == 1:  # fixed64
        return _require_available(data, offset, 8)
    if wire_type == 2:  # length-delimited
        length, offset = _read_varint(data, offset)
        return _require_available(data, offset, length)
    if wire_type == 3:  # start group
        return _skip_group(data, offset, field_number)
    if wire_type == 4:  # end group outside a group
        raise ProtobufWireError("unexpected end-group tag")
    if wire_type == 5:  # fixed32
        return _require_available(data, offset, 4)
    raise ProtobufWireError(f"invalid protobuf wire type {wire_type}")


def extract_varint_field(
    data: bytes, field_number_to_find: int
) -> tuple[bool, int | None, int]:
    """Extract the last occurrence of a top-level varint field.

    Protobuf scalar merge semantics use the last occurrence. The returned tuple
    is ``(present_on_wire, last_value, occurrence_count)``.
    """

    if field_number_to_find <= 0:
        raise ValueError("protobuf field numbers must be positive")

    offset = 0
    values: list[int] = []
    while offset < len(data):
        key, offset = _read_varint(data, offset)
        field_number = key >> 3
        wire_type = key & 0x07
        if field_number == 0:
            raise ProtobufWireError("protobuf field number zero is invalid")

        if field_number == field_number_to_find:
            if wire_type != 0:
                raise ProtobufWireError(
                    f"target field {field_number_to_find} has wire type "
                    f"{wire_type}, expected varint (0)"
                )
            value, offset = _read_varint(data, offset)
            values.append(value)
        else:
            offset = _skip_value(data, offset, field_number, wire_type)

    if not values:
        return False, None, 0
    return True, values[-1], len(values)


def discover_mcap_files(inputs: Sequence[str]) -> list[Path]:
    """Resolve files/directories into a deterministic, de-duplicated MCAP list."""

    discovered: list[Path] = []
    for raw_input in inputs:
        path = Path(raw_input).expanduser()
        if path.is_file():
            if path.suffix.lower() != ".mcap":
                raise ValueError(f"not an .mcap file: {path}")
            discovered.append(path)
        elif path.is_dir():
            discovered.extend(
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix.lower() == ".mcap"
            )
        else:
            raise FileNotFoundError(f"input does not exist: {path}")

    unique: dict[str, Path] = {}
    for path in discovered:
        resolved = path.resolve()
        unique[str(resolved)] = resolved
    return [unique[key] for key in sorted(unique)]


def _record_once(values: set[str], value: Any) -> None:
    if value is not None:
        values.add(str(value))


def audit_mcap(path: Path, topic: str, field_number: int) -> FileAudit:
    """Count the target field in all messages on ``topic`` in one MCAP."""

    try:
        from mcap.reader import make_reader
    except ImportError as exc:
        raise RuntimeError(
            "The 'mcap' package is missing. Install it with: "
            "python -m pip install mcap"
        ) from exc

    audit = FileAudit(file=str(path))
    schema_names: set[str] = set()
    schema_encodings: set[str] = set()
    message_encodings: set[str] = set()

    with path.open("rb") as stream:
        reader = make_reader(stream)
        for schema, channel, message in reader.iter_messages(
            topics=[topic], log_time_order=False
        ):
            audit.total_topic_messages += 1
            _record_once(message_encodings, getattr(channel, "message_encoding", None))
            if schema is not None:
                _record_once(schema_names, getattr(schema, "name", None))
                _record_once(schema_encodings, getattr(schema, "encoding", None))

            try:
                present, value, occurrence_count = extract_varint_field(
                    bytes(message.data), field_number
                )
                audit.parsed_messages += 1
                if occurrence_count > 1:
                    audit.duplicate_field_messages += 1
                if not present:
                    audit.missing_wire_field += 1
                elif value in audit.explicit_counts:
                    assert value is not None
                    audit.explicit_counts[value] += 1
                else:
                    assert value is not None
                    audit.other_values[value] = audit.other_values.get(value, 0) + 1
            except Exception as exc:  # retain later messages after a bad payload
                audit.parse_failures += 1
                if len(audit.first_errors) < 5:
                    audit.first_errors.append(
                        f"log_time={message.log_time}: {type(exc).__name__}: {exc}"
                    )

    audit.schema_names = sorted(schema_names)
    audit.schema_encodings = sorted(schema_encodings)
    audit.message_encodings = sorted(message_encodings)

    if audit.classified_messages() != audit.total_topic_messages:
        raise AssertionError(
            f"internal count mismatch in {path}: "
            f"classified={audit.classified_messages()}, "
            f"total={audit.total_topic_messages}"
        )
    return audit


def aggregate_audits(audits: Iterable[FileAudit]) -> FileAudit:
    """Combine file-level audits without losing error diagnostics."""

    result = FileAudit(file="ALL_FILES")
    schema_names: set[str] = set()
    schema_encodings: set[str] = set()
    message_encodings: set[str] = set()
    other_values: Counter[int] = Counter()

    for audit in audits:
        result.total_topic_messages += audit.total_topic_messages
        result.parsed_messages += audit.parsed_messages
        result.missing_wire_field += audit.missing_wire_field
        result.parse_failures += audit.parse_failures
        result.duplicate_field_messages += audit.duplicate_field_messages
        for value in range(5):
            result.explicit_counts[value] += audit.explicit_counts[value]
        other_values.update(audit.other_values)
        schema_names.update(audit.schema_names)
        schema_encodings.update(audit.schema_encodings)
        message_encodings.update(audit.message_encodings)
        for error in audit.first_errors:
            if len(result.first_errors) < 10:
                result.first_errors.append(f"{audit.file}: {error}")

    result.other_values = dict(sorted(other_values.items()))
    result.schema_names = sorted(schema_names)
    result.schema_encodings = sorted(schema_encodings)
    result.message_encodings = sorted(message_encodings)
    return result


def _percentage(count: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else 100.0 * count / denominator


def audit_to_row(audit: FileAudit) -> dict[str, Any]:
    """Flatten one audit for CSV output."""

    row: dict[str, Any] = {
        "file": audit.file,
        "total_topic_messages": audit.total_topic_messages,
        "parsed_messages": audit.parsed_messages,
        "explicit_value_0": audit.explicit_counts[0],
        "effective_value_0_including_missing": audit.effective_count_0,
        "missing_wire_field": audit.missing_wire_field,
        "other_values": json.dumps(audit.other_values, sort_keys=True),
        "parse_failures": audit.parse_failures,
        "duplicate_field_messages": audit.duplicate_field_messages,
        "schema_names": " | ".join(audit.schema_names),
        "schema_encodings": " | ".join(audit.schema_encodings),
        "message_encodings": " | ".join(audit.message_encodings),
    }
    for value in range(1, 5):
        row[f"value_{value}"] = audit.explicit_counts[value]
    for value in range(5):
        count = audit.effective_count(value)
        row[f"effective_pct_{value}"] = round(
            _percentage(count, audit.parsed_messages), 6
        )
    return row


def audit_to_json(audit: FileAudit) -> dict[str, Any]:
    data = asdict(audit)
    data["explicit_counts"] = {
        str(key): value for key, value in audit.explicit_counts.items()
    }
    data["other_values"] = {
        str(key): value for key, value in audit.other_values.items()
    }
    data["effective_counts"] = {
        str(value): audit.effective_count(value) for value in range(5)
    }
    data["effective_percentages_of_parsed"] = {
        str(value): round(
            _percentage(audit.effective_count(value), audit.parsed_messages), 6
        )
        for value in range(5)
    }
    return data


def _display_name(path: str, max_length: int = 48) -> str:
    if path == "ALL_FILES":
        return path
    name = Path(path).name
    if len(name) <= max_length:
        return name
    return f"{name[: max_length - 3]}..."


def render_text_report(
    audits: Sequence[FileAudit], aggregate: FileAudit, topic: str, field_number: int
) -> str:
    """Create a compact human-readable report."""

    all_rows = [*audits, aggregate]
    headers = [
        "file",
        "total",
        "parsed",
        "v0 effective",
        "v1",
        "v2",
        "v3",
        "v4",
        "missing*",
        "other",
        "fail",
    ]
    rows: list[list[str]] = []
    for audit in all_rows:
        rows.append(
            [
                _display_name(audit.file),
                str(audit.total_topic_messages),
                str(audit.parsed_messages),
                str(audit.effective_count_0),
                str(audit.explicit_counts[1]),
                str(audit.explicit_counts[2]),
                str(audit.explicit_counts[3]),
                str(audit.explicit_counts[4]),
                str(audit.missing_wire_field),
                str(sum(audit.other_values.values())),
                str(audit.parse_failures),
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def format_row(row: Sequence[str]) -> str:
        return "  ".join(
            cell.ljust(widths[index]) for index, cell in enumerate(row)
        ).rstrip()

    separator = "  ".join("-" * width for width in widths)
    lines = [
        "EstimatedDrivePaths topology_source audit",
        f"topic: {topic}",
        f"top-level protobuf field number: {field_number}",
        "",
        format_row(headers),
        separator,
        *[format_row(row) for row in rows],
        "",
        "Enum interpretation:",
        *[
            f"  {value}: {name}"
            for value, name in sorted(TOPOLOGY_SOURCE_NAMES.items())
        ],
        "",
        "* missing_wire_field is reported separately, but an omitted protobuf",
        "  scalar enum has effective value 0. Therefore v0 effective equals",
        "  explicit value 0 plus missing_wire_field.",
        "",
        "Scientific decision rule:",
        "  value 3 (kLaneMap): reject that frame for map-path reference evaluation",
        "  because direct map-topology selection makes the comparison circular.",
        "  value 4 (kSensorTopology): direct map-topology circularity is avoided,",
        "  but this alone does not prove full independence of the reference.",
        "  value 0/missing: provenance is unresolved for that frame.",
    ]
    if aggregate.first_errors:
        lines.extend(["", "First parse errors:", *[f"  {e}" for e in aggregate.first_errors]])
    return "\n".join(lines) + "\n"


def write_reports(
    output_dir: Path,
    audits: Sequence[FileAudit],
    aggregate: FileAudit,
    topic: str,
    field_number: int,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "topology_source_counts.csv"
    json_path = output_dir / "topology_source_counts.json"
    text_path = output_dir / "topology_source_report.txt"

    rows = [audit_to_row(audit) for audit in [*audits, aggregate]]
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "topic": topic,
        "protobuf_field_number": field_number,
        "enum_interpretation": {
            str(key): value for key, value in TOPOLOGY_SOURCE_NAMES.items()
        },
        "files": [audit_to_json(audit) for audit in audits],
        "aggregate": audit_to_json(aggregate),
    }
    with json_path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")

    text_path.write_text(
        render_text_report(audits, aggregate, topic, field_number),
        encoding="utf-8",
    )
    return csv_path, json_path, text_path


def _encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("self-test encoder accepts only non-negative integers")
    encoded = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            encoded.append(byte | 0x80)
        else:
            encoded.append(byte)
            return bytes(encoded)


def run_self_test() -> None:
    """Exercise the wire parser without requiring the ``mcap`` package."""

    field_1_text = _encode_varint((1 << 3) | 2) + _encode_varint(3) + b"abc"
    field_5_value_4 = _encode_varint((5 << 3) | 0) + _encode_varint(4)
    present, value, occurrences = extract_varint_field(
        field_1_text + field_5_value_4, 5
    )
    assert (present, value, occurrences) == (True, 4, 1)

    assert extract_varint_field(field_1_text, 5) == (False, None, 0)

    duplicate = field_5_value_4 + _encode_varint((5 << 3) | 0) + _encode_varint(3)
    assert extract_varint_field(duplicate, 5) == (True, 3, 2)

    fixed_fields = (
        _encode_varint((2 << 3) | 1)
        + b"12345678"
        + _encode_varint((3 << 3) | 5)
        + b"1234"
        + field_5_value_4
    )
    assert extract_varint_field(fixed_fields, 5) == (True, 4, 1)
    print("Self-test passed.")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Count top-level EstimatedDrivePaths.topology_source values in "
            "MCAP files without requiring BMW protobuf modules."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="One or more .mcap files and/or directories (recursive).",
    )
    parser.add_argument(
        "--topic",
        default=DEFAULT_TOPIC,
        help=f"MCAP topic to inspect (default: {DEFAULT_TOPIC}).",
    )
    parser.add_argument(
        "--field-number",
        type=int,
        default=DEFAULT_FIELD_NUMBER,
        help=(
            "Top-level protobuf field number for topology_source "
            f"(default: {DEFAULT_FIELD_NUMBER})."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/topology_source_audit"),
        help="Directory for CSV, JSON, and text reports.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Test the protobuf wire parser and exit; no MCAP package is required.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        run_self_test()
        return 0
    if not args.inputs:
        parser.error("provide at least one MCAP file or directory")
    if args.field_number <= 0:
        parser.error("--field-number must be positive")

    try:
        files = discover_mcap_files(args.inputs)
        if not files:
            raise FileNotFoundError("no .mcap files found in the supplied inputs")
        print(f"Found {len(files)} MCAP file(s).", file=sys.stderr)

        audits: list[FileAudit] = []
        for index, path in enumerate(files, start=1):
            print(f"[{index}/{len(files)}] {path}", file=sys.stderr)
            audits.append(audit_mcap(path, args.topic, args.field_number))

        aggregate = aggregate_audits(audits)
        report = render_text_report(audits, aggregate, args.topic, args.field_number)
        print(report, end="")

        csv_path, json_path, text_path = write_reports(
            args.output_dir, audits, aggregate, args.topic, args.field_number
        )
        print("Reports written:", file=sys.stderr)
        for output_path in (csv_path, json_path, text_path):
            print(f"  {output_path.resolve()}", file=sys.stderr)

        if aggregate.total_topic_messages == 0:
            print(
                f"ERROR: no messages found on topic {args.topic!r}.",
                file=sys.stderr,
            )
            return 2
        if aggregate.parse_failures:
            print(
                "WARNING: some payloads could not be parsed; inspect the report.",
                file=sys.stderr,
            )
            return 3
        return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
