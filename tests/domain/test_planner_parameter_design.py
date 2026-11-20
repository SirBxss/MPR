"""Synthetic decision sensitivity, quadratic maps and metadata stop rules."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.domain import planner_parameter_selection as p, planner_parameter_design as d
from lane_residuals.workflows.planner_parameter_selection import prepare_folds
from tests.io import parameter_selection_fixture as fixture


class PlannerParameterDesignTests(unittest.TestCase):
    def test_quadratic_map_matches_zero_state_rollout_with_source_clocks(self):
        rng=np.random.default_rng(55)
        for length in (3,5):
            speeds=tuple(np.linspace(12,22,length));intervals=tuple(np.linspace(.09,.11,length-1))
            y=rng.normal(0,.03,(4,length,21));flat=y.reshape(4,-1)
            for c in (0,4,8):
                matrix=d.quadratic_map(speeds,intervals,c)
                actual=p.rollout_costs(y,np.array(speeds),np.array(intervals),c,np.zeros((1,3)))['loss'][:,0]
                np.testing.assert_allclose(np.einsum('bi,ij,bj->b',flat,matrix,flat),actual,rtol=1e-11,atol=1e-12)
                self.assertGreater(np.linalg.eigvalsh(matrix).min(),-1e-9)

    def test_covariance_trace_matches_exact_finite_basis_expectation(self):
        length=3;speeds=(20.,)*length;intervals=(.1,)*(length-1)
        covariance=d.unit_covariance(length,.9);factor=np.linalg.cholesky(covariance)
        y=np.sqrt(21*length)*factor.T.reshape(21*length,length,21)
        matrix=d.quadratic_map(speeds,intervals,4)
        actual=p.rollout_costs(y,np.array(speeds),np.array(intervals),4,np.zeros((1,3)))['loss'].mean()
        self.assertAlmostEqual(actual,float(np.sum(matrix*covariance)),places=9)

    def test_variable_length_bound_uses_separate_weighted_blocks(self):
        matrices=[];eigenvalues=[]
        for length,weight in ((3,.4),(5,.6)):
            speeds=(20.,)*length;intervals=(.1,)*(length-1)
            matrices.append(weight*(d.quadratic_map(speeds,intervals,4)-d.quadratic_map(speeds,intervals,8)))
            eigenvalues.append(weight*d.flip_eigenvalue(speeds,intervals,4,8))
        n=len(matrices[0]);m=len(matrices[1]);block=np.zeros((n+m,n+m))
        block[:n,:n]=matrices[0];block[n:,n:]=matrices[1]
        self.assertAlmostEqual(np.linalg.eigvalsh(block)[-1],max(eigenvalues),places=10)

    def test_power_fixture_is_reproducible_and_distinguishes_temporal_moments(self):
        first=d.synthetic_power_screen();second=d.synthetic_power_screen()
        self.assertEqual(first,second);self.assertTrue(first['passed']);self.assertEqual(first['repeats'],8)
        self.assertNotIn(first['zero_choice'],(0,8))
        scenarios={(s['rho'],s['sigma_m']):s for s in first['scenarios']}
        self.assertNotEqual(scenarios[0.,.02]['exact_moment_choice'],scenarios[.9,.02]['exact_moment_choice'])
        self.assertGreaterEqual(first['qualifying_scenarios'],2)

    def test_metadata_reports_flip_bounds_and_classifies_singleton(self):
        family=fixture.frozen_family()
        with TemporaryDirectory() as tmp:
            b=fixture.data(Path(tmp),family)
            fold=prepare_folds(b.inputs,b.marker,b.plan,b.checkpoint,b.families)[0]
            report=d.design_diagnostics(fold.speeds,fold.context_records)
            self.assertTrue(report['informative']);self.assertEqual(len(report['settings']),3)
            self.assertEqual(len(report['quadratic_block_weights']),72)
            self.assertAlmostEqual(sum(report['quadratic_block_weights']),1.)
            self.assertTrue(report['settings']['gate_0.20']['flip_bounds'])
            native=p.feasible_candidates
            def singleton(*args):
                _,details=native(*args);mask=np.zeros(9,dtype=bool);mask[4]=True
                return mask,details
            with patch.object(p,'feasible_candidates',side_effect=singleton):
                blocked=d.design_diagnostics(fold.speeds,fold.context_records)
            self.assertFalse(blocked['informative'])
            self.assertIn('primary_feasible_set_has_fewer_than_two_candidates',blocked['reasons'])

    def test_quadratic_budget_blocks_large_allocations(self):
        self.assertRaisesRegex(ValueError,'quadratic_budget',d.quadratic_map,(20.,)*33,(.1,)*32,4)
        self.assertRaisesRegex(ValueError,'clock_or_speed',d.quadratic_map,(20.,)*3,(0.,.1),4)
        self.assertRaisesRegex(ValueError,'covariance_contract',d.unit_covariance,3,1.)

    def test_nominal_probe_envelope_is_unsaturated(self):
        r=p.engineering_screen()
        self.assertLess(r['maximum_nominal_probe_acceleration_mps2'],3.)
        self.assertLess(r['maximum_nominal_probe_jerk_mps3'],5.)
        for c in range(9):
            values=p.response_costs(np.zeros((1,8,21)),np.full(8,20.),np.full(7,.1),c)
            self.assertGreater(values['nominal_loss'].mean(),0.)
            self.assertEqual(values['law_loss'].sum(),0.)
            for m in p.METRICS[4:]:self.assertEqual(values[m].sum(),0.)

    def test_symmetric_tasks_cancel_cross_terms_with_biased_residuals(self):
        y=np.random.default_rng(88).normal(.03,.02,(4,5,21))
        speeds=np.array([12.,13.,14.,13.,12.]);intervals=np.array([.09,.1,.11,.1])
        for c in (0,4,8):
            values=p.response_costs(y,speeds,intervals,c)
            for m in p.COMPONENTS:
                np.testing.assert_allclose(values[m].mean(axis=1),values['nominal_'+m].mean(axis=1)+values['law_'+m].mean(axis=1),atol=1e-10)
            increment=p.rollout_costs(y,speeds,intervals,c,np.zeros((1,3)))
            total=p.rollout_costs(y,speeds,intervals,c,p.TASKS)
            for m in p.METRICS[4:]:
                np.testing.assert_array_equal(values[m],np.broadcast_to(increment[m],(4,4)))
                np.testing.assert_array_equal(values['total_'+m],total[m])

    def test_one_outlier_is_reported_without_automatic_veto(self):
        ids=[str(i) for i in range(6) for _ in range(12)];tracking=np.ones((9,72,4))
        tracking[8,0]=3.
        feasible,details=p.feasible_candidates(tracking,p.nominal_probes(),ids,.2)
        self.assertTrue(feasible[8]);self.assertEqual(details['binding_outings_by_candidate']['8'],[])
        self.assertEqual(details['worst_context_task_ratio_to_context_grid_best'][8],3.)
        tighter,_=p.feasible_candidates(tracking,p.nominal_probes(),ids,.1)
        self.assertFalse(tighter[8])

    def test_practical_rule_ignores_numerical_noise(self):
        ids=[str(i) for i in range(6) for _ in range(12)]
        grid=dict(costs=np.ones((9,8,2,72,7)),nominal_tracking=np.ones((9,72,4)),nominal_probe_tracking=p.nominal_probes(),
                  decomposition=np.zeros((9,8,2,72,3,4)),total_tails=np.zeros((9,8,2,72,3)))
        selection=p.select_parameters(grid,ids)
        held=dict(candidate_mean_metrics=[{m:1. for m in p.METRICS} for _ in range(9)],
            nominal_tracking_by_sequence_candidate_task=np.ones((1,9,4)).tolist(),nominal_peaks_by_sequence_candidate=np.zeros((1,9,2)).tolist())
        results=p.compare_choices(selection,held)
        for result in results.values():result['primary_AR_minus_zero']=-1e-14
        summary=p.summarize({str(i):results for i in range(7)})
        self.assertEqual(summary['settings']['draws_64_gate_0.20']['negative_outings'],0)
        self.assertFalse(summary['descriptive_primary_risk_improves'])
        for result in results.values():result['primary_AR_minus_zero']=-.005
        summary=p.summarize({str(i):results for i in range(7)})
        self.assertEqual(summary['settings']['draws_64_gate_0.20']['negative_outings'],7)
        self.assertFalse(summary['descriptive_primary_risk_improves'])
        for result in results.values():result['primary_AR_minus_zero']=-.02
        self.assertTrue(p.summarize({str(i):results for i in range(7)})['descriptive_primary_risk_improves'])


if __name__=='__main__':unittest.main()
