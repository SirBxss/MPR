"""Native synthetic predecessor reuse, one-state fits and attempt lifecycle.

Producer tuples/source gates are patched only in this synthetic class. Actual
MCAP/registry replay, original Gaussian/scalar fits and new one-state fits run.
"""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from lane_residuals.io import development_experiment as previous,development_one_state as contract,development_temporal as temporal
from lane_residuals.workflows import development_one_state as workflow
from lane_residuals.modeling.matched_one_state_ar import OneStateAR,MODEL_NAME
from lane_residuals.modeling.aiohmm import AutoregressiveInputOutputHMM
from tests.workflows import test_development_temporal as legacy


class DevelopmentOneStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        legacy.DevelopmentTemporalTests.setUpClass();cls.addClassCleanup(legacy.DevelopmentTemporalTests.doClassCleanups)
        cls.native=legacy.DevelopmentTemporalTests();cls.native.setUp();cls.addClassCleanup(cls.native.doCleanups)
        _,pin=cls.native.prepare();auth=cls.native.adopted(pin)
        if cls.native.train(pin,auth)!=0:raise AssertionError('Synthetic scalar baseline failed')
        cls.prior_pin=pin
        inputs,_=temporal.load_experiment(cls.native.project,cls.native.experiment,pin)
        cls.raw_path=next(s for r in inputs.previous_inputs.context.metadata['records'] for s in r['canonical_paths_private'])

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.project=self.root/'project'
        shutil.copytree(self.native.project,self.project);self.source=self.native.fixture.source
        p=patch.object(contract,'STATIONARY_SOURCE',tuple(self.source[k] for k in ('consumer_git_commit','consumer_git_tree','consumer_runtime_source_sha256')))
        p.start();self.addCleanup(p.stop)
        p=patch.object(workflow,'source_guard',return_value=self.source);p.start();self.addCleanup(p.stop)
        self.baseline=Path(self.native.request['result_zip'])
        self.request={'contract_revision':contract.REVISION,'original_temporal_experiment_directory':str(self.native.experiment),
            'expected_original_temporal_experiment_sha256':self.prior_pin,'stationary_ar_result_zip':str(self.baseline),
            'expected_stationary_ar_result_sha256':previous.sha(self.baseline),'experiment_directory':'outputs/experiments/private/one001',
            'training_directory':'outputs/models/private/one001','authorization':'config/private/one001.json','result_zip':str(self.root/'results.zip')}
        self.path=self.root/'one-request.json';self.common=dict(project=self.project,expected_tree='synthetic',expected_runtime='synthetic')

    def prepare(self):
        self.path.write_bytes(previous.encoded(self.request))
        return workflow.prepare(**self.common,request_path=self.path,expected_request_sha256=previous.sha(self.path))

    @property
    def folder(self):return self.project/self.request['experiment_directory']

    @property
    def output(self):return self.project/self.request['training_directory']

    def adopt(self,pin):
        value=contract.authorization_draft(pin);value['attestations']=dict.fromkeys(value['attestations'],True)
        path=self.project/self.request['authorization'];path.write_bytes(previous.encoded(value));return path

    def train(self,pin,auth):
        with redirect_stdout(io.StringIO()):
            return workflow.train(**self.common,experiment_directory=self.folder,expected_experiment_sha256=pin,
                authorization_path=auth,expected_authorization_sha256=previous.sha(auth))

    def test_native_prepare_fit_reload_four_model_scores_and_preserve_inputs(self):
        oldpin=previous.sha(self.baseline)
        with patch.object(AutoregressiveInputOutputHMM,'fit',side_effect=AssertionError('fit during prepare')):manifest,pin=self.prepare()
        self.assertEqual(manifest['protocol'],contract.PROTOCOL)
        self.assertEqual(len(manifest['adapter_layouts']),5)
        self.assertEqual(manifest['adapter_layouts'][0]['training']['frames'],2004)
        self.assertEqual(self.train(pin,self.adopt(pin)),0)
        receipt=json.loads((self.output/'run_receipt.json').read_text())
        self.assertEqual(receipt['status'],'complete_matched_one_state_ar_cross_validation');self.assertTrue(receipt['input_integrity_verified'])
        self.assertFalse(receipt['baseline_refitted']);self.assertFalse(receipt['transform_refitted']);self.assertEqual(len(receipt['completed']),5)
        prior=json.loads((self.native.output/'run_receipt.json').read_text())
        for mode,value in prior['comparison'].items():self.assertEqual(receipt['comparison'][mode],value)
        self.assertEqual(len(receipt['comparison']),4)
        self.assertEqual(receipt['all_folds_converged'],all(r['fit_converged'] for r in receipt['completed']))
        for row in receipt['completed']:
            self.assertEqual(row['training_rows'],2004);self.assertEqual(row['training_transitions'],1000);self.assertEqual(row['training_sequences'],1004)
            self.assertEqual(row['single_frame_density_scope'],'analytic_generated_history_marginal_not_teacher_forcing')
            saved=json.loads((self.output/(row['fold']['fold_id']+'_model.json')).read_text())
            restored=OneStateAR.from_dict(saved['state']);self.assertFalse(restored.model.has_latent_state_switching)
            self.assertEqual(saved['fit_report']['warnings'],row['fit_warnings'])
        with zipfile.ZipFile(self.request['result_zip']) as z:
            self.assertIsNone(z.testzip());self.assertEqual(z.read('training/accepted_stationary_ar_result.zip'),self.baseline.read_bytes())
            for line in z.read('SHA256SUMS').decode().splitlines():
                h,n=line.split('  ',1);self.assertEqual(hashlib.sha256(z.read(n)).hexdigest(),h)
        self.assertEqual(previous.sha(self.baseline),oldpin);self.assertFalse(Path(self.request['result_zip']+'.partial').exists())

    def test_old_false_partial_and_nonboolean_authorizations_refused_before_claim(self):
        _,pin=self.prepare();path=self.project/self.request['authorization']
        values=[temporal.authorization_draft(pin),contract.authorization_draft(pin)]
        for flag in [True,1,'true']:
            value=contract.authorization_draft(pin)
            if flag is True:value['attestations'][next(iter(value['attestations']))]=True
            else:value['attestations']=dict.fromkeys(value['attestations'],flag)
            values.append(value)
        for value in values:
            path.write_bytes(previous.encoded(value))
            with self.assertRaisesRegex(ValueError,'explicit_owner_authorization'):self.train(pin,path)
            self.assertFalse(self.output.exists());self.assertFalse((self.project/'outputs/fit_ledgers/private/matched_one_state_v01918').exists())

    def test_repinned_protocol_and_extra_experiment_file_refused(self):
        manifest,pin=self.prepare();value=deepcopy(manifest);value['protocol']['configuration']['state_count']=2
        marker=self.folder/'experiment.json';marker.write_bytes(previous.encoded(value))
        with self.assertRaisesRegex(ValueError,'cached_protocol'):contract.load_experiment(self.project,self.folder,previous.sha(marker))
        marker.write_bytes(previous.encoded(manifest));(self.folder/'extra.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'exact_experiment_file_set'):contract.load_experiment(self.project,self.folder,pin)

    def test_repinned_adapter_layout_cannot_replace_exact_preparation(self):
        manifest,pin=self.prepare();manifest['adapter_layouts'][0]['training']['interface_sha256']='a'*64
        path=self.folder/'experiment.json';path.write_bytes(previous.encoded(manifest))
        with self.assertRaisesRegex(ValueError,'cached_protocol'):contract.load_experiment(self.project,self.folder,previous.sha(path))

    def test_wrong_predecessor_pin_and_unreviewed_producer_refused(self):
        self.request['expected_stationary_ar_result_sha256']='a'*64
        with self.assertRaisesRegex(ValueError,'predecessor_digest'):self.prepare()
        with zipfile.ZipFile(self.baseline) as z:files={n:z.read(n) for n in z.namelist() if n!='SHA256SUMS'}
        r=json.loads(files['training/run_receipt.json']);r['source']['consumer_git_tree']='unreviewed';files['training/run_receipt.json']=previous.encoded(r)
        forged=self.root/'forged.zip'
        with zipfile.ZipFile(forged,'x',zipfile.ZIP_DEFLATED) as z:
            for n,b in files.items():z.writestr(n,b)
            z.writestr('SHA256SUMS',''.join(hashlib.sha256(b).hexdigest()+'  '+n+'\n' for n,b in sorted(files.items())))
        self.request.update(stationary_ar_result_zip=str(forged),expected_stationary_ar_result_sha256=previous.sha(forged))
        with self.assertRaisesRegex(ValueError,'unreviewed_producer'):self.prepare()
        self.assertFalse(self.folder.exists())

    def test_known_raw_input_refused_before_endpoint_lstat(self):
        self.request['stationary_ar_result_zip']=self.raw_path;self.path.write_bytes(previous.encoded(self.request))
        touched=[];original=Path.lstat
        def observe(p,*a,**kw):
            if str(p)==self.raw_path:touched.append(str(p));raise AssertionError('Raw endpoint queried')
            return original(p,*a,**kw)
        with patch.object(Path,'lstat',new=observe),self.assertRaisesRegex(ValueError,'known_raw_input'):
            contract.load_inputs(self.project,self.path,previous.sha(self.path))
        self.assertEqual(touched,[])

    def test_missing_ZIP_parent_and_partial_container_refused_early(self):
        self.request['result_zip']=str(self.root/'missing/result.zip')
        with self.assertRaisesRegex(ValueError,'zip_parent'):self.prepare()
        self.assertFalse(self.folder.exists())
        self.request['result_zip']=str(self.root/'results.zip')
        parent=self.project/'outputs/experiments/private/partial';parent.mkdir(parents=True);(parent/'request.json').write_text('{}')
        self.request['experiment_directory']=str(parent/'nested')
        with self.assertRaisesRegex(ValueError,'inside_partial'):self.prepare()

    def test_interrupt_preserves_receipt_ZIP_claim_and_blocks_renamed_attempt(self):
        _,pin=self.prepare();auth=self.adopt(pin)
        with patch.object(workflow,'fit_one_state_ar',side_effect=KeyboardInterrupt):self.assertEqual(self.train(pin,auth),130)
        receipt=json.loads((self.output/'run_receipt.json').read_text());self.assertEqual(receipt['exit_code'],130)
        self.assertTrue(receipt['input_integrity_verified']);self.assertTrue(Path(self.request['result_zip']).exists())
        self.assertTrue(Path(receipt['attempt_claim_path_private']).is_file())
        self.request.update(experiment_directory='outputs/experiments/private/rename',training_directory='outputs/models/private/rename',
            result_zip=str(self.root/'rename.zip'),authorization='config/private/rename.json')
        with self.assertRaisesRegex(ValueError,'design_already_attempted'):self.prepare()

    def test_packaging_failure_preserves_partial_and_failure_event(self):
        _,pin=self.prepare();auth=self.adopt(pin)
        def fail(path,roots):path.write_bytes(b'preserved partial');raise OSError('Synthetic failure')
        with patch.object(workflow,'package',side_effect=fail):self.assertEqual(self.train(pin,auth),2)
        receipt=json.loads((self.output/'run_receipt.json').read_text());self.assertEqual(receipt['exit_code'],2)
        self.assertEqual(receipt['status'],'failed_packaging_preserve_attempt');self.assertFalse(Path(self.request['result_zip']).exists())
        self.assertEqual(Path(self.request['result_zip']+'.partial').read_bytes(),b'preserved partial')
        event=Path(receipt['attempt_claim_path_private']+'.packaging_failure.json');self.assertTrue(event.is_file())

    def test_output_creation_failure_leaves_claim_and_separate_event_before_fit(self):
        _,pin=self.prepare();auth=self.adopt(pin);original=Path.mkdir
        def fail(p,*a,**kw):
            if p==self.output:raise OSError('synthetic disk failure')
            return original(p,*a,**kw)
        with patch.object(Path,'mkdir',new=fail),patch.object(workflow,'fit_one_state_ar') as fitter:self.assertEqual(self.train(pin,auth),2)
        fitter.assert_not_called();self.assertFalse(self.output.exists())
        events=list((self.project/'outputs/fit_ledgers/private/matched_one_state_v01918').rglob('*.output_creation_failure.json'))
        self.assertEqual(len(events),1);self.assertEqual(json.loads(events[0].read_text())['exit_code'],2)

    def test_post_publication_fsync_failure_preserves_ZIP_and_records_real_failure(self):
        _,pin=self.prepare();auth=self.adopt(pin);original=workflow.registry._fsync_directory
        def fail(path):
            if Path(path)==Path(self.request['result_zip']).parent:raise OSError('synthetic publication durability failure')
            return original(path)
        with patch.object(workflow.registry,'_fsync_directory',side_effect=fail):self.assertEqual(self.train(pin,auth),2)
        self.assertTrue(Path(self.request['result_zip']).is_file())
        events=list((self.project/'outputs/fit_ledgers/private/matched_one_state_v01918').rglob('*.packaging_failure.json'))
        self.assertEqual(len(events),1);event=json.loads(events[0].read_text());self.assertTrue(event['final_zip_present']);self.assertEqual(event['exit_code'],2)

    def test_noncooperating_output_created_during_replay_is_rechecked_before_claim(self):
        _,pin=self.prepare();auth=self.adopt(pin);original=contract.load_experiment
        def race(*a,**kw):
            result=original(*a,**kw);self.output.mkdir(parents=True);(self.output/'preserve.txt').write_text('external');return result
        with patch.object(contract,'load_experiment',side_effect=race),self.assertRaisesRegex(ValueError,'new_output'):self.train(pin,auth)
        self.assertEqual((self.output/'preserve.txt').read_text(),'external')
        self.assertFalse((self.project/'outputs/fit_ledgers/private/matched_one_state_v01918').exists())

    def test_auth_drift_during_fit_invalidates_integrity_without_retry(self):
        _,pin=self.prepare();auth=self.adopt(pin);original=workflow.fit_one_state_ar
        def drift(*a):
            result=original(*a);auth.write_text('{}');return result
        with patch.object(workflow,'fit_one_state_ar',side_effect=drift):self.assertEqual(self.train(pin,auth),2)
        receipt=json.loads((self.output/'run_receipt.json').read_text());self.assertFalse(receipt['input_integrity_verified'])

    def test_new_parent_chain_is_fsynced_without_rewriting_existing_directories(self):
        target=self.root/'new/a/b';calls=[];original=workflow.registry._fsync_directory
        def record(p):calls.append(Path(p));return original(p)
        with patch.object(workflow.registry,'_fsync_directory',side_effect=record):workflow.durable_parents(target)
        for d in [self.root/'new',self.root/'new/a',target]:self.assertIn(d,calls);self.assertIn(d.parent,calls)
        before=list(calls)
        with patch.object(workflow.registry,'_fsync_directory',side_effect=record):workflow.durable_parents(target)
        self.assertEqual(calls,before)
