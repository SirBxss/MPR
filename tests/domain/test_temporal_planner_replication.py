"""Independent weighting, clock binning and replication decision checks."""

from copy import deepcopy
import unittest

import numpy as np

from lane_residuals.domain import temporal_planner_pilot as pilot, temporal_planner_replication as policy


def score_table(records, differences):
    table = []
    for record, difference in zip((r for r in records if r["status"] == "eligible"), differences):
        arms = {arm: {policy.ENERGY: 3.0, policy.MARGINAL: 2.0,
                      policy.LATERAL: .2 if record["frame_count"] >= 3 else None} for arm in pilot.ARMS}
        arms["one_state_ar"][policy.ENERGY] += difference
        arms["stationary_ar"][policy.ENERGY] += difference / 2
        table.append(dict(sequence_index=record["sequence_index"], frame_count=record["frame_count"], arms=arms))
    result = dict(eligible_sequences=len(table), sequence_scores=table,
                  arms={arm: {key: float(np.mean([s["arms"][arm][key] for s in table
                                                  if s["arms"][arm][key] is not None]))
                              if any(s["arms"][arm][key] is not None for s in table) else None
                              for key in policy.METRICS} for arm in pilot.ARMS},
                  temporal_minus_permuted_energy_mps2={"one_state_ar": float(np.mean(differences)),
                                                        "stationary_ar": float(np.mean(differences) / 2)})
    return result


def record(index, seconds, length=3, status="eligible"):
    return dict(sequence_index=index, frame_count=length, status=status,
                source_start_ns_decimal=str(10**19 + seconds * 1_000_000_000))


class TemporalReplicationPolicyTests(unittest.TestCase):
    def test_blocks_use_all_sequence_origin_integer_epochs_and_pooled_weights(self):
        records = [record(0, 0, 1, "singleton"), record(1, 59, 2), record(2, 60, 3),
                   record(3, 61, 14), record(4, 90), record(5, 120), record(6, 150)]
        differences = [-.1, -.2, -.9, .4, .5, 0.]
        scores = score_table(records, differences)
        result = policy.diagnose(scores, scores, records)["one_state_ar"]
        self.assertEqual(result["nonempty_source_bins"], [1, 2, 3, 4, 5])
        self.assertEqual(result["source_origin_ns_decimal"], str(10**19))
        groups = [[-.1], [-.2, -.9], [.4], [.5], [0.]]
        rng = np.random.default_rng(193002)
        resampled = []
        for _ in range(1000):
            values = [x for i in rng.integers(5, size=5) for x in groups[i]]
            resampled.append(sum(values) / len(values))
        np.testing.assert_allclose(result["descriptive_95_block_interval_mps2"],
                                   np.quantile(resampled, [.025, .975]), atol=1e-15)
        self.assertEqual((result["negative_sequences"], result["positive_sequences"], result["tied_sequences"]), (3, 2, 1))
        self.assertEqual(result["length_groups"][-1]["sequences"], 1)
        self.assertAlmostEqual(result["length_groups"][-1]["mean_difference_mps2"], -.9)
        self.assertIsNone(result["length_groups"][2]["mean_difference_mps2"])

    def test_fewer_than_five_bins_marks_interval_unavailable(self):
        records = [record(0, 0, 2)]
        scores = score_table(records, [0.])
        result = policy.diagnose(scores, scores, records)["one_state_ar"]
        self.assertIsNone(result["descriptive_95_block_interval_mps2"])
        self.assertEqual(result["tied_sequences"], 1)

    def test_score_validation_rejects_nan_wrong_census_and_wrong_mean(self):
        records = [record(0, 0)]
        for kind in ("nan", "census", "mean", "lateral"):
            scores = score_table(records, [-.2])
            if kind == "nan":
                scores["sequence_scores"][0]["arms"]["one_state_ar"][policy.ENERGY] = float("nan")
            elif kind == "census":
                scores["sequence_scores"][0]["sequence_index"] = 1
            elif kind == "mean":
                scores["arms"]["one_state_ar"][policy.ENERGY] += .01
            else:
                scores["sequence_scores"][0]["arms"]["one_state_ar"][policy.LATERAL] = None
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                policy.validate_scores(scores, records)

    def folds(self, differences):
        result = {}
        for i, delta in enumerate(differences):
            # Unequal numbers of sequences must not change an outing's weight.
            records = [record(j, j) for j in range(i+1)]
            scores = score_table(records, [delta] * len(records))
            result[str(i)] = dict(scores=scores, prefix_scores=deepcopy(scores))
        return result

    def test_equal_outing_weights_and_separate_six_outing_rule(self):
        folds = self.folds([1., -.1, -.2, -.3, -.4, .1, .2])
        summary = policy.summarize_outings(folds, "0")
        self.assertAlmostEqual(summary["six_beyond_pilot"]["temporal_contrasts"]["one_state_ar"]["mean_difference_mps2"], -.7/6)
        self.assertAlmostEqual(summary["all_seven"]["temporal_contrasts"]["one_state_ar"]["mean_difference_mps2"], .3/7)
        self.assertTrue(summary["descriptive_primary_replication_passes"])
        self.assertEqual(summary["six_beyond_pilot"]["outing_ids"], [str(i) for i in range(1, 7)])

    def test_sign_rule_requires_both_conditions_and_strict_negativity(self):
        for differences, expected in (([0., -.1, -.1, -.1, -.1, 1., 1.], False),
                                      ([0., -1., -1., -1., 0., 0., 0.], False),
                                      ([0., -.1, -.1, -.1, -.1, .1, .1], True),
                                      ([0.] * 7, False)):
            summary = policy.summarize_outings(self.folds(differences), "0")
            self.assertEqual(summary["descriptive_primary_replication_passes"], expected)

    def test_missing_primary_blocks_and_missing_secondary_is_explicit(self):
        folds = self.folds([-.1] * 7)
        self.assertRaises(ValueError, policy.summarize_outings, {k: v for k, v in folds.items() if k != "6"}, "0")
        for key in ("scores", "prefix_scores"):
            for arm in pilot.ARMS:
                folds["6"][key]["arms"][arm][policy.LATERAL] = None
        summary = policy.summarize_outings(folds, "0")
        self.assertEqual(summary["six_beyond_pilot"]["outings_without_lateral_support"], ["6"])
        self.assertIsNone(summary["all_seven"]["arms"]["one_state_ar"][policy.LATERAL])
        self.assertIsInstance(summary["all_seven"]["arms"]["one_state_ar"][policy.ENERGY], float)


if __name__ == "__main__":
    unittest.main()
