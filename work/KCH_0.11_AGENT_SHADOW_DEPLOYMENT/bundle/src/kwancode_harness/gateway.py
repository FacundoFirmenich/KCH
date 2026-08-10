from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .adapters import FederationAdapters
from .canonical import canonical_json, require_sha256, require_string_list, require_text, sha256_json
from .controls import CONTROL_CATALOG, describe_controls, evaluate_control
from .ledger import Ledger
from .registry import Registry

EVIDENCE_ROLES = {"DIRECT", "DERIVED", "TRANSPORT", "EXECUTION", "OUTCOME"}
PROFILES = {"minimal", "research", "agent-shadow"}


class CapabilityError(ValueError):
    pass


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class Gateway:
    def __init__(
        self,
        state_path: str | Path,
        registry_path: str | Path,
        secret: bytes,
        *,
        profile: str = "agent-shadow",
        bundle_root: str | Path | None = None,
        now: Callable[[], int] | None = None,
    ):
        if len(secret) < 32:
            raise ValueError("HMAC secret must contain at least 32 bytes")
        if profile == "enforced":
            raise ValueError("profile enforced is PROHIBITED_UNTIL_GATES_PASS")
        if profile not in PROFILES:
            raise ValueError("unknown KCH profile")
        self.ledger = Ledger(state_path)
        self.registry = Registry(registry_path)
        self.secret = bytes(secret)
        self.profile = profile
        self.adapters = FederationAdapters(bundle_root)
        self.now = now or (lambda: int(time.time()))

    def _token(self, session: dict[str, Any], operation: str, binding: str, ttl_seconds: int) -> str:
        ttl = int(ttl_seconds)
        if ttl < 1 or ttl > 3600:
            raise ValueError("ttl_seconds must be between 1 and 3600")
        payload = {
            "schema": "kch.capability.v0.11.0",
            "session_id": session["session_id"],
            "objective_contract_sha256": session["objective_contract_sha256"],
            "jurisdiction": session["jurisdiction"],
            "authority_sha256": sha256_json(session["authority_granted"]),
            "operation": operation,
            "binding": binding,
            "nonce": secrets.token_hex(16),
            "exp": self.now() + ttl,
        }
        encoded = _b64encode(canonical_json(payload).encode("utf-8"))
        signature = hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
        return encoded + "." + signature

    def _decode(self, token: str, operation: str, binding: str, session: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded, signature = str(token).split(".", 1)
            expected = hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise CapabilityError("capability signature mismatch")
            payload = json.loads(_b64decode(encoded))
        except CapabilityError:
            raise
        except Exception as exc:
            raise CapabilityError("malformed capability token") from exc
        expected_fields = {
            "schema": "kch.capability.v0.11.0",
            "session_id": session["session_id"],
            "objective_contract_sha256": session["objective_contract_sha256"],
            "jurisdiction": session["jurisdiction"],
            "authority_sha256": sha256_json(session["authority_granted"]),
            "operation": operation,
            "binding": binding,
        }
        if any(payload.get(key) != value for key, value in expected_fields.items()):
            raise CapabilityError("capability binding mismatch")
        if int(payload.get("exp", 0)) <= self.now():
            raise CapabilityError("capability expired")
        if not isinstance(payload.get("nonce"), str) or len(payload["nonce"]) != 32:
            raise CapabilityError("capability nonce malformed")
        return payload

    @staticmethod
    def _consume(connection: sqlite3.Connection, payload: dict[str, Any]) -> None:
        try:
            connection.execute(
                "INSERT INTO consumed_capabilities(nonce,session_id,operation,consumed_at) VALUES(?,?,?,?)",
                (payload["nonce"], payload["session_id"], payload["operation"], str(payload["exp"])),
            )
        except sqlite3.IntegrityError as exc:
            raise CapabilityError("capability replay detected") from exc

    def _session(self, session_id: str) -> dict[str, Any]:
        with self.ledger.read() as connection:
            row = connection.execute("SELECT contract_json FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if row is None:
            raise ValueError("unknown session_id")
        return json.loads(row[0])

    def status(self) -> dict[str, Any]:
        integrity = self.ledger.verify()
        components = self.adapters.component_status()
        return {
            "schema": "kch.status.v0.11.0",
            "release": "KCH 0.11",
            "package_version": "0.11.0",
            "profile": self.profile,
            "mode": "SHADOW_AND_READ_ONLY_FEDERATION",
            "ledger": integrity,
            "registry_sha256": self.registry.hash,
            "reflexive_controls": len(CONTROL_CATALOG),
            "component_packages": components,
            "automatic_promotion": False,
            "mutating_execution_authorized": False,
            "enforced_profile": "PROHIBITED_UNTIL_GATES_PASS",
            "claim_ceiling": "CANONICAL_PRE2G_MACRORELEASE_WITH_BOUNDED_EXECUTABLE_INTEGRATION",
        }

    def open_session(self, value: dict[str, Any]) -> dict[str, Any]:
        session = {
            "schema": "kch.session.v0.11.0",
            "session_id": require_text(value.get("session_id"), "session_id"),
            "actor": require_text(value.get("actor"), "actor"),
            "objective_id": require_text(value.get("objective_id"), "objective_id"),
            "objective_contract_sha256": require_sha256(value.get("objective_contract_sha256"), "objective_contract_sha256"),
            "project_id": require_text(value.get("project_id"), "project_id"),
            "jurisdiction": require_text(value.get("jurisdiction"), "jurisdiction"),
            "authority_granted": require_string_list(value.get("authority_granted"), "authority_granted"),
            "stop_condition_ids": require_string_list(value.get("stop_condition_ids"), "stop_condition_ids"),
            "expected_evidence_ids": require_string_list(value.get("expected_evidence_ids"), "expected_evidence_ids"),
        }
        if session["actor"] not in {"USER", "SYSTEM_AUTHORITY"}:
            raise ValueError("only USER or SYSTEM_AUTHORITY may open a governed session")
        contract_hash = sha256_json(session)
        with self.ledger.transaction() as connection:
            event = self.ledger.append(connection, "SESSION_OPENED", {"session": session, "contract_sha256": contract_hash})
            connection.execute(
                "INSERT INTO sessions(session_id,contract_json,contract_sha256,created_event_hash) VALUES(?,?,?,?)",
                (session["session_id"], canonical_json(session), contract_hash, event["event_hash"]),
            )
        ttl = int(value.get("ttl_seconds", 900))
        return {
            "session": session,
            "session_contract_sha256": contract_hash,
            "evidence_capabilities": {item: self._token(session, "evidence.admit", item, ttl) for item in session["expected_evidence_ids"]},
            "proposal_capability": self._token(session, "action.propose", "NEW_PROPOSAL", ttl),
            "precommit_capability": self._token(session, "precommit.verify", "PRECOMMIT", ttl),
            "outcome_capability": self._token(session, "outcome.register", "OUTCOME", ttl),
            "rollback_capability": self._token(session, "rollback.record", "ROLLBACK", ttl),
            "profile": self.profile,
            "mutating_execution_authorized": False,
        }

    def admit_evidence(self, value: dict[str, Any]) -> dict[str, Any]:
        session = self._session(require_text(value.get("session_id"), "session_id"))
        evidence_id = require_text(value.get("evidence_id"), "evidence_id")
        capability = self._decode(value.get("capability", ""), "evidence.admit", evidence_id, session)
        role = require_text(value.get("role"), "role")
        if role not in EVIDENCE_ROLES:
            raise ValueError("invalid evidence role")
        if evidence_id not in session["expected_evidence_ids"]:
            raise ValueError("evidence_id was not preregistered")
        if value.get("jurisdiction") != session["jurisdiction"]:
            raise ValueError("evidence jurisdiction mismatch")
        record = {
            "schema": "kch.evidence.v0.11.0",
            "session_id": session["session_id"],
            "evidence_id": evidence_id,
            "source_sha256": require_sha256(value.get("source_sha256"), "source_sha256"),
            "jurisdiction": session["jurisdiction"],
            "role": role,
            "provenance_ids": require_string_list(value.get("provenance_ids"), "provenance_ids"),
        }
        record_hash = sha256_json(record)
        with self.ledger.transaction() as connection:
            self._consume(connection, capability)
            event = self.ledger.append(connection, "EVIDENCE_ADMITTED", {"record": record, "record_sha256": record_hash})
            connection.execute(
                "INSERT INTO evidence(session_id,evidence_id,record_json,record_sha256,event_hash) VALUES(?,?,?,?,?)",
                (session["session_id"], evidence_id, canonical_json(record), record_hash, event["event_hash"]),
            )
        return {"admitted": True, "record_sha256": record_hash, "event_hash": event["event_hash"], "authority_created": False}

    def compile_context(self, value: dict[str, Any]) -> dict[str, Any]:
        contexts = value.get("controls")
        if not isinstance(contexts, dict) or not contexts:
            raise ValueError("controls must be a non-empty object keyed by R01..R28")
        unknown = sorted(set(contexts) - set(CONTROL_CATALOG))
        if unknown:
            raise ValueError("unknown controls: " + ",".join(unknown))
        receipts = [evaluate_control(control_id, contexts[control_id]) for control_id in sorted(contexts)]
        verdicts = {state: sum(row["verdict"] == state for row in receipts) for state in ("PASS", "BLOCK", "ABSTAIN", "UNAVAILABLE")}
        core = {
            "schema": "kch.context-compile-receipt.v0.11.0",
            "release": "KCH 0.11",
            "receipts": receipts,
            "verdict_counts": verdicts,
            "composition_state": "BLOCK" if verdicts["BLOCK"] else "ABSTAIN" if verdicts["ABSTAIN"] or verdicts["UNAVAILABLE"] else "PASS",
            "authority_created": False,
        }
        return {**core, "receipt_sha256": sha256_json(core)}

    def propose_action(self, value: dict[str, Any]) -> dict[str, Any]:
        session = self._session(require_text(value.get("session_id"), "session_id"))
        capability = self._decode(value.get("capability", ""), "action.propose", "NEW_PROPOSAL", session)
        action_class = require_text(value.get("action_class"), "action_class")
        if action_class not in {"READ_ONLY", "MUTATING"}:
            raise ValueError("invalid action_class")
        proposal = {
            "schema": "kch.action-proposal.v0.11.0",
            "proposal_id": str(uuid4()),
            "session_id": session["session_id"],
            "route": require_text(value.get("route"), "route"),
            "action_class": action_class,
            "requested_authority": require_string_list(value.get("requested_authority"), "requested_authority"),
            "evidence_ids": require_string_list(value.get("evidence_ids"), "evidence_ids"),
            "arguments": value.get("arguments") if isinstance(value.get("arguments"), dict) else {},
        }
        proposal_hash = sha256_json(proposal)
        with self.ledger.transaction() as connection:
            self._consume(connection, capability)
            event = self.ledger.append(connection, "ACTION_PROPOSED", {"proposal": proposal, "proposal_sha256": proposal_hash})
            connection.execute(
                "INSERT INTO proposals(proposal_id,session_id,proposal_json,proposal_sha256,state,event_hash) VALUES(?,?,?,?,?,?)",
                (proposal["proposal_id"], session["session_id"], canonical_json(proposal), proposal_hash, "PROPOSED", event["event_hash"]),
            )
        return {
            "proposal": proposal,
            "proposal_sha256": proposal_hash,
            "authorization_capability": self._token(session, "action.authorize", proposal["proposal_id"], int(value.get("ttl_seconds", 900))),
            "authority_created": False,
        }

    def authorize_action(self, value: dict[str, Any]) -> dict[str, Any]:
        session = self._session(require_text(value.get("session_id"), "session_id"))
        proposal_id = require_text(value.get("proposal_id"), "proposal_id")
        capability = self._decode(value.get("capability", ""), "action.authorize", proposal_id, session)
        with self.ledger.transaction() as connection:
            row = connection.execute("SELECT proposal_json,state FROM proposals WHERE proposal_id=? AND session_id=?", (proposal_id, session["session_id"])).fetchone()
            if row is None or row["state"] != "PROPOSED":
                raise ValueError("proposal unavailable for authorization")
            proposal = json.loads(row["proposal_json"])
            receipts = value.get("control_receipts")
            if not isinstance(receipts, list) or not receipts:
                raise ValueError("control_receipts must be a non-empty list")
            invalid_receipts = [item for item in receipts if not isinstance(item, dict) or item.get("receipt_sha256") != sha256_json({k: v for k, v in item.items() if k != "receipt_sha256"})]
            hard = []
            abstain = []
            if invalid_receipts:
                hard.append("CONTROL_RECEIPT_INTEGRITY_FAILURE")
            verdicts = [item.get("verdict") for item in receipts if isinstance(item, dict)]
            if "BLOCK" in verdicts:
                hard.append("CONTROL_BLOCK")
            if any(item in {"ABSTAIN", "UNAVAILABLE"} for item in verdicts):
                abstain.append("CONTROL_EVIDENCE_INCOMPLETE")
            if not set(proposal["requested_authority"]) <= set(session["authority_granted"]):
                hard.append("AUTHORITY_EXPANSION")
            admitted = {item[0] for item in connection.execute("SELECT evidence_id FROM evidence WHERE session_id=?", (session["session_id"],))}
            if not set(proposal["evidence_ids"]) <= admitted:
                abstain.append("PROPOSAL_EVIDENCE_NOT_ADMITTED")
            if proposal["action_class"] == "MUTATING":
                abstain.append("MUTATING_EXECUTION_NOT_AUTHORIZED_IN_KCH_0.11")
            decision = "BLOCK" if hard else "ABSTAIN" if abstain else "ALLOW_READ_ONLY"
            self._consume(connection, capability)
            receipt = {
                "schema": "kch.action-authorization.v0.11.0",
                "proposal_id": proposal_id,
                "decision": decision,
                "hard_reasons": sorted(set(hard)),
                "abstain_reasons": sorted(set(abstain)),
                "control_receipt_sha256s": [item.get("receipt_sha256") for item in receipts if isinstance(item, dict)],
                "authority_created": False,
                "automatic_promotion": False,
            }
            receipt_hash = sha256_json(receipt)
            event = self.ledger.append(connection, "ACTION_AUTHORIZED", {"receipt": receipt, "receipt_sha256": receipt_hash})
            connection.execute("UPDATE proposals SET state=? WHERE proposal_id=?", (decision, proposal_id))
        output = {**receipt, "receipt_sha256": receipt_hash, "event_hash": event["event_hash"]}
        if decision == "ALLOW_READ_ONLY":
            output["execution_capability"] = self._token(session, "action.execute", proposal_id, int(value.get("ttl_seconds", 900)))
        return output

    def execute_action(self, value: dict[str, Any]) -> dict[str, Any]:
        session = self._session(require_text(value.get("session_id"), "session_id"))
        proposal_id = require_text(value.get("proposal_id"), "proposal_id")
        capability = self._decode(value.get("capability", ""), "action.execute", proposal_id, session)
        with self.ledger.transaction() as connection:
            row = connection.execute("SELECT proposal_json,state FROM proposals WHERE proposal_id=? AND session_id=?", (proposal_id, session["session_id"])).fetchone()
            if row is None or row["state"] != "ALLOW_READ_ONLY":
                raise ValueError("proposal is not authorized for read-only execution")
            proposal = json.loads(row["proposal_json"])
            self._consume(connection, capability)
            result = self._execute_read_route(proposal["route"], proposal["arguments"])
            event = self.ledger.append(connection, "READ_ONLY_ACTION_EXECUTED", {"proposal_id": proposal_id, "route": proposal["route"], "result_sha256": sha256_json(result)})
            connection.execute("UPDATE proposals SET state='EXECUTED_READ_ONLY' WHERE proposal_id=?", (proposal_id,))
        return {"executed": True, "execution_class": "READ_ONLY", "route": proposal["route"], "result": result, "event_hash": event["event_hash"], "authority_created": False}

    def _execute_read_route(self, route: str, arguments: dict[str, Any]) -> dict[str, Any]:
        routes = {
            "kch.component.status": lambda: self.adapters.component_status(),
            "kch.phl.projection": lambda: self.adapters.phl_projection(),
            "kch.sco.projection": lambda: self.adapters.sco_projection(arguments.get("sco_id")),
            "kch.mis.certificate.verify": lambda: self.adapters.mis_certificate_verify(),
            "kch.registry.evidence.audit": lambda: self.registry.audit_evidence(self.adapters.bundle_root),
        }
        if route not in routes:
            raise ValueError("route is not admitted in KCH 0.11 read-only federation")
        return routes[route]()

    def precommit_verify(self, value: dict[str, Any]) -> dict[str, Any]:
        session = self._session(require_text(value.get("session_id"), "session_id"))
        capability = self._decode(value.get("capability", ""), "precommit.verify", "PRECOMMIT", session)
        hard: list[str] = []
        abstain: list[str] = []
        if value.get("objective_contract_sha256") != session["objective_contract_sha256"]:
            hard.append("OBJECTIVE_CONTRACT_MISMATCH")
        if value.get("jurisdiction") != session["jurisdiction"]:
            hard.append("JURISDICTION_MISMATCH")
        if value.get("candidate_artifact_sha256") != value.get("observed_artifact_sha256"):
            hard.append("ARTIFACT_HASH_MISMATCH")
        observer = value.get("external_observer_verdict")
        if observer == "BLOCK":
            hard.append("EXTERNAL_OBSERVER_BLOCK")
        elif observer != "PASS":
            abstain.append("EXTERNAL_OBSERVER_UNAVAILABLE")
        evidence_ids = set(require_string_list(value.get("evidence_ids"), "evidence_ids"))
        expected = set(session["expected_evidence_ids"])
        if not evidence_ids <= expected:
            hard.append("UNEXPECTED_EVIDENCE_SUBSTITUTION")
        with self.ledger.transaction() as connection:
            admitted = {row[0] for row in connection.execute("SELECT evidence_id FROM evidence WHERE session_id=?", (session["session_id"],))}
            if not evidence_ids <= admitted:
                abstain.append("EVIDENCE_NOT_ADMITTED")
            self._consume(connection, capability)
            decision = "BLOCK" if hard else "ABSTAIN" if abstain else "ALLOW_SHADOW_PRECOMMIT"
            receipt = {
                "schema": "kch.precommit-receipt.v0.11.0",
                "session_id": session["session_id"],
                "decision": decision,
                "hard_reasons": sorted(set(hard)),
                "abstain_reasons": sorted(set(abstain)),
                "evidence_ids": sorted(evidence_ids),
                "automatic_promotion": False,
                "mutating_execution_authorized": False,
            }
            receipt_hash = sha256_json(receipt)
            event = self.ledger.append(connection, "PRECOMMIT_VERIFIED", {"receipt": receipt, "receipt_sha256": receipt_hash})
        return {**receipt, "receipt_sha256": receipt_hash, "event_hash": event["event_hash"]}

    def record_rollback(self, value: dict[str, Any]) -> dict[str, Any]:
        session = self._session(require_text(value.get("session_id"), "session_id"))
        capability = self._decode(value.get("capability", ""), "rollback.record", "ROLLBACK", session)
        record = {
            "schema": "kch.rollback-record.v0.11.0",
            "session_id": session["session_id"],
            "target_event_hash": require_sha256(value.get("target_event_hash"), "target_event_hash"),
            "reason": require_text(value.get("reason"), "reason"),
            "human_authorized": value.get("human_authorized") is True,
            "mechanism": "APPEND_ONLY_COMPENSATING_RECORD",
            "history_rewritten": False,
        }
        with self.ledger.transaction() as connection:
            self._consume(connection, capability)
            event = self.ledger.append(connection, "ROLLBACK_RECORDED", record)
        return {**record, "event_hash": event["event_hash"], "physical_rollback_executed": False}

    def register_outcome(self, value: dict[str, Any]) -> dict[str, Any]:
        session = self._session(require_text(value.get("session_id"), "session_id"))
        capability = self._decode(value.get("capability", ""), "outcome.register", "OUTCOME", session)
        record = {
            "schema": "kch.outcome.v0.11.0",
            "session_id": session["session_id"],
            "outcome_id": require_text(value.get("outcome_id"), "outcome_id"),
            "state": require_text(value.get("state"), "state"),
            "evidence_ids": require_string_list(value.get("evidence_ids"), "evidence_ids"),
            "adverse": value.get("adverse") is True,
            "interpretation": require_text(value.get("interpretation"), "interpretation"),
        }
        with self.ledger.transaction() as connection:
            self._consume(connection, capability)
            event = self.ledger.append(connection, "OUTCOME_REGISTERED", record)
        return {**record, "event_hash": event["event_hash"], "historical_result_rewritten": False}

    def audit_export(self) -> dict[str, Any]:
        return self.ledger.export()

    def control_catalog(self) -> dict[str, Any]:
        return describe_controls()
