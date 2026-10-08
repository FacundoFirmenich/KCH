"""Real local runtime integration, with no model response generated or fabricated.

Persisted assistant tool-call envelopes below are explicit recovery-contract
inputs authored by this test, not claims of model inference. The client sentinel
only proves whether a model boundary would have been crossed; it returns nothing.
"""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from kch_composed.journal import SessionConfigurationError, UncertainEffectError
from kch_composed.runtime import ContextBudgetError, Runtime, SessionBusy
from kch_composed.tools import ToolDenied


PACKAGE = Path(__file__).resolve().parents[1]
REPOSITORY = PACKAGE.parents[1]


class NoModelBoundarySentinel:
    """No service, no inference: fail immediately if the boundary is reached."""
    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        raise AssertionError("model boundary reached; no inference performed by this test")


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kch-runtime-contract-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.state = self.root / "state"
        self.original = (REPOSITORY / "README.md").read_bytes()
        self.second = (PACKAGE / "src/kch_composed/model.py").read_bytes()
        shutil.copyfile(REPOSITORY / "README.md", self.workspace / "README.md")
        shutil.copyfile(PACKAGE / "src/kch_composed/model.py", self.workspace / "model.py")
        self.runtime = self.open()

    def open(self, **changes):
        fields = {"repository": REPOSITORY, "state": self.state, "workspace": self.workspace,
                  "principal": "runtime-contract-owner", "session": "runtime-contract-session"}
        fields.update(changes)
        runtime = Runtime(**fields)
        self.addCleanup(runtime.memory.close)
        self.addCleanup(runtime.journal.close)
        return runtime

    def seed_recovery_contract(self, *, tool="read_file", arguments=None):
        arguments = arguments or {"path": "README.md", "max_bytes": 65536}
        # Deliberately authored protocol input, not a fabricated model output.
        return self.runtime.journal.append("message", {"role": "assistant", "content": None,
            "tool_calls": [{"id": "explicit-recovery-contract", "type": "function",
                            "function": {"name": tool, "arguments": json.dumps(arguments)}}]})

    def test_read_ingest_fold_unfold_survive_runtime_reopen(self):
        result = self.runtime.execute("read-original", "read_file", {"path": "README.md", "max_bytes": 65536})
        self.assertTrue(result["ok"])
        self.assertEqual(base64.b64decode(result["value"]["content"]["data"]), self.original[:65536])
        self.runtime.execute("ingest-original", "memory_ingest", {"path": "README.md", "source_id": "original"})
        self.runtime.execute("ingest-transport", "memory_ingest", {"path": "model.py", "source_id": "transport"})
        folded = self.runtime.execute("fold-sources", "memory_fold", {"source_ids": ["original", "transport"]})
        restarted = self.open()
        unfolded = restarted.execute("unfold-after-reopen", "memory_unfold", {"fold_id": folded["value"]["fold_id"]})
        self.assertTrue(unfolded["ok"])
        self.assertEqual([base64.b64decode(x["content"]["data"]) for x in unfolded["value"]],
                         [self.original, self.second])
        self.assertTrue(restarted.inspect()["journal"])

    def test_session_scope_and_configuration_immutable(self):
        self.runtime.execute("ingest", "memory_ingest", {"path": "README.md", "source_id": "original"})
        other = self.open(session="different-session")
        result = other.execute("recall", "memory_recall", {"source_id": "original"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "KeyError")
        self.assertNotEqual(other.tools.native_session_id, self.runtime.tools.native_session_id)
        with self.assertRaises(SessionConfigurationError):
            self.open(enabled={"read_file"})

    def test_idempotent_call_returns_persisted_bytes_and_rejects_changed_arguments(self):
        args = {"path": "README.md", "max_bytes": 65536}
        first = self.runtime.execute("durable-read", "read_file", args)
        # The workspace source changes to another actual repository file.
        shutil.copyfile(PACKAGE / "src/kch_composed/model.py", self.workspace / "README.md")
        restarted = self.open()
        self.assertEqual(restarted.execute("durable-read", "read_file", args), first)
        fresh = restarted.execute("fresh-read", "read_file", args)
        self.assertEqual(base64.b64decode(fresh["value"]["content"]["data"]), self.second[:65536])
        with self.assertRaises(ValueError):
            restarted.execute("durable-read", "read_file", {"path": "model.py"})

    def test_recovery_executes_persisted_tool_contract_against_real_files(self):
        event = self.seed_recovery_contract()
        restarted = self.open()
        results = restarted.recover_tools()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["call_id"], f"model:{event['seq']}:explicit-recovery-contract")
        self.assertEqual(base64.b64decode(results[0]["result"]["value"]["content"]["data"]), self.original[:65536])
        self.assertEqual(restarted.recover_tools(), [])
        self.assertEqual(restarted.journal.messages()[-1]["role"], "tool")

    def test_completed_effect_without_tool_message_recovers_receipt_only(self):
        args = {"path": "README.md", "max_bytes": 65536}
        event = self.seed_recovery_contract(arguments=args)
        call_id = f"model:{event['seq']}:explicit-recovery-contract"
        recorded = self.runtime.execute(call_id, "read_file", args)
        shutil.copyfile(PACKAGE / "src/kch_composed/model.py", self.workspace / "README.md")
        restarted = self.open()
        results = restarted.recover_tools()
        self.assertEqual(results[0]["result"], recorded)
        self.assertEqual(base64.b64decode(results[0]["result"]["value"]["content"]["data"]), self.original[:65536])

    def test_started_call_blocks_recovery_without_a_confirmed_outcome(self):
        args = {"path": "README.md", "max_bytes": 65536}
        event = self.seed_recovery_contract(arguments=args)
        call_id = f"model:{event['seq']}:explicit-recovery-contract"
        self.runtime.journal.call_begin(call_id, "read_file", args)
        restarted = self.open()
        with self.assertRaises(UncertainEffectError):
            restarted.recover_tools()
        self.assertEqual(restarted.journal.calls()[0]["status"], "STARTED")
        self.assertFalse(any(m.get("role") == "tool" for m in restarted.journal.messages()))

    def test_cancel_and_resume_are_durable_and_do_not_create_denied_call(self):
        self.runtime.cancel()
        restarted = self.open()
        with self.assertRaises(ToolDenied):
            restarted.execute("cancelled-read", "read_file", {"path": "README.md"})
        self.assertEqual(restarted.journal.calls(), [])
        sentinel = NoModelBoundarySentinel()
        response = restarted.run(sentinel, self.original.decode("utf-8"))
        self.assertEqual(response["status"], "CANCELLED")
        self.assertEqual(sentinel.calls, 0)
        restarted.resume()
        self.assertTrue(restarted.execute("resumed-read", "read_file", {"path": "README.md"})["ok"])

    def test_uncertain_model_request_requires_ack_before_model_boundary(self):
        self.runtime.journal.append("model.request", {"request_id": "explicit-request-delivery-contract",
            "messages_sha256": hashlib.sha256(self.original).hexdigest(), "tool_names": []})
        sentinel = NoModelBoundarySentinel()
        with self.assertRaises(UncertainEffectError):
            self.runtime.run(sentinel, self.original.decode("utf-8"))
        self.assertEqual(sentinel.calls, 0)
        # Explicit acknowledgement may reach the boundary; sentinel returns no model data.
        with self.assertRaisesRegex(AssertionError, "no inference performed"):
            self.runtime.run(sentinel, self.original.decode("utf-8"), retry_model=True)
        self.assertEqual(sentinel.calls, 1)
        acks = [e for e in self.runtime.journal.events() if e["kind"] == "model.retry_acknowledged"]
        self.assertEqual([e["payload"]["request_id"] for e in acks], ["explicit-request-delivery-contract"])

    def test_context_budget_blocks_model_boundary_without_dropping_messages(self):
        sentinel = NoModelBoundarySentinel()
        with self.assertRaises(ContextBudgetError):
            self.runtime.run(sentinel, self.original.decode("utf-8"), max_context_bytes=1)
        self.assertEqual(sentinel.calls, 0)
        self.assertIn(self.original.decode("utf-8"), [m["content"] for m in self.runtime.journal.messages()])
        self.assertFalse(any(e["kind"] == "model.request" for e in self.runtime.journal.events()))

    def test_pending_tools_reject_a_new_user_turn_before_model_boundary(self):
        self.seed_recovery_contract()
        sentinel = NoModelBoundarySentinel()
        with self.assertRaisesRegex(ValueError, "Pending tool messages"):
            self.runtime.run(sentinel, self.original.decode("utf-8"))
        self.assertEqual(sentinel.calls, 0)

    def test_session_lock_rejects_second_owner(self):
        other = self.open()
        with self.runtime.lock():
            with self.assertRaises(SessionBusy):
                other.execute("locked-read", "read_file", {"path": "README.md"})
        self.assertEqual(other.journal.calls(), [])

    def test_private_runtime_state_inside_workspace_is_not_a_tool_resource(self):
        nested = self.open(state=self.workspace / "private-state", session="private-state-isolation")
        self.assertTrue((self.workspace / "private-state/sessions.sqlite").is_file())
        (self.workspace / "state-link.sqlite").symlink_to(self.workspace / "private-state/sessions.sqlite")
        for index, path in enumerate(("private-state/sessions.sqlite", "private-state/memory.sqlite", "state-link.sqlite")):
            with self.subTest(path=path):
                result = nested.execute(f"denied-state-read-{index}", "read_file", {"path": path})
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"], "ToolDenied")
                archived = nested.execute(f"denied-state-ingest-{index}", "memory_ingest",
                                          {"path": path, "source_id": f"private-state-{index}"})
                self.assertFalse(archived["ok"])
                self.assertEqual(archived["error"], "ToolDenied")
        self.assertTrue(nested.execute("allowed-workspace-read", "read_file", {"path": "README.md"})["ok"])


if __name__ == "__main__":
    unittest.main()
