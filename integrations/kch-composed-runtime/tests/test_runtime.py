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
import sqlite3
import tempfile
import unittest

from kch_composed.journal import SessionConfigurationError, UncertainEffectError
from kch_composed.model import ModelProtocolError, ModelTruncationError
from kch_composed.runtime import ContextBudgetError, Runtime, SessionBusy, canonical
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
        self.assertFalse(response["prompt_accepted"])
        self.assertEqual(restarted.journal.messages(), [])
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

    def test_terminal_persisted_assistant_is_not_generated_again(self):
        # Authored terminal protocol record, not a reported inference result.
        self.runtime.journal.append("message", {"role": "user", "content": "Inspect source"})
        final = {"role": "assistant", "content": self.original.decode("utf-8")}
        self.runtime.journal.append("message", final)
        sentinel = NoModelBoundarySentinel()
        response = self.open().run(sentinel)
        self.assertEqual(response["status"], "COMPLETED")
        self.assertEqual(response["message"], final)
        self.assertTrue(response["reused_persisted_response"])
        self.assertEqual(sentinel.calls, 0)

    def test_exact_legacy_assistant_recovers_delivery_without_retrying_model(self):
        self.runtime.journal.append("message", {"role": "user", "content": "Inspect source"})
        digest = hashlib.sha256(canonical(self.runtime.journal.messages()).encode()).hexdigest()
        self.runtime.journal.append("model.request", {"request_id": "legacy-response-contract",
            "messages_sha256": digest, "tool_names": []})
        final = {"role": "assistant", "content": self.original.decode("utf-8")}
        assistant_event = self.runtime.journal.append("message", final)
        sentinel = NoModelBoundarySentinel()
        restarted = self.open()
        response = restarted.run(sentinel)
        self.assertEqual(response["status"], "COMPLETED")
        self.assertEqual(sentinel.calls, 0)
        receipt = [e for e in restarted.journal.events() if e["kind"] == "model.received"][0]["payload"]
        self.assertEqual(receipt["request_id"], "legacy-response-contract")
        self.assertEqual(receipt["recovered_from_message_seq"], assistant_event["seq"])
        self.assertIsNone(receipt["usage"])
        self.assertIsNone(receipt["finish_reason"])

    def test_legacy_message_without_matching_request_context_stays_uncertain(self):
        self.runtime.journal.append("message", {"role": "user", "content": "Inspect source"})
        self.runtime.journal.append("model.request", {"request_id": "unmatched-context-contract",
            "messages_sha256": hashlib.sha256(self.original).hexdigest(), "tool_names": []})
        self.runtime.journal.append("message", {"role": "assistant", "content": self.original.decode("utf-8")})
        sentinel = NoModelBoundarySentinel()
        with self.assertRaises(UncertainEffectError):
            self.open().run(sentinel)
        self.assertEqual(sentinel.calls, 0)
        self.assertFalse(any(e["kind"] == "model.received" for e in self.runtime.journal.events()))

    def test_interrupted_tool_pairing_cannot_execute_an_old_batch(self):
        self.seed_recovery_contract()
        self.runtime.journal.append("message", {"role": "user", "content": "Invalid intervening turn contract"})
        with self.assertRaises(ModelProtocolError):
            self.runtime.recover_tools()
        self.assertEqual(self.runtime.journal.calls(), [])

    def test_stop_after_real_tool_prevents_next_model_request(self):
        self.runtime.journal.append("message", {"role": "user", "content": "Inspect source"})
        self.seed_recovery_contract()
        execute = self.runtime.tools.execute

        def execute_then_stop(*args, **kwargs):
            value = execute(*args, **kwargs)
            self.runtime.cancel()
            return value

        self.runtime.tools.execute = execute_then_stop
        sentinel = NoModelBoundarySentinel()
        response = self.runtime.run(sentinel)
        self.assertEqual(response["status"], "CANCELLED")
        self.assertEqual(sentinel.calls, 0)
        self.assertEqual(self.runtime.journal.calls()[0]["status"], "DONE")
        self.assertEqual(self.runtime.journal.messages()[-1]["role"], "tool")
        self.assertFalse(any(e["kind"] == "model.request" for e in self.runtime.journal.events()))

    def test_stop_during_contract_client_return_persists_response_without_effects(self):
        # This deliberately authored client tests protocol control flow only.
        # It does not call, impersonate or measure a model.
        owner = self.runtime
        tool_message = {"role": "assistant", "content": None, "tool_calls": [{
            "id": "explicit-stop-contract", "type": "function", "function": {
                "name": "read_file", "arguments": '{"path":"README.md"}'}}]}

        class ContractClient:
            def complete(self, messages, tools):
                owner.cancel()
                return tool_message

        response = owner.run(ContractClient(), "Inspect source")
        self.assertEqual(response["status"], "CANCELLED")
        self.assertTrue(response["response_persisted"])
        self.assertEqual(owner.journal.calls(), [])
        events = owner.journal.events()
        self.assertEqual([e["kind"] for e in events[-2:]], ["message", "model.received"])
        owner.resume()
        recovered = owner.recover_tools()
        self.assertEqual(base64.b64decode(recovered[0]["result"]["value"]["content"]["data"]),
                         self.original[:65536])

    def test_reported_truncation_from_alternate_client_cannot_complete_or_dispatch(self):
        content = self.original.decode("utf-8")

        class ExplicitTruncationContractClient:
            last_finish_reason = "length"

            def complete(self, messages, tools):
                return {"role": "assistant", "content": content}

        with self.assertRaises(ModelTruncationError):
            self.runtime.run(ExplicitTruncationContractClient(), "Inspect source")
        self.assertEqual(self.runtime.journal.calls(), [])
        self.assertFalse(any(e["kind"] == "model.received" for e in self.runtime.journal.events()))

    def test_context_manager_closes_real_databases_idempotently(self):
        with self.open(session="context-managed-session") as runtime:
            self.assertTrue(runtime.journal.verify())
        runtime.close()
        with self.assertRaises(sqlite3.ProgrammingError):
            runtime.journal.verify()
        with self.assertRaises(sqlite3.ProgrammingError):
            runtime.memory.search(runtime.scope, "source")

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
