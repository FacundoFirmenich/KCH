from __future__ import annotations

import re
from typing import Any

from .canonical import LearningChannel, LearningError, PHL_SCORE_SCHEMA
from .service_release import LearningService


class InstrumentLearningService(LearningService):
    """Explicitly non-training PHL path for end-to-end instrument validation."""

    def start_phl_instrument(self) -> dict[str, Any]:
        with self.ledger._connect() as connection:
            active = connection.execute("SELECT session_id FROM sessions WHERE state='ACTIVE' LIMIT 1").fetchone()
        if active:
            raise LearningError(f"active learning session prevents instrument start: {active[0]}")
        session = self.ledger.start_session(
            LearningChannel.PHL,
            "MODEL_TEST_OPERATOR",
            "PHL_INSTRUMENT_SELF_TEST",
            exclusive=True,
        )
        return {
            **session,
            "expansion": "POST_HOC_LEARNING",
            "interface": "INTERACTIVE_PYTHON_WORKBENCH_INSTRUMENT_MODE",
            "ordinary_kch_work_allowed": False,
            "score_schema": PHL_SCORE_SCHEMA,
            "instrument_only": True,
            "training_eligible": False,
        }

    def score_phl_instrument(
        self,
        session_id: str,
        decision_id: str,
        score_display: str,
        contextual_text: str,
        correction_text: str = "",
    ) -> dict[str, Any]:
        if not re.fullmatch(r"\d{3}", score_display) or not 0 <= int(score_display) <= 100:
            raise LearningError("instrument PHL score must preserve 000..100")
        if "NOT_USER_DATA" not in contextual_text:
            raise LearningError("instrument context must explicitly declare NOT_USER_DATA")
        receipt = self.ledger.add_feedback(
            session_id,
            decision_id,
            LearningChannel.PHL,
            "MODEL_TEST_OPERATOR",
            {
                "score_display": score_display,
                "score_int": int(score_display),
                "contextual_text": contextual_text,
                "correction_text": correction_text,
                "score_schema": PHL_SCORE_SCHEMA,
                "evidence_class": "INSTRUMENTAL_BOUNDARY_TEST_NOT_USER_DATA",
                "training_eligible": False,
                "future_only": True,
                "quality_judgment_asserted": False,
            },
        )
        return {
            **receipt,
            "channel": "PHL",
            "actor": "MODEL_TEST_OPERATOR",
            "training_eligible": False,
            "current_decision_mutated": False,
        }

    def compile_training_packet(self, session_id: str) -> dict[str, Any]:
        session = self.ledger.session(session_id)
        rows = self.ledger.feedback_for_session(session_id)
        eligible = [row for row in rows if row["record"].get("training_eligible", True)]
        excluded = [row for row in rows if not row["record"].get("training_eligible", True)]
        examples = []
        corrections = []
        for row in eligible:
            decision = self.ledger.decision(row["decision_id"])
            examples.append(
                {
                    "decision_id": row["decision_id"],
                    "decision_record_hash": decision["record_hash"],
                    "feedback_record_hash": row["record_hash"],
                    "feedback": row["record"],
                }
            )
            correction = row["record"].get("correction_text", "").strip()
            if correction:
                corrections.append({"decision_id": row["decision_id"], "explicit_user_correction": correction})
        packet = {
            "schema": "kch.learning.training_packet.v0.1.0",
            "source_session_id": session_id,
            "channel": session["channel"],
            "examples": examples,
            "explicit_correction_candidates": corrections,
            "excluded_feedback": [
                {
                    "feedback_id": row["feedback_id"],
                    "feedback_record_hash": row["record_hash"],
                    "reason": "INSTRUMENTAL_BOUNDARY_TEST_NOT_USER_DATA",
                }
                for row in excluded
            ],
            "learning_semantics": "FUTURE_ONLY",
            "reward_mapping": "UNRESOLVED_NO_LINEARITY_ASSUMED",
            "activation": "PROHIBITED_UNTIL_REPLAY_AND_EXPLICIT_USER_APPROVAL",
            "historical_decisions_mutated": False,
        }
        receipt = self.ledger.store_packet(session_id, packet)
        return {**receipt, "packet": packet}
