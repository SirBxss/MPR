from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from mcap.reader import make_reader


def format_timestamp(timestamp_ns: int) -> str:
    """Convert an MCAP nanosecond timestamp to a readable UTC time."""
    timestamp_seconds = timestamp_ns / 1_000_000_000
    return datetime.fromtimestamp(
        timestamp_seconds,
        tz=timezone.utc,
    ).isoformat()


def format_data(data: bytes, message_encoding: str) -> str:
    """Decode JSON messages or show a hexadecimal preview for binary data."""
    if message_encoding.lower() == "json":
        try:
            decoded = json.loads(data.decode("utf-8"))
            return json.dumps(decoded, indent=2)
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

    preview_length = 40
    preview = data[:preview_length].hex(" ")

    if len(data) > preview_length:
        preview += " ..."

    return f"{preview} ({len(data)} bytes)"


def inspect_mcap(file_path: Path, message_limit: int) -> None:
    if not file_path.exists():
        raise FileNotFoundError(f"MCAP file not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    topic_counts: Counter[str] = Counter()

    print(f"Opening: {file_path.resolve()}")
    print(f"File size: {file_path.stat().st_size / 1_000_000:.2f} MB")

    with file_path.open("rb") as stream:
        reader = make_reader(stream)

        header = reader.get_header()

        print("\nMCAP header")
        print(f"Profile: {header.profile or '<not specified>'}")
        print(f"Library: {header.library or '<not specified>'}")

        print(f"\nFirst {message_limit} messages")

        displayed_messages = 0

        for schema, channel, message in reader.iter_messages():
            topic_counts[channel.topic] += 1

            if displayed_messages >= message_limit:
                continue

            schema_name = schema.name if schema is not None else "<no schema>"
            schema_encoding = (
                schema.encoding if schema is not None else "<no schema>"
            )

            print("\n" + "-" * 70)
            print(f"Topic:            {channel.topic}")
            print(f"Schema:           {schema_name}")
            print(f"Schema encoding:  {schema_encoding}")
            print(f"Message encoding: {channel.message_encoding}")
            print(f"Sequence:         {message.sequence}")
            print(f"Log time:         {format_timestamp(message.log_time)}")
            print(f"Publish time:     {format_timestamp(message.publish_time)}")
            print("Data:")
            print(format_data(message.data, channel.message_encoding))

            displayed_messages += 1

    print("\n" + "=" * 70)
    print("Topics in the MCAP file")

    for topic, count in sorted(topic_counts.items()):
        print(f"{topic}: {count} messages")

    print(f"\nTotal messages: {sum(topic_counts.values())}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open and inspect an MCAP file."
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the .mcap file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of messages to display; default: 10",
    )

    args = parser.parse_args()

    try:
        inspect_mcap(args.file, args.limit)
    except Exception as error:
        raise SystemExit(f"Error: {error}") from error


if __name__ == "__main__":
    main()