from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


GATE = Path(__file__).resolve().parents[1]
WORKSPACE = GATE.parents[1]
sys.path.insert(0, str(GATE / "src"))

from kch_activation.engine import ActivationEngine, CONSENT_CHOICES
from kch_activation.ledger import ActivationLedger
from kch_activation.rules import RuleCatalog


class Clock:
    def __init__(self):
        self.value = 2_000_000_000

    def __call__(self) -> int:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += seconds


class Harness:
    def __init__(self, root: Path):
        self.clock = Clock()
        self.calls: list[tuple[str, dict]] = []
        self.ledger = ActivationLedger(root / "activation.sqlite3", now=self.clock)
        self.catalog = RuleCatalog(GATE / "config" / "activation_rules.v0.1.0.json")
        self.engine = ActivationEngine(self.ledger, self.catalog, self.execute, now=self.clock)

    def execute(self, tool_name: str, arguments: dict) -> dict:
        self.calls.append((tool_name, arguments))
        return {"tool": tool_name, "arguments": arguments, "observed": True}


class ActivationGateUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.harness = Harness(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def ask(self, session: str = "s1", event: str = "e1") -> dict:
        return self.harness.engine.scan(session, event, "USER_PROMPT_SUBMIT", "Comprueba el estado del runtime KCH")

    def test_exact_four_choices_and_yes_is_one_use(self) -> None:
        asked = self.ask()
        self.assertEqual(asked["action"], "ASK_USER")
        self.assertEqual(tuple(asked["choices"]), CONSENT_CHOICES)
        self.assertEqual(asked["proposal"]["source_text"], "Comprueba el estado del runtime KCH")
        decision = self.harness.engine.respond("s1", "Sí")
        self.assertEqual(decision["action"], "EXECUTED")
        self.assertEqual(decision["proposal"]["state"], "EXECUTED_ONCE")
        self.assertEqual(len(self.harness.calls), 1)
        self.assertEqual(self.harness.ledger.get_proposal("s1", asked["proposal"]["proposal_id"])["source_text"], "")
        with self.assertRaisesRegex(ValueError, "no hay una consulta"):
            self.harness.engine.respond("s1", "Sí")

    def test_no_declines_once_without_policy(self) -> None:
        self.ask()
        decision = self.harness.engine.respond("s1", "No")
        self.assertEqual(decision["action"], "DECLINED")
        self.assertEqual(len(self.harness.calls), 0)
        self.assertIsNone(self.harness.ledger.policy("s1", "ACT-STATUS-001", "kch.super.status"))

    def test_never_is_same_rule_same_tool_same_session_only(self) -> None:
        self.ask()
        decision = self.harness.engine.respond("s1", "Nunca en esta sesión")
        self.assertEqual(decision["action"], "SUPPRESSED_FOR_SESSION")
        suppressed = self.harness.engine.scan("s1", "e2", "USER_PROMPT_SUBMIT", "Verifica el estado del runtime KCH")
        self.assertEqual(suppressed["action"], "SUPPRESSED")
        other_session = self.harness.engine.scan("s2", "e3", "USER_PROMPT_SUBMIT", "Verifica el estado del runtime KCH")
        self.assertEqual(other_session["action"], "ASK_USER")

    def test_always_executes_current_and_future_matching_events_only_in_session(self) -> None:
        self.ask()
        decision = self.harness.engine.respond("s1", "Siempre en esta sesión")
        self.assertEqual(decision["action"], "EXECUTED")
        self.assertEqual(decision["session_policy"], "ALWAYS_THIS_SESSION")
        second = self.harness.engine.scan("s1", "e2", "USER_PROMPT_SUBMIT", "Verifica el estado del runtime KCH")
        self.assertEqual(second["action"], "EXECUTED")
        self.assertTrue(second["automatic_under_session_policy"])
        self.assertEqual(len(self.harness.calls), 2)
        other_session = self.harness.engine.scan("s2", "e3", "USER_PROMPT_SUBMIT", "Verifica el estado del runtime KCH")
        self.assertEqual(other_session["action"], "ASK_USER")

    def test_session_close_erases_policies_but_preserves_valid_chain(self) -> None:
        self.ask()
        self.harness.engine.respond("s1", "Siempre en esta sesión")
        closed = self.harness.engine.close_session("s1")
        self.assertEqual(closed["session_policies_removed"], 1)
        self.assertIsNone(self.harness.ledger.policy("s1", "ACT-STATUS-001", "kch.super.status"))
        self.assertEqual(self.harness.ledger.verify()["gate"], "PASS")

    def test_failed_executor_is_not_recorded_as_success_or_always_policy(self) -> None:
        def fail(_name: str, _arguments: dict) -> dict:
            raise RuntimeError("observable failure")

        self.harness.engine.executor = fail
        self.ask()
        decision = self.harness.engine.respond("s1", "Siempre en esta sesión")
        self.assertEqual(decision["action"], "EXECUTION_FAILED")
        self.assertEqual(decision["proposal"]["state"], "EXECUTION_FAILED")
        self.assertIsNone(self.harness.ledger.policy("s1", "ACT-STATUS-001", "kch.super.status"))
        self.assertEqual(self.harness.ledger.status("s1")["executions"], {"FAIL": 1})

    def test_pending_prompt_is_bypassed_by_unrelated_new_prompt(self) -> None:
        asked = self.ask()
        result = self.harness.engine.scan("s1", "e2", "USER_PROMPT_SUBMIT", "Escribe un saludo breve")
        self.assertEqual(result["action"], "NO_ACTIVATION")
        old = self.harness.ledger.get_proposal("s1", asked["proposal"]["proposal_id"])
        self.assertEqual(old["state"], "BYPASSED_BY_NEW_PROMPT")
        self.assertEqual(old["source_text"], "")

    def test_ledger_tampering_is_detected(self) -> None:
        self.ask()
        connection = sqlite3.connect(self.harness.ledger.path)
        try:
            connection.execute("UPDATE events SET payload_json='{}' WHERE sequence=1")
            connection.commit()
        finally:
            connection.close()
        verified = self.harness.ledger.verify()
        self.assertEqual(verified["gate"], "FAIL")
        self.assertIn("EVENT_HASH:1", verified["defects"])

    def test_invalid_response_does_not_infer_consent(self) -> None:
        self.ask()
        with self.assertRaisesRegex(ValueError, "respuesta inválida"):
            self.harness.engine.respond("s1", "quizá")
        self.assertEqual(len(self.harness.calls), 0)
        self.assertIsNotNone(self.harness.ledger.pending("s1"))


class ActivationGateIntegrationTests(unittest.TestCase):
    def test_codex_hook_blocks_then_replays_and_applies_session_policy(self) -> None:
        user_hook = GATE / "adapters" / "codex" / "kch_activation_user_prompt.py"
        end_hook = GATE / "adapters" / "codex" / "kch_activation_session_end.py"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            activation_state = root / "activation.sqlite3"
            env = dict(os.environ)
            env["KCH_ACTIVATION_STATE"] = str(activation_state)
            env["KCH_011_STATE"] = str(root / "base.sqlite3")

            def hook(script: Path, payload: dict) -> dict | None:
                completed = subprocess.run(
                    [r"C:\Python314\python.exe", "-X", "utf8", str(script)],
                    input=json.dumps(payload, ensure_ascii=False),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env=env,
                    cwd=WORKSPACE,
                    timeout=30,
                    check=True,
                )
                return json.loads(completed.stdout) if completed.stdout else None

            first = hook(user_hook, {"session_id": "hook-s1", "turn_id": "t1", "prompt": "Comprueba el estado del runtime KCH"})
            assert first is not None
            self.assertEqual(first["decision"], "block")
            for choice in CONSENT_CHOICES:
                self.assertIn(choice, first["reason"])

            accepted = hook(user_hook, {"session_id": "hook-s1", "turn_id": "t2", "prompt": "Siempre en esta sesión"})
            assert accepted is not None
            context = accepted["hookSpecificOutput"]["additionalContext"]
            self.assertIn("PETICIÓN ORIGINAL", context)
            self.assertIn("Comprueba el estado del runtime KCH", context)
            self.assertIn('"action": "EXECUTED"', context)

            automatic = hook(user_hook, {"session_id": "hook-s1", "turn_id": "t3", "prompt": "Verifica de nuevo el estado del runtime KCH"})
            assert automatic is not None
            auto_context = automatic["hookSpecificOutput"]["additionalContext"]
            self.assertIn("AUTO_ALWAYS_THIS_SESSION", auto_context)
            self.assertIn("automatic_under_session_policy", auto_context)

            self.assertIsNone(hook(end_hook, {"session_id": "hook-s1", "reason": "other"}))
            ledger = ActivationLedger(activation_state)
            self.assertIsNone(ledger.policy("hook-s1", "ACT-STATUS-001", "kch.super.status"))
            self.assertEqual(ledger.verify()["gate"], "PASS")
            with ledger.connection() as connection:
                phl_count = connection.execute("SELECT COUNT(*) FROM executions WHERE tool_name='kch.phl.projection'").fetchone()[0]
            self.assertEqual(phl_count, 0)

    def test_overlay_mcp_exposes_base_plus_activation_without_phl_execution(self) -> None:
        launcher = GATE / "launcher" / "run_kch_activation.py"
        process = subprocess.Popen(
            [r"C:\Python314\python.exe", "-X", "utf8", "-u", str(launcher)],
            cwd=WORKSPACE,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        assert process.stdin and process.stdout

        def request(value: dict) -> dict:
            process.stdin.write(json.dumps(value, ensure_ascii=False) + "\n")
            process.stdin.flush()
            return json.loads(process.stdout.readline())

        try:
            initialized = request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            self.assertEqual(initialized["result"]["serverInfo"]["version"], "0.11.0+activation.gate.1")
            self.assertIn("Nunca en esta sesión", initialized["result"]["instructions"])
            listed = request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            names = {row["name"] for row in listed["result"]["tools"]}
            self.assertEqual(len(names), 53)
            self.assertIn("kch.activation.scan", names)
            self.assertIn("kch.phl.projection", names)
            called = request({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "kch.activation.status", "arguments": {"session_id": "mcp-test"}}})
            status = json.loads(called["result"]["content"][0]["text"])
            self.assertFalse(status["phl_real_execution"])
            self.assertEqual(status["mode"], "CONSULT_FIRST")
        finally:
            process.terminate()
            process.wait(timeout=10)
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
