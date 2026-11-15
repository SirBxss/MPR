"""Native evidence reuse restores each original model and verifies its fold."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lane_residuals.io import development_experiment as original, temporal_planner_replication as reader
from lane_residuals.io.temporal_planner_pilot import TemporalModels, restore_models
from lane_residuals.modeling.matched_stationary_ar import StationaryAR
from tests.io.test_temporal_planner_pilot import archive
from tests.modeling import test_matched_one_state_ar as fixture


class TemporalReplicationReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.MatchedOneStateTests.setUpClass()
        cls.one = fixture.MatchedOneStateTests.state

    def test_complete_native_replay_once_then_exact_saved_states_for_every_fold(self):
        base = self.one.transform_source
        stationary = StationaryAR(base, .8, 35, (30., 30., 20., 735))
        folds = [dict(fold_id="fold_"+str(i), validation_outing="held_"+str(i),
                      training_outings=["train_"+str(i)]) for i in range(7)]
        one_raw = archive({"training/"+f["fold_id"]+"_model.json": dict(fold=f,
             base_conditional_transform_source_sha256="a"*64, state=self.one.to_dict()) for f in folds})
        stationary_raw = archive({"training/"+f["fold_id"]+"_model.json": dict(fold=f,
             base_conditional_model_sha256="a"*64, state=stationary.to_dict()) for f in folds})
        inputs = SimpleNamespace(stationary_raw=stationary_raw, temporal_inputs=SimpleNamespace(
            states={f["fold_id"]: {"conditional_gaussian": (base, "a"*64)} for f in folds}))
        first = restore_models(one_raw, stationary_raw, folds[0], base, "a"*64)
        with TemporaryDirectory() as directory:
            path = Path(directory)/"states.zip"
            path.write_bytes(one_raw)
            plan = dict(folds=[dict(fold=f) for f in folds], one_state_experiment_sha256="b"*64,
                        one_state_result_sha256=original.sha(path))
            with patch.object(reader, "load_models", return_value=(inputs, first)) as native, \
                 patch.object(reader, "restore_models", wraps=restore_models) as restore:
                verified, models = reader.load_all_models(Path(directory), Path(directory)/"experiment", plan, {}, path)
                native.assert_called_once()
                self.assertEqual(restore.call_count, 6)
                self.assertIs(verified, inputs)
                self.assertEqual(list(models), [f["fold_id"] for f in folds])
                for state in models.values():
                    self.assertEqual(state.gaussian.to_dict(), base.to_dict())
                    self.assertEqual(state.one_state.to_dict(), self.one.to_dict())
                    self.assertEqual(state.stationary.to_dict(), stationary.to_dict())
                # A selected fold with a different parent transform is rejected.
                inputs.temporal_inputs.states[folds[-1]["fold_id"]]["conditional_gaussian"] = (base, "c"*64)
                self.assertRaisesRegex(ValueError, "fold_or_transform_mismatch", reader.load_all_models,
                                      Path(directory), Path(directory)/"experiment", plan, {}, path)

    def test_native_lineage_failure_is_not_replaced_by_archive_only_restore(self):
        plan = dict(folds=[dict(fold=dict(fold_id="first"))], one_state_experiment_sha256="a"*64,
                    one_state_result_sha256="b"*64)
        with patch.object(reader, "load_models", side_effect=ValueError("native_lineage_failed")), \
             patch.object(reader, "restore_models") as restore:
            self.assertRaisesRegex(ValueError, "native_lineage_failed", reader.load_all_models,
                                  Path("/synthetic"), Path("/synthetic/experiment"), plan, {}, Path("/synthetic/states.zip"))
            restore.assert_not_called()


if __name__ == "__main__":
    unittest.main()
