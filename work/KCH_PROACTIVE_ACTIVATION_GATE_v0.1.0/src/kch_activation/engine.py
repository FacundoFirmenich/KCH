from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from .canonical import normalize_text, sha256_json
from .ledger import ActivationLedger
from .rules import ActivationRule, RuleCatalog


CONSENT_CHOICES = (
    "Sí",
    "No",
    "Nunca en esta sesión",
    "Siempre en esta sesión",
)
NORMALIZED_CHOICES = {
    normalize_text("Sí"): "YES",
    normalize_text("No"): "NO",
    normalize_text("Nunca en esta sesión"): "NEVER_THIS_SESSION",
    normalize_text("Siempre en esta sesión"): "ALWAYS_THIS_SESSION",
}


class ActivationEngine:
    def __init__(
        self,
        ledger: ActivationLedger,
        catalog: RuleCatalog,
        executor: Callable[[str, dict[str, Any]], dict[str, Any]],
        *,
        now: Callable[[], int] | None = None,
    ):
        self.ledger = ledger
        self.catalog = catalog
        self.executor = executor
        self.now = now or (lambda: int(time.time()))

    @staticmethod
    def parse_response(text: str) -> str | None:
        return NORMALIZED_CHOICES.get(normalize_text(text).strip())

    @staticmethod
    def _question(rule: ActivationRule) -> str:
        return (
            f"KCH considera indicado lanzar «{rule.target_tool}» porque {rule.reason_es}. "
            "¿Deseas ejecutarla? Responde exactamente con una de estas cuatro opciones: "
            "Sí · No · Nunca en esta sesión · Siempre en esta sesión."
        )

    def _new_proposal(self, session_id: str, event_id: str, rule: ActivationRule, source_text: str) -> dict[str, Any]:
        created_at = self.now()
        core = {
            "session_id": session_id,
            "event_id": event_id,
            "rule_id": rule.rule_id,
            "tool_name": rule.target_tool,
            "arguments": rule.arguments,
            "created_at": created_at,
        }
        return self.ledger.create_proposal(
            {
                **core,
                "proposal_id": str(uuid.uuid4()),
                "question": self._question(rule),
                "reason": rule.reason_es,
                "confidence": rule.confidence,
                "fingerprint": sha256_json(core),
                "source_text": source_text,
                "expires_at": created_at + self.catalog.proposal_ttl_seconds,
            }
        )

    def _execute(self, proposal: dict[str, Any], response: str, success_state: str) -> dict[str, Any]:
        original_prompt = proposal.get("source_text", "")
        claimed = self.ledger.claim_execution(proposal["session_id"], proposal["proposal_id"], response)
        execution_id = str(uuid.uuid4())
        try:
            result = self.executor(claimed["tool_name"], claimed["arguments"])
        except Exception as exc:
            failed = self.ledger.finish_execution(claimed["session_id"], claimed["proposal_id"], "EXECUTION_FAILED")
            receipt = self.ledger.record_execution(failed, execution_id, "FAIL", None)
            return {
                "schema": "kch.activation-decision.v0.1.0",
                "action": "EXECUTION_FAILED",
                "response": response,
                "proposal": failed,
                "execution": receipt,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "original_prompt": original_prompt,
            }
        result_hash = sha256_json(result)
        completed = self.ledger.finish_execution(claimed["session_id"], claimed["proposal_id"], success_state)
        receipt = self.ledger.record_execution(completed, execution_id, "PASS", result_hash)
        return {
            "schema": "kch.activation-decision.v0.1.0",
            "action": "EXECUTED",
            "response": response,
            "proposal": completed,
            "execution": receipt,
            "tool_result": result,
            "original_prompt": original_prompt,
        }

    def respond(self, session_id: str, response_text: str, proposal_id: str | None = None) -> dict[str, Any]:
        response = self.parse_response(response_text)
        if response is None:
            raise ValueError("respuesta inválida: use Sí, No, Nunca en esta sesión o Siempre en esta sesión")
        proposal = self.ledger.get_proposal(session_id, proposal_id) if proposal_id else self.ledger.pending(session_id)
        if proposal is None:
            raise ValueError("no hay una consulta de activación pendiente en esta sesión")
        original_prompt = proposal.get("source_text", "")
        if response == "NO":
            resolved = self.ledger.resolve(session_id, proposal["proposal_id"], response, "DECLINED_ONCE")
            return {"schema": "kch.activation-decision.v0.1.0", "action": "DECLINED", "response": response, "proposal": resolved, "original_prompt": original_prompt}
        if response == "NEVER_THIS_SESSION":
            resolved = self.ledger.resolve(session_id, proposal["proposal_id"], response, "NEVER_THIS_SESSION")
            self.ledger.set_policy(session_id, proposal["rule_id"], proposal["tool_name"], response)
            return {"schema": "kch.activation-decision.v0.1.0", "action": "SUPPRESSED_FOR_SESSION", "response": response, "proposal": resolved, "original_prompt": original_prompt}
        if response == "YES":
            return self._execute(proposal, response, "EXECUTED_ONCE")
        decision = self._execute(proposal, response, "ALWAYS_THIS_SESSION_EXECUTED")
        if decision["action"] == "EXECUTED":
            self.ledger.set_policy(session_id, proposal["rule_id"], proposal["tool_name"], response)
            decision["session_policy"] = response
        return decision

    def scan(self, session_id: str, event_id: str, event_type: str, text: str) -> dict[str, Any]:
        pending = self.ledger.pending(session_id)
        if pending is not None:
            if self.parse_response(text) is not None:
                return self.respond(session_id, text, pending["proposal_id"])
            self.ledger.bypass_pending(session_id, pending["proposal_id"])

        for rule in self.catalog.match(event_type, text):
            prior = self.ledger.proposal_for_event(session_id, event_id, rule.rule_id)
            if prior is not None:
                return {"schema": "kch.activation-scan.v0.1.0", "action": "DEDUPLICATED", "proposal": prior}

            policy = self.ledger.policy(session_id, rule.rule_id, rule.target_tool)
            if policy == "NEVER_THIS_SESSION":
                self.ledger.record_suppression(session_id, event_id, rule.rule_id, rule.target_tool, policy)
                return {"schema": "kch.activation-scan.v0.1.0", "action": "SUPPRESSED", "policy": policy, "rule": rule.describe()}

            if policy == "ALWAYS_THIS_SESSION":
                proposal = self._new_proposal(session_id, event_id, rule, text)
                decision = self._execute(proposal, "AUTO_ALWAYS_THIS_SESSION", "ALWAYS_THIS_SESSION_EXECUTED")
                decision["session_policy"] = policy
                decision["automatic_under_session_policy"] = True
                return decision

            if self.ledger.rule_question_count(session_id, rule.rule_id) >= rule.max_queries_per_session:
                self.ledger.record_suppression(session_id, event_id, rule.rule_id, rule.target_tool, "QUERY_BUDGET_EXHAUSTED")
                continue

            latest = self.ledger.latest_resolution_time(session_id, rule.rule_id)
            if latest is not None and self.now() - latest < rule.cooldown_seconds:
                self.ledger.record_suppression(session_id, event_id, rule.rule_id, rule.target_tool, "COOLDOWN")
                continue

            proposal = self._new_proposal(session_id, event_id, rule, text)
            return {
                "schema": "kch.activation-scan.v0.1.0",
                "action": "ASK_USER",
                "proposal": proposal,
                "choices": list(CONSENT_CHOICES),
                "action_class": "READ_ONLY",
                "phl_real_execution": False,
            }

        return {"schema": "kch.activation-scan.v0.1.0", "action": "NO_ACTIVATION"}

    def close_session(self, session_id: str) -> dict[str, Any]:
        return self.ledger.close_session(session_id)

    def status(self, session_id: str | None = None) -> dict[str, Any]:
        return {
            "schema": "kch.proactive-activation-gate-status.v0.1.0",
            "mode": "CONSULT_FIRST",
            "choices": list(CONSENT_CHOICES),
            "catalog": self.catalog.describe(),
            "ledger": self.ledger.status(session_id),
            "mutating_autoexecution": False,
            "phl_real_execution": False,
        }
