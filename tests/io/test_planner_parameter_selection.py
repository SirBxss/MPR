"""Complete six-law restoration, solver pins and native failure propagation."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from lane_residuals.io import planner_parameter_selection as reader
from tests.io import parameter_selection_fixture as fixture


class PlannerParameterReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.family=fixture.frozen_family()

    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.bundle=fixture.data(self.root,self.family)
        self.files,self.native,self.marker,self.pin=fixture.flow_return(self.bundle,self.family)

    def test_all_six_laws_restore_with_exact_transforms_and_flow_solvers(self):
        states=reader.restore_families(fixture.pack(self.files),self.native,self.marker,self.bundle.marker)
        self.assertEqual(len(states),7)
        for family in states.values():
            self.assertEqual(family.unconditional.to_dict(),self.family.unconditional.to_dict())
            self.assertEqual(family.temporal.one_state.to_dict(),self.family.temporal.one_state.to_dict())
            self.assertEqual(family.temporal.stationary.to_dict(),self.family.temporal.stationary.to_dict())
            self.assertEqual(set(family.hashes),{"unconditional_gaussian","conditional_gaussian","stationary_ar","one_state_ar",
                "unconditional_flow","conditional_flow","unconditional_flow_solver","conditional_flow_solver"})
            for mode in ("unconditional","conditional"):
                self.assertEqual(family.flows[mode].to_dict(),self.family.flows[mode].to_dict())

    def test_invalid_result_cannot_restore_states_despite_valid_member_checksums(self):
        for key in ("baseline_refitted","input_integrity_verified","status"):
            files=deepcopy(self.files)
            receipt=files["training/run_receipt.json"]
            receipt[key] = True if key=="baseline_refitted" else False if key=="input_integrity_verified" else "failed"
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,"completed_flow_lineage"):
                reader.restore_families(fixture.pack(files),self.native,self.marker,self.bundle.marker)

    def test_native_lineage_failure_has_no_archive_only_fallback(self):
        with patch.object(reader.flow_io,"load_experiment",side_effect=ValueError("synthetic_native_failure")), \
             patch.object(reader,"restore_families") as restore:
            self.assertRaisesRegex(ValueError,"synthetic_native_failure",reader.load_families,
                self.root,self.root/"experiment","a"*64,self.root/"result.zip","b"*64)
            restore.assert_not_called()


if __name__=="__main__":
    unittest.main()
