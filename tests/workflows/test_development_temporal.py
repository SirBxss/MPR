"""Native synthetic lineage, immutable Gaussian reuse and AR attempt lifecycle.

The only producer allowlist patch is scoped to this synthetic class. The
source/environment gate is stubbed as in the earlier native fixture. Actual
MCAP export, registry/cohort replay, baseline fit, AR fit and scoring execute.
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

from lane_residuals.io import development_temporal as contract, development_experiment as previous
from lane_residuals.workflows import development_temporal as workflow
from lane_residuals.modeling import matched_stationary_ar, matched_gaussian
from tests.workflows import test_development_experiment as old
from tests.workflows import test_bounded_recording_readiness as bounded


class DevelopmentTemporalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original=bounded.BoundedWorkflowTests.prepare
        def temporal_prepare(instance,*args,**kwargs):
            times=kwargs.get('times')
            if times is not None and len(times)==501:
                start=times[0]
                kwargs['times']=tuple(start+(j//2)*500_000_000+(j%2)*100_000_000 for j in range(501))
            return original(instance,*args,**kwargs)
        with patch.object(bounded.BoundedWorkflowTests,'prepare',temporal_prepare):
            old.DevelopmentExperimentTests.setUpClass()
        cls.addClassCleanup(old.DevelopmentExperimentTests.doClassCleanups)
        cls.native=old.DevelopmentExperimentTests();cls.native.setUp()
        cls.addClassCleanup(cls.native.doCleanups)
        _,pin=cls.native.prepare();auth=cls.native.adopted(pin)
        if cls.native.train(pin,auth) != 0:
            raise AssertionError('Native synthetic Gaussian baseline failed')

    def setUp(self):
        self.fixture=self.native
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.project=self.root/'project'
        shutil.copytree(self.fixture.project,self.project)
        pin=previous.sha(self.fixture.experiment/'experiment.json')
        self.baseline=Path(self.fixture.request['result_zip'])
        source=self.fixture.source
        p=patch.object(contract,'GAUSSIAN_SOURCE',tuple(source[k] for k in
            ('consumer_git_commit','consumer_git_tree','consumer_runtime_source_sha256')))
        p.start();self.addCleanup(p.stop)
        p=patch.object(workflow,'source_guard',return_value=source);p.start();self.addCleanup(p.stop)
        self.request={'contract_revision':contract.REVISION,'original_experiment_directory':str(self.fixture.experiment),
            'expected_original_experiment_sha256':pin,'gaussian_result_zip':str(self.baseline),
            'expected_gaussian_result_sha256':previous.sha(self.baseline),
            'experiment_directory':'outputs/experiments/private/ar001','training_directory':'outputs/models/private/ar001',
            'authorization':'config/private/ar-authorization.json','result_zip':str(self.root/'ar-results.zip')}
        self.path=self.root/'ar-request.json'
        self.kwargs=dict(project=self.project,expected_tree='synthetic',expected_runtime='synthetic')

    def prepare(self):
        self.path.write_bytes(previous.encoded(self.request))
        return workflow.prepare(**self.kwargs,request_path=self.path,expected_request_sha256=previous.sha(self.path))

    @property
    def experiment(self):return self.project/self.request['experiment_directory']

    @property
    def output(self):return self.project/self.request['training_directory']

    def adopted(self,pin):
        value=contract.authorization_draft(pin);value['attestations']=dict.fromkeys(value['attestations'],True)
        path=self.project/self.request['authorization'];path.write_bytes(previous.encoded(value));return path

    def train(self,pin,auth):
        with redirect_stdout(io.StringIO()):
            return workflow.train(**self.kwargs,experiment_directory=self.experiment,expected_experiment_sha256=pin,
                authorization_path=auth,expected_authorization_sha256=previous.sha(auth))

    def test_native_reuse_fit_state_reload_scores_and_atomic_result(self):
        original=previous.sha(self.baseline)
        with patch.object(matched_gaussian,'fit_matched_gaussian',side_effect=AssertionError('baseline refit')), \
                patch.object(workflow,'fit_stationary_ar',side_effect=AssertionError('fit during prepare')):
            manifest,pin=self.prepare()
        self.assertEqual(manifest['protocol'],contract.PROTOCOL)
        auth=self.adopted(pin)
        self.assertEqual(self.train(pin,auth),0)
        receipt=json.loads((self.output/'run_receipt.json').read_text())
        self.assertEqual(receipt['status'],'complete_matched_stationary_ar_cross_validation')
        self.assertTrue(receipt['input_integrity_verified']);self.assertFalse(receipt['baseline_refitted'])
        self.assertEqual(len(receipt['completed']),5)
        self.assertEqual(set(receipt['comparison']),{'conditional_gaussian','unconditional_gaussian',matched_stationary_ar.MODEL_NAME})
        for comparison in receipt['paired_temporal_comparison']['metrics'].values():
            self.assertEqual(comparison['assessed_outings']+comparison['unassessed_outings'],5)
            self.assertEqual(len(comparison['paired_outings']),5)
        energy=receipt['paired_temporal_comparison']['metrics']['mean_normalized_sequence_energy_score_m']
        self.assertEqual(energy['assessed_outings'],5)
        old_receipt=json.loads((self.fixture.output/'run_receipt.json').read_text())
        for mode in previous.MODEL_NAMES:self.assertEqual(receipt['comparison'][mode],old_receipt['aggregate'][mode])
        for row in receipt['completed']:
            self.assertEqual(row['training_transitions'],1000)
            baseline=next(r for r in old_receipt['completed'] if r['fold']==row['fold'] and r['model']=='conditional_gaussian')
            self.assertEqual(row['metrics']['mean_physical_joint_nll'],baseline['metrics']['mean_physical_joint_nll'])
        claim=Path(receipt['attempt_claim_path_private']);self.assertEqual(previous.sha(claim),receipt['attempt_claim_sha256'])
        with zipfile.ZipFile(self.request['result_zip']) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.read('training/accepted_gaussian_result.zip'),self.baseline.read_bytes())
            for line in z.read('SHA256SUMS').decode().splitlines():
                h,n=line.split('  ',1);self.assertEqual(hashlib.sha256(z.read(n)).hexdigest(),h)
        self.assertFalse(Path(self.request['result_zip']+'.partial').exists())
        self.assertEqual(previous.sha(self.baseline),original)

    def test_old_gaussian_authorization_and_partial_or_nonboolean_flags_refused(self):
        _,pin=self.prepare()
        values=[previous.authorization_draft(pin),contract.authorization_draft(pin)]
        partial=contract.authorization_draft(pin);partial['attestations'][next(iter(contract.ATTESTATIONS))]=True
        values.append(partial)
        for bad in ['true',1]:
            value=contract.authorization_draft(pin);value['attestations']=dict.fromkeys(value['attestations'],bad);values.append(value)
        path=self.project/self.request['authorization']
        for value in values:
            path.write_bytes(previous.encoded(value))
            with self.assertRaisesRegex(ValueError,'explicit_owner_ar'):self.train(pin,path)
            self.assertFalse(self.output.exists())
        self.assertFalse((self.project/'outputs/fit_ledgers').exists())

    def test_paired_missing_lag_is_unassessed_and_duplicate_folds_refused(self):
        fold={'fold_id':'fold001','validation_outing':'one'}
        metrics=dict.fromkeys(contract.PROTOCOL['primary_metrics'],1.)
        base={'model':'conditional_gaussian','fold':fold,'metrics':metrics}
        result=deepcopy(base);result['metrics']['median_absolute_lag_one_correlation_error']=None
        result['metrics']['mean_normalized_sequence_energy_score_m']=.75
        paired=contract.paired_temporal_comparison([base],[result])['metrics']
        self.assertEqual(paired['median_absolute_lag_one_correlation_error']['assessed_outings'],0)
        self.assertIsNone(paired['median_absolute_lag_one_correlation_error']['equal_outing_mean_difference'])
        self.assertEqual(paired['mean_normalized_sequence_energy_score_m']['equal_outing_mean_difference'],-.25)
        with self.assertRaisesRegex(ValueError,'exact_paired'):contract.paired_temporal_comparison([base],[result,result])

    def test_mutated_protocol_fold_or_extra_marker_file_cannot_be_repinned(self):
        manifest,pin=self.prepare();marker=self.experiment/'experiment.json'
        value=deepcopy(manifest);value['protocol']['maximum_absolute_phi']=.999
        marker.write_bytes(previous.encoded(value))
        with self.assertRaisesRegex(ValueError,'cached_protocol'):contract.load_experiment(self.project,self.experiment,previous.sha(marker))
        marker.write_bytes(previous.encoded(manifest));(self.experiment/'extra.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'exact_experiment_file_set'):contract.load_experiment(self.project,self.experiment,pin)

    def test_existing_request_authorization_and_row_markers_block_nested_outputs(self):
        for name in ['request.json','authorization.json','row_manifest.json']:
            partial=self.project/'outputs/experiments/private'/name.replace('.json','')
            partial.mkdir(parents=True);(partial/name).write_text('{}')
            self.request['experiment_directory']=str(partial/'nested')
            before=set(self.project.rglob('*'))
            with self.assertRaisesRegex(ValueError,'inside_partial'):self.prepare()
            self.assertEqual(before,set(self.project.rglob('*')))

    def test_missing_result_parent_refused_before_fit_or_claim(self):
        self.request['result_zip']=str(self.root/'missing/result.zip')
        with self.assertRaisesRegex(ValueError,'zip_parent'):self.prepare()
        self.assertFalse(self.experiment.exists());self.assertFalse((self.project/'outputs/fit_ledgers').exists())

    def test_interrupt_preserves_receipt_zip_and_permanent_attempt_claim(self):
        _,pin=self.prepare();auth=self.adopted(pin)
        with patch.object(workflow,'fit_stationary_ar',side_effect=KeyboardInterrupt):self.assertEqual(self.train(pin,auth),130)
        receipt=json.loads((self.output/'run_receipt.json').read_text())
        self.assertEqual(receipt['exit_code'],130);self.assertEqual(receipt['completed'],[])
        self.assertTrue(receipt['input_integrity_verified']);self.assertTrue(Path(self.request['result_zip']).exists())
        self.assertTrue(Path(receipt['attempt_claim_path_private']).is_file())
        with self.assertRaisesRegex(ValueError,'new_output'):self.train(pin,auth)

    def test_new_request_and_output_names_cannot_repeat_the_same_design(self):
        manifest,pin=self.prepare();auth=self.adopted(pin)
        with patch.object(workflow,'fit_stationary_ar',side_effect=RuntimeError('synthetic failure')):
            self.assertEqual(self.train(pin,auth),2)
        self.request.update(experiment_directory='outputs/experiments/private/renamed',training_directory='outputs/models/private/renamed',
            result_zip=str(self.root/'renamed.zip'),authorization='config/private/renamed.json')
        with self.assertRaisesRegex(ValueError,'design_already_attempted'):self.prepare()
        self.assertFalse(self.experiment.exists())

    def test_packaging_failure_preserves_partial_and_reports_matching_local_failure(self):
        _,pin=self.prepare();auth=self.adopted(pin)
        def fail(path,roots):
            path.write_bytes(b'partial-preserve-me')
            raise OSError('synthetic packaging failure')
        with patch.object(workflow,'package',side_effect=fail):self.assertEqual(self.train(pin,auth),2)
        receipt=json.loads((self.output/'run_receipt.json').read_text())
        self.assertEqual(receipt['status'],'failed_packaging_preserve_attempt');self.assertEqual(receipt['exit_code'],2)
        self.assertFalse(Path(self.request['result_zip']).exists())
        self.assertEqual(Path(self.request['result_zip']+'.partial').read_bytes(),b'partial-preserve-me')
        self.assertTrue(Path(receipt['attempt_claim_path_private']).is_file())

    def test_input_drift_during_fit_invalidates_integrity(self):
        _,pin=self.prepare();auth=self.adopted(pin);original=workflow.fit_stationary_ar
        def drift(*args):
            state=original(*args);auth.write_text('{}');return state
        with patch.object(workflow,'fit_stationary_ar',side_effect=drift):self.assertEqual(self.train(pin,auth),2)
        receipt=json.loads((self.output/'run_receipt.json').read_text());self.assertFalse(receipt['input_integrity_verified'])

    def test_wrong_baseline_digest_refused_without_new_outputs(self):
        self.request['expected_gaussian_result_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'result_digest'):self.prepare()
        self.assertFalse(self.experiment.exists())

    def test_forged_producer_is_rejected_even_with_consistent_zip_checksums(self):
        with zipfile.ZipFile(self.baseline) as z:files={n:z.read(n) for n in z.namelist() if n!='SHA256SUMS'}
        receipt=json.loads(files['training/run_receipt.json']);receipt['source']['consumer_git_tree']='unreviewed'
        files['training/run_receipt.json']=previous.encoded(receipt)
        forged=self.root/'forged.zip'
        with zipfile.ZipFile(forged,'x',zipfile.ZIP_DEFLATED) as z:
            for name,raw in files.items():z.writestr(name,raw)
            z.writestr('SHA256SUMS',''.join(hashlib.sha256(raw).hexdigest()+'  '+n+'\n' for n,raw in sorted(files.items())))
        self.request.update(gaussian_result_zip=str(forged),expected_gaussian_result_sha256=previous.sha(forged))
        with self.assertRaisesRegex(ValueError,'unreviewed_producer'):self.prepare()
        self.assertFalse(self.experiment.exists())
