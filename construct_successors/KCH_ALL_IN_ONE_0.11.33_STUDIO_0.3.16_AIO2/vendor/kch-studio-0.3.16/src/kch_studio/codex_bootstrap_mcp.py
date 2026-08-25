from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from ._version import __version__

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "kch-codex-bootstrap", "version": __version__}


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
            "Search the complete KCH tool catalog and the native-first runtime surface by name, "
            "alias or description. Search does not call the selected surface and does not create "
            "operational authority."
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
        "name": "kch_native_surface_status",
        "description": (
            "Inspect the five native-first KCH runtimes without importing or executing them. "
            "Native skill activation remains preferable to MCP transport."
        ),
        "inputSchema": _object({"component": {"type": "string"}}),
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


NATIVE_SURFACES = [
    {
        "name": "kwandisk",
        "title": "KwanDisk",
        "description": (
            "Native-first governed storage inventory, analysis, synchronization planning, "
            "reconstruction and reversible quarantine under cloud-first local-minimal custody."
        ),
        "aliases": ["disk", "drive", "storage", "cloud", "backup", "quarantine"],
        "skill": "kch-kwandisk",
        "runtime_path": "runtime/kwandisk",
    },
    {
        "name": "tokenmaster",
        "title": "TokenMaster",
        "description": (
            "Native-first token, cost, model and subagent orchestration planner with bounded "
            "multi-layer execution strategies."
        ),
        "aliases": ["token", "budget", "cost", "model", "subagent", "compute"],
        "skill": "kch-tokenmaster",
        "runtime_path": "runtime/tokenmaster",
    },
    {
        "name": "mis031_full_csi",
        "title": "MIS 0.3.1 Full CSI",
        "description": (
            "Native-first Mathematics of Semantic Information surface for typed qualitative "
            "composition, authority and future-only learning."
        ),
        "aliases": ["mis", "semantic", "qualitative", "composition", "csi"],
        "skill": "kch-mis-governance",
        "runtime_path": "runtime/kch_mis031_full_csi",
    },
    {
        "name": "mu_transmuter_scpp",
        "title": "mu EQ/QE, Transmuter and SCPP",
        "description": (
            "Native-first temporal memory, conjugate co-significance, structural processing and "
            "pentaxial preventive governance surface."
        ),
        "aliases": ["mu", "mu_eq", "mu_qe", "transmuter", "scpp", "pentaxial"],
        "skill": "kch-mu-transmuter-scpp",
        "runtime_path": "runtime/kch_mu_transmuter_scpp",
    },
    {
        "name": "virtuous_handoff",
        "title": "Virtuous Handoff",
        "description": (
            "Native-first complete multi-chat transfer with EOF evidence, reconciliation, exact "
            "receipt and source-side validation before promotion."
        ),
        "aliases": ["handoff", "transfer", "migration", "continuity", "rehydration", "chat"],
        "skill": "kch-virtuous-handoff",
        "runtime_path": "runtime/kch_virtuous_handoff",
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
            "native_surface_count": len(NATIVE_SURFACES),
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

    @staticmethod
    def _native_plugin_root() -> Path | None:
        configured = os.environ.get("KCH_NATIVE_PLUGIN_ROOT") or os.environ.get("PLUGIN_ROOT")
        return Path(configured).resolve() if configured else None

    def native_surface_status(self, component: str = "") -> dict[str, Any]:
        requested = component.strip().casefold().replace("-", "_")
        plugin_root = self._native_plugin_root()
        rows = []
        for descriptor in NATIVE_SURFACES:
            if requested and requested not in {
                str(descriptor["name"]).casefold(),
                str(descriptor["title"]).casefold().replace(" ", "_"),
            }:
                continue
            runtime_path = str(descriptor["runtime_path"])
            observed = plugin_root is not None
            available = (plugin_root / runtime_path).is_dir() if plugin_root else None
            rows.append(
                {
                    "name": descriptor["name"],
                    "title": descriptor["title"],
                    "skill": descriptor["skill"],
                    "runtime_path": runtime_path,
                    "availability_observed": observed,
                    "available": available,
                    "native_first": True,
                    "mcp_dispatchable": False,
                }
            )
        if requested and not rows:
            raise ValueError(f"unknown native KCH surface: {component}")
        return {
            "schema": "kch.codex-native-surface-status.v0.1.0",
            "surfaces": rows,
            "count": len(rows),
            "plugin_root_observed": plugin_root is not None,
            "all_observed_available": (
                all(row["available"] is True for row in rows) if plugin_root else None
            ),
            "native_precedes_mcp": True,
            "authority_created": False,
            "runtime_imported": False,
            "runtime_executed": False,
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
                        "kind": "mcp_tool",
                        "dispatchable": True,
                        "native_skill": None,
                    }
                )
        for descriptor in NATIVE_SURFACES:
            haystack = " ".join(
                (
                    str(descriptor["name"]).replace("_", " "),
                    str(descriptor["title"]),
                    str(descriptor["description"]),
                    " ".join(str(alias) for alias in descriptor["aliases"]),
                    str(descriptor["skill"]),
                )
            ).casefold()
            if all(term in haystack for term in terms):
                matches.append(
                    {
                        "name": descriptor["name"],
                        "description": descriptor["description"],
                        "read_only": True,
                        "kind": "native_runtime",
                        "dispatchable": False,
                        "native_skill": descriptor["skill"],
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
            "native_surface_count": len(NATIVE_SURFACES),
            "searchable_entry_count": len(self._catalog or {}) + len(NATIVE_SURFACES),
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
        elif name == "kch_native_surface_status":
            value = self.native_surface_status(str(arguments.get("component", "")))
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
                        "the full tool catalog in the startup handshake. Native surfaces returned "
                        "by search must activate their precise skill rather than be forced through "
                        "MCP dispatch. Never infer user consent. "
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
