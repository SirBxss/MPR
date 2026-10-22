import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lane_residuals.io import development_experiment as contract
from lane_residuals.workflows import development_experiment as workflow


class DevelopmentExperimentContractTests(unittest.TestCase):
    def test_home_relative_destination_is_expanded_before_project_resolution(self):
        self.assertEqual(contract.resolve('/synthetic-project','~/mpr-test-result.zip'),
                         Path('~/mpr-test-result.zip').expanduser())

    def test_pinned_metadata_preserves_actual_formatting_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'request.json'
            raw = b'{ "example" : 1 }\n'
            path.write_bytes(raw)
            value,returned = contract.pinned_json(path,hashlib.sha256(raw).hexdigest())
            self.assertEqual(value,{'example':1})
            self.assertEqual(returned,raw)

    def test_raw_suffix_is_rejected_before_endpoint_stat_or_open(self):
        raw = Path('/synthetic-owner/raw.mcap')
        with patch('os.stat',side_effect=AssertionError('stat before raw guard')), \
                patch('os.lstat',side_effect=AssertionError('lstat before raw guard')), \
                self.assertRaisesRegex(ValueError,'raw_or_traversal'):
            contract.pinned_json(raw,'a'*64)

    def test_numeric_true_or_extra_scope_cannot_adopt_authorization(self):
        value = contract.authorization_draft('a'*64)
        value['attestations'] = dict.fromkeys(contract.ATTESTATIONS,1)
        with self.assertRaisesRegex(ValueError,'explicit_owner'):
            contract.require_authorization(value,'a'*64)
        value['attestations'] = dict.fromkeys(contract.ATTESTATIONS,True)
        value['advanced_real_fit_authorized'] = True
        with self.assertRaisesRegex(ValueError,'explicit_owner'):
            contract.require_authorization(value,'a'*64)

    def test_new_empty_directory_or_dangling_symlink_changes_evidence_file_set(self):
        for kind in ('directory','symlink'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                inputs = contract.ExperimentInputs({},None,(),{}, {(root,'*'):frozenset()})
                if kind == 'directory':
                    (root/'new').mkdir()
                else:
                    (root/'new').symlink_to(root/'absent')
                with self.assertRaisesRegex(ValueError,'file_set_changed'):
                    inputs.unchanged()

    def test_import_resolution_is_checked_before_querying_the_selected_git_project(self):
        with patch.object(workflow.subprocess,'check_output',side_effect=AssertionError('git queried')), \
                self.assertRaisesRegex(ValueError,'import_must_resolve'):
            workflow.source_guard(Path('/different-selected-project'),'a'*40,'b'*64)
