"""Protocol-conformance tests, NOT model inference or a scientific benchmark.

Numeric response values are copied from TypeSafe's official primitive pages
(retrieved 2026-10-08). Negative cases deliberately corrupt those documented
responses to exercise rejection; they are never presented as model results.
"""
import copy
from dataclasses import FrozenInstanceError
import unittest

from kch_composed.sensors import (SensorContractError, SystemOneSensor,
                                  import_rdss_receipt, observe_response)


CHOICE_Q = {"department": {"type": "choice", "instructions": "Department",
                           "criteria": {"returns": None, "shipping": None, "billing": None}}}
CHOICE_RESPONSE = {"model": "jev-1.13.0", "answers": {"department": {
    "type": "choice", "choice": "returns", "confidence": 1.0,
    "probabilities": {"shipping": 0.0, "returns": 1.0, "billing": 0.0}}},
    "usage": {"input_tokens": 328, "output_tokens": 34}}
N_Q = {"is_human_escalation": {"type": "noul"}, "is_repeat_contact": {"type": "noul"}}
N_RESPONSE = {"model": "jev-1.13.0", "answers": {
    "is_human_escalation": {"type": "noul", "noul": 0.99},
    "is_repeat_contact": {"type": "noul", "noul": 0.93}},
    "usage": {"input_tokens": 360, "output_tokens": 39}}
S_Q = {"bug_severity": {"type": "score", "criteria": [None, None, None]}}
S_RESPONSE = {"model": "jev-1.13.0", "answers": {"bug_severity": {
    "type": "score", "score": 1.43, "confidence": 0.35,
    "probabilities": {"0": 0.0, "1": 0.57, "2": 0.43}}}}


def observe(response, questions, primitive="choice"):
    return observe_response(response, questions, provider="typesafe-docs-contract-example",
                            model_revision="jev-1.13.0", historical=True,
                            source_ref="https://docs.typesafe.ai/primitives/" + primitive)


class TypedSensorContractTests(unittest.TestCase):
    def test_documented_choice_preserved_without_authority(self):
        result = observe(CHOICE_RESPONSE, CHOICE_Q)
        self.assertEqual(result.status, "OBSERVED")
        self.assertEqual(result.signals[0].value, "returns")
        self.assertEqual(result.to_dict()["raw"], CHOICE_RESPONSE)
        self.assertEqual(result.authority, "NONE")
        self.assertFalse(result.promotion_allowed)
        self.assertTrue(result.development_only)

    def test_documented_noul_does_not_invent_confidence(self):
        result = observe(N_RESPONSE, N_Q, "noul")
        self.assertEqual([s.value for s in result.signals], [0.99, 0.93])
        self.assertTrue(all(s.confidence is None for s in result.signals))

    def test_documented_score_remains_fractional(self):
        result = observe(S_RESPONSE, S_Q, "score")
        self.assertEqual(result.signals[0].value, 1.43)
        self.assertEqual(dict(result.signals[0].probabilities), {"0": 0.0, "1": 0.57, "2": 0.43})

    def test_missing_answer_abstains_with_no_partial_signals(self):
        response = copy.deepcopy(N_RESPONSE)
        del response["answers"]["is_repeat_contact"]
        result = observe(response, N_Q, "noul")
        self.assertEqual(result.status, "ABSTAIN")
        self.assertEqual(result.signals, ())

    def test_corrupt_probability_does_not_get_renormalized(self):
        response = copy.deepcopy(CHOICE_RESPONSE)
        response["answers"]["department"]["probabilities"]["returns"] = -1
        result = observe(response, CHOICE_Q)
        self.assertEqual(result.status, "ABSTAIN")
        self.assertEqual(result.to_dict()["raw"], response)

    def test_boolean_not_accepted_as_numeric_model_score(self):
        response = copy.deepcopy(N_RESPONSE)
        response["answers"]["is_human_escalation"]["noul"] = True
        self.assertEqual(observe(response, N_Q, "noul").status, "ABSTAIN")

    def test_nonfinite_data_is_rejected(self):
        response = copy.deepcopy(N_RESPONSE)
        response["answers"]["is_human_escalation"]["noul"] = float("nan")
        with self.assertRaises(SensorContractError):
            observe(response, N_Q, "noul")

    def test_criteria_order_changes_request_identity(self):
        reversed_q = copy.deepcopy(CHOICE_Q)
        reversed_q["department"]["criteria"] = dict(reversed(list(CHOICE_Q["department"]["criteria"].items())))
        self.assertNotEqual(observe(CHOICE_RESPONSE, CHOICE_Q).questions_sha256,
                            observe(CHOICE_RESPONSE, reversed_q).questions_sha256)

    def test_truncation_is_explicit_abstention(self):
        response = copy.deepcopy(CHOICE_RESPONSE)
        response["state_truncated"] = True
        result = observe(response, CHOICE_Q)
        self.assertEqual(result.status, "ABSTAIN")
        self.assertIn("state_truncated", result.reasons)

    def test_closed_set_stress_cannot_be_used_as_deployment_signal(self):
        response = copy.deepcopy(CHOICE_RESPONSE)
        response["control"] = "closed_set_stress"
        result = observe(response, CHOICE_Q)
        self.assertEqual(result.status, "ABSTAIN")

    def test_observation_is_immutable_and_export_detached(self):
        result = observe(CHOICE_RESPONSE, CHOICE_Q)
        with self.assertRaises(FrozenInstanceError):
            result.status = "AUTHORIZED"
        exported = result.to_dict()
        exported["raw"]["answers"].clear()
        self.assertEqual(result.to_dict()["raw"], CHOICE_RESPONSE)

    def test_unknown_historical_schema_is_not_reinterpreted(self):
        with self.assertRaises(SensorContractError):
            import_rdss_receipt(CHOICE_RESPONSE, CHOICE_Q, provider="typesafe",
                                model_revision="jev-1.13.0", source_ref="documented-example")

    def test_unavailable_backend_abstains_without_secret_message(self):
        def unavailable(**kwargs):
            raise ConnectionError("sensitive-message-must-not-escape")
        sensor = SystemOneSensor(unavailable, provider="contract-failure-test",
                                 model_revision="not-an-inference", source_ref="test")
        result = sensor.evaluate("", N_Q)
        self.assertEqual(result.status, "ABSTAIN")
        self.assertNotIn("sensitive-message", result.raw_json)
        self.assertIn("ConnectionError", result.raw_json)


if __name__ == "__main__":
    unittest.main()
