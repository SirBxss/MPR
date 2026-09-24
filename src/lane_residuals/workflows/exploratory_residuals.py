"""Exact-lineage batch02 exploratory extraction; no split, fit or outing lock."""

from __future__ import annotations

from collections import Counter
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import logging
from pathlib import Path
import platform
import shutil
from typing import Any

from ..domain.exploratory_residuals import build_archive
from ..io.corpus_inventory import sha256_file
from ..io.expanded_sequence_dataset import write_deterministic_npz
from ..io.exploratory_residuals import inconclusive, inspect_recording_residuals
from ..io.independent_outing_intake import read_strict_json_with_bytes
from ..io.mcap import McapDependencyError
from ..io.recording_pair_feasibility import decoder_types
from ..io.reports import write_strict_json
from . import recording_pair_feasibility as pilot

LOGGER = logging.getLogger(__name__)
CONTRACT_REVISION = "v0.19.2-batch02-exploratory-residuals-2026-09-24-a1"
DIAGNOSTICS_SHA256 = "fad94bc2b20715cb8067883c637f1f208f562fc29d4fcc6bd24bd0e0054a6ffb"
DIAGNOSTICS_SOURCE_SHA256 = "2f09d5a192d23e28833df06a4d3920768384d186d3fba334765b5620eda5267b"
SUMMARY_NAME = "exploratory_residual_summary.json"
AUDIT_NAME = "candidate_audit.json"
ARCHIVE_NAME = "exploratory_residuals.npz"


def _preserved_diagnostics(path: Path, records, counts):
    payload, raw = read_strict_json_with_bytes(path)
    if hashlib.sha256(raw).hexdigest() != DIAGNOSTICS_SHA256:
        raise ValueError("preserved diagnostics SHA-256 differs from the completed result")
    expected = {"status": "complete", "contract_revision": pilot.DIAGNOSTIC_REVISION,
        "purpose": "recording_level_reference_failures_and_numeric_pair_timing",
        "preserved_feasibility_sha256": pilot.PRESERVED_REPORT_SHA256,
        "registration_sha256": pilot.REGISTRATION_SHA256, "container_context_sha256": pilot.CONTEXT_SHA256,
        "runtime_source_sha256": DIAGNOSTICS_SOURCE_SHA256, "raw_hashes_verified": True,
        "physical_session_provenance": "unavailable_owner_report_2026-09-20", "independent_outing_count": None,
        "roles_assigned": False, "cohort_lock_created": False,
        "causal_input_availability_checked": False, "residuals_computed": False}
    if any(type(payload.get(k)) is not type(v) or payload.get(k) != v for k, v in expected.items()):
        raise ValueError("preserved diagnostic contract or lineage mismatch")
    rows = payload["recordings"]
    by_path = {row["relative_path_private"]: row for row in rows}
    if len(rows) != 4 or set(by_path) != set(counts):
        raise ValueError("preserved diagnostics must cover all four recordings")
    for _, identity, _ in records:
        row = by_path[identity["relative_path"]]
        if (row["status"] != "complete" or row["failure_code"] is not None or
                row["legacy_counts_match_preserved"] is not True or
                row["raw_sha256"] != identity["sha256"] or row["size_bytes"] != identity["size_bytes"] or
                row["counts"] != counts[identity["relative_path"]] or not isinstance(row["diagnostics"], dict)):
            raise ValueError("preserved diagnostic recording identity/count mismatch")
    return {path: row["diagnostics"] for path, row in by_path.items()}


def run_exploratory_residuals(arguments: Any):
    output = arguments.output_directory.expanduser()
    if output.exists():
        raise FileExistsError(f"new output directory required: {output}")
    scratch = arguments.scratch_directory.expanduser().resolve(strict=True)
    if not scratch.is_dir() or shutil.disk_usage(scratch).free < pilot.MINIMUM_FREE_SCRATCH_BYTES:
        raise ValueError("scratch needs at least 10 GiB free on local disk")
    if pilot._available_memory_bytes() < pilot.MINIMUM_AVAILABLE_MEMORY_BYTES:
        raise ValueError("execution guard: at least 6 GiB MemAvailable required")
    records = pilot._inputs(arguments.mcap_root, arguments.registration, arguments.container_context)
    counts = pilot._preserved_counts(arguments.preserved_feasibility_report, records)
    diagnostics = _preserved_diagnostics(arguments.preserved_diagnostics_report, records, counts)
    try:
        versions = {"python": platform.python_version(), **{name: version(name) for name in
                    ("mcap", "mcap-protobuf-support", "protobuf", "numpy")}}
    except PackageNotFoundError as error:
        raise McapDependencyError("install the project MCAP extra before extraction") from error
    decoder_types()
    package = Path(__file__).resolve().parents[1]
    source_hashes = {p.relative_to(package).as_posix(): sha256_file(p) for p in sorted(package.rglob("*.py"))}
    for index, (path, identity, before) in enumerate(records, 1):
        LOGGER.info("Verifying registered raw bytes %d/4", index)
        if sha256_file(path) != identity["sha256"] or pilot._file_state(path) != before:
            raise ValueError("raw MCAP hash/file state changed before extraction")
    results = []
    for index, (path, identity, before) in enumerate(records, 1):
        LOGGER.info("Extracting recording %d/4 with disk-backed geometry and odometry", index)
        try:
            if pilot._file_state(path) != before:
                result = inconclusive("file_changed_before_decode")
            else:
                result = inspect_recording_residuals(path, scratch, counts[identity["relative_path"]], diagnostics[identity["relative_path"]])
                if pilot._file_state(path) != before:
                    result = inconclusive("file_changed_during_decode")
        except OSError:
            result = inconclusive("raw_file_unavailable_during_processing")
        results.append({"recording_id": f"recording_{index:02d}", "relative_path_private": identity["relative_path"],
            "raw_sha256": identity["sha256"], "size_bytes": identity["size_bytes"], **result})
    # Catch mutation of an earlier file while later recordings were processed.
    for index, (path, _, before) in enumerate(records):
        try:
            unchanged = pilot._file_state(path) == before
        except OSError:
            unchanged = False
        if not unchanged:
            results[index].update(inconclusive("file_changed_before_export"))
    complete = all(r["status"] == "complete" for r in results)
    candidates = []
    for result in results:
        rows = result.pop("candidates")
        if complete:
            for row in rows:
                row.update(recording_id=result["recording_id"], candidate_index=len(candidates))
                candidates.append(row)
    arrays, support = build_archive(candidates) if complete else (None, None)
    failures = Counter(code for row in candidates for code in row["condition_failure_codes"])
    residual_failures = Counter(row["residual_failure_code"] for row in candidates if row["residual_failure_code"] is not None)
    report = {"contract_revision": CONTRACT_REVISION,
        "purpose": "exploratory_recording_local_edp_rlmb_residuals_without_outing_admission",
        "status": "complete" if complete else "inconclusive",
        "registration_sha256": pilot.REGISTRATION_SHA256, "container_context_sha256": pilot.CONTEXT_SHA256,
        "preserved_feasibility_sha256": pilot.PRESERVED_REPORT_SHA256, "preserved_diagnostics_sha256": DIAGNOSTICS_SHA256,
        "runtime_versions": versions, "runtime_source_sha256": hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest(),
        "raw_hashes_verified": True, "physical_session_provenance": "unavailable_owner_report_2026-09-20",
        "independent_outing_count": None, "roles_assigned": False, "cohort_lock_created": False,
        "model_fitted": False, "standardizers_fitted": False, "residuals_exported": complete,
        "recorded_input_causality_checked": complete, "physical_input_availability_proven": False,
        "candidate_count": len(candidates) if complete else None,
        "condition_failure_counts": dict(sorted(failures.items())) if complete else None,
        "residual_failure_counts": dict(sorted(residual_failures.items())) if complete else None,
        "support": support, "recordings": results, "artifacts_sha256": {},
        "interpretation": "Exploratory EDP-minus-RLMB pseudo-residuals, not physical ground-truth errors or an eligible outing cohort. Geometric profiles and the complete-feature subset are separate. Speed preserves the fixed 50 ms displacement definition and requires all used odometry state times <= estimate source time and log times <= estimate log time. These recorded-clock checks do not establish clock equivalence or real vehicle availability. No file stitching, LANE_MAP pooling, split, fit or final-validation claim."}
    output.mkdir(parents=True, exist_ok=False)
    if complete:
        # No successful artifact is published from a partial four-file batch.
        # The summary is the completion marker and is written last with hashes.
        write_deterministic_npz(output / ARCHIVE_NAME, arrays)
        audit = [{**{k: v for k, v in row.items() if k not in ("residuals_m", "conditions")},
            "residual_available": row["residuals_m"] is not None,
            "conditions_available": row["conditions"] is not None} for row in candidates]
        write_strict_json(output / AUDIT_NAME, {"contract_revision": CONTRACT_REVISION, "rows": audit})
        report["artifacts_sha256"] = {name: sha256_file(output / name) for name in (ARCHIVE_NAME, AUDIT_NAME)}
    write_strict_json(output / SUMMARY_NAME, report)
    LOGGER.info("Extraction %s; %s geometric profiles, %s complete-feature profiles; no model fitted", report["status"],
        None if support is None else support["geometric_profile_count"],
        None if support is None else support["conditioned_profile_count"])
    return report, 0 if complete else 3
