from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kwancode_harness.controls import evaluate_control
from kwancode_harness.gateway import CapabilityError, Gateway
from kwancode_harness.mcp_server import MCPServer, TOOLS


REGISTRY = {
    "schema": "kch.federated-registry.v0.11.0",
    "release": "KCH 0.11",
    "services": [{
        "active_name": "KwanCode Harness",
        "release_id": "KCH_0.11",
        "family": "KCH_CANONICAL_MACRORELEASE",
        "state": "CANONICAL_PRE2G_FEDERATED_MACRORELEASE",
        "jurisdiction": "governance and read-only federation",
        "authority_inheritance": False,
    }],
    "quarantine": [],
}


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = root / "registry.json"
        self.registry.write_text(json.dumps(REGISTRY), encoding="utf-8")
        self.gateway = Gateway(root / "state.sqlite3", self.registry, b"s" * 32, now=lambda: 1000)

    def tearDown(self):
        self.temp.cleanup()

    def open(self, *, evidence=True):
        return self.gateway.open_session({
            "session_id": "S1", "actor": "USER", "objective_id": "O1",
            "objective_contract_sha256": "a" * 64, "project_id": "P1", "jurisdiction": "J1",
            "authority_granted": ["READ"], "stop_condition_ids": ["STOP"],
            "expected_evidence_ids": ["E1"] if evidence else [], "ttl_seconds": 100,
        })

    def admit(self, opened):
        return self.gateway.admit_evidence({
            "session_id": "S1", "evidence_id": "E1", "source_sha256": "b" * 64,
            "jurisdiction": "J1", "role": "DIRECT", "provenance_ids": ["SRC"],
            "capability": opened["evidence_capabilities"]["E1"],
        })

    def test_session_evidence_and_precommit(self):
        opened = self.open()
        self.admit(opened)
        receipt = self.gateway.precommit_verify({
            "session_id": "S1", "objective_contract_sha256": "a" * 64, "jurisdiction": "J1",
            "evidence_ids": ["E1"], "candidate_artifact_sha256": "c" * 64,
            "observed_artifact_sha256": "c" * 64, "external_observer_verdict": "PASS",
            "capability": opened["precommit_capability"],
        })
        self.assertEqual(receipt["decision"], "ALLOW_SHADOW_PRECOMMIT")
        self.assertEqual(self.gateway.ledger.verify()["gate"], "PASS")

    def test_capability_replay_is_blocked(self):
        opened = self.open()
        self.admit(opened)
        with self.assertRaises(CapabilityError):
            self.admit(opened)

    def test_read_only_proposal_can_execute(self):
        opened = self.open()
        self.admit(opened)
        proposal = self.gateway.propose_action({
            "session_id": "S1", "route": "kch.component.status", "action_class": "READ_ONLY",
            "requested_authority": ["READ"], "evidence_ids": ["E1"], "arguments": {},
            "capability": opened["proposal_capability"],
        })
        control = evaluate_control("R03", {"requested_authority": ["READ"], "granted_authority": ["READ"], "action_classified": True})
        authorized = self.gateway.authorize_action({
            "session_id": "S1", "proposal_id": proposal["proposal"]["proposal_id"],
            "control_receipts": [control], "capability": proposal["authorization_capability"],
        })
        self.assertEqual(authorized["decision"], "ALLOW_READ_ONLY")
        result = self.gateway.execute_action({
            "session_id": "S1", "proposal_id": proposal["proposal"]["proposal_id"],
            "capability": authorized["execution_capability"],
        })
        self.assertTrue(result["executed"])
        self.assertEqual(result["execution_class"], "READ_ONLY")

    def test_mutating_proposal_abstains(self):
        opened = self.open(evidence=False)
        proposal = self.gateway.propose_action({
            "session_id": "S1", "route": "anything", "action_class": "MUTATING",
            "requested_authority": ["READ"], "evidence_ids": [], "arguments": {},
            "capability": opened["proposal_capability"],
        })
        control = evaluate_control("R03", {"requested_authority": ["READ"], "granted_authority": ["READ"], "action_classified": True})
        result = self.gateway.authorize_action({
            "session_id": "S1", "proposal_id": proposal["proposal"]["proposal_id"],
            "control_receipts": [control], "capability": proposal["authorization_capability"],
        })
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertNotIn("execution_capability", result)

    def test_enforced_profile_is_prohibited(self):
        with self.assertRaisesRegex(ValueError, "PROHIBITED"):
            Gateway(Path(self.temp.name) / "x.sqlite3", self.registry, b"s" * 32, profile="enforced")

    def test_mcp_surface_has_49_tools_and_28_direct_controls(self):
        names = [tool["name"] for tool in TOOLS]
        self.assertEqual(len(names), 49)
        self.assertEqual(len([name for name in names if name.startswith("kch.control.R")]), 28)
        listed = MCPServer(self.gateway).handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(len(listed["result"]["tools"]), 49)

    def test_audit_export_is_hash_bound(self):
        self.open(evidence=False)
        exported = self.gateway.audit_export()
        self.assertEqual(exported["release"], "KCH 0.11")
        self.assertEqual(len(exported["export_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
