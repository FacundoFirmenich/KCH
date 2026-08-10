from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from kch_phl_integration.client import IntegrationClient
from kch_phl_integration.contracts import DecisionContractError, validate_reviewable_decision
from kch_phl_integration.server import IntegrationHTTPServer
from kch_phl_integration.service import (
    ConflictError,
    EffectiveIntegrationService,
    RequestCollisionError,
)


CLIENT_A = {"client_id": "codex", "client_instance_id": "test-a"}
CLIENT_B = {"client_id": "cline", "client_instance_id": "test-b"}


def decision(decision_id: str = "decision-001", component_id: str = "kch.rgg") -> dict:
    return {
        "schema": "kch.reviewable-decision.v0.2.0",
        "decision_id": decision_id,
        "emitted_at": "2026-08-09T12:00:00+00:00",
        "component_id": component_id,
        "decision_type": "INSTRUMENT_CONTRACT_FIXTURE_NOT_USER_DATA",
        "initiator": "automated-test",
        "trigger": "contract-validation",
        "objective_contract_sha256": "0" * 64,
        "purpose_id": "test-only",
        "jurisdiction": "temporary validation database only",
        "input_provenance_ids": ["fixture:decision-v0.2.0"],
        "source_event_ids": [],
        "evidence_ids": ["test:test_effective_integration"],
        "active_rule_ids": ["NO_USER_FEEDBACK"],
        "summary": "Validate the decision envelope.",
        "rationale": "Exercise an exact schema without representing a real KCH decision.",
        "alternatives_considered": ["UNAVAILABLE"],
        "confidence_representation": {"kind": "TEST_ASSERTION", "value": "DETERMINISTIC", "meaning": "not empirical confidence"},
        "risk_class": "TEST_ONLY",
        "authority_granted": ["WRITE_TEMPORARY_FIXTURE"],
        "authority_exercised": ["WRITE_TEMPORARY_FIXTURE"],
        "claim_ceiling": "INSTRUMENT_VALIDATION_ONLY",
        "consequence": "No effect outside the temporary test database.",
        "reversibility": "Temporary directory deletion.",
        "stop_condition_ids": ["TEST_END"],
        "source_uri": "test://kch-phl-integration/decision-fixture",
    }


class EffectiveIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.service = EffectiveIntegrationService(self.path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, method, request_id: str, *args, client=CLIENT_A, **kwargs):
        return method(*args, client=client, request_id=request_id, expected_head_hash=self.service.head(), **kwargs)

    def classify(self, service_id="Super-MCP", method="write", classification="MUTATING"):
        return self.write(
            self.service.register_mutability,
            f"catalog-{service_id}-{method}",
            {"service_id": service_id, "method": method, "classification": classification, "evidence_ref": "test://catalog"},
        )

    def test_decision_contract_accepts_exact_record(self):
        result = validate_reviewable_decision(decision())
        self.assertEqual(result["contract_state"], "CONFORMANT_WITH_UNAVAILABLE")
        self.assertEqual(result["unavailable_fields"], ["alternatives_considered"])

    def test_decision_contract_rejects_missing_and_extra_fields(self):
        missing = decision()
        missing.pop("jurisdiction")
        with self.assertRaises(DecisionContractError):
            validate_reviewable_decision(missing)
        extra = decision()
        extra["undeclared"] = True
        with self.assertRaises(DecisionContractError):
            validate_reviewable_decision(extra)

    def test_decision_contract_rejects_authority_escalation(self):
        record = decision()
        record["authority_exercised"] = ["DELETE_STATE"]
        with self.assertRaises(DecisionContractError):
            validate_reviewable_decision(record)

    def test_request_idempotency_does_not_append_event(self):
        head = self.service.head()
        first = self.service.register_decision(decision(), client=CLIENT_A, request_id="same", expected_head_hash=head)
        events = self.service.projection()["events"]
        replay = self.service.register_decision(decision(), client=CLIENT_A, request_id="same", expected_head_hash=head)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(self.service.projection()["events"], events)
        self.assertEqual(first["resulting_head_hash"], replay["resulting_head_hash"])

    def test_request_collision_is_rejected(self):
        head = self.service.head()
        self.service.register_decision(decision(), client=CLIENT_A, request_id="collision", expected_head_hash=head)
        with self.assertRaises(RequestCollisionError):
            self.service.register_decision(decision("decision-002"), client=CLIENT_A, request_id="collision", expected_head_hash=self.service.head())

    def test_stale_head_rejects_second_client(self):
        shared_head = self.service.head()
        self.service.register_decision(decision(), client=CLIENT_A, request_id="a", expected_head_hash=shared_head)
        with self.assertRaises(ConflictError):
            self.service.register_decision(decision("decision-002"), client=CLIENT_B, request_id="b", expected_head_hash=shared_head)

    def test_decision_id_content_collision_is_rejected(self):
        self.write(self.service.register_decision, "first", decision())
        changed = decision()
        changed["summary"] = "Different content."
        with self.assertRaises(ConflictError):
            self.write(self.service.register_decision, "second", changed)

    def test_phl_blocks_mutation_without_calling_executor(self):
        self.classify()
        session = self.write(self.service.start_phl, "start", trigger="TEST_EXCLUSIVE_LOCK")["result"]["session_id"]
        called = []
        result = self.write(self.service.dispatch, "blocked", "Super-MCP", "write", {}, lambda: called.append(True))
        self.assertFalse(result["result"]["allowed"])
        self.assertEqual(called, [])
        self.write(self.service.close_phl, "close", session)

    def test_read_only_dispatch_remains_available_during_phl(self):
        self.classify(method="status", classification="READ_ONLY")
        session = self.write(self.service.start_phl, "start-read", trigger="TEST_READ_ONLY")
        result = self.write(self.service.dispatch, "read", "Super-MCP", "status", {}, lambda: {"ok": True})
        self.assertTrue(result["result"]["executed"])
        self.write(self.service.close_phl, "close-read", session["result"]["session_id"])

    def test_unclassified_method_fails_closed(self):
        called = []
        result = self.write(self.service.dispatch, "unknown", "unknown", "mutate", {}, lambda: called.append(True))
        self.assertEqual(result["result"]["reason"], "UNCLASSIFIED_METHOD_FAIL_CLOSED")
        self.assertEqual(called, [])

    def test_restart_retains_active_phl_lock(self):
        self.classify()
        self.write(self.service.start_phl, "restart-start", trigger="TEST_RESTART")
        restarted = EffectiveIntegrationService(self.path)
        result = restarted.dispatch("Super-MCP", "write", {}, lambda: "must-not-run", client=CLIENT_B, request_id="after-restart", expected_head_hash=restarted.head())
        self.assertFalse(result["result"]["allowed"])

    def test_peer_head_divergence_is_explicit(self):
        self.assertEqual(self.service.compare_peer_head("f" * 64)["state"], "DIVERGENT_LEDGER_COPY_DETECTED")
        self.assertEqual(self.service.compare_peer_head("GENESIS")["state"], "IN_SYNC")

    def test_event_tampering_is_detected(self):
        self.write(self.service.register_decision, "tamper-event", decision())
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE events SET payload_json='{}' WHERE sequence=1")
        self.assertEqual(self.service.verify()["gate"], "FAIL")

    def test_projection_tampering_is_detected(self):
        self.write(self.service.register_decision, "tamper-projection", decision())
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE decisions SET record_json='{}' WHERE decision_id='decision-001'")
        self.assertEqual(self.service.verify()["gate"], "FAIL")

    def test_emitter_gate_is_not_estimable_until_inventory_is_complete(self):
        self.write(
            self.service.register_emitter,
            "one-emitter",
            {"component_id": "one", "registry_name": "One", "inventory_state": "UNAVAILABLE_CONTRACT", "evidence_ref": "test://one"},
        )
        self.assertEqual(self.service.gate_state()["state"], "NOT_ESTIMABLE_EMITTER_INVENTORY_INCOMPLETE")

    def test_emitter_gate_is_bounded_when_contracts_are_unavailable(self):
        for index in range(16):
            state = "UNAVAILABLE_CONTRACT" if index == 0 else "NON_DECISION_SERVICE"
            self.write(
                self.service.register_emitter,
                f"emitter-{index}",
                {"component_id": f"component-{index}", "registry_name": f"Component {index}", "inventory_state": state, "evidence_ref": "test://inventory"},
            )
        self.assertEqual(self.service.gate_state()["state"], "PASS_EFFECTIVE_KCH_PHL_INTEGRATION_BOUNDED")

    def test_emitter_gate_full_state_is_logic_only_not_empirical_claim(self):
        for index in range(16):
            self.write(
                self.service.register_emitter,
                f"full-{index}",
                {"component_id": f"component-{index}", "registry_name": f"Component {index}", "inventory_state": "NON_DECISION_SERVICE", "evidence_ref": "test://logic-only"},
            )
        self.assertEqual(self.service.gate_state()["state"], "PASS_EFFECTIVE_KCH_PHL_INTEGRATION_FULL")

    def test_integrity_passes_for_untampered_state(self):
        self.write(self.service.register_decision, "integrity", decision())
        result = self.service.verify()
        self.assertEqual(result["gate"], "PASS")
        self.assertEqual(result["feedback_count"], 0)


class HTTPBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        service = EffectiveIntegrationService(Path(self.temp.name) / "http.sqlite3")
        self.token = "t" * 32
        self.server = IntegrationHTTPServer(("127.0.0.1", 0), service, self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def test_http_clients_detect_stale_head(self):
        first = IntegrationClient(self.url, self.token, "codex", "http-a")
        second = IntegrationClient(self.url, self.token, "cline", "http-b")
        first.refresh()
        second.refresh()
        first.register_decision(decision(), request_id="http-first")
        with self.assertRaises(ConflictError):
            second.register_decision(decision("decision-002"), request_id="http-second")

    def test_http_rejects_unauthorized_client(self):
        request = urllib.request.Request(self.url + "/v1/projection", headers={"Authorization": "Bearer invalid"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 401)


if __name__ == "__main__":
    unittest.main()
