from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from lane_residuals.domain.exploratory_residuals import build_archive
from lane_residuals.io.corpus_inventory import sha256_file
from lane_residuals.io.expanded_sequence_dataset import write_deterministic_npz
from lane_residuals.io.exploratory_archive import (
    ARCHIVE, AUDIT, LINEAGE, REVISION, SUMMARY, load_exploratory_archive,
)


def save_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False), encoding="utf-8")


class ArchiveValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        rows = []
        for i, recording in enumerate(("recording_01", "recording_01", "recording_02",
                                       "recording_03", "recording_04")):
            row = {"recording_id": recording, "candidate_index": i, "pair_index": i,
                   "estimate_message_index": i, "reference_message_index": i,
                   "estimate_source_time_ns_private": 2**64 - 10 + i,
                   "reference_source_time_ns_private": 2**64 - 10 + i,
                   "residuals_m": None if i == 2 else [float(i)] * 21,
                   "conditions": None if i == 3 else [float(i)] * 6}
            rows.append(row)
        arrays, support = build_archive(rows)
        write_deterministic_npz(self.path / ARCHIVE, arrays)
        audit_rows = []
        for row in rows:
            audit_rows.append({**{k: v for k, v in row.items() if k not in ("residuals_m", "conditions")},
                               "residual_available": row["residuals_m"] is not None,
                               "conditions_available": row["conditions"] is not None,
                               "condition_failure_codes": [] if row["conditions"] is not None else ["missing_speed"],
                               "residual_failure_code": None if row["residuals_m"] is not None else "geometry_failure"})
        save_json(self.path / AUDIT, {"contract_revision": REVISION, "rows": audit_rows})
        self.summary = {
            "contract_revision": REVISION, "purpose": "exploratory_recording_local_edp_rlmb_residuals_without_outing_admission",
            "status": "complete", "physical_session_provenance": "unavailable_owner_report_2026-09-20",
            "independent_outing_count": None, "roles_assigned": False, "cohort_lock_created": False,
            "model_fitted": False, "standardizers_fitted": False, "raw_hashes_verified": True,
            "residuals_exported": True, "recorded_input_causality_checked": True,
            "physical_input_availability_proven": False, "candidate_count": len(rows),
            "condition_failure_counts": dict(Counter(c for r in audit_rows for c in r["condition_failure_codes"])),
            "residual_failure_counts": {"geometry_failure": 1}, "support": support,
            "recordings": [{"recording_id": f"recording_{j:02d}", "status": "complete",
                            "legacy_counts_match_preserved": True, "diagnostics_match_preserved": True,
                            "failure_code": None,
                            "counts": {"sensor_anchored_h100_pair_count": [2, 1, 1, 1][j - 1]}}
                           for j in range(1, 5)], **LINEAGE}
        self.rehash()

    def rehash(self):
        self.summary["artifacts_sha256"] = {n: sha256_file(self.path / n) for n in (AUDIT, ARCHIVE)}
        save_json(self.path / SUMMARY, self.summary)
        self.expected_sha = sha256_file(self.path / SUMMARY)

    def read(self):
        return load_exploratory_archive(self.path, expected_summary_sha256=self.expected_sha)

    def test_valid_subset_and_uint64_identity(self):
        archive = self.read()
        self.assertEqual(archive.arrays["residuals_m"].shape, (4, 21))
        self.assertEqual(archive.conditioned_residuals_m[:, 0].tolist(), [0., 1., 4.])
        self.assertEqual(archive.arrays["estimate_source_time_ns_decimal"][0], str(2**64 - 10))
        self.assertFalse(archive.arrays["conditions"].flags.writeable)

    def test_rejects_wrong_published_summary_and_tampered_artifact(self):
        with self.assertRaisesRegex(ValueError, "pinned published result"):
            load_exploratory_archive(self.path)
        (self.path / AUDIT).write_bytes((self.path / AUDIT).read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.read()

    def test_rejects_rehashed_wrong_subset_without_relying_on_hash(self):
        with np.load(self.path / ARCHIVE, allow_pickle=False) as source:
            arrays = {key: source[key] for key in source.files}
        arrays["conditioned_profile_indices"] = np.array([0, 2, 3], dtype=np.int64)
        write_deterministic_npz(self.path / ARCHIVE, arrays)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "condition-to-profile mapping"):
            self.read()

    def test_rejects_rehashed_forged_temporal_support_and_identity(self):
        self.summary["support"]["geometry_transition_count"] += 1
        self.rehash()
        with self.assertRaisesRegex(ValueError, "geometry temporal support"):
            self.read()
        self.summary["support"]["geometry_transition_count"] -= 1
        audit = json.loads((self.path / AUDIT).read_text())
        audit["rows"][0]["estimate_source_time_ns_private"] -= 1
        save_json(self.path / AUDIT, audit)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "estimate timestamp mismatch"):
            self.read()


if __name__ == "__main__":
    unittest.main()
