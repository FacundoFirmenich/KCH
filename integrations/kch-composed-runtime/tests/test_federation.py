"""Real original SuperMCP subprocess tests; no surrogate MCP or model server."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from kch_composed.federation import (
    FederationBridge, FederationDenied, FederationUncertain, kch_config,
)


REPOSITORY = Path(__file__).resolve().parents[3]
READY = all(importlib.util.find_spec(name) for name in ("jsonschema", "numpy", "scipy"))


@unittest.skipUnless(READY, "Install the federation optional dependencies")
class FederationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.audit = self.root / "audit.sqlite"
        self.config = kch_config(REPOSITORY, REPOSITORY, self.root / "runtime", "contract-test", "original-kch",
            {"kch.super.status": {"read_only": True}, "studio_status": {"read_only": True},
             "lock_list": {"read_only": True, "fixed_arguments": {"include_inactive": False}}})
        self.bridge = FederationBridge(self.config, self.audit)
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.bridge.close)

    def alias(self, native):
        return "kch_" + hashlib.sha256(native.encode()).hexdigest()[:32]

    def invoke(self, native, args=None, call_id="one"):
        return self.bridge.invoke(self.alias(native), {} if args is None else args, call_id=call_id)

    def test_real_catalogue_and_independent_base_studio_execution(self):
        catalog = self.bridge.discover()
        names = {item["name"] for item in catalog}
        self.assertEqual(len(catalog), len(names))
        self.assertIn("studio_build_and_seal", names)
        self.assertIn("kch.super.session.open", names)
        self.assertEqual(len(self.bridge.schemas()), 3)
        self.assertTrue(all(len(s["function"]["name"]) <= 64 for s in self.bridge.schemas()))
        base = self.invoke("kch.super.status")
        status = json.loads(base["result"]["content"][0]["text"])
        self.assertEqual(status["package_version"], "0.11.0")
        self.assertFalse(status["mutating_execution_authorized"])
        studio = self.invoke("studio_status", call_id="studio")
        governance = studio["result"]["structuredContent"]["governance"]
        self.assertEqual(governance["state"], "VERIFIED_COMPILED_GOVERNANCE")
        self.assertEqual(governance["compiled_artifacts_verified"], 8)
        self.assertEqual(governance["source_nodes_verified"], 23)
        self.assertTrue(self.bridge.audit()["valid"])
        self.assertEqual(self.bridge.audit()["calls_by_status"], {"COMPLETED": 2})

    def test_host_fixed_arguments_hidden_and_not_overridable(self):
        descriptor = next(s for s in self.bridge.schemas() if s["function"]["name"] == self.alias("lock_list"))
        self.assertNotIn("include_inactive", descriptor["function"]["parameters"]["properties"])
        with self.assertRaises(FederationDenied):
            self.invoke("lock_list", {"include_inactive": False})
        receipt = self.invoke("lock_list", call_id="permitted")
        self.assertFalse(receipt["result"].get("isError", False))

    def test_canonical_schema_enforced_before_dispatch(self):
        with self.assertRaises(FederationDenied):
            self.invoke("kch.super.status", {"actor": "SYSTEM_AUTHORITY"})
        self.assertEqual(self.bridge.audit()["calls_by_status"], {})

    def test_discovery_never_enables_unlisted_tool(self):
        self.bridge.discover()
        with self.assertRaises(FederationDenied):
            self.invoke("kch.super.registry")
        with self.assertRaises(FederationDenied):
            self.invoke("studio_create_session", {"spec": {}})
        self.assertEqual(self.bridge.audit()["calls_by_status"], {})

    def test_mutation_cannot_be_relabelled_read_only(self):
        self.bridge.close()
        config = deepcopy(self.config)
        config["allowed_tools"] = {"studio_create_session": {"read_only": True}}
        bridge = FederationBridge(config, self.audit)
        self.addCleanup(bridge.close)
        with self.assertRaisesRegex(FederationDenied, "read-only annotation"):
            bridge.discover()

    def test_mutation_requires_trusted_host_authorizer(self):
        config = deepcopy(self.config)
        config["allowed_tools"] = {"studio_create_session": {"read_only": False}}
        with self.assertRaises(FederationDenied):
            FederationBridge(config, self.audit)

    def test_host_schema_constrains_native_schema(self):
        self.bridge.close()
        config = deepcopy(self.config)
        config["allowed_tools"] = {"lock_list": {"read_only": True, "argument_schema": {
            "type": "object", "properties": {"include_inactive": {"const": False}}, "required": ["include_inactive"]}}}
        self.bridge = FederationBridge(config, self.audit)
        self.addCleanup(self.bridge.close)
        with self.assertRaises(FederationDenied):
            self.invoke("lock_list", {"include_inactive": True})
        with self.assertRaises(FederationDenied):
            self.invoke("lock_list", {"include_inactive": 0})
        self.assertFalse(self.invoke("lock_list", {"include_inactive": False})["result"].get("isError", False))

    def test_completed_call_is_replayed_without_new_dispatch_after_restart(self):
        first = self.invoke("kch.super.status")
        self.bridge.close()
        restarted = FederationBridge(self.config, self.audit)
        self.addCleanup(restarted.close)
        second = restarted.invoke(self.alias("kch.super.status"), {}, call_id="one")
        self.assertEqual(first, second)
        self.assertEqual(restarted.audit()["calls_by_status"], {"COMPLETED": 1})

    def test_id_cannot_select_another_tool(self):
        self.invoke("kch.super.status")
        with self.assertRaises(FederationDenied):
            self.invoke("studio_status")

    def test_actual_child_death_is_uncertain_and_not_replayed(self):
        self.bridge.discover()
        self.bridge._client.process.kill()
        self.bridge._client.process.wait(timeout=5)
        with self.assertRaises(FederationUncertain):
            self.invoke("kch.super.status")
        self.assertEqual(self.bridge.audit()["calls_by_status"], {"UNCERTAIN": 1})
        with self.assertRaises(FederationUncertain):
            self.invoke("kch.super.status")
        self.assertEqual(self.bridge.audit()["calls_by_status"], {"UNCERTAIN": 1})

    def test_state_cannot_be_shared_across_scope(self):
        self.bridge.discover()
        changed = deepcopy(self.config)
        changed["session"] = "another-session"
        other = FederationBridge(changed, self.audit)
        self.addCleanup(other.close)
        with self.assertRaises(FederationDenied):
            other.discover()

    def test_original_config_and_returned_catalog_cannot_mutate_policy(self):
        binding = self.bridge.binding()
        self.config["principal"] = "changed-outside-bridge"
        self.config["allowed_tools"]["studio_create_session"] = {"read_only": True}
        catalog = self.bridge.discover()
        catalog[0]["name"] = "tampered"
        self.assertEqual(self.bridge.binding(), binding)
        self.assertNotIn("tampered", {t["name"] for t in self.bridge.discover()})
        with self.assertRaises(FederationDenied):
            self.invoke("studio_create_session")

    def test_original_governance_lock_rejects_corruption(self):
        self.bridge.discover()
        self.bridge.close()
        marker = self.root / "runtime/locked_governance/.kch-csi-generated-v0.1.0"
        original = marker.read_bytes()
        marker.write_bytes(original[:-1])
        with self.assertRaises(FederationDenied):
            self.bridge.discover()

    def test_audit_detects_receipt_chain_tampering(self):
        self.invoke("kch.super.status")
        with sqlite3.connect(self.audit) as db:
            db.execute("UPDATE federation_events SET previous_hash='invalid' WHERE sequence=2")
        self.assertFalse(self.bridge.audit()["valid"])
        with self.assertRaises(FederationDenied):
            self.invoke("studio_status", call_id="after-tamper")

    def test_completed_result_tampering_is_not_a_valid_cached_receipt(self):
        self.invoke("kch.super.status")
        with sqlite3.connect(self.audit) as db:
            row = db.execute("SELECT response FROM federation_calls").fetchone()
            cached = json.loads(row[0])
            cached["result"]["content"] = []
            db.execute("UPDATE federation_calls SET response=?", (json.dumps(cached),))
        self.assertFalse(self.bridge.audit()["valid"])
        with self.assertRaises(FederationDenied):
            self.invoke("kch.super.status")

    def test_deleted_projection_cannot_replay_a_completed_effect(self):
        self.invoke("kch.super.status")
        with sqlite3.connect(self.audit) as db:
            db.execute("DELETE FROM federation_calls")
        self.assertFalse(self.bridge.audit()["valid"])
        with self.assertRaises(FederationDenied):
            self.invoke("kch.super.status")
        with sqlite3.connect(self.audit) as db:
            events = [json.loads(row[0]) for row in db.execute("SELECT body FROM federation_events")]
        self.assertEqual(sum(e["kind"] == "DISPATCH_STARTED" for e in events), 1)

    def test_cached_receipt_authority_and_exact_contract_cannot_be_altered(self):
        original = self.invoke("kch.super.status")
        altered = []
        for key, value in (("authority_inherited", True), ("authority_inherited", 0),
                           ("schema", "promoted"), ("unaudited_authority", True)):
            item = deepcopy(original)
            item["receipt"][key] = value
            altered.append(item)
        item = deepcopy(original)
        item["unaudited_authority"] = True
        altered.append(item)
        for item in altered:
            with self.subTest(receipt=item["receipt"]):
                with sqlite3.connect(self.audit) as db:
                    db.execute("UPDATE federation_calls SET response=?", (json.dumps(item),))
                self.assertFalse(self.bridge.audit()["valid"])
                with self.assertRaises(FederationDenied):
                    self.invoke("kch.super.status")
        with sqlite3.connect(self.audit) as db:
            events = [json.loads(row[0]) for row in db.execute("SELECT body FROM federation_events")]
        self.assertEqual(sum(e["kind"] == "DISPATCH_STARTED" for e in events), 1)

    def test_projection_cannot_add_unrecorded_call(self):
        self.bridge.discover()
        with sqlite3.connect(self.audit) as db:
            db.execute("INSERT INTO federation_calls VALUES(?,?,?,'STARTED',NULL)",
                (self.bridge.binding()["config_sha256"], "unrecorded", "unknown"))
        self.assertFalse(self.bridge.audit()["valid"])

    def test_uncertain_projection_cannot_be_deleted_or_changed_to_started(self):
        self.bridge.discover()
        self.bridge._client.process.kill()
        self.bridge._client.process.wait(timeout=5)
        with self.assertRaises(FederationUncertain):
            self.invoke("kch.super.status")
        with sqlite3.connect(self.audit) as db:
            db.execute("UPDATE federation_calls SET status='STARTED'")
        self.assertFalse(self.bridge.audit()["valid"])
        with self.assertRaises(FederationDenied):
            self.invoke("kch.super.status")

    def test_truncated_event_tail_is_rejected_by_persisted_head(self):
        self.invoke("kch.super.status")
        with sqlite3.connect(self.audit) as db:
            db.execute("DELETE FROM federation_events WHERE sequence=(SELECT MAX(sequence) FROM federation_events)")
        self.assertFalse(self.bridge.audit()["valid"])
        with self.assertRaises(FederationDenied):
            self.invoke("studio_status", call_id="after-truncation")

    def test_nested_authority_is_not_accepted_as_freeform_payload(self):
        self.bridge.close()
        config = deepcopy(self.config)
        config["allowed_tools"] = {"extension_recommend": {"read_only": True}}
        self.bridge = FederationBridge(config, self.audit)
        self.addCleanup(self.bridge.close)
        with self.assertRaisesRegex(FederationDenied, "bound by the host"):
            self.invoke("extension_recommend", {"records": [{"authority": "SYSTEM_AUTHORITY"}],
                "objective": "inspect repository", "available_runtimes": []})
        self.assertEqual(self.bridge.audit()["calls_by_status"], {})

    def test_remote_schema_reference_is_rejected_without_lookup(self):
        self.config["allowed_tools"]["kch.super.status"]["argument_schema"] = {"$ref": "https://example.invalid/schema"}
        with self.assertRaises(FederationDenied):
            FederationBridge(self.config, self.audit)


if __name__ == "__main__":
    unittest.main()
