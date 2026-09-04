"""Pure v0.17 independent-outing intake and cohort-lock rules.

The module contains no MCAP, modeling, planner, sampling, evaluation, or
visualization dependency.  Private labels are used only as manifest keys;
cohort assignment depends exclusively on immutable raw-content hashes.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence


VERSION = "0.17.0"
MANIFEST_VERSION = "0.17"
PURPOSE = "independent_outing_intake_and_cohort_lock"
MANIFEST_PURPOSE = "prospective_independent_outing_intake"
CONTRACT_REVISION = "v0.17.0-reviewed-2026-09-03-layout-c1"
SPLIT_SALT = b"MPR-v0.17-final-split-v1"
MINIMUM_ELIGIBLE_NEW_OUTING_COUNT = 7
MINIMUM_USABLE_DURATION_NS = 120_000_000_000
MINIMUM_ELIGIBLE_FRAME_COUNT = 500
MAXIMUM_SEQUENCE_GAP_NS = 200_000_000
MAXIMUM_ANCHOR_DISTANCE_M = 1.0
ODOMETRY_INTERPOLATION_GAP_NS = 50_000_000
EXPECTED_TOPOLOGY_SOURCE = "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY"

_TOP_LEVEL_FIELDS = frozenset(
    {
        "version",
        "purpose",
        "acquisition_batch_closed",
        "created_before_outcome_inspection",
        "legacy_development_outing_count",
        "prior_successful_lock_sha256",
        "superseding_contract_amendment_id",
        "outings",
    }
)
_OUTING_FIELDS = frozenset(
    {
        "private_outing_label",
        "acquisition_start_utc",
        "separate_physical_session",
        "independence_basis_private",
        "mcap_basenames_private",
    }
)


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str], name: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{name} fields differ: missing={missing}, extra={extra}")


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _lowercase_sha256(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _timezone_aware_iso8601(value: Any, name: str) -> str:
    text = _nonempty_string(value, name)
    parse_value = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(parse_value)
    except ValueError as error:
        raise ValueError(f"{name} must be ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a UTC offset")
    return text


@dataclass(frozen=True)
class ManifestOuting:
    """One prospectively declared physical outing."""

    private_outing_label: str
    acquisition_start_utc: str
    separate_physical_session: bool
    independence_basis_private: str
    mcap_basenames_private: tuple[str, ...]


@dataclass(frozen=True)
class AcquisitionManifest:
    """Strict, outcome-blind acquisition declaration."""

    acquisition_batch_closed: bool
    created_before_outcome_inspection: bool
    legacy_development_outing_count: int
    prior_successful_lock_sha256: str | None
    superseding_contract_amendment_id: str | None
    outings: tuple[ManifestOuting, ...]

    @property
    def basename_to_private_label(self) -> dict[str, str]:
        return {
            basename: outing.private_outing_label
            for outing in self.outings
            for basename in outing.mcap_basenames_private
        }

    @property
    def is_superseding(self) -> bool:
        return self.prior_successful_lock_sha256 is not None


def parse_acquisition_manifest(payload: Any) -> AcquisitionManifest:
    """Validate the exact prospective manifest schema without normalization."""

    if not isinstance(payload, Mapping):
        raise ValueError("acquisition manifest must be a JSON object")
    _exact_fields(payload, _TOP_LEVEL_FIELDS, "acquisition manifest")
    if payload["version"] != MANIFEST_VERSION:
        raise ValueError(f"manifest version must be {MANIFEST_VERSION!r}")
    if payload["purpose"] != MANIFEST_PURPOSE:
        raise ValueError(f"manifest purpose must be {MANIFEST_PURPOSE!r}")
    for field in ("acquisition_batch_closed", "created_before_outcome_inspection"):
        if type(payload[field]) is not bool or payload[field] is not True:
            raise ValueError(f"{field} must be literally true")
    legacy_count = payload["legacy_development_outing_count"]
    if type(legacy_count) is not int or legacy_count != 1:
        raise ValueError("legacy_development_outing_count must be integer 1")

    prior_raw = payload["prior_successful_lock_sha256"]
    prior = None if prior_raw is None else _lowercase_sha256(
        prior_raw, "prior_successful_lock_sha256"
    )
    amendment_raw = payload["superseding_contract_amendment_id"]
    amendment = None if amendment_raw is None else _nonempty_string(
        amendment_raw, "superseding_contract_amendment_id"
    )
    if (prior is None) != (amendment is None):
        raise ValueError(
            "prior_successful_lock_sha256 and superseding_contract_amendment_id "
            "must both be null or both be non-null"
        )

    raw_outings = payload["outings"]
    if not isinstance(raw_outings, list) or not raw_outings:
        raise ValueError("outings must be a nonempty array")
    outings: list[ManifestOuting] = []
    labels: set[str] = set()
    all_basenames: set[str] = set()
    for index, raw in enumerate(raw_outings):
        name = f"outings[{index}]"
        if not isinstance(raw, Mapping):
            raise ValueError(f"{name} must be an object")
        _exact_fields(raw, _OUTING_FIELDS, name)
        label = _nonempty_string(raw["private_outing_label"], f"{name}.private_outing_label")
        if label in labels:
            raise ValueError("private_outing_label values must be unique")
        timestamp = _timezone_aware_iso8601(
            raw["acquisition_start_utc"], f"{name}.acquisition_start_utc"
        )
        if type(raw["separate_physical_session"]) is not bool or raw[
            "separate_physical_session"
        ] is not True:
            raise ValueError(f"{name}.separate_physical_session must be literally true")
        basis = _nonempty_string(
            raw["independence_basis_private"], f"{name}.independence_basis_private"
        )
        raw_basenames = raw["mcap_basenames_private"]
        if not isinstance(raw_basenames, list) or not raw_basenames:
            raise ValueError(f"{name}.mcap_basenames_private must be a nonempty array")
        basenames: list[str] = []
        local: set[str] = set()
        for basename_raw in raw_basenames:
            basename = _nonempty_string(
                basename_raw, f"{name}.mcap_basenames_private item"
            )
            if (
                basename != basename.replace("\\", "/").split("/")[-1]
                or not basename.lower().endswith(".mcap")
            ):
                raise ValueError("manifest MCAP entries must be unqualified .mcap basenames")
            if basename in local or basename in all_basenames:
                raise ValueError("manifest MCAP basenames must be globally unique")
            local.add(basename)
            all_basenames.add(basename)
            basenames.append(basename)
        labels.add(label)
        outings.append(
            ManifestOuting(
                private_outing_label=label,
                acquisition_start_utc=timestamp,
                separate_physical_session=True,
                independence_basis_private=basis,
                mcap_basenames_private=tuple(basenames),
            )
        )
    return AcquisitionManifest(
        acquisition_batch_closed=True,
        created_before_outcome_inspection=True,
        legacy_development_outing_count=legacy_count,
        prior_successful_lock_sha256=prior,
        superseding_contract_amendment_id=amendment,
        outings=tuple(outings),
    )


@dataclass(frozen=True)
class FrameTechnicalEvidence:
    """Outcome-blind eligibility state for one decoded EDP message."""

    estimate_message_index: int
    source_time_ns: int | None
    topology_source_name: str
    topology_gate_candidate: bool
    h100_geometry_ready: bool
    anchor_distance_within_limit: bool
    causal_inputs_available: bool
    raw_usable: bool
    eligible: bool
    failure_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.estimate_message_index) is not int or self.estimate_message_index < 0:
            raise ValueError("estimate_message_index must be a nonnegative integer")
        if self.source_time_ns is not None and (
            type(self.source_time_ns) is not int or self.source_time_ns < 0
        ):
            raise ValueError("source_time_ns must be a nonnegative integer or null")
        if not self.topology_source_name:
            raise ValueError("topology_source_name must be nonempty")
        if len(self.failure_codes) != len(set(self.failure_codes)):
            raise ValueError("frame failure codes must be unique")
        expected = bool(
            self.source_time_ns is not None
            and self.topology_source_name == EXPECTED_TOPOLOGY_SOURCE
            and self.topology_gate_candidate
            and self.h100_geometry_ready
            and self.anchor_distance_within_limit
            and self.causal_inputs_available
            and self.raw_usable
        )
        if self.eligible != expected:
            raise ValueError("eligible frame state is inconsistent with fixed v0.17 gates")


@dataclass(frozen=True)
class RecordingTechnicalEvidence:
    """Technical counts retained for one MCAP without numeric frame values."""

    estimate_message_count: int
    map_message_count: int
    frames: tuple[FrameTechnicalEvidence, ...]
    failure_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if min(self.estimate_message_count, self.map_message_count) < 0:
            raise ValueError("message counts must be nonnegative")
        indices = [frame.estimate_message_index for frame in self.frames]
        if indices != sorted(indices) or len(indices) != len(set(indices)):
            raise ValueError("technical frames must have unique ordered message indices")
        if len(self.failure_codes) != len(set(self.failure_codes)):
            raise ValueError("recording failure codes must be unique")

    @property
    def topology_candidate_count(self) -> int:
        return sum(frame.topology_gate_candidate for frame in self.frames)

    @property
    def sensor_topology_candidate_count(self) -> int:
        return sum(
            frame.topology_gate_candidate
            and frame.topology_source_name == EXPECTED_TOPOLOGY_SOURCE
            for frame in self.frames
        )

    @property
    def non_sensor_topology_candidate_count(self) -> int:
        return self.topology_candidate_count - self.sensor_topology_candidate_count

    @property
    def eligible_frame_count(self) -> int:
        return sum(frame.eligible for frame in self.frames)


@dataclass(frozen=True)
class OutingEligibilityEvidence:
    raw_usable_recording_count: int
    usable_duration_ns: int
    usable_intervals_monotonic_nonoverlapping: bool
    topology_candidate_count: int
    non_sensor_topology_candidate_count: int
    eligible_frame_count: int
    sequence_count: int
    retained_eligible_frame_count: int


@dataclass(frozen=True)
class OutingEligibility:
    technically_eligible: bool
    has_raw_usable_recording: bool
    usable_duration_passes: bool
    topology_passes: bool
    eligible_frame_count_passes: bool
    sequence_integrity_passes: bool
    failure_codes: tuple[str, ...]


def evaluate_outing_eligibility(evidence: OutingEligibilityEvidence) -> OutingEligibility:
    """Apply the fixed 120 s, topology, 500-frame, and sequence gates."""

    if min(
        evidence.raw_usable_recording_count,
        evidence.usable_duration_ns,
        evidence.topology_candidate_count,
        evidence.non_sensor_topology_candidate_count,
        evidence.eligible_frame_count,
        evidence.sequence_count,
        evidence.retained_eligible_frame_count,
    ) < 0:
        raise ValueError("outing evidence counts must be nonnegative")
    if evidence.non_sensor_topology_candidate_count > evidence.topology_candidate_count:
        raise ValueError("non-sensor topology count exceeds candidate count")
    has_raw = evidence.raw_usable_recording_count >= 1
    duration = (
        evidence.usable_intervals_monotonic_nonoverlapping
        and evidence.usable_duration_ns >= MINIMUM_USABLE_DURATION_NS
    )
    topology = evidence.non_sensor_topology_candidate_count == 0
    frames = evidence.eligible_frame_count >= MINIMUM_ELIGIBLE_FRAME_COUNT
    sequence_integrity = (
        evidence.sequence_count >= 1
        and evidence.retained_eligible_frame_count == evidence.eligible_frame_count
    )
    failures: list[str] = []
    if not has_raw:
        failures.append("no_raw_usable_recording")
    if not evidence.usable_intervals_monotonic_nonoverlapping:
        failures.append("usable_source_intervals_overlap_or_are_not_monotonic")
    if evidence.usable_duration_ns < MINIMUM_USABLE_DURATION_NS:
        failures.append("usable_duration_below_120s")
    if not topology:
        failures.append("mixed_or_unknown_topology_source")
    if not frames:
        failures.append("eligible_frame_count_below_500")
    if not sequence_integrity:
        failures.append("eligible_sequence_integrity_failed")
    return OutingEligibility(
        technically_eligible=has_raw and duration and topology and frames and sequence_integrity,
        has_raw_usable_recording=has_raw,
        usable_duration_passes=duration,
        topology_passes=topology,
        eligible_frame_count_passes=frames,
        sequence_integrity_passes=sequence_integrity,
        failure_codes=tuple(failures),
    )


def outing_fingerprint_sha256(file_sha256_values: Sequence[str]) -> str:
    """Hash the sorted raw-content multiset; basenames never enter this path."""

    if not file_sha256_values:
        raise ValueError("outing fingerprint requires at least one file hash")
    values = sorted(
        _lowercase_sha256(value, "outing file SHA-256")
        for value in file_sha256_values
    )
    encoded = b"".join(value.encode("ascii") + b"\n" for value in values)
    return hashlib.sha256(encoded).hexdigest()


def split_score_sha256(outing_fingerprint: str) -> str:
    fingerprint = _lowercase_sha256(
        outing_fingerprint, "outing_fingerprint_sha256"
    )
    return hashlib.sha256(
        SPLIT_SALT + b"\0" + fingerprint.encode("ascii")
    ).hexdigest()


def fixed_final_count(eligible_new_outing_count: int) -> int:
    if type(eligible_new_outing_count) is not int or eligible_new_outing_count < 0:
        raise ValueError("eligible_new_outing_count must be a nonnegative integer")
    return max(2, math.ceil((eligible_new_outing_count + 1) / 5))


@dataclass(frozen=True)
class CohortAssignment:
    outing_id: str
    outing_fingerprint_sha256: str
    split_score_sha256: str | None
    split_rank: int | None
    cohort_role: str | None


def assign_cohorts(
    fingerprints_by_label: Mapping[str, str],
    eligible_private_labels: Sequence[str],
) -> tuple[dict[str, CohortAssignment], int | None, bool]:
    """Assign opaque IDs independently from content-only split-score ranking."""

    if not fingerprints_by_label:
        raise ValueError("at least one declared outing is required")
    validated = {
        _nonempty_string(label, "private outing label"): _lowercase_sha256(
            fingerprint, "outing fingerprint"
        )
        for label, fingerprint in fingerprints_by_label.items()
    }
    if len(set(validated.values())) != len(validated):
        raise ValueError("declared outing fingerprints must be unique")
    eligible = set(eligible_private_labels)
    if not eligible.issubset(validated):
        raise ValueError("eligible labels must be declared outings")

    opaque_order = sorted(validated, key=lambda label: bytes.fromhex(validated[label]))
    opaque_ids = {
        label: f"outing_{index:03d}" for index, label in enumerate(opaque_order, 1)
    }
    gate_passed = len(eligible) >= MINIMUM_ELIGIBLE_NEW_OUTING_COUNT
    if not gate_passed:
        return (
            {
                label: CohortAssignment(
                    outing_id=opaque_ids[label],
                    outing_fingerprint_sha256=validated[label],
                    split_score_sha256=None,
                    split_rank=None,
                    cohort_role=None,
                )
                for label in validated
            },
            None,
            False,
        )

    final_count = fixed_final_count(len(eligible))
    if not 2 <= final_count < len(eligible):
        raise AssertionError("fixed final-count invariant failed")
    score_by_label = {
        label: split_score_sha256(validated[label]) for label in eligible
    }
    split_order = sorted(
        eligible,
        key=lambda label: (
            bytes.fromhex(score_by_label[label]),
            bytes.fromhex(validated[label]),
        ),
    )
    rank_by_label = {label: index for index, label in enumerate(split_order, 1)}
    assignments = {
        label: CohortAssignment(
            outing_id=opaque_ids[label],
            outing_fingerprint_sha256=validated[label],
            split_score_sha256=(score_by_label[label] if label in eligible else None),
            split_rank=(rank_by_label[label] if label in eligible else None),
            cohort_role=(
                "excluded"
                if label not in eligible
                else "final_test"
                if rank_by_label[label] <= final_count
                else "development"
            ),
        )
        for label in validated
    }
    return assignments, final_count, True


__all__ = [
    "AcquisitionManifest",
    "CONTRACT_REVISION",
    "CohortAssignment",
    "EXPECTED_TOPOLOGY_SOURCE",
    "FrameTechnicalEvidence",
    "MANIFEST_PURPOSE",
    "MANIFEST_VERSION",
    "MAXIMUM_ANCHOR_DISTANCE_M",
    "MAXIMUM_SEQUENCE_GAP_NS",
    "MINIMUM_ELIGIBLE_FRAME_COUNT",
    "MINIMUM_ELIGIBLE_NEW_OUTING_COUNT",
    "MINIMUM_USABLE_DURATION_NS",
    "ManifestOuting",
    "ODOMETRY_INTERPOLATION_GAP_NS",
    "OutingEligibility",
    "OutingEligibilityEvidence",
    "PURPOSE",
    "RecordingTechnicalEvidence",
    "SPLIT_SALT",
    "VERSION",
    "assign_cohorts",
    "evaluate_outing_eligibility",
    "fixed_final_count",
    "outing_fingerprint_sha256",
    "parse_acquisition_manifest",
    "split_score_sha256",
]
