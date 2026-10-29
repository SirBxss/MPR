import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from lane_residuals.io import speed_mechanism as io
from lane_residuals.domain.speed_mechanism import REVISION
from tests.domain.test_speed_mechanism import row


def fixture():
    objects,events,blocks,supports={},[],[],[]
    for i in range(3):
        outing=f"synthetic_{i}";rows=[row(0),row(1,False,False)]
        audit=json.dumps({"rows":rows}).encode();audit_pin=hashlib.sha256(audit).hexdigest()
        summary=json.dumps({"pre_residual_candidate_count":2,"artifacts_sha256":{"candidate_audit.json":audit_pin}}).encode()
        pin=hashlib.sha256(summary).hexdigest()
        objects[audit_pin]=audit;objects[pin]=summary
        events.append({"kind":"archive","files":{"numeric/numeric_export.json":pin,"numeric/candidate_audit.json":audit_pin}})
        blocks.append(SimpleNamespace(outing_id=outing,archive=SimpleNamespace(summary_sha256=pin,raw_sha256_by_recording={"synthetic":str(i)*64})))
        supports.append({"outing_id":outing,"archive_sha256":pin,"geometry_vectors":2,"complete_feature_rows":1,
            "maximum_complete_sequence_duration_ns":0,"maximum_complete_sequence_frames":1})
    context=SimpleNamespace(objects=objects,metadata={"events":events},cohort={"outings":[
        {"outing_id":f"synthetic_{i}","cohort_role":"development"} for i in range(3)]+[{"outing_id":"final","cohort_role":"final_test"}]},
        cohort_sha256="c"*64,registry_sha256="d"*64)
    inputs=SimpleNamespace(context=context,blocks=blocks,watched={},file_sets={},unchanged=Mock())
    return inputs,{"archives":supports}


class MechanismInputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.path=self.base/"request.json"
        self.request={"revision":REVISION,"experiment_directory":"experiment","experiment_sha256":"a"*64,
            "previously_examined_outing_id":"synthetic_0"}
        self.inputs,self.manifest=fixture()

    def save(self):
        data=json.dumps(self.request).encode();self.path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def load(self):
        pin=self.save()
        with patch.object(io.original,"load_experiment",return_value=(self.inputs,self.manifest)) as native:
            result=io.load(self.base,self.path,pin)
            self.assertEqual(native.call_count,1)
            return result

    def test_positive_reuses_native_validator_and_binds_all_audits(self):
        loaded=self.load()
        self.assertEqual(len(loaded["outings"]),3)
        self.assertEqual(sum(o["previously_examined"] for o in loaded["outings"]),1)
        self.inputs.unchanged.assert_called_once()
        self.assertEqual(self.inputs.watched[self.path],loaded["request_sha256"])

    def test_closed_request_and_digest_fail_before_native_replay(self):
        pin=self.save()
        with patch.object(io.original,"load_experiment",side_effect=AssertionError("not called")):
            with self.assertRaises(ValueError):io.load(self.base,self.path,"0"*64)
            self.request["raw_path"]="forbidden.mcap";pin=self.save()
            with self.assertRaises(ValueError):io.load(self.base,self.path,pin)

    def test_native_role_or_history_failure_is_propagated(self):
        pin=self.save()
        with patch.object(io.original,"load_experiment",side_effect=ValueError("locked_final_evidence_invalidated_no_reroll")):
            with self.assertRaisesRegex(ValueError,"locked_final"):
                io.load(self.base,self.path,pin)

    def test_final_missing_and_duplicate_outings_are_rejected(self):
        for mode in ("final","missing","duplicate"):
            with self.subTest(mode=mode):
                self.inputs,self.manifest=fixture()
                if mode=="final":self.inputs.blocks[0].outing_id="final"
                elif mode=="missing":self.inputs.blocks.pop()
                else:self.inputs.blocks.append(self.inputs.blocks[0])
                with self.assertRaisesRegex(ValueError,"development_coverage"):
                    self.load()

    def test_audit_digest_or_recording_drift_is_rejected(self):
        pin=self.manifest["archives"][0]["archive_sha256"]
        summary=json.loads(self.inputs.context.objects[pin]);audit_pin=summary["artifacts_sha256"]["candidate_audit.json"]
        self.inputs.context.objects[audit_pin]+=b" "
        with self.assertRaisesRegex(ValueError,"audit_object_digest"):self.load()
        self.inputs,self.manifest=fixture();self.inputs.blocks[0].archive.raw_sha256_by_recording={"wrong":"0"*64}
        with self.assertRaisesRegex(ValueError,"recording_or_support"):self.load()

    def test_bad_original_counts_and_unknown_prior_case_are_rejected(self):
        self.manifest["archives"][0]["complete_feature_rows"]=0
        with self.assertRaisesRegex(ValueError,"candidate_counts"):self.load()
        self.inputs,self.manifest=fixture();self.request["previously_examined_outing_id"]="unknown"
        with self.assertRaisesRegex(ValueError,"prior_case_not_in_development"):self.load()


if __name__ == "__main__":unittest.main()
