"""Real filesystem, memory and native-gate integration tests.

All mutable state is isolated in TemporaryDirectory. The positive native test
prepares an explicitly labelled administrative authorization in the test DB;
it never impersonates the native interactive user gesture. This is a contract
test of consumption, not a claim that a real user approved a production action.
Sensor tests replay a published protocol example, never model inference.
"""

import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
REPOSITORY = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE / "src"))

from kch_composed.memory import MemoryStore, Scope
from kch_composed.tools import ToolDenied, ToolService


class WorkspaceToolCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="kch-tool-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.real_source = REPOSITORY / "README.md"
        self.content = self.real_source.read_bytes()
        shutil.copyfile(self.real_source, self.workspace / "README.md")
        self.memory = MemoryStore(self.root / "memory.sqlite")
        self.addCleanup(self.memory.close)
        self.scope = Scope("contract-test-owner", str(self.workspace), "contract-session")
        self.service = ToolService(REPOSITORY, self.workspace, self.memory, self.scope)

    def execute(self, name, args, *, call_id="contract-call"):
        return self.service.execute(name, args, call_id=call_id)


class WorkspaceToolTests(WorkspaceToolCase):
    def test_read_real_repository_bytes_without_promoting_source_authority(self):
        result = self.execute("read_file", {"path": "README.md", "offset": 3, "max_bytes": 127})
        actual = base64.b64decode(result["content"]["data"])
        self.assertEqual(actual, self.content[3:130])
        self.assertEqual(result["range_sha256"], hashlib.sha256(actual).hexdigest())
        self.assertEqual(result["source_role"], "UNTRUSTED_DATA")

    def test_existing_traversal_and_symlink_escape_are_denied(self):
        outside = self.root / "outside.md"
        shutil.copyfile(self.real_source, outside)
        (self.workspace / "escape.md").symlink_to(outside)
        for path in ("../outside.md", str(outside), "escape.md"):
            for tool in ("read_file", "memory_ingest"):
                args = {"path": path}
                if tool == "memory_ingest":
                    args["source_id"] = "escaped-source"
                with self.subTest(path=path, tool=tool), self.assertRaises(ToolDenied):
                    self.execute(tool, args)
        with self.assertRaises(KeyError):
            self.memory.recall(self.scope, "escaped-source")

    def test_model_cannot_supply_host_identity_or_configuration(self):
        for key in ("principal", "session", "scope", "native_data", "workspace", "enabled"):
            with self.subTest(key=key), self.assertRaises(ToolDenied):
                self.execute("read_file", {"path": "README.md", key: "unauthorized-selector"})
        self.assertEqual(self.service.scope, self.scope)

    def test_write_and_unregistered_sensors_are_disabled(self):
        with self.assertRaises(ToolDenied):
            self.execute("write_file", {"path": "output.md", "content": self.content.decode()})
        self.assertFalse((self.workspace / "output.md").exists())
        self.assertNotIn("write_file", [s["function"]["name"] for s in self.service.schemas()])
        service = ToolService(REPOSITORY, self.workspace, self.memory, self.scope,
                              enabled={"sensor_observe"})
        with self.assertRaises(ToolDenied):
            service.execute("sensor_observe", {"sensor": "not-registered", "state": {},
                                               "questions": {}}, call_id="no-sensor")

    def test_real_memory_ingestion_folding_and_cross_session_denial(self):
        first = self.execute("memory_ingest", {"path": "README.md", "source_id": "repository-readme"})
        second_path = self.workspace / "model.py"
        shutil.copyfile(PACKAGE / "src/kch_composed/model.py", second_path)
        self.execute("memory_ingest", {"path": "model.py", "source_id": "transport-source"})
        recalled = self.execute("memory_recall", {"source_id": "repository-readme"})
        self.assertEqual(base64.b64decode(recalled["content"]["data"]), self.content)
        self.assertEqual(first["scope"]["session"], self.scope.session)
        folded = self.execute("memory_fold", {"source_ids": ["repository-readme", "transport-source"]})
        unfolded = self.execute("memory_unfold", {"fold_id": folded["fold_id"]})
        self.assertEqual([base64.b64decode(x["content"]["data"]) for x in unfolded],
                         [self.content, second_path.read_bytes()])
        self.assertEqual(first["sha256"], hashlib.sha256(self.content).hexdigest())
        results = self.execute("memory_search", {"query": "KCH", "limit": 20})
        self.assertTrue(results)
        view = self.execute("memory_view", {"max_bytes": 256, "recent": 2})
        self.assertIsInstance(view, dict)
        other = ToolService(REPOSITORY, self.workspace, self.memory,
                            Scope(self.scope.principal, self.scope.workspace, "another-session"))
        with self.assertRaises(KeyError):
            other.execute("memory_recall", {"source_id": "repository-readme"}, call_id="other")
        with self.assertRaises(KeyError):
            other.execute("memory_unfold", {"fold_id": folded["fold_id"]}, call_id="other")
        self.assertEqual(other.execute("memory_search", {"query": "KCH"}, call_id="other"), [])

    def test_tool_bounds_and_types_are_enforced_before_effects(self):
        for args in ({"path": "README.md", "offset": -1},
                     {"path": "README.md", "max_bytes": 65537},
                     {"path": "README.md", "max_bytes": True},
                     {"path": "README.md", "offset": "0"}):
            with self.subTest(args=args), self.assertRaises(ToolDenied):
                self.execute("read_file", args)
        small = ToolService(REPOSITORY, self.workspace, self.memory, self.scope, max_source_bytes=8)
        with self.assertRaises(ToolDenied):
            small.execute("memory_ingest", {"path": "README.md", "source_id": "too-big"}, call_id="limit")
        with self.assertRaises(KeyError):
            self.memory.recall(self.scope, "too-big")

    def test_malformed_fold_members_are_denied_before_database_access(self):
        statements = []
        self.memory._db.set_trace_callback(statements.append)
        try:
            for source_ids in ([{"source_id": "repository-readme"}], [True], [1], [""]):
                with self.subTest(source_ids=source_ids), self.assertRaises(ToolDenied):
                    self.execute("memory_fold", {"source_ids": source_ids})
            self.assertEqual(statements, [])
        finally:
            self.memory._db.set_trace_callback(None)

    def test_read_offset_overflow_is_denied_before_file_open(self):
        for offset in (2**63, 10**100):
            with self.subTest(offset=offset), patch.object(Path, "open", side_effect=AssertionError("Unexpected file open")):
                with self.assertRaises(ToolDenied):
                    self.execute("read_file", {"path": "README.md", "offset": offset})

    def test_host_sensor_binding_replays_primary_document_only(self):
        # Reuse the exact TypeSafe primary-document example already attributed
        # by the sensor module tests. It is explicitly a historical replay.
        spec = importlib.util.spec_from_file_location("sensor_document_contract", PACKAGE / "tests/test_sensors.py")
        examples = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(examples)
        class DocumentReplay:
            def evaluate(self, state, questions):
                return examples.observe(examples.CHOICE_RESPONSE, questions)
        service = ToolService(REPOSITORY, self.workspace, self.memory, self.scope,
                              enabled={"sensor_observe"}, sensors={"primary-doc-replay": DocumentReplay()})
        result = service.execute("sensor_observe", {"sensor": "primary-doc-replay",
            "state": {"source_sha256": hashlib.sha256(self.content).hexdigest()},
            "questions": examples.CHOICE_Q}, call_id="document-contract")
        self.assertEqual(result["raw"], examples.CHOICE_RESPONSE)
        self.assertTrue(result["historical"])
        self.assertTrue(result["development_only"])
        self.assertEqual(result["authority"], "NONE")
        self.assertFalse(result["promotion_allowed"])


class NativeWriteContractTests(WorkspaceToolCase):
    def native_service(self):
        self.native_data = self.root / "isolated-native-state"
        self.service = ToolService(REPOSITORY, self.workspace, self.memory, self.scope,
            enabled=ToolService.DEFAULT | {"write_file"}, native_data=self.native_data)
        return self.service

    def initialize_contract_lock(self):
        self.native_service()
        probe = self.service._native("probe", {})
        self.assertFalse(probe["locksEnabled"])
        self.database = self.native_data / "kch_native_r21.sqlite"
        now = datetime.now(timezone.utc).isoformat()
        # Administrative test setup, confined to this freshly created DB.
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE settings SET value='true' WHERE key='locks_enabled'")
            db.execute("INSERT INTO locks(id,kind,pattern,enabled,created_at) VALUES(?,?,?,?,?)",
                       ("contract-fixture-write-lock", "EXACT", "tool:write", 1, now))
        self.assertEqual(self.service._native("probe", {})["exactToolLocks"], ["tool:write"])

    def propose_write(self):
        args = {"path": "authorized-copy.md", "content": self.content.decode("utf-8")}
        with self.assertRaises(ToolDenied):
            self.execute("write_file", args, call_id="first-denied")
        self.assertFalse((self.workspace / args["path"]).exists())
        with sqlite3.connect(self.database) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM proposals WHERE session_id=? ORDER BY created_at DESC",
                             (self.service.native_session_id,)).fetchone()
        self.assertIsNotNone(row)
        exact = {"file_path": str(self.workspace / args["path"]), "content": args["content"]}
        expected = hashlib.sha256(json.dumps(exact, ensure_ascii=False, sort_keys=True,
                                            separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(row["args_sha256"], expected)
        return args, dict(row)

    def prepare_isolated_authorization_fixture(self, row):
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE proposals SET reason=?,impact=?,recovery=?,status='AUTHORIZED' WHERE id=?",
                       ("isolated integration contract test", "temporary copy of actual source bytes",
                        "TemporaryDirectory cleanup", row["id"]))
            db.execute("INSERT INTO authorizations(proposal_id,session_id,args_sha256,authorized_at) VALUES(?,?,?,?)",
                       (row["id"], row["session_id"], row["args_sha256"], now))

    def test_native_write_without_initialized_authority_is_denied(self):
        self.native_service()
        with self.assertRaises(ToolDenied):
            self.execute("write_file", {"path": "absent.md", "content": self.content.decode()})
        self.assertFalse((self.workspace / "absent.md").exists())
        self.service._native("probe", {})
        with self.assertRaises(ToolDenied):
            self.execute("write_file", {"path": "absent.md", "content": self.content.decode()})

    def test_native_lock_creates_exact_proposal_without_execution(self):
        self.initialize_contract_lock()
        self.propose_write()
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM authorizations").fetchone()[0], 0)
        probe = self.service._native("probe", {})
        self.assertTrue(probe["chainValid"])
        self.assertGreater(probe["events"], 0)

    def test_native_admin_rejects_noninteractive_authorization(self):
        self.initialize_contract_lock()
        _, row = self.propose_write()
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE proposals SET status='PROPOSED' WHERE id=?", (row["id"],))
        admin = REPOSITORY / "construct_successors/KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2/vendor/kch-native-r33-0.11.33/scripts/kch_native_admin.py"
        result = subprocess.run([sys.executable, str(admin), "authorize", row["id"]],
            input="", text=True, capture_output=True,
            env={**os.environ, "KCH_NATIVE_DATA": str(self.native_data)}, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DENIED_NOT_A_TRUSTED_INTERACTIVE_USER_GESTURE", result.stderr)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM authorizations").fetchone()[0], 0)

    def test_native_grant_is_exact_session_scoped_consumable_and_receipted(self):
        self.initialize_contract_lock()
        args, row = self.propose_write()
        self.prepare_isolated_authorization_fixture(row)
        altered = {**args, "content": args["content"] + "\n"}
        with self.assertRaises(ToolDenied):
            self.execute("write_file", altered, call_id="wrong-args")
        other = ToolService(REPOSITORY, self.workspace, self.memory,
            Scope(self.scope.principal, self.scope.workspace, "another-session"),
            enabled={"write_file"}, native_data=self.native_data)
        with self.assertRaises(ToolDenied):
            other.execute("write_file", args, call_id="wrong-session")
        for scope in (Scope("another-principal", self.scope.workspace, self.scope.session),
                      Scope(self.scope.principal, "another-workspace-identity", self.scope.session)):
            foreign = ToolService(REPOSITORY, self.workspace, self.memory, scope,
                                  enabled={"write_file"}, native_data=self.native_data)
            with self.subTest(scope=scope), self.assertRaises(ToolDenied):
                foreign.execute("write_file", args, call_id="wrong-host-identity")
        self.assertFalse((self.workspace / args["path"]).exists())
        with sqlite3.connect(self.database) as db:
            self.assertIsNone(db.execute("SELECT consumed_at FROM authorizations WHERE proposal_id=?",
                                        (row["id"],)).fetchone()[0])
        result = self.execute("write_file", args, call_id="authorized-effect")
        destination = self.workspace / args["path"]
        self.assertEqual(destination.read_bytes(), self.content)
        self.assertEqual(result["sha256"], hashlib.sha256(self.content).hexdigest())
        with sqlite3.connect(self.database) as db:
            consumed = db.execute("SELECT consumed_at,consumed_tool_use_id FROM authorizations WHERE proposal_id=?",
                                  (row["id"],)).fetchone()
            self.assertIsNotNone(consumed[0])
            self.assertEqual(consumed[1], "authorized-effect")
            receipt = db.execute("SELECT event_name FROM events WHERE event_hash=?",
                                 (result["native_event_hash"],)).fetchone()
            self.assertEqual(receipt[0], "KCHComposedToolResult")
        with self.assertRaises(ToolDenied):
            self.execute("write_file", args, call_id="cannot-overwrite")
        destination.unlink()  # Remove only the just-created temporary test copy.
        with self.assertRaises(ToolDenied):
            self.execute("write_file", args, call_id="cannot-reuse-consumed-grant")
        self.assertFalse(destination.exists())
        self.assertTrue(self.service._native("probe", {})["chainValid"])

    def test_write_symlink_parent_escape_is_denied_before_native_dispatch(self):
        self.native_service()
        outside_dir = self.root / "outside-dir"
        outside_dir.mkdir()
        (self.workspace / "escape-dir").symlink_to(outside_dir, target_is_directory=True)
        with self.assertRaises(ToolDenied):
            self.execute("write_file", {"path": "escape-dir/output.md", "content": self.content.decode()})
        self.assertFalse((outside_dir / "output.md").exists())
        self.assertFalse(self.native_data.exists())

    def test_receipt_failure_after_real_effect_is_not_classified_as_pre_effect_denial(self):
        self.initialize_contract_lock()
        args, row = self.propose_write()
        self.prepare_isolated_authorization_fixture(row)
        native = self.service._native
        def receipt_transport_failure(action, payload):
            if action == "receipt":
                raise ToolDenied("contract test: receipt transport unavailable")
            return native(action, payload)
        with patch.object(self.service, "_native", side_effect=receipt_transport_failure):
            with self.assertRaises(RuntimeError):
                self.execute("write_file", args, call_id="effect-before-receipt-failure")
        self.assertEqual((self.workspace / args["path"]).read_bytes(), self.content)

    def test_cancellation_after_native_grant_prevents_file_open(self):
        self.initialize_contract_lock()
        args, row = self.propose_write()
        self.prepare_isolated_authorization_fixture(row)
        self.service.cancel_check = lambda: True
        with patch.object(Path, "open", side_effect=AssertionError("File must not open after cancellation")):
            with self.assertRaises(ToolDenied):
                self.execute("write_file", args, call_id="cancelled-before-effect")
        self.assertFalse((self.workspace / args["path"]).exists())
        with sqlite3.connect(self.database) as db:
            consumed = db.execute("SELECT consumed_at,consumed_tool_use_id FROM authorizations WHERE proposal_id=?",
                                  (row["id"],)).fetchone()
            self.assertIsNotNone(consumed[0])
            self.assertEqual(consumed[1], "cancelled-before-effect")
            self.assertEqual(db.execute("SELECT count(*) FROM events WHERE event_name='KCHComposedToolResult'").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
