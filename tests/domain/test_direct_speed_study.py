import copy
import unittest

from lane_residuals.domain.direct_speed_study import agreement, analyze, sequences, population
from lane_residuals.domain.velocity_source_ties import summarize as paired
from lane_residuals.domain.velocity_timing import TOPICS
from tests.io.velocity_timing_fixture import row, LOG, SOURCE


def update(topic,log,source,value=10,qualifier=1):
    return {"topic":topic,"log_ns":str(log),"publish_ns":str(SOURCE-1),"source_ns":str(source),
        "value":value,"qualifier":qualifier,"outer_qualifier":2,"standstill_status":0,"nested_present":True}


class StudyDomainTests(unittest.TestCase):
    def test_unchanged_primary_and_same_update_secondary_with_no_fallback(self):
        targets = [row(i) for i in range(3)]
        records = [update(t,LOG-10,SOURCE-10,value=8) for t in TOPICS]
        records += [update(t,LOG+100_000_000-10,SOURCE+100_000_000,value=10) for t in TOPICS]
        records += [update(t,LOG+200_000_000-10,SOURCE+200_000_000-10,value=11,qualifier=255) for t in TOPICS]
        old,old_frames = paired(records,targets)
        result,frames = analyze(records,targets,{0:8,1:10,2:11})
        for frame,original in zip(frames,old_frames):
            for key,value in original.items():self.assertEqual(frame[key],value)
        for topic in TOPICS:
            rules = result["topics"][topic]["rules"]
            self.assertEqual(rules["primary"]["support"]["frames"],2)
            self.assertEqual(rules["strict_source_secondary"]["support"]["frames"],1)
            self.assertEqual(rules["primary"]["agreement_on_original_complete_rows"]["bias_mps"],0)
        self.assertFalse(result["topics"][TOPICS[0]]["primary_temporal_target_met"])

    def test_geometry_and_estimate_feature_failures_remain_excluded(self):
        targets = [row(i) for i in range(2)]
        targets[0]["residual_available"] = False
        targets[1]["condition_failure_codes"] = ["estimate_features_unavailable"]
        records = [update(t,LOG-1,SOURCE-1) for t in TOPICS]
        result,_ = analyze(records,targets,{})
        for item in result["topics"].values():
            self.assertEqual(item["geometry_without_estimate_failure_rows"],0)
            self.assertIsNone(item["rules"]["primary"]["stratum_coverage"])
            self.assertFalse(item["primary_temporal_target_met"])

    def test_run_lists_keep_pair_message_recording_and_gap_resets(self):
        rows = [row(i) for i in range(7)]
        rows[3]["pair_index"] += 1
        rows[4]["recording_id"] = "other"
        rows[6]["estimate_source_time_ns_decimal_private"] = str(SOURCE+2_000_000_000)
        result = sequences(rows,[True]*7)
        self.assertEqual([r["frames"] for r in result["runs"]],[3,1,1,1,1])
        with self.assertRaisesRegex(ValueError,"mask_length"):
            sequences(rows,[True])

    def test_agreement_missing_zero_range_and_predeclared_bounds(self):
        self.assertIsNone(agreement([])["within_provisional_tolerances"])
        result = agreement([(5,5),(5,5)])
        self.assertIsNone(result["maximum_difference_over_combined_range"])
        self.assertTrue(result["within_provisional_tolerances"])
        self.assertTrue(agreement([(5,5.5)])["within_provisional_tolerances"])
        self.assertFalse(agreement([(5,6)])["within_provisional_tolerances"])

    def test_negative_values_are_observed_without_abs_or_policy_change(self):
        result,frames = analyze([update(t,LOG-1,SOURCE-1,value=-2) for t in TOPICS],[row(0)],{0:2})
        self.assertEqual(result["topics"][TOPICS[0]]["negative_retained_value_count"],1)
        self.assertEqual(frames[0]["candidate_value_native_units"],-2)
        self.assertEqual(result["topics"][TOPICS[0]]["rules"]["primary"]["agreement_on_original_complete_rows"]["bias_mps"],-4)

    def test_population_is_per_outing_and_missing_class_stays_unassessable(self):
        import numpy as np
        from types import SimpleNamespace
        rows = [row(i) for i in range(3)]
        rows[1].update(conditions_available=False,condition_failure_codes=["speed_uses_future_source_sample"])
        rows[2].update(conditions_available=False,condition_failure_codes=["estimate_features_missing"])
        arrays = {"recording_id":np.array(["synthetic"]*3),"candidate_index":np.arange(3),
            "residuals_m":np.tile([[1.],[3.],[99.]],(1,21)),"stations_m":np.arange(21)*5}
        block = SimpleNamespace(outing_id="a",archive=SimpleNamespace(arrays=arrays,summary_sha256="a"*64))
        second = copy.deepcopy(block);second.outing_id="b"
        report,stations = population([block,second],{"a":rows,"b":[row(i) for i in range(3)]})
        self.assertEqual(stations[0]["future_only_minus_complete_mean_m"],2)
        self.assertEqual(stations[0]["original_complete_count"],1)
        self.assertIsNone(stations[21]["future_only_minus_complete_mean_m"])
        self.assertEqual(report["outings"][0]["other_rows"],1)
        self.assertFalse(report["frame_independence_assumed"])
        arrays["candidate_index"][2] = 1
        with self.assertRaisesRegex(ValueError,"geometry_identity"):
            population([block],{"a":rows})
