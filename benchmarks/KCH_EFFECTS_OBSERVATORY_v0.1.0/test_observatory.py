import json
import unittest
from pathlib import Path

from observatory import activation_receipt, compile_effects


ROOT = Path(__file__).resolve().parent


def evidence():
    docs = []
    for n in ("001", "002", "003"):
        local_delivery = ROOT / "real_inputs" / f"evaluation_{n}.json"
        canonical_repo = ROOT.parent / f"KCH_PREPILOT_{n}" / "evaluation.json"
        source = local_delivery if local_delivery.exists() else canonical_repo
        docs.append(json.loads(source.read_text(encoding="utf-8")))
    return compile_effects(docs)


class HistoricalEvidenceTests(unittest.TestCase):
    def test_historical_pairs_are_compiled_without_rewriting_adversity(self):
        report = evidence()
        self.assertEqual(report["aggregate"]["total_pairs"], 3)
        self.assertEqual(report["aggregate"]["admissible_pairs"], 2)
        self.assertEqual(report["aggregate"]["invalid_pairs"], 1)
        self.assertEqual(report["aggregate"]["ties"], 2)
        self.assertEqual(report["aggregate"]["candidate_wins"], 0)
        self.assertEqual(report["aggregate"]["baseline_wins"], 0)
        self.assertEqual(report["pairs"][0]["condition_gate"], "INVALID_CONDITION_INTEGRITY")
        self.assertFalse(report["automatic_activation_gate"]["eligible"])

    def test_directional_posterior_remains_prior_with_no_discordant_pairs(self):
        posterior = evidence()["paired_bayes"]
        self.assertEqual(posterior["discordant_cases"], 0)
        self.assertAlmostEqual(posterior["probability_candidate_better"], 0.5, places=12)
        self.assertLess(posterior["conditional_advantage_credible95"][0], -0.9)
        self.assertGreater(posterior["conditional_advantage_credible95"][1], 0.9)


class ActivationTests(unittest.TestCase):
    def profile(self, **updates):
        base = {"policy": "ASK", "explicit_user_request": False, "risk": 0.8, "coupling": 0.8, "provenance_need": 0.9, "authority_sensitivity": 0.9, "recovery_need": 0.8, "budget_remaining_ratio": 0.5, "reserve_ratio": 0.15}
        base.update(updates)
        return base

    def test_need_without_authority_asks_and_does_not_activate(self):
        receipt = activation_receipt(evidence(), self.profile())
        self.assertEqual(receipt["decision"], "ASK_USER_BEFORE_USE")
        self.assertFalse(receipt["execution_authorized"])
        self.assertFalse(receipt["traceability"]["silent_activation_allowed"])

    def test_explicit_request_authorizes_exactly_one_run(self):
        receipt = activation_receipt(evidence(), self.profile(explicit_user_request=True))
        self.assertEqual(receipt["decision"], "ACTIVE_EXPLICIT_ONE_RUN")
        self.assertTrue(receipt["execution_authorized"])
        self.assertEqual(receipt["authority_source"], "explicit_user_request")

    def test_never_policy_overrides_request(self):
        receipt = activation_receipt(evidence(), self.profile(policy="NEVER", explicit_user_request=True))
        self.assertEqual(receipt["decision"], "OFF_USER_POLICY")
        self.assertFalse(receipt["execution_authorized"])

    def test_auto_policy_is_blocked_by_current_evidence(self):
        receipt = activation_receipt(evidence(), self.profile(policy="AUTO_BOUNDED"))
        self.assertEqual(receipt["decision"], "ASK_USER_BEFORE_USE")
        self.assertFalse(receipt["execution_authorized"])

    def test_budget_reserve_fails_closed(self):
        receipt = activation_receipt(evidence(), self.profile(budget_remaining_ratio=0.13))
        self.assertEqual(receipt["decision"], "OFF_BUDGET_RESERVE")
        self.assertFalse(receipt["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
