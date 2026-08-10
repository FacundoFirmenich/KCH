from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from kch_sco.csi import lower_superchat
from kch_sco.ledger import SCOConflictError, SCOService
from kch_sco.models import ContractError, validate_node, validate_receipt


ACTOR = "sco-test-fixture"


def superchat(sco_id="sco-test"):
    return {
        "schema": "kch.sco.superchat.v0.1.0",
        "sco_id": sco_id,
        "name": "SCO instrument test",
        "objective": "Validate orchestration mechanics without representing a real user project.",
        "non_goals": ["No live provider dispatch", "No native context ingestion"],
        "jurisdiction": "temporary test database",
        "claim_ceiling": "INSTRUMENT_VALIDATION_ONLY",
    }


def node(node_id, provider="CODEX", native_uri=None, authority=None, role="WORKER", connector="REFERENCE_ONLY_NO_LIVE_BRIDGE"):
    prefixes = {"CODEX": "codex://threads/", "CHATGPT": "chatgpt://threads/", "CLINE": "cline://tasks/", "COWORK": "cowork://tasks/", "OPENCODE": "opencode://sessions/"}
    return {
        "schema": "kch.sco.node.v0.1.0",
        "sco_id": "sco-test",
        "node_id": node_id,
        "provider": provider,
        "native_uri": native_uri or prefixes[provider] + node_id,
        "title": f"Test node {node_id}",
        "role": role,
        "responsibilities": ["Execute bounded test work"],
        "capabilities": ["REFERENCE_ONLY"],
        "authority_granted": authority or ["PRODUCE_TEST_RECEIPT"],
        "autonomy_level": "RESPOND_WITHIN_SCOPE",
        "context_policy": "SCOPED_DISCLOSURE_ONLY",
        "memory_policy": "NATIVE_MEMORY_PRESERVED",
        "connector_state": connector,
        "source_provenance": "test://fixture-not-provider-evidence",
    }


def disclosure():
    return {
        "schema": "kch.sco.scoped-disclosure.v0.1.0",
        "allowed_ref_kinds": ["EVIDENCE_REF", "ARTIFACT_REF"],
        "maximum_payload_bytes": 65536,
        "forbidden_transfers": ["FULL_CONTEXT_MERGE", "NATIVE_MEMORY_COPY", "IMPLICIT_AUTHORITY_TRANSFER"],
    }


def edge(edge_id, source, target, relation="SUPPLIES_EVIDENCE"):
    return {
        "schema": "kch.sco.edge.v0.1.0",
        "sco_id": "sco-test",
        "edge_id": edge_id,
        "source_node_id": source,
        "target_node_id": target,
        "relation": relation,
        "disclosure_contract": disclosure(),
        "activation_condition": "EXPLICIT_WORK_ORDER",
        "gate_id": "gate:test",
    }


def order(order_id, target, depends=None, authority=None):
    return {
        "schema": "kch.sco.work-order.v0.1.0",
        "sco_id": "sco-test",
        "order_id": order_id,
        "target_node_id": target,
        "objective": f"Execute bounded fixture {order_id}.",
        "input_refs": ["test://input"],
        "disclosed_fragments": [],
        "required_outputs": ["TEST_RECEIPT"],
        "authority_granted": authority or ["PRODUCE_TEST_RECEIPT"],
        "depends_on": depends or [],
        "termination": "Receipt ingested",
        "claim_ceiling": "TEST_ONLY",
    }


def receipt(receipt_id, order_id, node_id, outcome="SUCCEEDED", authority=None):
    return {
        "schema": "kch.sco.receipt.v0.1.0",
        "receipt_id": receipt_id,
        "order_id": order_id,
        "node_id": node_id,
        "outcome": outcome,
        "output_refs": [f"test://output/{receipt_id}"] if outcome == "SUCCEEDED" else [],
        "evidence_ids": ["test-evidence"],
        "claims": ["Instrument route exercised"] if outcome == "SUCCEEDED" else [],
        "limitations": ["Test fixture only"],
        "authority_exercised": authority or ["PRODUCE_TEST_RECEIPT"],
        "completed_at": "2026-08-09T00:00:00+00:00",
    }


class SCOTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "sco.sqlite3"
        self.service = SCOService(self.path)
        self.write(self.service.create_superchat, "create", superchat())

    def tearDown(self):
        self.temp.cleanup()

    def write(self, method, command_id, *args, **kwargs):
        return method(*args, actor=ACTOR, command_id=command_id, expected_head_hash=self.service.head(), **kwargs)

    def add(self, node_id, **kwargs):
        return self.write(self.service.add_node, f"node-{node_id}", node(node_id, **kwargs))

    def test_sovereign_references_export_without_native_content(self):
        self.add("source")
        self.add("worker")
        self.write(self.service.add_edge, "edge", edge("e1", "source", "worker"))
        bundle = self.service.export_bundle("sco-test")
        self.assertFalse(bundle["native_chat_content_included"])
        self.assertFalse(bundle["native_memory_included"])
        self.assertEqual({item["native_uri"] for item in bundle["nodes"]}, {"codex://threads/source", "codex://threads/worker"})

    def test_context_and_memory_fusion_are_rejected(self):
        record = node("bad")
        record["context_policy"] = "SHARED_PROJECT_CONTEXT"
        with self.assertRaises(ContractError):
            validate_node(record)
        record = node("bad-memory")
        record["memory_policy"] = "CENTRAL_MEMORY_REPLACES_NATIVE"
        with self.assertRaises(ContractError):
            validate_node(record)

    def test_provider_uri_contract_is_exact(self):
        record = node("bad-uri", provider="CLINE")
        record["native_uri"] = "codex://threads/not-cline"
        with self.assertRaises(ContractError):
            validate_node(record)

    def test_same_native_chat_cannot_be_selected_twice(self):
        self.add("one", native_uri="codex://threads/exact")
        with self.assertRaises(SCOConflictError):
            self.add("two", native_uri="codex://threads/exact")

    def test_stale_writer_is_rejected(self):
        stale = self.service.head()
        self.service.add_node(node("a"), actor="a", command_id="a", expected_head_hash=stale)
        with self.assertRaises(SCOConflictError):
            self.service.add_node(node("b"), actor="b", command_id="b", expected_head_hash=stale)

    def test_command_replay_is_idempotent(self):
        head = self.service.head()
        first = self.service.add_node(node("same"), actor=ACTOR, command_id="same", expected_head_hash=head)
        replay = self.service.add_node(node("same"), actor=ACTOR, command_id="same", expected_head_hash=head)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(first["resulting_head_hash"], replay["resulting_head_hash"])

    def test_work_order_cannot_escalate_node_authority(self):
        self.add("worker")
        with self.assertRaises(SCOConflictError):
            self.write(self.service.issue_work_order, "bad-order", order("o1", "worker", authority=["DELETE_NATIVE_CHAT"]))

    def test_receipt_cannot_report_authority_escalation(self):
        self.add("worker")
        self.write(self.service.issue_work_order, "order", order("o1", "worker"))
        with self.assertRaises(SCOConflictError):
            self.write(self.service.ingest_receipt, "bad-receipt", receipt("r1", "o1", "worker", authority=["DELETE_NATIVE_CHAT"]))

    def test_dependency_becomes_ready_after_success(self):
        self.add("a")
        self.add("b")
        self.write(self.service.issue_work_order, "o1", order("o1", "a"))
        self.write(self.service.issue_work_order, "o2", order("o2", "b", depends=["o1"]))
        self.assertIn("WAITING_DEPENDENCY", self.service.schedule("sco-test")["states"])
        self.write(self.service.ingest_receipt, "r1", receipt("r1", "o1", "a"))
        self.assertEqual(self.service.schedule("sco-test")["ready_count"], 1)

    def test_adverse_dependency_is_preserved_and_blocks_downstream(self):
        self.add("a")
        self.add("b")
        self.write(self.service.issue_work_order, "o1", order("o1", "a"))
        self.write(self.service.issue_work_order, "o2", order("o2", "b", depends=["o1"]))
        self.write(self.service.ingest_receipt, "r1", receipt("r1", "o1", "a", outcome="FAILED", authority=[]))
        states = self.service.schedule("sco-test")["states"]
        self.assertIn("FAILED_PRESERVED", states)
        self.assertIn("BLOCKED_DEPENDENCY_ADVERSE", states)

    def test_abstention_is_not_coerced_into_failure_or_success(self):
        self.add("a")
        self.write(self.service.issue_work_order, "o1", order("o1", "a"))
        self.write(self.service.ingest_receipt, "r1", receipt("r1", "o1", "a", outcome="ABSTAINED", authority=[]))
        self.assertIn("ABSTAINED_PRESERVED", self.service.schedule("sco-test")["states"])

    def test_conflict_requires_adjudicator_authority(self):
        self.add("a")
        self.add("b")
        self.add("judge", authority=["PRODUCE_TEST_RECEIPT"])
        for item in ("a", "b"):
            self.write(self.service.issue_work_order, f"o-{item}", order(f"o-{item}", item))
            self.write(self.service.ingest_receipt, f"r-{item}", receipt(f"r-{item}", f"o-{item}", item))
        conflict = {"schema": "kch.sco.conflict.v0.1.0", "sco_id": "sco-test", "conflict_id": "c1", "receipt_ids": ["r-a", "r-b"], "question": "Which bounded result applies?", "state": "OPEN_PRESERVED", "adjudicator_node_id": "judge", "resolution_ref": "UNAVAILABLE"}
        with self.assertRaises(SCOConflictError):
            self.write(self.service.declare_conflict, "conflict", conflict)

    def test_conflict_preserves_divergence(self):
        self.add("a")
        self.add("b")
        self.add("judge", authority=["ADJUDICATE_CONFLICT"])
        for item in ("a", "b"):
            self.write(self.service.issue_work_order, f"o-{item}", order(f"o-{item}", item))
            self.write(self.service.ingest_receipt, f"r-{item}", receipt(f"r-{item}", f"o-{item}", item))
        conflict = {"schema": "kch.sco.conflict.v0.1.0", "sco_id": "sco-test", "conflict_id": "c1", "receipt_ids": ["r-a", "r-b"], "question": "Which bounded result applies?", "state": "OPEN_PRESERVED", "adjudicator_node_id": "judge", "resolution_ref": "UNAVAILABLE"}
        result = self.write(self.service.declare_conflict, "conflict", conflict)
        self.assertTrue(result["result"]["divergence_preserved"])

    def test_graph_cycles_are_visible(self):
        self.add("a")
        self.add("b")
        self.write(self.service.add_edge, "e1", edge("e1", "a", "b", "REVIEWS"))
        self.write(self.service.add_edge, "e2", edge("e2", "b", "a", "CHALLENGES"))
        self.assertTrue(self.service.graph_diagnostics("sco-test")["cycles"])

    def test_retirement_preserves_node_record(self):
        self.add("a")
        self.write(self.service.retire_node, "retire", "sco-test", "a")
        bundle = self.service.export_bundle("sco-test")
        self.assertEqual(len(bundle["nodes"]), 1)
        self.assertEqual(self.service.projection("sco-test")["nodes"], 1)

    def test_dispatch_envelope_fails_honestly_without_bridge(self):
        self.add("a")
        self.write(self.service.issue_work_order, "o1", order("o1", "a"))
        envelope = self.service.dispatch_envelopes("sco-test")[0]
        self.assertFalse(envelope["automatic_dispatch_performed"])
        self.assertEqual(envelope["dispatch_blocker"], "HOST_BRIDGE_REQUIRED")

    def test_csi_lowering_uses_existing_primitives_and_no_new_authority(self):
        self.add("a")
        lowering = lower_superchat(self.service.export_bundle("sco-test"))
        kinds = {item["kind"] for item in lowering["raw_csi_program"]}
        self.assertEqual(kinds, {"OPEN_SESSION", "SEAL_IDENTITAS", "ADD_DATUM", "MODE_ON"})
        self.assertFalse(lowering["authority_created"])
        self.assertFalse(lowering["native_contexts_merged"])

    def test_integrity_detects_projection_tampering(self):
        self.add("a")
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("UPDATE nodes SET record_json='{}' WHERE node_id='a'")
            connection.commit()
        self.assertEqual(self.service.verify()["gate"], "FAIL")

    def test_all_named_provider_uri_families_register(self):
        for provider in ("CODEX", "CHATGPT", "CLINE", "COWORK", "OPENCODE"):
            self.add(provider.lower(), provider=provider)
        self.assertEqual(self.service.projection("sco-test")["nodes"], 5)

    def test_success_receipt_requires_output_reference(self):
        record = receipt("r", "o", "n")
        record["output_refs"] = []
        with self.assertRaises(ContractError):
            validate_receipt(record)

    def test_untampered_ledger_passes_integrity(self):
        self.add("a")
        self.assertEqual(self.service.verify()["gate"], "PASS")


if __name__ == "__main__":
    unittest.main()
