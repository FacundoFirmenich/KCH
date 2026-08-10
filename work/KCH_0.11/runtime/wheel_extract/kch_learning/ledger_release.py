from __future__ import annotations

import json

from .ledger import LearningLedger as _LearningLedger


class LearningLedger(_LearningLedger):
    def feedback_for_decision(self, decision_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM feedback WHERE decision_id=? ORDER BY rowid", (decision_id,)).fetchall()
        return [{**dict(row), "record": json.loads(row["record_json"])} for row in rows]
