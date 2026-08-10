from __future__ import annotations

from pathlib import Path
from typing import Any

from kch_super_mcp.gateway import CapabilityError, Gateway

from .ledger_release import LearningLedger
from .service_release import LearningService


class LearningAwareGateway(Gateway):
    """Bind the PHL exclusive lock to every mutating v0.1.0 Super-MCP operation."""

    def __init__(self, state_path: Path, registry_path: Path, secret: bytes, learning_state_path: Path, **kwargs: Any):
        super().__init__(state_path, registry_path, secret, **kwargs)
        self.learning = LearningService(LearningLedger(learning_state_path))

    def _require_learning_gate(self) -> None:
        gate = self.learning.ordinary_work_gate()
        if not gate["ordinary_kch_work_allowed"]:
            raise CapabilityError(f"PHL_EXCLUSIVE_PERSONAL_TRAINING_MODE:{gate['active_phl_session_id']}")

    def status(self) -> dict[str, Any]:
        return {**super().status(), "learning_gate": self.learning.ordinary_work_gate()}

    def open_session(self, value: dict[str, Any]) -> dict[str, Any]:
        self._require_learning_gate()
        return super().open_session(value)

    def admit_evidence(self, value: dict[str, Any]) -> dict[str, Any]:
        self._require_learning_gate()
        return super().admit_evidence(value)

    def precommit_verify(self, value: dict[str, Any]) -> dict[str, Any]:
        self._require_learning_gate()
        return super().precommit_verify(value)
