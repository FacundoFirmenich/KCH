from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "kch-codex-bootstrap", "version": "0.3.2"}


def _object(
    properties: dict[str, Any], required: list[str] | None = None
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


TOOLS = [
    {
        "name": "kch_bootstrap_status",
        "description": (
            "Inspect the bounded Codex front door without materializing the full KCH runtime."
        ),
        "inputSchema": _object({}),
        "readOnly": True,
    },
    {
        "name": "kch_catalog_search",
        "description": (
            "Search the complete KCH tool catalog by name or description. Search does not call "
            "the selected tool and does not create operational authority."
        ),
        "inputSchema": _object(
            {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            ["query"],
        ),
        "readOnly": True,
    },
    {
        "name": "kch_governed_preflight",
        "description": (
            "Run the canonical KCH startup and governance gate. Call this first in every new "
            "task before material action; it authorizes no external side effect."
        ),
        "inputSchema": _object({}),
        "readOnly": True,
    },
    {
        "name": "kch_response_authority_adjudicate",
        "description": (
            "Adjudicate a structured candidate response against active KCH authority before "
            "release. This is a local gate, not semantic truth or host interposition."
        ),
        "inputSchema": _object({"candidate": {"type": "object"}}, ["candidate"]),
        "readOnly": False,
    },
    {
        "name": "kch_dispatch",
        "description": (
            "Dispatch one exact catalogued KCH tool through the full governed runtime. This "
            "does not bypass the target tool's consent, permission, PHL or authority controls."
        ),
        "inputSchema": _object(
            {
                "tool_name": {"type": "string"},
                "arguments": {"type": "object"},
            },
            ["tool_name"],
        ),
        "readOnly": False,
    },
]


class CodexBootstrapMCP:
    """Small Codex-facing catalog and governed dispatcher for the full Super-MCP."""

    def __init__(self, runtime_root: str | Path):
        self.root = Path(runtime_root).resolve()
        self._super: Any | None = None
        self._catalog: dict[str, dict[str, Any]] | None = None

    @property
    def super_materialized(self) -> bool:
        return self._super is not None

    def _load_catalog(self) -> dict[str, dict[str, Any]]:
        if self._catalog is not None:
            return self._catalog
        from .mcp_server import TOOLS as STUDIO_TOOLS
        from .super_mcp_overlay import _load_frozen_base

        base = _load_frozen_base()
        combined = [*base.TOOLS, *STUDIO_TOOLS]
        self._catalog = {str(item["name"]): dict(item) for item in combined}
        if len(self._catalog) != len(combined):
            raise RuntimeError("full KCH tool catalog contains a name collision")
        return self._catalog

    def _ensure_super(self) -> Any:
        if self._super is not None:
            return self._super
        from .super_mcp_overlay import IntegratedSuperMCP, prepare_runtime_environment

        prepare_runtime_environment(self.root)
        self._super = IntegratedSuperMCP(self.root)
        return self._super

    @staticmethod
    def _content(value: Any) -> dict[str, Any]:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(value, ensure_ascii=True, sort_keys=True),
                }
            ],
            "structuredContent": value,
        }

    def status(self) -> dict[str, Any]:
        return {
            "schema": "kch.codex-bootstrap-status.v0.1.0",
            "state": "BOUNDED_FRONT_DOOR_READY",
            "advertised_tool_count": len(TOOLS),
            "full_runtime_materialized": self.super_materialized,
            "full_catalog_loaded": self._catalog is not None,
            "governance_hierarchy": ["HARNESS", "AGENTS", "RULES"],
            "phl_authorized": True,
            "phl_training_executed": False,
            "phl_real_executed": False,
            "automatic_preflight_observed": False,
            "host_interposition_established": False,
            "claim_ceiling": "CODEX_MCP_TRANSPORT_FRONT_DOOR_ONLY",
        }

    def catalog_search(self, query: str, limit: int = 10) -> dict[str, Any]:
        terms = [term for term in query.strip().casefold().replace("_", " ").split() if term]
        if not terms:
            raise ValueError("query must not be empty")
        bounded = max(1, min(int(limit), 50))
        matches = []
        for name, descriptor in self._load_catalog().items():
            haystack = " ".join(
                (
                    name.replace("_", " "),
                    str(descriptor.get("title", "")),
                    str(descriptor.get("description", "")),
                )
            ).casefold()
            if all(term in haystack for term in terms):
                matches.append(
                    {
                        "name": name,
                        "description": str(descriptor.get("description", "")),
                        "read_only": bool(descriptor.get("readOnly", False)),
                    }
                )
        matches.sort(key=lambda item: item["name"])
        return {
            "schema": "kch.codex-bootstrap-catalog-search.v0.1.0",
            "query": query,
            "matches": matches[:bounded],
            "matched_total": len(matches),
            "returned": min(len(matches), bounded),
            "full_catalog_count": len(self._catalog or {}),
            "tool_executed": False,
            "authority_created": False,
        }

    def dispatch(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name in {item["name"] for item in TOOLS}:
            raise ValueError("bootstrap tools cannot recursively dispatch themselves")
        catalog = self._load_catalog()
        if tool_name not in catalog:
            raise ValueError(f"unknown KCH tool: {tool_name}")
        response = self._ensure_super().handle(
            {
                "jsonrpc": "2.0",
                "id": "bootstrap-dispatch",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
        )
        if response is None:
            raise RuntimeError("full KCH runtime returned no dispatch response")
        if "error" in response:
            raise ValueError(str(response["error"].get("message", response["error"])))
        return dict(response["result"]["structuredContent"])

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "kch_bootstrap_status":
            value = self.status()
        elif name == "kch_catalog_search":
            value = self.catalog_search(
                str(arguments.get("query", "")), int(arguments.get("limit", 10))
            )
        elif name == "kch_governed_preflight":
            value = self.dispatch("kch_preflight", {})
        elif name == "kch_response_authority_adjudicate":
            value = self.dispatch(
                "response_authority_adjudicate",
                {"candidate": dict(arguments.get("candidate", {}))},
            )
        elif name == "kch_dispatch":
            value = self.dispatch(
                str(arguments.get("tool_name", "")),
                dict(arguments.get("arguments", {})),
            )
        else:
            raise ValueError(f"unknown bootstrap tool: {name}")
        return self._content(value)

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
                    "serverInfo": SERVER_INFO,
                    "instructions": (
                        "KCH is the governing harness. In every new task call "
                        "kch_governed_preflight before material action, preserve HARNESS > AGENTS "
                        "> RULES, and use kch_catalog_search plus kch_dispatch instead of requiring "
                        "the 277-tool catalog in the startup handshake. Never infer user consent. "
                        "PHL is authorized but must not be trained without genuine feedback. "
                        "Capability, permission, authority, execution and training remain distinct. "
                        "Adverse gates and NOT_ESTIMABLE results must be preserved."
                    ),
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": item["name"],
                            "description": item["description"],
                            "inputSchema": item["inputSchema"],
                            "annotations": {"readOnlyHint": item["readOnly"]},
                        }
                        for item in TOOLS
                    ]
                }
            elif method == "tools/call":
                params = dict(message.get("params", {}))
                result = self.call(
                    str(params.get("name", "")), dict(params.get("arguments", {}))
                )
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
        if self._super is not None:
            self._super.close()


def main() -> None:
    root = Path(os.environ.get("KCH_STUDIO_RUNTIME", Path.cwd() / ".kch-studio-runtime"))
    server = CodexBootstrapMCP(root)
    try:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                response = server.handle(request)
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
