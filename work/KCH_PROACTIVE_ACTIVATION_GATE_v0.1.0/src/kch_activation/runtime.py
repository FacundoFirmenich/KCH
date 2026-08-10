from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from kwancode_harness.mcp_server import MCPServer as BaseMCPServer
from kwancode_harness.mcp_server import build_gateway

from .engine import ActivationEngine
from .ledger import ActivationLedger
from .rules import READ_ONLY_TOOL_ALLOWLIST, RuleCatalog


class ActivationRuntime:
    def __init__(self):
        self.base_server = BaseMCPServer(build_gateway())
        missing = sorted(READ_ONLY_TOOL_ALLOWLIST - set(self.base_server.handlers))
        if missing:
            raise RuntimeError(f"read-only activation targets unavailable: {missing}")
        rules = Path(os.environ["KCH_ACTIVATION_RULES"])
        state = Path(os.environ["KCH_ACTIVATION_STATE"])
        self.ledger = ActivationLedger(state)
        self.catalog = RuleCatalog(rules)
        self.engine = ActivationEngine(self.ledger, self.catalog, self.execute_read_only)

    def execute_read_only(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in READ_ONLY_TOOL_ALLOWLIST:
            raise ValueError("activation target is not allowlisted read-only")
        payload = self.base_server.handlers[tool_name](arguments)
        if not isinstance(payload, dict):
            raise TypeError("KCH read-only handler returned a non-object payload")
        return payload
