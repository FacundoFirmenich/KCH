from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any

from ._version import __version__
from .mcp_server import PROTOCOL_VERSION
from .mcp_server import TOOLS as STUDIO_TOOLS
from .mcp_server import StudioMCP

CLOUD_FIRST_STORAGE_POLICY = {
    "mode": "CLOUD_FIRST_LOCAL_MINIMAL",
    "authoritativeStore": "GOOGLE_DRIVE",
    "localRole": "ACTIVE_SOURCE_RUNTIME_AND_EPHEMERAL_STAGING_ONLY",
    "heavyDerivedStorageOnSystemDisk": False,
    "remoteVerificationRequiredBeforeDeletion": True,
    "unknownArtifactDeletable": False,
    "automaticDeletionOnPressure": False,
}

SUPER_MCP_SERVER_INFO = {
    "name": "kch-super-mcp",
    "version": __version__,
}

BASE_READ_ONLY_TOOLS = {
    "kch.super.status",
    "kch.super.registry",
    "kch.super.controls",
    "kch.super.context.compile",
    "kch.super.audit.export",
    "kch.super.registry.evidence.audit",
    "kch.component.status",
    "kch.phl.projection",
    "kch.sco.projection",
    "kch.mis.certificate.verify",
    "kch.kwanprompts.probe",
    "kch.rgg.probe",
    "kch.obl_phl.probe",
}


def _load_frozen_base() -> Any:
    try:
        from kwancode_harness import mcp_server as base

        return base
    except ImportError:
        work_root = Path(__file__).resolve().parents[3]
        candidates = (
            work_root / "KCH_0.11_REEXTRACT_FINAL" / "src",
            work_root / "KCH_0.11" / "src",
        )
        for candidate in candidates:
            if candidate.is_dir():
                sys.path.insert(0, str(candidate))
                from kwancode_harness import mcp_server as base

                return base
        raise RuntimeError(
            "KCH 0.11 runtime unavailable: install the bundled kwancode_harness-0.11.0 wheel "
            "inside the isolated environment or mount a frozen KCH 0.11 source checkout"
        )


class IntegratedSuperMCP:
    """Loss-aware composition: frozen KCH 0.11 plus Studio/Fabric overlay."""

    def __init__(self, runtime_root: str | Path):
        self.root = Path(runtime_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        base = _load_frozen_base()
        self.base_module = base
        self.base = base.MCPServer(base.build_gateway())
        self.studio = StudioMCP(self.root / "studio_overlay")
        self._base_capabilities_registered = False
        self.base_tool_names = {tool["name"] for tool in base.TOOLS}
        self.base_read_only_tools = {
            name
            for name in self.base_tool_names
            if name in BASE_READ_ONLY_TOOLS or name.startswith("kch.control.")
        }
        base_names = {tool["name"] for tool in base.TOOLS}
        overlay_names = {tool["name"] for tool in STUDIO_TOOLS}
        collisions = base_names & overlay_names
        if collisions:
            raise ValueError(f"Super-MCP tool collision: {sorted(collisions)}")

    def _ensure_studio_runtime(self) -> None:
        advanced = self.studio.ensure_runtime()
        if self._base_capabilities_registered:
            return
        advanced.phl.register_capabilities(
            [
                {
                    "name": tool["name"],
                    "readOnly": tool["name"] in self.base_read_only_tools,
                }
                for tool in self.base_module.TOOLS
            ]
        )
        self._base_capabilities_registered = True

    @staticmethod
    def _ok(message_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": message_id, "result": result}

    @staticmethod
    def _error(message_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {"code": code, "message": message},
        }

    @staticmethod
    def resources() -> list[dict[str, Any]]:
        return [
            {
                "uri": "kch://super-mcp/status",
                "name": "KCH Super-MCP status",
                "description": "Bounded surface, storage and authority status.",
                "mimeType": "application/json",
            },
            {
                "uri": "kch://super-mcp/integration",
                "name": "KCH Super-MCP integration receipt",
                "description": "Federated base and Studio composition receipt.",
                "mimeType": "application/json",
            },
            {
                "uri": "kch://super-mcp/preflight",
                "name": "KCH governed preflight",
                "description": "Full preflight; reading can initialize optional local runtimes.",
                "mimeType": "application/json",
            },
        ]

    def status(self) -> dict[str, Any]:
        overlay_names = {tool["name"] for tool in STUDIO_TOOLS}
        return {
            "schema": "kch.super-mcp.status.v0.2.0",
            "status": "READY_BOUNDED",
            "protocolVersion": PROTOCOL_VERSION,
            "server": SUPER_MCP_SERVER_INFO,
            "combinedToolCount": len(self.base_tool_names | overlay_names),
            "authorityInherited": False,
            "automaticPromotion": False,
            "physicalExecutionAuthority": False,
            "phlAuthorized": True,
            "phlTrainingExecuted": False,
            "storagePolicy": CLOUD_FIRST_STORAGE_POLICY,
            "surfaceRole": "FEDERATED_DISCOVERY_AND_INVOCATION_NOT_GOVERNING_SYSTEM",
        }

    def _read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "kch://super-mcp/status":
            value: Any = self.status()
        elif uri == "kch://super-mcp/integration":
            value = self.receipt()
        elif uri == "kch://super-mcp/preflight":
            response = self.handle(
                {
                    "jsonrpc": "2.0",
                    "id": "super-mcp:resource:preflight",
                    "method": "tools/call",
                    "params": {"name": "kch_preflight", "arguments": {}},
                }
            )
            if response is None or "error" in response:
                raise RuntimeError(f"preflight resource failed: {response}")
            value = response["result"]
        else:
            raise ValueError(f"Unknown Super-MCP resource: {uri}")
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(value, ensure_ascii=False, sort_keys=True),
                }
            ]
        }

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        message_id = message.get("id")
        method = message.get("method")
        if method == "ping":
            return self._ok(message_id, {})
        if method == "resources/list":
            return self._ok(message_id, {"resources": self.resources()})
        if method == "resources/read":
            params = message.get("params") or {}
            uri = params.get("uri") if isinstance(params, dict) else None
            if not isinstance(uri, str) or not uri:
                return self._error(message_id, -32602, "resources/read requires uri")
            try:
                return self._ok(message_id, self._read_resource(uri))
            except (ValueError, RuntimeError) as exc:
                return self._error(message_id, -32602, str(exc))
        if method == "initialize":
            response = self.base.handle(message)
            if response and "result" in response:
                response["result"]["serverInfo"] = SUPER_MCP_SERVER_INFO
                capabilities = dict(response["result"].get("capabilities", {}))
                capabilities["resources"] = {"subscribe": False, "listChanged": False}
                response["result"]["capabilities"] = capabilities
                response["result"]["instructions"] = (
                    "This Super-MCP is KCH's federated discovery and invocation surface, not KCH's governing identity. "
                    "KCH 0.11 authority remains frozen beneath a versioned successor overlay. Governance is HARNESS > AGENTS > RULES; "
                    "the user constitution and programmed DIRECT rules govern orchestration. PLAN, RUN and CONSTRUCT are distinct. "
                    "Every component is strategically material and must pass local-completeness and systemic-synergy gates. "
                    "Search is not install; isolated install requires four-way consent; full checkpoints require a size warning and explicit confirmation. "
                    "PHL is authorized and available but remains untrained until genuine user feedback; an active PHL session blocks ordinary mutations across both base and overlay tools."
                )
            return response
        if method == "tools/list":
            response = self.base.handle(message)
            if response and "result" in response:
                for descriptor in response["result"]["tools"]:
                    descriptor["annotations"] = {
                        "readOnlyHint": descriptor["name"] in self.base_read_only_tools
                    }
                response["result"]["tools"].extend(
                    {
                        "name": tool["name"],
                        "title": tool["title"],
                        "description": tool["description"],
                        "inputSchema": tool["inputSchema"],
                        "annotations": {"readOnlyHint": tool["readOnly"]},
                    }
                    for tool in STUDIO_TOOLS
                )
            return response
        if method == "tools/call":
            self._ensure_studio_runtime()
            params = dict(message.get("params", {}))
            name = str(params.get("name", ""))
            if name in self.studio.handlers:
                return self.studio.handle(message)
            if name in self.base_tool_names:
                try:
                    return self.studio.advanced.phl.dispatch(
                        name,
                        dict(params.get("arguments", {})),
                        lambda _arguments: self.base.handle(message),
                    )
                except Exception as exc:
                    return {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {"code": -32602, "message": str(exc)},
                    }
        return self.base.handle(message)

    def receipt(self) -> dict[str, Any]:
        self._ensure_studio_runtime()
        assert self.studio.advanced is not None
        base_tools = {tool["name"] for tool in self.base_module.TOOLS}
        overlay_tools = {tool["name"] for tool in STUDIO_TOOLS}
        return {
            "schema": "kch.super-mcp-studio-integration-receipt.v0.2.0",
            "surface": {
                "name": SUPER_MCP_SERVER_INFO["name"],
                "protocol_version": PROTOCOL_VERSION,
                "transport": "stdio",
                "role": "FEDERATED_DISCOVERY_AND_INVOCATION",
            },
            "base": {
                "name": "kwancode-harness",
                "version": "0.11.0",
                "tool_count": len(base_tools),
            },
            "overlay": {
                "name": "kch-csi-studio",
                "version": __version__,
                "tool_count": len(overlay_tools),
            },
            "combined_tool_count": len(base_tools | overlay_tools),
            "tool_collisions": sorted(base_tools & overlay_tools),
            "base_modified": False,
            "authority_inherited": False,
            "installation_authorized": False,
            "storage_policy": CLOUD_FIRST_STORAGE_POLICY,
            "phl_authorized": True,
            "phl_training_executed": self.studio.advanced.phl.status()["training_executed"],
            "phl_real_executed": self.studio.advanced.phl.status()["training_executed"],
        }

    def close(self) -> None:
        if self.studio.advanced is not None:
            self.studio.advanced.close()


def prepare_runtime_environment(root: Path) -> dict[str, Any]:
    """Provision local runtime state without embedding or reusing user credentials."""
    root.mkdir(parents=True, exist_ok=True)
    secret_path = root / "kch_011_hmac_secret.txt"
    generated = False
    if not os.environ.get("KCH_011_HMAC_SECRET"):
        if secret_path.is_file():
            secret = secret_path.read_text(encoding="ascii").strip()
        else:
            secret = secrets.token_hex(32)
            secret_path.write_text(secret + "\n", encoding="ascii")
            try:
                secret_path.chmod(0o600)
            except OSError:
                pass
            generated = True
        os.environ["KCH_011_HMAC_SECRET"] = secret
    os.environ.setdefault("KCH_011_STATE", str(root / "kch_011_state.sqlite3"))
    return {
        "runtime_root": str(root),
        "secret_path": str(secret_path),
        "secret_generated": generated,
        "secret_embedded_in_package": False,
        "state_path": os.environ["KCH_011_STATE"],
    }


def main() -> None:
    root = Path(os.environ.get("KCH_STUDIO_RUNTIME", Path.cwd() / ".kch-studio-runtime"))
    prepare_runtime_environment(root)
    server = IntegratedSuperMCP(root)
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
                print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
    finally:
        server.close()


if __name__ == "__main__":
    main()
