"""A batch02 technical recording audit; cannot create a v0.17 cohort lock."""

from __future__ import annotations

import hashlib
import logging
import json
from pathlib import Path, PurePosixPath
import platform
import shutil
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from ..io.corpus_inventory import sha256_file
from ..io.independent_outing_intake import discover_mcaps, read_strict_json_with_bytes
from ..io.mcap import McapDependencyError
from ..io.recording_pair_feasibility import decoder_types, inspect_recording_pairs
from ..io.reports import write_strict_json


LOGGER = logging.getLogger(__name__)
CONTRACT_REVISION = "v0.19.0-batch02-recording-pair-feasibility-2026-09-20-a1"
REGISTRATION_SHA256 = "c7fbce82c027afde3b05b7046e68d338657afc85f14ee5bde8ce5cfde392ad6f"
CONTEXT_SHA256 = "b59f89d646349921b7078f05bdb705be7c477bfc20076c9c68fdb3f933729bad"
OUTPUT_NAME = "recording_pair_feasibility.json"
DIAGNOSTIC_REVISION = "v0.19.1-batch02-reference-timing-2026-09-22-a1"
DIAGNOSTIC_OUTPUT_NAME = "recording_pair_diagnostics.json"
PRESERVED_REPORT_SHA256 = "89cbeeb89d3939a297f1602a8750663fd6cfa514d3376642053e05754548f9ec"
PRESERVED_SOURCE_SHA256 = "f121352befc008965d2ee770b76b01be7101d5bba76000963185249bb951df0d"
MINIMUM_AVAILABLE_MEMORY_BYTES = 6 * 1024**3
MINIMUM_FREE_SCRATCH_BYTES = 10 * 1024**3


def _available_memory_bytes() -> int:
    """Execution guard on the target Linux host, not an eligibility rule."""
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise ValueError("Linux MemAvailable is required for this pilot")


def _file_state(path: Path) -> tuple[int, int, int, int]:
    state = path.stat()
    return state.st_size, state.st_mtime_ns, state.st_dev, state.st_ino


def _inputs(root: Path, registration_path: Path, context_path: Path):
    registration, registration_bytes = read_strict_json_with_bytes(registration_path)
    context, context_bytes = read_strict_json_with_bytes(context_path)
    if hashlib.sha256(registration_bytes).hexdigest() != REGISTRATION_SHA256:
        raise ValueError("registration SHA-256 does not match the frozen batch02 input")
    if hashlib.sha256(context_bytes).hexdigest() != CONTEXT_SHA256:
        raise ValueError("container-context SHA-256 does not match the frozen batch02 input")
    if context["registration_sha256"] != REGISTRATION_SHA256:
        raise ValueError("context/registration lineage mismatch")
    records = registration["files"]
    context_by_path = {row["relative_path"]: row for row in context["files"]}
    root = root.expanduser().resolve(strict=True)
    result = []
    for row in records:
        relative = PurePosixPath(row["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe registered path")
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("registered MCAP is outside the batch02 root")
        counterpart = context_by_path[row["relative_path"]]
        if (counterpart["size_bytes"] != row["size_bytes"] or
                counterpart["sha256_from_registration_not_rehashed"] != row["sha256"]):
            raise ValueError("context/registration file identity mismatch")
        before = _file_state(path)
        if before[0] != row["size_bytes"]:
            raise ValueError("registered file size changed")
        result.append((path, row, before))
    found = discover_mcaps(root)
    if (len(result) != 4 or len(found) != 4 or len(context_by_path) != 4 or
            len({path for path, _, _ in result}) != 4 or
            set(found) != {path for path, _, _ in result}):
        raise ValueError("exact four-file batch02 coverage is required")
    return result


def _preserved_counts(path: Path, records) -> dict[str, dict[str, Any]]:
    payload, raw = read_strict_json_with_bytes(path)
    if hashlib.sha256(raw).hexdigest() != PRESERVED_REPORT_SHA256:
        raise ValueError("preserved feasibility SHA-256 does not match the completed pilot")
    expected = {
        "contract_revision": CONTRACT_REVISION, "status": "complete",
        "purpose": "recording_level_geometry_feasibility_without_session_provenance",
        "registration_sha256": REGISTRATION_SHA256, "container_context_sha256": CONTEXT_SHA256,
        "runtime_source_sha256": PRESERVED_SOURCE_SHA256, "raw_hashes_verified": True,
        "physical_session_provenance": "unavailable_owner_report_2026-09-20",
        "independent_outing_count": None, "roles_assigned": False,
        "cohort_lock_created": False, "causal_input_availability_checked": False,
        "residuals_computed": False,
    }
    if any(key not in payload or type(payload[key]) is not type(value) or payload[key] != value
           for key, value in expected.items()):
        raise ValueError("preserved feasibility contract or lineage mismatch")
    rows = payload["recordings"]
    by_path = {row["relative_path_private"]: row for row in rows}
    if len(rows) != 4 or set(by_path) != {row["relative_path"] for _, row, _ in records}:
        raise ValueError("preserved feasibility must cover the exact four recordings")
    for _, identity, _ in records:
        row = by_path[identity["relative_path"]]
        if (row["status"] != "complete" or row["failure_code"] is not None or
                row["raw_sha256"] != identity["sha256"] or row["size_bytes"] != identity["size_bytes"] or
                not isinstance(row["counts"], dict) or not row["counts"]):
            raise ValueError("preserved recording identity or completion mismatch")
    return {path: row["counts"] for path, row in by_path.items()}


def run_recording_pair_feasibility(arguments: Any) -> tuple[dict[str, Any], int]:
    preserved_path = getattr(arguments, "preserved_feasibility_report", None)
    diagnostic_mode = preserved_path is not None
    output = arguments.output_directory.expanduser()
    if output.exists():
        raise FileExistsError(f"new output directory required: {output}")
    scratch = arguments.scratch_directory.expanduser().resolve(strict=True)
    if not scratch.is_dir() or shutil.disk_usage(scratch).free < MINIMUM_FREE_SCRATCH_BYTES:
        raise ValueError("scratch directory needs at least 10 GiB free on local disk")
    if _available_memory_bytes() < MINIMUM_AVAILABLE_MEMORY_BYTES:
        raise ValueError("execution guard: at least 6 GiB MemAvailable required; free memory before the pilot")
    records = _inputs(arguments.mcap_root, arguments.registration, arguments.container_context)
    preserved_counts = _preserved_counts(preserved_path, records) if diagnostic_mode else None
    try:
        runtime_versions = {"python": platform.python_version(), "mcap": version("mcap"),
                            "mcap-protobuf-support": version("mcap-protobuf-support"),
                            "protobuf": version("protobuf"), "numpy": version("numpy")}
    except PackageNotFoundError as error:
        raise McapDependencyError('Install the project MCAP extra before this audit') from error
    if diagnostic_mode:
        decoder_types()
    package_root = Path(__file__).resolve().parents[1]
    source_hashes = {p.relative_to(package_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(package_root.rglob("*.py"))}
    # The administrative time collector did not rehash raw files. This first
    # payload audit must establish current byte identity before inspecting them.
    for index, (path, row, before) in enumerate(records, 1):
        LOGGER.info("Verifying registered raw bytes %d/4", index)
        if sha256_file(path) != row["sha256"] or _file_state(path) != before:
            raise ValueError("raw MCAP hash or file state changed; no geometry audit created")
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for index, (path, row, before) in enumerate(records, 1):
        LOGGER.info("Inspecting recording %d/4 with disk-backed geometry", index)
        try:
            if _file_state(path) != before:
                result = {"status": "inconclusive", "failure_code": "file_changed_before_decode", "counts": None}
            else:
                result = inspect_recording_pairs(path, scratch, **(
                    {"include_diagnostics": True} if diagnostic_mode else {}))
                if _file_state(path) != before:
                    result = {"status": "inconclusive", "failure_code": "file_changed_during_decode", "counts": None}
        except OSError:
            result = {"status": "inconclusive", "failure_code": "raw_file_unavailable_during_processing", "counts": None}
        if diagnostic_mode:
            matches = None
            if result["status"] == "complete":
                matches = result["counts"] == preserved_counts[row["relative_path"]]
                if not matches:
                    result = {"status": "inconclusive", "failure_code": "preserved_counts_mismatch", "counts": None}
            if result["status"] != "complete":
                result["diagnostics"] = None
            result["legacy_counts_match_preserved"] = matches
        results.append({"relative_path_private": row["relative_path"],
                        "raw_sha256": row["sha256"], "size_bytes": row["size_bytes"], **result})
    complete = all(row["status"] == "complete" for row in results)
    report = {
        "contract_revision": CONTRACT_REVISION,
        "purpose": "recording_level_geometry_feasibility_without_session_provenance",
        "status": "complete" if complete else "inconclusive",
        "registration_sha256": REGISTRATION_SHA256,
        "container_context_sha256": CONTEXT_SHA256,
        "runtime_versions": runtime_versions,
        "runtime_source_sha256": hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest(),
        "raw_hashes_verified": True,
        "physical_session_provenance": "unavailable_owner_report_2026-09-20",
        "independent_outing_count": None,
        "roles_assigned": False,
        "cohort_lock_created": False,
        "causal_input_availability_checked": False,
        "residuals_computed": False,
        "interpretation": "EDP/RLMB geometry counts only, not eligible frames/outings. Complete numeric timestamp streams are paired with the canonical intake's ungated mutual-nearest rule. No physical timing, independent reference, session identity, residual target change or final-evaluation claim follows.",
        "recordings": results,
    }
    if diagnostic_mode:
        report.update({
            "contract_revision": DIAGNOSTIC_REVISION,
            "purpose": "recording_level_reference_failures_and_numeric_pair_timing",
            "preserved_feasibility_sha256": PRESERVED_REPORT_SHA256,
            "interpretation": "Original EDP/RLMB counts must match the preserved pilot. Static conversion reasons and numeric source-time deltas only; no delta gate, physical synchronization, independent reference, session identity, eligible frames, residuals or model claim follows.",
        })
    write_strict_json(output / (DIAGNOSTIC_OUTPUT_NAME if diagnostic_mode else OUTPUT_NAME), report)
    return report, 0 if complete else 3
