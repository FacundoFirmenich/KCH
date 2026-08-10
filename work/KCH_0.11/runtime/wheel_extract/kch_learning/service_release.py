from __future__ import annotations

from typing import Any

from .canonical import LearningError
from .ledger_release import LearningLedger
from .service import LearningService as _LearningService


class LearningService(_LearningService):
    ledger: LearningLedger

    def _require_ordinary_work_gate(self) -> None:
        gate = self.ordinary_work_gate()
        if not gate["ordinary_kch_work_allowed"]:
            raise LearningError(f"ordinary KCH work blocked by active PHL session {gate['active_phl_session_id']}")

    def register_decision(self, record: dict[str, Any]) -> dict[str, Any]:
        self._require_ordinary_work_gate()
        return super().register_decision(record)

    def launch_obl(self, decision_id: str, initiator: str, trigger: str) -> dict[str, Any]:
        self._require_ordinary_work_gate()
        return super().launch_obl(decision_id, initiator, trigger)

    def submit_obl(self, session_id: str, decision_id: str, verdict: str, context: str = "", correction: str = "", actor: str = "USER") -> dict[str, Any]:
        self._require_ordinary_work_gate()
        return super().submit_obl(session_id, decision_id, verdict, context, correction, actor)

    def start_phl(self, trigger: str = "USER_EXPLICIT_WORKBENCH_START") -> dict[str, Any]:
        with self.ledger._connect() as connection:
            active_obl = connection.execute("SELECT session_id FROM sessions WHERE channel='OBL' AND state='ACTIVE' LIMIT 1").fetchone()
        if active_obl:
            raise LearningError(f"close active OBL session {active_obl[0]} before acquiring the exclusive PHL lock")
        return super().start_phl(trigger)
