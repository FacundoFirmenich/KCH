from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from kch_mis_v03_integration.adapter import AdapterContractError, EXPECTED, MISV03Adapter, sha256_file
from kch_mis_v03_integration.csi import lower_to_csi


ROOT = Path(__file__).resolve().parents[1]


class MISV03AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = MISV03Adapter(
            wheel=ROOT / "vendor" / "mis_qualitative_bayes-0.3.1-py3-none-any.whl",
            corpus=ROOT / "evidence" / "KHC_TWO_BATTERY_MASTER_RESULTS_v2.0.7.json",
            report=ROOT / "evidence" / "MIS_v0_3_EXPERIMENT_REPORT.json",
            ledgers=ROOT / "evidence" / "MIS_v0_3_KHC_FUTURE_ONLY_LEDGERS.json",
            manifest=ROOT / "evidence" / "MIS_RELEASE_MANIFEST_v0.3.1.json",
        )
        cls.report = json.loads((ROOT / "evidence" / "MIS_v0_3_EXPERIMENT_REPORT.json").read_text(encoding="utf-8"))

    def test_custody_hashes_are_exact(self) -> None:
        self.assertEqual(sha256_file(ROOT / "vendor" / "mis_qualitative_bayes-0.3.1-py3-none-any.whl"), EXPECTED["wheel"])
        self.assertEqual(sha256_file(ROOT / "evidence" / "KHC_TWO_BATTERY_MASTER_RESULTS_v2.0.7.json"), EXPECTED["corpus"])

    def test_description_creates_no_authority(self) -> None:
        value = self.adapter.describe()
        self.assertFalse(value["authority_created"])
        self.assertFalse(value["execution_authorized"])
        self.assertFalse(value["automatic_promotion"])

    def test_full_historical_certificate_and_persisted_ledgers(self) -> None:
        value = self.adapter.audit_historical_khc()
        self.assertEqual((value["records"], value["units_unique"]), (480, 480))
        self.assertEqual((value["streams"], value["persisted_ledgers_verified"]), (60, 60))
        self.assertTrue(value["frozen_report_exact_match"])
        self.assertTrue(self.adapter.verify_certificate(value)["valid"])

    def test_historical_certificate_tamper_is_rejected(self) -> None:
        value = self.adapter.audit_historical_khc()
        tampered = copy.deepcopy(value)
        tampered["records"] = 479
        with self.assertRaises(AdapterContractError):
            self.adapter.verify_certificate(tampered)

    def test_exact_decision_matches_frozen_formal_example(self) -> None:
        example = self.report["loss_decision_example"]
        request = {
            "schema": "kch.mis.v03.exact-decision-request.v0.1.0",
            "request_id": "test-frozen-formal-example",
            "purpose_id": "INTERFACE_CONFORMANCE_ONLY",
            "jurisdiction": "Formal validation example; not empirical.",
            "evidence_ids": [f"sha256:{EXPECTED['report']}"],
            "states": list(example["prior"]["masses"]),
            "prior": example["prior"]["masses"],
            "likelihood": example["likelihood"],
            "actions": example["loss"]["actions"],
            "losses": example["loss"]["losses"],
            "tie_action": None,
        }
        certificate = self.adapter.exact_decide(request)
        self.assertEqual(certificate["posterior"], example["posterior"])
        self.assertEqual(certificate["decision"], example["decision"])
        self.assertTrue(self.adapter.verify_certificate(certificate)["valid"])

    def test_noncanonical_fraction_fails_closed(self) -> None:
        example = self.report["loss_decision_example"]
        request = {
            "schema": "kch.mis.v03.exact-decision-request.v0.1.0",
            "request_id": "test-noncanonical",
            "purpose_id": "NEGATIVE_CONTRACT_TEST",
            "jurisdiction": "Unit test only.",
            "evidence_ids": [],
            "states": list(example["prior"]["masses"]),
            "prior": dict(example["prior"]["masses"]),
            "likelihood": example["likelihood"],
            "actions": example["loss"]["actions"],
            "losses": example["loss"]["losses"],
            "tie_action": None,
        }
        request["prior"][next(iter(request["prior"]))] = "2/4"
        with self.assertRaises(ValueError):
            self.adapter.exact_decide(request)

    def test_csi_lowering_preserves_authority_separation(self) -> None:
        certificate = self.adapter.audit_historical_khc()
        lowered = lower_to_csi(certificate, "0" * 64)
        self.assertFalse(lowered["authority_created"])
        self.assertFalse(lowered["execution_authorized"])
        self.assertFalse(lowered["automatic_promotion"])
        self.assertEqual(lowered["topological_address"], ["KCH", "FEDERATED_MATHEMATICAL_SERVICES", "MIS", "v0.3.1"])


if __name__ == "__main__":
    unittest.main()

