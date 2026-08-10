from __future__ import annotations

import json
import sys
from typing import Any

from kwancode_harness.mcp_server import PROTOCOL_VERSION, RESOURCES, TOOLS as BASE_TOOLS

from .runtime import ActivationRuntime


def obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


STR = {"type": "string", "minLength": 1}
ACTIVATION_TOOLS = (
    {
        "name": "kch.activation.scan",
        "description": "Evaluate one host event against bounded deterministic KCH activation rules; consults before execution unless a session-scoped policy already applies.",
        "inputSchema": obj({"session_id": STR, "event_id": STR, "event_type": {"enum": ["USER_PROMPT_SUBMIT"]}, "text": STR}, ["session_id", "event_id", "event_type", "text"]),
    },
    {
        "name": "kch.activation.respond",
        "description": "Resolve one pending activation with exactly Sí, No, Nunca en esta sesión, or Siempre en esta sesión.",
        "inputSchema": obj({"session_id": STR, "proposal_id": STR, "response": {"enum": ["Sí", "No", "Nunca en esta sesión", "Siempre en esta sesión"]}}, ["session_id", "response"]),
    },
    {
        "name": "kch.activation.status",
        "description": "Return activation rules, session policies, execution counts, and append-only chain integrity.",
        "inputSchema": obj({"session_id": STR}, []),
    },
    {
        "name": "kch.activation.session.close",
        "description": "Close activation state for one host session and erase its always/never policies while preserving audit events.",
        "inputSchema": obj({"session_id": STR}, ["session_id"]),
    },
)

INSTRUCTIONS = (
    "KCH proactive activation gate v0.1.0 operates in CONSULT_FIRST mode. "
    "When a bounded rule indicates a read-only KCH inspection, call kch.activation.scan. "
    "If it returns ASK_USER, ask the user directly and accept exactly four choices: Sí; No; "
    "Nunca en esta sesión; Siempre en esta sesión. Sí applies once. No declines once. "
    "Nunca and Siempre are scoped only to the current host session and the same rule/tool. "
    "Never infer consent. Mutating autoexecution and real PHL execution are unavailable."
)


class OverlayServer:
    def __init__(self):
        self.runtime = ActivationRuntime()
        self.base = self.runtime.base_server

    @staticmethod
    def _tool_result(payload: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, sort_keys=True)}], "isError": False}

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if message.get("method") == "notifications/initialized":
            return None
        request_id = message.get("id")
        method = message.get("method")
        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"tools": {}, "resources": {}},
                        "serverInfo": {"name": "kwancode-harness-proactive-activation-overlay", "version": "0.11.0+activation.gate.1"},
                        "instructions": INSTRUCTIONS,
                    },
                }
            if method == "tools/list":
                return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": [*BASE_TOOLS, *ACTIVATION_TOOLS]}}
            if method == "resources/list":
                return {"jsonrpc": "2.0", "id": request_id, "result": {"resources": list(RESOURCES)}}
            if method == "tools/call":
                params = message.get("params") or {}
                name = params.get("name")
                arguments = params.get("arguments") or {}
                if name == "kch.activation.scan":
                    payload = self.runtime.engine.scan(arguments["session_id"], arguments["event_id"], arguments["event_type"], arguments["text"])
                elif name == "kch.activation.respond":
                    payload = self.runtime.engine.respond(arguments["session_id"], arguments["response"], arguments.get("proposal_id"))
                elif name == "kch.activation.status":
                    payload = self.runtime.engine.status(arguments.get("session_id"))
                elif name == "kch.activation.session.close":
                    payload = self.runtime.engine.close_session(arguments["session_id"])
                else:
                    return self.base.handle(message)
                return {"jsonrpc": "2.0", "id": request_id, "result": self._tool_result(payload)}
            return self.base.handle(message)
        except (KeyError, ValueError, TypeError) as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32001, "message": str(exc)}}
        except Exception:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": "internal error"}}


def main() -> None:
    server = OverlayServer()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = server.handle(request)
            if response is not None:
                print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
        except json.JSONDecodeError:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}), flush=True)
