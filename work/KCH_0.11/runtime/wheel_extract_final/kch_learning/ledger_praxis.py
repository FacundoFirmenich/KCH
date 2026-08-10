from __future__ import annotations

import hashlib
import json
from typing import Any

from .canonical import LearningError
from .ledger_release import LearningLedger as _LearningLedger


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PraxisLearningLedger(_LearningLedger):
    def _initialize(self) -> None:
        super()._initialize()
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS phl_workbench_state (
                session_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                last_event_hash TEXT NOT NULL
                )"""
            )

    def load_workbench_state(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT state_json FROM phl_workbench_state WHERE session_id=?", (session_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_workbench_state(self, session_id: str, state: dict[str, Any]) -> dict[str, Any]:
        state_json = _canonical(state)
        state_hash = _sha(state_json)
        with self._connect() as connection:
            session = connection.execute("SELECT channel,state FROM sessions WHERE session_id=?", (session_id,)).fetchone()
            if not session or session["channel"] != "PHL" or session["state"] != "ACTIVE":
                raise LearningError("workbench state requires an active PHL session")
            event = self._append_event(
                connection,
                "PHL_WORKBENCH_STATE_SAVED",
                {"session_id": session_id, "state_hash": state_hash},
            )
            connection.execute(
                """INSERT INTO phl_workbench_state(session_id,state_json,state_hash,last_event_hash)
                VALUES(?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET
                state_json=excluded.state_json,state_hash=excluded.state_hash,last_event_hash=excluded.last_event_hash""",
                (session_id, state_json, state_hash, event["event_hash"]),
            )
        return {"session_id": session_id, "state_hash": state_hash, "event_hash": event["event_hash"]}

    def verify(self) -> dict[str, Any]:
        result = super().verify()
        defects = list(result["defects"])
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM phl_workbench_state ORDER BY session_id").fetchall()
            sessions = {row[0] for row in connection.execute("SELECT session_id FROM sessions WHERE channel='PHL'").fetchall()}
            event_hashes = {row[0] for row in connection.execute("SELECT event_hash FROM events").fetchall()}
        for row in rows:
            if _sha(row["state_json"]) != row["state_hash"]:
                defects.append(f"PHL_WORKBENCH_STATE_HASH:{row['session_id']}")
            if row["session_id"] not in sessions:
                defects.append(f"PHL_WORKBENCH_SESSION_LINK:{row['session_id']}")
            if row["last_event_hash"] not in event_hashes:
                defects.append(f"PHL_WORKBENCH_EVENT_LINK:{row['session_id']}")
        return {
            **result,
            "gate": "PASS" if not defects else "FAIL",
            "defects": defects,
            "workbench_state_count": len(rows),
        }
