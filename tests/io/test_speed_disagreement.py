from io import BytesIO
import json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from lane_residuals.io import speed_disagreement as d
from tests.io.speed_disagreement_fixture import make_files,pack,sha,encoded

class DisagreementIOTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.path=self.root/'result.zip';self.files=make_files()
    def load(self,files=None):
        raw=pack(self.files if files is None else files);self.path.write_bytes(raw);return d.load_return(self.path,sha(raw))
    def mutate(self,name,fn):
        v=json.loads(self.files[name]);fn(v);self.files[name]=encoded(v)
    def test_complete_cache_and_native_replay(self):
        result=self.load();self.assertEqual(len(result['cases']),2);self.assertEqual(len(result['cases'][0]['frames']),6)
        self.assertIn('not live',result['input_provenance']);self.assertEqual(len(result['input_member_sha256']),31)
    def test_digest_refusal(self):
        raw=pack(self.files);self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'return_digest'):d.load_return(self.path,'a'*64)
    def test_input_symlink_refused(self):
        real=self.root/'real.zip';raw=pack(self.files);real.write_bytes(raw);self.path.symlink_to(real)
        with self.assertRaises(OSError):d.load_return(self.path,sha(raw))
    def test_bad_manifest(self):
        raw=pack(self.files);stream=BytesIO()
        with zipfile.ZipFile(BytesIO(raw)) as old,zipfile.ZipFile(stream,'w') as new:
            for n in old.namelist():new.writestr(n,b'bad' if n=='SHA256SUMS' else old.read(n))
        raw=stream.getvalue();self.path.write_bytes(raw)
        with self.assertRaises(ValueError):d.load_return(self.path,sha(raw))
    def test_unknown_member_refused(self):
        self.files['unexpected.json']=b'{}'
        with self.assertRaisesRegex(ValueError,'budget_or_duplicates'):self.load()
    def test_traversal_refused(self):
        value=self.files.pop('owner_launcher.py');self.files['../owner_launcher.py']=value
        with self.assertRaisesRegex(ValueError,'archive_path'):self.load()
    def test_duplicate_member_refused(self):
        raw=pack(self.files);stream=BytesIO(raw)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(stream,'a') as z:z.writestr('owner_launcher.py',b'duplicate')
        raw=stream.getvalue();self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'duplicates'):d.load_return(self.path,sha(raw))
    def test_expansion_bound_precedes_parse(self):
        with patch.object(d,'MAX_EXPANDED_BYTES',1),self.assertRaisesRegex(ValueError,'budget'):self.load()
    def test_modified_case_audit_refused(self):
        self.mutate('study_attempt_003/probe/outing_001/original_candidate_audit.private.json',lambda v:v['rows'][0].update(candidate_index=99))
        with self.assertRaisesRegex(ValueError,'metadata_binding'):self.load()
    def test_modified_frame_csv_refused(self):
        n='study_attempt_003/probe/outing_001/frame_decisions.private.csv';self.files[n]=self.files[n].replace(b'10.0',b'11.0')
        with self.assertRaisesRegex(ValueError,'original_replay'):self.load()
    def test_prior_review_and_execution_bindings(self):
        for name in ('pinned_inputs/previous_attempt_001.zip','pinned_inputs/previous_attempt_002.zip','independent_review_note.private.md','pinned_inputs/source_protocol_review.private.md','owner_entrypoint.py'):
            original=self.files[name];self.files[name]=b'changed'
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'binding'):self.load()
            self.files[name]=original
    def test_incomplete_timeout_or_retry_refused(self):
        name='study_attempt_003/launcher_receipt.private.json';original=self.files[name]
        for key,val in (('status','incomplete'),('parent_timeout',True),('parent_interrupted',True),('metadata_only_retries',1),('child_exit_code',False)):
            self.files[name]=original;self.mutate(name,lambda v:v.update({key:val}))
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'single_round_parent'):self.load()
    def test_scope_change_refused(self):
        self.mutate('study_attempt_003/probe/report.private.json',lambda v:v.update(speed_feature_adopted=True))
        with self.assertRaisesRegex(ValueError,'original_scope'):self.load()
