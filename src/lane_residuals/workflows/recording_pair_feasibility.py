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
from ..io.recording_pair_feasibility import inspect_recording_pairs
from ..io.reports import write_strict_json


LOGGER = logging.getLogger(__name__)
CONTRACT_REVISION = "v0.19.0-batch02-recording-pair-feasibility-2026-09-20-a1"
REGISTRATION_SHA256 = "c7fbce82c027afde3b05b7046e68d338657afc85f14ee5bde8ce5cfde392ad6f"
CONTEXT_SHA256 = "b59f89d646349921b7078f05bdb705be7c477bfc20076c9c68fdb3f933729bad"
OUTPUT_NAME = "recording_pair_feasibility.json"
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


def run_recording_pair_feasibility(arguments: Any) -> tuple[dict[str, Any], int]:
    output = arguments.output_directory.expanduser()
    if output.exists():
        raise FileExistsError(f"new output directory required: {output}")
    scratch = arguments.scratch_directory.expanduser().resolve(strict=True)
    if not scratch.is_dir() or shutil.disk_usage(scratch).free < MINIMUM_FREE_SCRATCH_BYTES:
        raise ValueError("scratch directory needs at least 10 GiB free on local disk")
    if _available_memory_bytes() < MINIMUM_AVAILABLE_MEMORY_BYTES:
        raise ValueError("execution guard: at least 6 GiB MemAvailable required; free memory before the pilot")
    records = _inputs(arguments.mcap_root, arguments.registration, arguments.container_context)
    try:
        runtime_versions = {"python": platform.python_version(), "mcap": version("mcap"),
                            "mcap-protobuf-support": version("mcap-protobuf-support"),
                            "protobuf": version("protobuf"), "numpy": version("numpy")}
    except PackageNotFoundError as error:
        raise McapDependencyError('Install the project MCAP extra before this audit') from error
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
                result = inspect_recording_pairs(path, scratch)
                if _file_state(path) != before:
                    result = {"status": "inconclusive", "failure_code": "file_changed_during_decode", "counts": None}
        except OSError:
            result = {"status": "inconclusive", "failure_code": "raw_file_unavailable_during_processing", "counts": None}
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
    write_strict_json(output / OUTPUT_NAME, report)
    return report, 0 if complete else 3
