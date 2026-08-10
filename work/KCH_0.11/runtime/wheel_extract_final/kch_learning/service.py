from __future__ import annotations

import re
from typing import Any

from .canonical import FeedbackVerdict, Initiator, LearningChannel, LearningError, PHL_SCORE_SCHEMA
from .ledger import LearningLedger


class LearningService:
    def __init__(self, ledger: LearningLedger):
        self.ledger = ledger

    def register_decision(self, record: dict[str, Any]) -> dict[str, Any]:
        required = ("decision_id", "component", "decision_type", "summary", "rationale", "consequence", "source_uri")
        missing = [field for field in required if not str(record.get(field, "")).strip()]
        if missing:
            raise LearningError(f"missing decision fields: {','.join(missing)}")
        normalized = {
            **record,
            "alternatives": list(record.get("alternatives", [])),
            "evidence": list(record.get("evidence", [])),
            "uncertainty": record.get("uncertainty", "UNAVAILABLE"),
            "policy_version": record.get("policy_version", "UNAVAILABLE"),
            "claim_scope": record.get("claim_scope", "LOCAL_DECISION_RECORD_ONLY"),
        }
        return self.ledger.register_decision(normalized)

    def launch_obl(self, decision_id: str, initiator: str, trigger: str) -> dict[str, Any]:
        initiator_enum = Initiator(initiator)
        decision = self.ledger.decision(decision_id)
        session = self.ledger.start_session(LearningChannel.OBL, initiator_enum, trigger, exclusive=False, decision_id=decision_id)
        return {
            **session,
            "expansion": "ONBOARDING_LEARNING",
            "interface": "ONE_LINE_COMMAND_BOX",
            "decision": decision,
            "feedback_commands": ["accept", "correct --context TEXT --correction TEXT", "abstain --context TEXT"],
            "model_may_launch": True,
            "model_may_author_user_feedback": False,
            "future_only": True,
        }

    def submit_obl(self, session_id: str, decision_id: str, verdict: str, context: str = "", correction: str = "", actor: str = "USER") -> dict[str, Any]:
        if actor != "USER":
            raise LearningError("OBL feedback authorship is reserved to the user in v0.1.0")
        verdict_enum = FeedbackVerdict(verdict)
        if verdict_enum == FeedbackVerdict.CORRECT and not correction.strip():
            raise LearningError("CORRECT requires explicit correction text")
        receipt = self.ledger.add_feedback(
            session_id,
            decision_id,
            LearningChannel.OBL,
            actor,
            {"verdict": verdict_enum, "contextual_text": context, "correction_text": correction, "future_only": True},
        )
        return {**receipt, "channel": "OBL", "future_only": True, "current_decision_mutated": False}

    def start_phl(self, trigger: str = "USER_EXPLICIT_WORKBENCH_START") -> dict[str, Any]:
        session = self.ledger.start_session(LearningChannel.PHL, Initiator.USER, trigger, exclusive=True)
        return {
            **session,
            "expansion": "POST_HOC_LEARNING",
            "interface": "INTERACTIVE_PYTHON_WORKBENCH",
            "ordinary_kch_work_allowed": False,
            "score_schema": PHL_SCORE_SCHEMA,
        }

    def score_phl(self, session_id: str, decision_id: str, score_display: str, contextual_text: str = "", correction_text: str = "") -> dict[str, Any]:
        if not re.fullmatch(r"\d{3}", score_display):
            raise LearningError("PHL score must preserve the three-character format 000..100")
        score_int = int(score_display)
        if not 0 <= score_int <= 100:
            raise LearningError("PHL score must be within 000..100")
        receipt = self.ledger.add_feedback(
            session_id,
            decision_id,
            LearningChannel.PHL,
            "USER",
            {
                "score_display": score_display,
                "score_int": score_int,
                "contextual_text": contextual_text,
                "correction_text": correction_text,
                "score_schema": PHL_SCORE_SCHEMA,
                "future_only": True,
            },
        )
        return {**receipt, "channel": "PHL", "current_decision_mutated": False, "future_only": True}

    def compile_training_packet(self, session_id: str) -> dict[str, Any]:
        session = self.ledger.session(session_id)
        rows = self.ledger.feedback_for_session(session_id)
        examples = []
        correction_candidates = []
        for row in rows:
            decision = self.ledger.decision(row["decision_id"])
            item = {
                "decision_id": row["decision_id"],
                "decision_record_hash": decision["record_hash"],
                "feedback_record_hash": row["record_hash"],
                "feedback": row["record"],
            }
            examples.append(item)
            correction = row["record"].get("correction_text", "").strip()
            if correction:
                correction_candidates.append({"decision_id": row["decision_id"], "explicit_user_correction": correction})
        packet = {
            "schema": "kch.learning.training_packet.v0.1.0",
            "source_session_id": session_id,
            "channel": session["channel"],
            "examples": examples,
            "explicit_correction_candidates": correction_candidates,
            "learning_semantics": "FUTURE_ONLY",
            "reward_mapping": "UNRESOLVED_NO_LINEARITY_ASSUMED",
            "activation": "PROHIBITED_UNTIL_REPLAY_AND_EXPLICIT_USER_APPROVAL",
            "historical_decisions_mutated": False,
        }
        receipt = self.ledger.store_packet(session_id, packet)
        return {**receipt, "packet": packet}

    def ordinary_work_gate(self) -> dict[str, Any]:
        session_id = self.ledger.active_phl_session()
        return {
            "ordinary_kch_work_allowed": session_id is None,
            "active_phl_session_id": session_id,
            "reason": None if session_id is None else "PHL_EXCLUSIVE_PERSONAL_TRAINING_MODE",
        }

    def close_session(self, session_id: str) -> dict[str, Any]:
        return self.ledger.close_session(session_id)
