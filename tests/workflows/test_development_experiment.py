"""Native synthetic archives through preparation, adopted fit and failure ZIPs.

Only the environment/source gate is stubbed in these disposable fixture projects.
Real cohort/registry/numeric replay, Gaussian fitting, persistence and scores run.
The existing native producer fixture allowlist remains scoped to the test class.
"""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

from lane_residuals.domain import numeric_export
from lane_residuals.io import development_experiment as contract, artifact_registry as registry, locked_development as locked
from lane_residuals.workflows import development_experiment as workflow
from tests.workflows import test_locked_development_export as fixtures


class DevelopmentExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.LockedDevelopmentExportTests.setUpClass()
        cls.addClassCleanup(fixtures.LockedDevelopmentExportTests.tearDownClass)
        source = fixtures.LockedDevelopmentExportTests()
        source.setUp()
        cls.addClassCleanup(source.doCleanups)
        # Extend the existing two-target native test plan to its entire five-
        # development-outing cohort, preserving the two unexposed final outings.
        for i,raw in enumerate(source.fixture.development[2:],2):
            lineage = locked.readiness_files(source.context,raw)
            reg = registry.decode(source.context.original_objects[lineage['registration/registration.json']])
            auth = {'contract_revision':numeric_export.AUTHORIZATION_REVISION,'purpose':numeric_export.AUTHORIZATION_PURPOSE,
                'batch_id':reg['batch_id'],'registration_sha256':lineage['registration/registration.json'],
                'source_specification_sha256':lineage['registration/source_specification.json'],
                'preserved_readiness_report_sha256':lineage['readiness.json'],'authorized_raw_sha256':[raw],
                'attestations':dict.fromkeys(numeric_export.ATTESTATIONS,True)}
            p = source.root/f'owner-adopted-{i}.json'; p.write_text(json.dumps(auth))
            source.plan['targets'].append({'raw_sha256':raw,'authorization':str(p),'expected_authorization_sha256':contract.sha(p),
                'numeric_output':f'data/derived/synthetic-{i}','reserved_registry':f'data/catalog/private/reserved-{i}',
                'complete_registry':f'data/catalog/private/complete-{i}'})
        with redirect_stdout(io.StringIO()):
            code = source.execute(source.native_command)
        if code != 0:
            raise AssertionError((source.attempt/'run_receipt.json').read_text())
        cls.template = source

    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.project = self.root/'project'
        source = self.template
        shutil.copytree(source.project,self.project)
        def mapped(p):
            p = Path(p)
            return self.project/p.relative_to(source.project) if p.is_relative_to(source.project) else p
        receipt_path = mapped(source.attempt)/'run_receipt.json'
        receipt = json.loads(receipt_path.read_text())
        self.request = {'contract_revision':contract.REVISION,
            'cohort_directory':str(mapped(source.fixture.fixture.output)),
            'expected_cohort_sha256':source.fixture.pin,
            'original_registry_directory':str(mapped(source.fixture.fixture.registry_directory)),
            'expected_original_registry_sha256':receipt['original_registry_sha256'],
            'descendants':[{'directory':str(mapped(c['directory'])),'sha256':c['sha256']} for c in receipt['descendants']],
            'archive_sha256':receipt['matched_archives_sha256'],
            'export_receipt':str(receipt_path),'expected_export_receipt_sha256':contract.sha(receipt_path),
            'experiment_directory':'outputs/experiments/private/experiment001',
            'training_directory':'outputs/models/private/gaussian001','result_zip':str(self.root/'results.zip'),
            'authorization':'config/private/development_gaussian_authorization.json'}
        self.request_path = self.root/'request.json'
        self.source = {'consumer_git_commit':'synthetic','consumer_git_tree':'synthetic',
            'consumer_runtime_source_sha256':'synthetic','consumer_runtime_versions':{'fixture':'synthetic'}}
        p = patch.object(workflow,'source_guard',return_value=self.source); p.start(); self.addCleanup(p.stop)
        self.kwargs = dict(project=self.project,expected_tree='synthetic',expected_runtime='synthetic')

    def prepare(self):
        self.request_path.write_bytes(contract.encoded(self.request))
        return workflow.prepare(**self.kwargs,request_path=self.request_path,expected_request_sha256=contract.sha(self.request_path))

    @property
    def experiment(self):
        return self.project/self.request['experiment_directory']

    @property
    def output(self):
        return self.project/self.request['training_directory']

    def adopted(self,pin):
        auth = contract.authorization_draft(pin)
        auth['attestations'] = dict.fromkeys(contract.ATTESTATIONS,True)
        path = self.project/self.request['authorization']
        path.write_bytes(contract.encoded(auth))
        return path

    def train(self,pin,path):
        with redirect_stdout(io.StringIO()):
            return workflow.train(**self.kwargs,experiment_directory=self.experiment,expected_experiment_sha256=pin,
                authorization_path=path,expected_authorization_sha256=contract.sha(path))

    def test_native_prepare_adopt_fit_reload_score_zip_and_no_retry(self):
        with patch.object(workflow,'fit_matched_gaussian',side_effect=AssertionError('fit during prepare')):
            manifest,pin = self.prepare()
        self.assertEqual(len(manifest['folds']),5)
        self.assertFalse(manifest['model_admission_authorized'])
        path = self.adopted(pin)
        self.assertEqual(self.train(pin,path),0)
        receipt = json.loads((self.output/'run_receipt.json').read_text())
        self.assertEqual(receipt['status'],'complete_development_gaussian_cross_validation')
        self.assertEqual(len(receipt['completed']),10)
        self.assertTrue(receipt['input_integrity_verified'])
        self.assertFalse(receipt['final_evaluation_authorized'])
        for item in receipt['completed']:
            self.assertNotIn(item['fold']['validation_outing'],item['fold']['training_outings'])
            self.assertEqual(item['training_rows'],4*501)
            self.assertEqual(item['metrics']['frame_count'],501)
            self.assertEqual(item['metrics']['valid_transitions'],0)
            self.assertIsNone(item['metrics']['median_absolute_lag_one_correlation_error'])
        with zipfile.ZipFile(self.request['result_zip']) as z:
            self.assertIsNone(z.testzip())
            for line in z.read('SHA256SUMS').decode().splitlines():
                import hashlib
                h,name = line.split('  ',1)
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),h)
        with self.assertRaisesRegex(ValueError,'new_output_required'):
            self.train(pin,path)

    def test_false_partial_nonboolean_and_wrong_scope_authorizations_fail_before_output(self):
        _,pin = self.prepare()
        false = contract.authorization_draft(pin)
        values = [false,deepcopy(false),deepcopy(false)]
        values[1]['attestations'][next(iter(contract.ATTESTATIONS))] = True
        values[2]['attestations'] = dict.fromkeys(contract.ATTESTATIONS,1)
        for value in values:
            path = self.project/self.request['authorization']; path.write_bytes(contract.encoded(value))
            with self.assertRaisesRegex(ValueError,'explicit_owner'):
                self.train(pin,path)
            self.assertFalse(self.output.exists())

    def test_partial_development_selection_and_final_archive_are_rejected(self):
        self.request['archive_sha256'] = self.request['archive_sha256'][:-1]
        with self.assertRaisesRegex(ValueError,'receipt_selection'):
            self.prepare()
        self.assertFalse(self.experiment.exists())

    def test_edited_repinned_fold_or_row_map_cannot_replay(self):
        manifest,pin = self.prepare()
        manifest['folds'][0]['training_outings'].append(manifest['folds'][0]['validation_outing'])
        marker = self.experiment/'experiment.json'; marker.write_bytes(contract.encoded(manifest))
        with self.assertRaisesRegex(ValueError,'cached_rows_folds_or_protocol'):
            contract.load_experiment(self.project,self.experiment,contract.sha(marker))

    def test_new_unregistered_numeric_consent_blocks_preparation(self):
        auth = json.loads(self.template.fixture.native.adopted.read_text())
        auth['authorized_raw_sha256'] = ['f'*64]
        path = self.project/'config/private/numeric_export_authorization_new.json'
        path.write_text(json.dumps(auth))
        with self.assertRaisesRegex(ValueError,'unregistered_new_numeric_consent'):
            self.prepare()
        self.assertFalse(self.experiment.exists())

    def test_old_or_omitted_chain_and_wrong_original_digest_fail(self):
        for field,value in [('descendants',self.request['descendants'][:-1]),('expected_original_registry_sha256','f'*64)]:
            old = self.request[field]; self.request[field] = value
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.prepare()
            self.request[field] = old
        self.assertFalse(self.experiment.exists())

    def test_failure_or_interrupt_is_packaged_and_started_attempt_is_not_retried(self):
        _,pin = self.prepare(); path = self.adopted(pin)
        with patch.object(workflow,'fit_matched_gaussian',side_effect=KeyboardInterrupt):
            self.assertEqual(self.train(pin,path),130)
        receipt = json.loads((self.output/'run_receipt.json').read_text())
        self.assertTrue(receipt['fit_attempted'])
        self.assertEqual(receipt['completed'],[])
        self.assertTrue(Path(self.request['result_zip']).is_file())
        with self.assertRaisesRegex(ValueError,'new_output_required'):
            self.train(pin,path)

    def test_input_drift_during_fit_invalidates_complete_result(self):
        _,pin = self.prepare(); path = self.adopted(pin)
        original = workflow.fit_matched_gaussian
        def drift(*args,**kwargs):
            value = original(*args,**kwargs)
            self.request_path.write_text('changed external original request')
            # This original request is deliberately not the sealed experiment's
            # authority. Alter an actually pinned input to exercise postflight.
            watched = Path(self.request['export_receipt']); watched.write_text('{}')
            return value
        with patch.object(workflow,'fit_matched_gaussian',side_effect=drift):
            self.assertEqual(self.train(pin,path),2)
        receipt = json.loads((self.output/'run_receipt.json').read_text())
        self.assertFalse(receipt['input_integrity_verified'])

    def test_nested_partial_evidence_and_existing_outputs_fail_before_writing(self):
        partial = self.project/'outputs/experiments/private/partial'
        (partial/'objects').mkdir(parents=True)
        self.request['experiment_directory'] = str(partial/'nested')
        before = set(self.project.rglob('*'))
        with self.assertRaisesRegex(ValueError,'immutable_or_partial'):
            self.prepare()
        self.assertEqual(before,set(self.project.rglob('*')))
