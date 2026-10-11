from __future__ import annotations

from collections import Counter
import inspect
import math
import unittest

import numpy as np

import null_perturbation_operators_v016 as op


class OperatorQualificationTests(unittest.TestCase):
    def assertFinite(self, value):
        self.assertTrue(np.all(np.isfinite(np.asarray(value, dtype=np.float64))))

    def test_001_all_required_symbols_exist(self):
        for name in op.REQUIRED_OPERATOR_SYMBOLS:
            self.assertTrue(callable(getattr(op, name, None)), name)

    def test_002_seeded_rng_reproducible(self):
        a = op.seeded_rng("same", 17).integers(0, 2**31, 20)
        b = op.seeded_rng("same", 17).integers(0, 2**31, 20)
        np.testing.assert_array_equal(a, b)

    def test_003_seeded_rng_namespace_separation(self):
        a = op.seeded_rng("a", 17).integers(0, 2**31, 20)
        b = op.seeded_rng("b", 17).integers(0, 2**31, 20)
        self.assertFalse(np.array_equal(a, b))

    def test_004_circular_distance_wrap_and_symmetry(self):
        self.assertEqual(op.circular_distance_degrees(359, 1), 2.0)
        self.assertEqual(op.circular_distance_degrees(1, 359), 2.0)
        np.testing.assert_allclose(op.circular_distance_degrees([0, 170], [180, -170], 180), [0, 20])

    def test_005_circular_distance_invalid_period_fails(self):
        with self.assertRaises(op.OperatorContractError):
            op.circular_distance_degrees(1, 2, 0)

    def test_006_head_to_normal_is_unit_and_orthogonal(self):
        head = np.array([0.0, 90.0, 180.0, 270.0])
        normal = op.head_to_normal(head)
        theta = np.deg2rad(head)
        heading = np.stack((np.sin(theta), np.cos(theta)), axis=-1)
        np.testing.assert_allclose(np.sum(normal * heading, axis=1), 0.0, atol=1e-15)
        np.testing.assert_allclose(np.linalg.norm(normal, axis=1), 1.0, atol=1e-15)
        np.testing.assert_allclose(normal[0], [1.0, 0.0], atol=1e-15)

    def test_007_reflected_rake_is_involution(self):
        rake = np.array([-179.0, -90.0, 0.0, 45.0, 179.0])
        twice = op.reflected_rake(op.reflected_rake(rake))
        np.testing.assert_allclose(twice, rake)

    def test_008_uncertainty_draws_are_bounded_and_reproducible(self):
        args = ([350, 10], [80, 5], [170, -170], [20, 20], [15, 15], [30, 30])
        a = op.propagate_mechanism_uncertainty(*args, replicates=64, namespace="u", seed=5)
        b = op.propagate_mechanism_uncertainty(*args, replicates=64, namespace="u", seed=5)
        for key in ("strike_draws", "dip_draws", "rake_draws"):
            np.testing.assert_array_equal(a[key], b[key])
        self.assertTrue(np.all((a["strike_draws"] >= 0) & (a["strike_draws"] < 360)))
        self.assertTrue(np.all((a["dip_draws"] >= 0) & (a["dip_draws"] <= 90)))
        self.assertTrue(np.all((a["rake_draws"] >= -180) & (a["rake_draws"] < 180)))

    def test_009_uncertainty_missing_or_negative_fails(self):
        with self.assertRaises(op.OperatorContractError):
            op.propagate_mechanism_uncertainty([0], [45], [0], [-1], [1], [1], replicates=1, namespace="x", seed=1)
        with self.assertRaises(op.OperatorContractError):
            op.propagate_mechanism_uncertainty([math.nan], [45], [0], [1], [1], [1], replicates=1, namespace="x", seed=1)

    def test_010_posterior_zero_uncertainty_matches_exact_mark(self):
        out = op.posterior_mark_expectations([10], [40], [-20], [0], [0], [0], draws=8, namespace="p", seed=1)
        exact = op._mechanism_marks([10], [40], [-20])[0]
        np.testing.assert_allclose(out["mean_mark"][0], exact, atol=1e-15)
        np.testing.assert_allclose(out["variance_mark"], 0.0, atol=1e-15)

    def test_011_mark_permutation_preserves_stratum_multisets(self):
        marks = np.arange(24, dtype=float).reshape(12, 2)
        cohort = ["A"] * 8 + ["B"] * 4
        component = ["x"] * 4 + ["y"] * 4 + ["z"] * 4
        time = [1, 2, 3, 4, 31, 32, 33, 34, 1, 2, 3, 4]
        magnitude = [2.1] * 12; quality = ["Q"] * 12
        out, diag = op.permute_within_bins(marks, cohort, component, time, magnitude, quality, rng=op.seeded_rng("perm", 1))
        self.assertEqual(diag["event_count"], 12)
        keys = list(zip(cohort, component, np.floor(np.array(time)/30), np.floor(np.array(magnitude)/.5), quality))
        for key in set(keys):
            idx = [i for i, k in enumerate(keys) if k == key]
            self.assertEqual(Counter(map(tuple, marks[idx])), Counter(map(tuple, out[idx])))

    def test_012_singleton_permutation_unchanged_and_reported(self):
        marks = np.array([[1.0, 2.0], [3.0, 4.0]])
        out, diag = op.permute_within_bins(marks, ["A", "A"], ["x", "y"], [0, 0], [1, 1], ["Q", "Q"], rng=op.seeded_rng("s", 2))
        np.testing.assert_array_equal(out, marks)
        self.assertEqual(diag["singleton_stratum_count"], 2)

    def test_013_static_logodds_is_antisymmetric(self):
        a = op.static_logodds(7, 10)
        b = op.static_logodds(3, 10)
        self.assertAlmostEqual(a, -b, places=14)

    def test_014_static_field_exact_and_backoff(self):
        marks = np.array([[1.,0.],[2.,0.],[3.,0.],[4.,0.]])
        drawn, backoff, diag = op.draw_static_fields(
            marks, ["n1","n1","n2","n3"], ["c1","c1","c1","c2"], ["A","A","A","B"],
            [2.1,2.1,2.1,3.1], ["Q","Q","Q","R"],
            ["n1","missing","missing","missing"], ["c1","c1","missing","missing"], ["A","A","A","B"],
            [2.1,2.1,2.1,99.0], ["Q","Q","Q","missing"], rng=op.seeded_rng("static", 4))
        np.testing.assert_array_equal(backoff, [0,1,2,3])
        self.assertEqual(diag["maximum_backoff_level"], 3)
        self.assertFinite(drawn)

    def test_015_static_field_missing_cohort_fails(self):
        with self.assertRaises(op.OperatorContractError):
            op.draw_static_fields([[1.,0.]], ["n"], ["c"], ["A"], [1.], ["Q"], ["x"], ["z"], ["B"], [2.], ["R"], rng=op.seeded_rng("f", 1))

    @staticmethod
    def parameters():
        return {
            "productivity": 0.44,
            "magnitude_scaling": 0.3,
            "c_days": 0.1,
            "p": 1.1,
            "network_scale_km": 1.5,
            "magnitude_reference": 2.0,
            "background_rate_per_day": 0.2,
            "branching_ratio": 0.5,
        }

    def test_016_eval_intensity_positive_and_decays(self):
        p = self.parameters()
        w = op.eval_intensity([0,0,0], [1,2,1], [2,2,2], [0,0,5], p)
        self.assertTrue(np.all(w > 0))
        self.assertGreater(w[0], w[1])
        self.assertGreater(w[0], w[2])

    def test_017_eval_intensity_temporal_violation_fails(self):
        with self.assertRaises(op.OperatorContractError):
            op.eval_intensity([1], [1], [2], [1], self.parameters())

    def test_018_parent_state_probabilities_close(self):
        state = op.compute_parent_state([0,1,2,3], [2,2,2,2], [1,2,2,3], [0,0,1,2], [1,1,1,1], self.parameters())
        for child in range(4):
            total = state.background_probability[child] + np.sum(state.edge_probability[state.child_index == child])
            self.assertAlmostEqual(total, 1.0, places=14)

    def test_019_parent_state_self_edge_fails(self):
        with self.assertRaises(op.OperatorContractError):
            op.compute_parent_state([0,1], [2,2], [1], [1], [1], self.parameters())

    def _rewire_fixture(self):
        # Complete temporal bipartite support: early parents 0..5, later children 6..11.
        times = np.arange(12, dtype=float)
        parent = np.array([0,1,2,3,4,5,0,1,2,3,4,5])
        child = np.array([6,7,8,9,10,11,7,8,9,10,11,6])
        weights = np.ones(12)
        cohorts = ["A"] * 12
        allowed = {(p,c) for p in range(6) for c in range(6,12)}
        return times, parent, child, weights, cohorts, allowed

    def test_020_rewiring_preserves_degrees_weights_and_time(self):
        times, parent, child, weight, cohorts, allowed = self._rewire_fixture()
        result = op.rewire_parent_graph(parent, child, weight, times, cohorts, rng=op.seeded_rng("rw", 9), candidate_allowed=allowed,
                                         target_successful_swaps_per_edge=1.0, minimum_successful_swaps_per_edge=.5, maximum_proposals_per_edge=100)
        self.assertEqual(Counter(result.parent_index), Counter(parent))
        self.assertEqual(Counter(result.child_index), Counter(child))
        self.assertEqual(Counter(result.weight), Counter(weight))
        self.assertTrue(np.all(times[result.parent_index] < times[result.child_index]))
        self.assertNotEqual(list(zip(parent,child)), list(zip(result.parent_index,result.child_index)))
        self.assertGreater(result.diagnostics["net_changed_edge_fraction"], 0.0)

    def test_021_rewiring_fail_closed_on_impossible_candidate_contract(self):
        times, parent, child, weight, cohorts, _ = self._rewire_fixture()
        allowed = set(zip(parent.tolist(), child.tolist()))
        with self.assertRaises(op.OperatorContractError):
            op.rewire_parent_graph(parent, child, weight, times, cohorts, rng=op.seeded_rng("rwfail", 9), candidate_allowed=allowed,
                                   target_successful_swaps_per_edge=1.0, minimum_successful_swaps_per_edge=.5, maximum_proposals_per_edge=5)

    def test_022_make_rewired_null_is_deterministic(self):
        times, parent, child, weight, cohorts, allowed = self._rewire_fixture()
        state = op.ParentState(child, parent, weight, weight/2, np.ones(12), np.ones(12))
        a = op.make_rewired_null(state, times, cohorts, namespace="null", seed=3, candidate_allowed=allowed,
                                  target_successful_swaps_per_edge=1, minimum_successful_swaps_per_edge=.5)
        b = op.make_rewired_null(state, times, cohorts, namespace="null", seed=3, candidate_allowed=allowed,
                                  target_successful_swaps_per_edge=1, minimum_successful_swaps_per_edge=.5)
        np.testing.assert_array_equal(a.parent_index, b.parent_index)
        np.testing.assert_array_equal(a.child_index, b.child_index)

    def test_023_simulate_catalog_deterministic_and_stable(self):
        p = self.parameters()
        a = op.simulate_catalog(duration_days=50, parameters=p, empirical_magnitudes=[1.5,2,2.5], network_nodes=["a","b"],
                                transition_matrix=[[.8,.2],[.3,.7]], namespace="sim", seed=8, maximum_events=10000)
        b = op.simulate_catalog(duration_days=50, parameters=p, empirical_magnitudes=[1.5,2,2.5], network_nodes=["a","b"],
                                transition_matrix=[[.8,.2],[.3,.7]], namespace="sim", seed=8, maximum_events=10000)
        np.testing.assert_array_equal(a.time_days, b.time_days)
        np.testing.assert_array_equal(a.parent_index, b.parent_index)
        self.assertTrue(np.all(np.diff(a.time_days) >= 0))
        self.assertFalse(a.diagnostics["parameter_update_performed"])
        self.assertEqual(a.diagnostics["signed_twist_parameter"], 0.0)

    def test_024_simulate_catalog_rejects_supercritical(self):
        p = self.parameters(); p["branching_ratio"] = 1.0
        with self.assertRaises(op.OperatorContractError):
            op.simulate_catalog(duration_days=1, parameters=p, empirical_magnitudes=[2], network_nodes=["a"], transition_matrix=None,
                                namespace="sim", seed=1)

    def test_025_nonhelical_simulation_preserves_graph_and_zero_twist(self):
        state = op.ParentState(np.array([1]), np.array([0]), np.array([.2]), np.array([.5]), np.array([.4,.4]), np.array([.5,.5]))
        out = op.simulate_nonhelical_fixed_parent_weights(
            state, [[1.,0.],[0.,1.]], ["n1","n2"], ["c","c"], ["A","A"], [2.,2.], ["Q","Q"],
            ["n1"], ["c"], ["A"], [2.], ["Q"], namespace="nh", seed=1)
        np.testing.assert_array_equal(out["parent_index"], state.parent_index)
        np.testing.assert_array_equal(out["edge_weight"], state.edge_intensity)
        self.assertEqual(out["signed_twist_parameter"], 0.0)
        self.assertFalse(out["parameter_update_performed"])

    def test_026_score_perfect_candidate_beats_baseline(self):
        out = op.score_null_metrics([0,10,20], [5,15,25], [5,15,25], [0,10,20])
        self.assertGreater(out["relative_axial_rmse_improvement"], 0)
        self.assertGreater(out["mean_log_score_gain_per_edge"], 0)

    def test_027_direction_reversal_equivariance(self):
        parent = np.array([0.,10.,20.,30.]); child = np.array([5.,20.,10.,40.])
        fwd = op.score_null_metrics(parent, child, child, parent)
        rev = op.score_null_metrics(child, parent, parent, child)
        self.assertAlmostEqual(fwd["signed_chirality"], -rev["signed_chirality"], places=14)
        self.assertAlmostEqual(fwd["axial_loss"], rev["axial_loss"], places=14)

    def test_028_moving_block_length_domain_and_reproducibility(self):
        times = np.arange(100, dtype=float)
        a = op.moving_block_resample(times, span_days=10, rng=op.seeded_rng("mbb", 7))
        b = op.moving_block_resample(times, span_days=10, rng=op.seeded_rng("mbb", 7))
        self.assertEqual(len(a), len(times)); self.assertTrue(np.all((a >= 0) & (a < len(times))))
        np.testing.assert_array_equal(a, b)

    def test_029_moving_block_requires_sorted_time(self):
        with self.assertRaises(op.OperatorContractError):
            op.moving_block_resample([1,0], span_days=1, rng=op.seeded_rng("x", 1))

    def test_030_public_functions_have_no_io_parameters(self):
        forbidden = {"path", "file", "url", "database", "connection", "socket"}
        for name in op.REQUIRED_OPERATOR_SYMBOLS:
            params = {p.lower() for p in inspect.signature(getattr(op, name)).parameters}
            self.assertFalse(params & forbidden, (name, params & forbidden))

    def test_031_all_numeric_outputs_are_float64_or_int64(self):
        self.assertEqual(op.head_to_normal([0]).dtype, np.float64)
        self.assertEqual(op.moving_block_resample([0.,1.], span_days=1, rng=op.seeded_rng("dtype", 1)).dtype, np.int64)

    def test_032_no_imputation_on_nonfinite_input(self):
        with self.assertRaises(op.OperatorContractError):
            op.score_null_metrics([0], [math.nan], [0], [0])

    def test_033_static_field_preserves_source_mark_rows(self):
        marks = np.array([[1.,2.],[3.,4.],[5.,6.]])
        out, _, _ = op.draw_static_fields(marks,["n"]*3,["c"]*3,["A"]*3,[2]*3,["Q"]*3,
                                          ["n"]*20,["c"]*20,["A"]*20,[2]*20,["Q"]*20,rng=op.seeded_rng("rows",2))
        source = {tuple(row) for row in marks}
        self.assertTrue(all(tuple(row) in source for row in out))

    def test_034_parent_probabilities_are_positive(self):
        state = op.compute_parent_state([0,1,2], [2,2,2], [1,2], [0,1], [1,1], self.parameters())
        self.assertTrue(np.all(state.edge_probability > 0))
        self.assertTrue(np.all(state.background_probability > 0))

    def test_035_reflection_flips_chirality_mark(self):
        m1 = op._mechanism_marks([10],[45],[30])[0,6]
        m2 = op._mechanism_marks([10],[45],[op.reflected_rake(30)])[0,6]
        self.assertAlmostEqual(m1, -m2, places=14)

    def test_036_score_weight_scaling_invariant(self):
        args = ([0,10], [5,20], [5,20], [0,10])
        a = op.score_null_metrics(*args, edge_weight=[1,2])
        b = op.score_null_metrics(*args, edge_weight=[10,20])
        for key in a:
            self.assertAlmostEqual(a[key], b[key], places=14)

    def test_037_permutation_is_deterministic(self):
        marks=np.arange(40,dtype=float).reshape(20,2); base=(["A"]*20,["c"]*20,np.arange(20),[2.1]*20,["Q"]*20)
        a,_=op.permute_within_bins(marks,*base,rng=op.seeded_rng("pd",1))
        b,_=op.permute_within_bins(marks,*base,rng=op.seeded_rng("pd",1))
        np.testing.assert_array_equal(a,b)

    def test_038_input_arrays_are_not_mutated(self):
        times, parent, child, weight, cohorts, allowed = self._rewire_fixture()
        originals = [x.copy() for x in (times,parent,child,weight)]
        op.rewire_parent_graph(parent,child,weight,times,cohorts,rng=op.seeded_rng("immut",1),candidate_allowed=allowed,
                               target_successful_swaps_per_edge=1,minimum_successful_swaps_per_edge=.5)
        for observed, expected in zip((times,parent,child,weight), originals): np.testing.assert_array_equal(observed,expected)

    def test_039_parent_rewiring_preserves_edge_count(self):
        times, parent, child, weight, cohorts, allowed = self._rewire_fixture()
        out=op.rewire_parent_graph(parent,child,weight,times,cohorts,rng=op.seeded_rng("count",2),candidate_allowed=allowed,
                                   target_successful_swaps_per_edge=1,minimum_successful_swaps_per_edge=.5)
        self.assertEqual(len(out.parent_index),len(parent))

    def test_040_operator_module_contract_ids_are_frozen(self):
        self.assertEqual(op.PROTOCOL_ID, "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f")
        self.assertEqual(op.RUNTIME_CONTRACT_ID, "h13nullspec:bc68343eee99c797c27795b9c5e73b7bec63764f678ab4c195572281acf79dff")


if __name__ == "__main__":
    unittest.main(verbosity=2)
