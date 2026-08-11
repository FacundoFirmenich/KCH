from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .codex_bootstrap_mcp import PROTOCOL_VERSION, CodexBootstrapMCP

TOOL = {
    "name": "kch_governed_preflight",
    "description": (
        "Run the canonical read-only KCH startup gate. This creates no external side effect, "
        "permission, operational authority or PHL training."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": True},
}


class CodexPreflightMCP:
    """One-tool auto-approvable server separated from the operational dispatcher."""

    def __init__(self, runtime_root: str | Path):
        self.bootstrap = CodexBootstrapMCP(runtime_root)

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request_id = message.get("id")
        method = message.get("method")
        if method == "notifications/initialized":
            return None
        try:
            if method == "initialize":
                result: Any = {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "kch-codex-preflight", "version": "0.3.9"},
                    "instructions": (
                        "Mandatory startup binding: call kch_governed_preflight exactly once "
                        "before the first material action in every new task. It is read-only and "
                        "must not be replaced by prose or simulated. Proceed only on PASS. On "
                        "FAIL, preserve the adverse gate and explain the blocker. PHL is authorized "
                        "but remains untrained unless genuine user feedback explicitly starts it."
                    ),
                }
            elif method == "tools/list":
                result = {"tools": [TOOL]}
            elif method == "tools/call":
                params = dict(message.get("params", {}))
                if str(params.get("name", "")) != TOOL["name"]:
                    raise ValueError("only kch_governed_preflight is available")
                result = self.bootstrap.call("kch_governed_preflight", {})
            elif method == "ping":
                result = {}
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"method not found: {method}"},
                }
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": str(exc)},
            }

    def close(self) -> None:
        self.bootstrap.close()


def main() -> None:
    root = Path(os.environ.get("KCH_STUDIO_RUNTIME", Path.cwd() / ".kch-studio-runtime"))
    server = CodexPreflightMCP(root)
    try:
        for line in sys.stdin:
            try:
                response = server.handle(json.loads(line))
            except json.JSONDecodeError:
                response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "parse error"},
                }
            except Exception as exc:
                response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32603, "message": str(exc)},
                }
            if response is not None:
                print(json.dumps(response, ensure_ascii=True, separators=(",", ":")), flush=True)
    finally:
        server.close()


if __name__ == "__main__":
    main()
