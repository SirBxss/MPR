from __future__ import annotations

import base64
import csv
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from mcap.reader import make_reader


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_PATH = Path(
    r"C:\Users\q679381\OneDrive - BMW Group\Thesis\Data\mcap_data.zip"
)

# Number of sample messages saved from each channel/topic.
SAMPLES_PER_CHANNEL = 3

# Maximum number of payload bytes shown for binary messages.
BINARY_PREVIEW_BYTES = 100

# Set this to False when payload samples should not be exported.
INCLUDE_PAYLOAD_SAMPLES = True


def timestamp_to_text(timestamp_ns: int) -> str:
    """Convert nanoseconds since Unix epoch to readable UTC time."""
    if timestamp_ns <= 0:
        return ""

    try:
        seconds = timestamp_ns / 1_000_000_000
        return datetime.fromtimestamp(
            seconds,
            tz=timezone.utc,
        ).isoformat()
    except (OverflowError, OSError, ValueError):
        return ""


def is_probably_text(data: bytes) -> bool:
    """Return True when most bytes look like readable text."""
    if not data:
        return True

    sample = data[:2000]

    printable_count = sum(
        byte in (9, 10, 13) or 32 <= byte <= 126
        for byte in sample
    )

    return printable_count / len(sample) > 0.85


def payload_preview(data: bytes, message_encoding: str) -> dict:
    """
    Create a compact representation of a message payload.

    JSON and readable text are shown directly. Binary messages are represented
    by hexadecimal and Base64 previews.
    """
    result = {
        "payload_size_bytes": len(data),
        "preview_type": "",
        "preview": "",
    }

    encoding = (message_encoding or "").lower()

    if "json" in encoding:
        try:
            decoded = json.loads(data.decode("utf-8"))
            result["preview_type"] = "json"
            result["preview"] = decoded
            return result
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

    if is_probably_text(data):
        try:
            text = data.decode("utf-8", errors="replace")

            result["preview_type"] = "text"
            result["preview"] = text[:3000]

            if len(text) > 3000:
                result["preview_truncated"] = True

            return result
        except Exception:
            pass

    binary_preview = data[:BINARY_PREVIEW_BYTES]

    result["preview_type"] = "binary"
    result["preview"] = {
        "hex": binary_preview.hex(" "),
        "base64": base64.b64encode(binary_preview).decode("ascii"),
    }

    if len(data) > BINARY_PREVIEW_BYTES:
        result["preview_truncated"] = True

    return result


def schema_to_text(schema_data: bytes) -> str:
    """Convert schema data into a useful readable representation."""
    if not schema_data:
        return "<empty schema>"

    if is_probably_text(schema_data):
        return schema_data.decode("utf-8", errors="replace")

    preview = schema_data[:1000]

    return (
        f"<binary schema: {len(schema_data)} bytes>\n"
        f"Hex preview:\n{preview.hex(' ')}\n\n"
        f"Base64 preview:\n"
        f"{base64.b64encode(preview).decode('ascii')}"
    )


def prepare_input(input_path: Path) -> list[Path]:
    """
    Return all MCAP files represented by the input.

    The input can be:
    - one .mcap file
    - a directory containing MCAP files
    - a ZIP file containing MCAP files
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input does not exist: {input_path}")

    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        extraction_directory = (
            input_path.parent / f"{input_path.stem}_extracted"
        )

        extraction_directory.mkdir(parents=True, exist_ok=True)

        print(f"Extracting ZIP to:\n{extraction_directory}")

        with ZipFile(input_path, "r") as zip_file:
            zip_file.extractall(extraction_directory)

        mcap_files = sorted(extraction_directory.rglob("*.mcap"))

    elif input_path.is_file() and input_path.suffix.lower() == ".mcap":
        mcap_files = [input_path]

    elif input_path.is_dir():
        mcap_files = sorted(input_path.rglob("*.mcap"))

    else:
        raise ValueError(
            "INPUT_PATH must point to a .zip file, .mcap file, or directory."
        )

    if not mcap_files:
        raise FileNotFoundError(
            f"No MCAP files were found in: {input_path}"
        )

    return mcap_files


def inspect_mcap(
    mcap_path: Path,
    samples_file,
    schemas_file,
) -> tuple[list[dict], list[str]]:
    """Inspect one MCAP file and return topic statistics and report lines."""
    topic_statistics: dict[int, dict] = {}
    samples_saved: defaultdict[int, int] = defaultdict(int)
    schemas_written: set[int] = set()

    report_lines = [
        "=" * 100,
        f"FILE: {mcap_path.name}",
        f"PATH: {mcap_path}",
        f"SIZE: {mcap_path.stat().st_size / (1024 * 1024):.2f} MiB",
    ]

    with mcap_path.open("rb") as stream:
        reader = make_reader(stream)
        header = reader.get_header()

        report_lines.extend(
            [
                f"MCAP profile: {header.profile or '<not specified>'}",
                f"Writer library: {header.library or '<not specified>'}",
                "",
            ]
        )

        for schema, channel, message in reader.iter_messages():
            channel_id = channel.id
            schema_name = schema.name if schema else ""
            schema_encoding = schema.encoding if schema else ""
            schema_id = schema.id if schema else 0

            if channel_id not in topic_statistics:
                topic_statistics[channel_id] = {
                    "file": mcap_path.name,
                    "file_size_mib": round(
                        mcap_path.stat().st_size / (1024 * 1024),
                        3,
                    ),
                    "channel_id": channel_id,
                    "topic": channel.topic,
                    "schema_id": schema_id,
                    "schema_name": schema_name,
                    "schema_encoding": schema_encoding,
                    "message_encoding": channel.message_encoding,
                    "message_count": 0,
                    "first_log_time_ns": message.log_time,
                    "last_log_time_ns": message.log_time,
                    "first_log_time_utc": timestamp_to_text(
                        message.log_time
                    ),
                    "last_log_time_utc": timestamp_to_text(
                        message.log_time
                    ),
                    "total_payload_bytes": 0,
                    "minimum_payload_bytes": len(message.data),
                    "maximum_payload_bytes": len(message.data),
                    "channel_metadata": json.dumps(
                        channel.metadata,
                        ensure_ascii=False,
                    ),
                }

            stats = topic_statistics[channel_id]
            payload_size = len(message.data)

            stats["message_count"] += 1
            stats["last_log_time_ns"] = message.log_time
            stats["last_log_time_utc"] = timestamp_to_text(
                message.log_time
            )
            stats["total_payload_bytes"] += payload_size
            stats["minimum_payload_bytes"] = min(
                stats["minimum_payload_bytes"],
                payload_size,
            )
            stats["maximum_payload_bytes"] = max(
                stats["maximum_payload_bytes"],
                payload_size,
            )

            # Write each schema once per MCAP file.
            if schema and schema.id not in schemas_written:
                schemas_written.add(schema.id)

                schemas_file.write("\n" + "=" * 100 + "\n")
                schemas_file.write(f"File: {mcap_path.name}\n")
                schemas_file.write(f"Schema ID: {schema.id}\n")
                schemas_file.write(f"Schema name: {schema.name}\n")
                schemas_file.write(
                    f"Schema encoding: {schema.encoding}\n"
                )
                schemas_file.write(
                    f"Schema size: {len(schema.data)} bytes\n"
                )
                schemas_file.write("-" * 100 + "\n")
                schemas_file.write(schema_to_text(bytes(schema.data)))
                schemas_file.write("\n")

            # Save only a small number of samples from each channel.
            if (
                INCLUDE_PAYLOAD_SAMPLES
                and samples_saved[channel_id] < SAMPLES_PER_CHANNEL
            ):
                sample = {
                    "file": mcap_path.name,
                    "channel_id": channel.id,
                    "topic": channel.topic,
                    "schema_name": schema_name,
                    "schema_encoding": schema_encoding,
                    "message_encoding": channel.message_encoding,
                    "sequence": message.sequence,
                    "log_time_ns": message.log_time,
                    "log_time_utc": timestamp_to_text(
                        message.log_time
                    ),
                    "publish_time_ns": message.publish_time,
                    "publish_time_utc": timestamp_to_text(
                        message.publish_time
                    ),
                    "payload": payload_preview(
                        bytes(message.data),
                        channel.message_encoding,
                    ),
                }

                samples_file.write(
                    json.dumps(sample, ensure_ascii=False) + "\n"
                )

                samples_saved[channel_id] += 1

    rows = []

    for stats in topic_statistics.values():
        message_count = stats["message_count"]

        stats["average_payload_bytes"] = round(
            stats["total_payload_bytes"] / message_count,
            2,
        )

        duration_ns = (
            stats["last_log_time_ns"] - stats["first_log_time_ns"]
        )

        stats["duration_seconds"] = round(
            max(duration_ns, 0) / 1_000_000_000,
            3,
        )

        rows.append(stats)

    rows.sort(key=lambda row: row["topic"])

    report_lines.append(f"Number of channels: {len(rows)}")
    report_lines.append(
        f"Total messages: {sum(row['message_count'] for row in rows)}"
    )
    report_lines.append("")
    report_lines.append("TOPICS")
    report_lines.append("-" * 100)

    for row in rows:
        report_lines.extend(
            [
                f"Topic: {row['topic']}",
                f"  Channel ID:       {row['channel_id']}",
                f"  Schema:           {row['schema_name']}",
                f"  Schema encoding:  {row['schema_encoding']}",
                f"  Message encoding: {row['message_encoding']}",
                f"  Message count:    {row['message_count']}",
                f"  First timestamp:  {row['first_log_time_utc']}",
                f"  Last timestamp:   {row['last_log_time_utc']}",
                f"  Duration:         {row['duration_seconds']} seconds",
                (
                    "  Payload size:     "
                    f"min={row['minimum_payload_bytes']}, "
                    f"average={row['average_payload_bytes']}, "
                    f"max={row['maximum_payload_bytes']} bytes"
                ),
                "",
            ]
        )

    return rows, report_lines


def main() -> None:
    mcap_files = prepare_input(INPUT_PATH)

    output_directory = INPUT_PATH.parent / "mcap_inspection_output"

    # Remove only the previously generated output directory.
    if output_directory.exists():
        shutil.rmtree(output_directory)

    output_directory.mkdir(parents=True, exist_ok=True)

    report_path = output_directory / "mcap_report.txt"
    topics_csv_path = output_directory / "mcap_topics.csv"
    samples_path = output_directory / "mcap_samples.jsonl"
    schemas_path = output_directory / "mcap_schemas.txt"

    all_topic_rows: list[dict] = []
    complete_report: list[str] = [
        "MCAP INSPECTION REPORT",
        f"Input: {INPUT_PATH}",
        f"Number of MCAP files: {len(mcap_files)}",
        "",
    ]

    with (
        samples_path.open("w", encoding="utf-8") as samples_file,
        schemas_path.open("w", encoding="utf-8") as schemas_file,
    ):
        schemas_file.write("MCAP SCHEMAS\n")

        for index, mcap_path in enumerate(mcap_files, start=1):
            print(
                f"[{index}/{len(mcap_files)}] "
                f"Inspecting {mcap_path.name}"
            )

            try:
                rows, report_lines = inspect_mcap(
                    mcap_path,
                    samples_file,
                    schemas_file,
                )

                all_topic_rows.extend(rows)
                complete_report.extend(report_lines)

            except Exception as error:
                error_text = (
                    f"ERROR while reading {mcap_path}: "
                    f"{type(error).__name__}: {error}"
                )

                print(error_text)
                complete_report.extend(
                    [
                        "=" * 100,
                        error_text,
                        "",
                    ]
                )

    report_path.write_text(
        "\n".join(complete_report),
        encoding="utf-8",
    )

    if all_topic_rows:
        fieldnames = [
            "file",
            "file_size_mib",
            "channel_id",
            "topic",
            "schema_id",
            "schema_name",
            "schema_encoding",
            "message_encoding",
            "message_count",
            "first_log_time_ns",
            "first_log_time_utc",
            "last_log_time_ns",
            "last_log_time_utc",
            "duration_seconds",
            "minimum_payload_bytes",
            "average_payload_bytes",
            "maximum_payload_bytes",
            "total_payload_bytes",
            "channel_metadata",
        ]

        with topics_csv_path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=fieldnames,
            )

            writer.writeheader()
            writer.writerows(all_topic_rows)

    bundle_base_path = INPUT_PATH.parent / "mcap_inspection_bundle"

    bundle_path = shutil.make_archive(
        str(bundle_base_path),
        "zip",
        root_dir=output_directory,
    )

    print("\nInspection complete.")
    print(f"Report:  {report_path}")
    print(f"Topics:  {topics_csv_path}")
    print(f"Samples: {samples_path}")
    print(f"Schemas: {schemas_path}")
    print(f"\nUpload this bundle:\n{bundle_path}")


if __name__ == "__main__":
    main()