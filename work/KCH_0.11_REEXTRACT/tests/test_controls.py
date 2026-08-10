from __future__ import annotations

import unittest

from kwancode_harness.controls import CONTROL_CATALOG, describe_controls, evaluate_control


PASS_CONTEXTS = {
    "R01": {"governing_objective_id": "OBJ", "candidate_objective_id": "OBJ"},
    "R02": {"source_project_id": "A", "target_project_id": "A", "transfer_contract_verified": False, "authority_inherited": False},
    "R03": {"requested_authority": ["READ"], "granted_authority": ["READ"], "action_classified": True},
    "R04": {"external_observer": True, "observer_independence_verified": True},
    "R05": {"scope": "bounded", "deliverables": ["receipt"], "cost_receipt": {"tokens": 10}},
    "R06": {"token_budget": 100, "fanout_budget": 2, "projected_tokens": 90, "projected_fanout": 1},
    "R07": {"probe_applicable": True, "probe_executed": True, "probe_result": "PASS"},
    "R08": {"relevance_state": "DIRECT"},
    "R09": {"governing_mode": "SCIENCE", "claim_mode": "SCIENCE", "boundary_explicit": True},
    "R10": {"applicability": "DIRECT"},
    "R11": {"position_change": "BETTER", "evidence_delta": "new executable gate"},
    "R12": {"options": [{"id": "A", "chosen": True, "opportunity_cost": "B"}, {"id": "B", "chosen": False, "opportunity_cost": "A"}]},
    "R13": {"observed_result": "PASS", "meaning": "bounded", "limitations": "real use pending", "next_critical_action": "paired gate"},
    "R14": {"commercial_readiness_claimed": False, "readiness_evidence": {}},
    "R15": {"claims": [{"claim_id": "C1", "source_ids": ["E1"], "execution_id": "X1", "jurisdiction": "J"}]},
    "R16": {"canonical_name": "KCH 0.11", "genealogy": ["KCH 0.10"], "collision_free": True},
    "R17": {"corrections": [{"correction_id": "U1", "applied": True}]},
    "R18": {"contamination_hits": []},
    "R19": {"handoff": {"source": "T", "governing_objective": "O", "chronology": ["1"], "evidence_boundary": "B", "pending_gates": ["G"], "next_action": "N"}},
    "R20": {"planned_artifacts": ["A"], "necessary_artifacts": ["A"]},
    "R21": {"adverse_results": [{"retained": True, "design_update": "change scorer"}]},
    "R22": {"repairs": [{"original_sha256": "a" * 64, "defect": "D", "change": "C", "validation": "PASS", "replacement_sha256": "b" * 64}]},
    "R23": {"human_interrupt_pending": False},
    "R24": {"decision_equivalent": True, "evidence_contract_equivalent": True},
    "R25": {"evidence_roles": {"E1": "DIRECT", "E2": "EXECUTION"}},
    "R26": {"sample_count": 10, "unique_values": 3, "metric_discriminates": True},
    "R27": {"transport_complete": True, "unit_failures": []},
    "R28": {"evidence_available": False, "authority_after_loss": "READ_ONLY"},
}


class ControlTests(unittest.TestCase):
    def test_exact_28_controls(self):
        self.assertEqual(list(CONTROL_CATALOG), [f"R{i:02d}" for i in range(1, 29)])
        catalog = describe_controls()
        self.assertEqual(catalog["count"], 28)
        self.assertEqual(catalog["effectiveness_claim"], "NOT_ESTABLISHED_WITH_REAL_USE_FOR_ALL_CONTROLS")

    def test_all_pass_contexts_are_executable(self):
        for control_id, context in PASS_CONTEXTS.items():
            with self.subTest(control_id=control_id):
                receipt = evaluate_control(control_id, context)
                self.assertEqual(receipt["verdict"], "PASS")
                self.assertFalse(receipt["authority_created"])
                self.assertEqual(len(receipt["receipt_sha256"]), 64)

    def test_missing_input_is_unavailable(self):
        for control_id in CONTROL_CATALOG:
            with self.subTest(control_id=control_id):
                self.assertEqual(evaluate_control(control_id, {})["verdict"], "UNAVAILABLE")

    def test_objective_drift_blocks(self):
        value = {"governing_objective_id": "A", "candidate_objective_id": "B"}
        self.assertEqual(evaluate_control("R01", value)["verdict"], "BLOCK")

    def test_authority_expansion_blocks(self):
        value = {"requested_authority": ["WRITE"], "granted_authority": ["READ"], "action_classified": True}
        self.assertEqual(evaluate_control("R03", value)["verdict"], "BLOCK")

    def test_decision_evidence_divergence_blocks(self):
        value = {"decision_equivalent": True, "evidence_contract_equivalent": False}
        self.assertEqual(evaluate_control("R24", value)["verdict"], "BLOCK")

    def test_degenerate_metric_blocks(self):
        value = {"sample_count": 20, "unique_values": 1, "metric_discriminates": False}
        self.assertEqual(evaluate_control("R26", value)["verdict"], "BLOCK")

    def test_evidence_loss_requires_authority_degradation(self):
        value = {"evidence_available": False, "authority_after_loss": "MUTATING"}
        self.assertEqual(evaluate_control("R28", value)["verdict"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
