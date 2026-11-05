import copy,math,unittest
from lane_residuals.domain.speed_disagreement import bracket,summarize
from lane_residuals.domain.direct_speed_study import analyze
from lane_residuals.domain.velocity_timing import TOPICS
from tests.io.velocity_timing_fixture import row,LOG,SOURCE

class DisagreementDomainTests(unittest.TestCase):
    def frames(self):
        targets=[row(0)]
        s=str(SOURCE)
        targets[0]['speed_bracket_evidence']={'previous_lower_timestamp_ns_decimal_private':str(SOURCE-60_000_000),'previous_upper_timestamp_ns_decimal_private':str(SOURCE-40_000_000),'current_lower_timestamp_ns_decimal_private':s,'current_upper_timestamp_ns_decimal_private':s}
        events=[{'topic':t,'log_ns':str(LOG-1),'source_ns':s,'publish_ns':str(SOURCE-1),'value':14.,'qualifier':1,'nested_present':True} for t in TOPICS]
        _,frames=analyze(events,targets,{0:10.})
        return targets,frames
    def test_integer_bracket_above_float_exact_range(self):
        v=bracket('18014398509481989','18014398509481984','18014398509481994')
        self.assertEqual(v['fraction'],.5);self.assertEqual(v['span_ns'],'10')
    def test_exact_missing_and_invalid_stay_distinct(self):
        self.assertEqual(bracket('10','10','10')['state'],'exact')
        self.assertEqual(bracket('10',None,'10')['state'],'missing')
        for low,high in (('11','12'),('12','11'),('0','10')):self.assertEqual(bracket('10',low,high)['state'],'invalid')
    def test_malformed_stamp_is_not_coerced(self):
        for x in (True,1.0,'01','1.0'):
            with self.subTest(x=x),self.assertRaises(ValueError):bracket('10',x,'11')
    def test_second_crossing(self):self.assertTrue(bracket('1000000000','999999999','1000000001')['crosses_second'])
    def test_masks_values_and_inputs_unchanged(self):
        targets,frames=self.frames();before=copy.deepcopy((targets,frames));a,rows=summarize(targets,frames)
        self.assertEqual((targets,frames),before);self.assertEqual(len(rows),2)
        self.assertTrue(rows[0]['primary_complete']);self.assertFalse(rows[0]['strict_source_complete'])
        self.assertEqual(rows[0]['candidate_speed_mps'],14.);self.assertEqual(rows[0]['candidate_minus_old_mps'],4.)
        self.assertFalse(a['cause_identified']);self.assertFalse(a['speed_feature_adopted'])
    def test_frozen_limit_exceedance_and_empty_group(self):
        targets,frames=self.frames();a,rows=summarize(targets,frames)
        self.assertTrue(rows[0]['exceeds_frozen_maximum_difference'])
        group=next(g for g in a['groups'] if g['topic']==TOPICS[0] and g['group']=='source_earlier')
        self.assertEqual(group['rows'],0);self.assertIsNone(group['within_provisional_tolerances'])
    def test_missing_brackets_remain_unknown_not_exact(self):
        targets,frames=self.frames();targets[0]['speed_bracket_evidence']={}
        a,rows=summarize(targets,frames);self.assertEqual(rows[0]['previous_bracket_state'],'missing')
        self.assertEqual(next(g for g in a['groups'] if g['topic']==TOPICS[0] and g['group']=='previous_unknown')['rows'],1)
    def test_missing_old_is_not_filled(self):
        targets,frames=self.frames()
        for r in frames:r['old_speed_mps']=None;r['original_local_complete']=False
        _,rows=summarize(targets,frames);self.assertIsNone(rows[0]['candidate_minus_old_mps'])
    def test_shared_missing_value_refused(self):
        targets,frames=self.frames();frames[0]['old_speed_mps']=None
        with self.assertRaisesRegex(ValueError,'shared_value_missing'):summarize(targets,frames)
    def test_nonfinite_and_boolean_value_refused(self):
        for value in (math.inf,math.nan,True):
            targets,frames=self.frames();frames[0]['old_speed_mps']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'finite_value'):summarize(targets,frames)
    def test_duplicate_or_missing_frames_refused(self):
        targets,frames=self.frames()
        with self.assertRaisesRegex(ValueError,'frame_identity'):summarize(targets,frames+[frames[0]])
        with self.assertRaisesRegex(ValueError,'missing_frame'):summarize(targets,frames[:1])
    def test_duplicate_target_refused(self):
        targets,frames=self.frames()
        with self.assertRaisesRegex(ValueError,'duplicate_target'):summarize(targets+targets,frames)
