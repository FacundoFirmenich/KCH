from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from .contracts import sha256_json

SUPPORTED_HOSTS = frozenset({"codex", "vscode", "cline", "opencode"})


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


class HostAdapterCompiler:
    """Compile inert, reviewable host projections; never install or enable them."""

    def __init__(self, output_root: str | Path):
        self.output_root = Path(output_root).resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)

    def compile(
        self,
        *,
        name: str,
        command: list[str],
        targets: Iterable[str],
        cwd: str | None = None,
    ) -> dict[str, Any]:
        normalized = tuple(dict.fromkeys(target.lower() for target in targets))
        unknown = set(normalized) - SUPPORTED_HOSTS
        if unknown:
            raise ValueError(f"unsupported host targets: {sorted(unknown)}")
        if not command or any(not isinstance(item, str) or not item for item in command):
            raise ValueError("command must be a non-empty argv array")
        command_path, args = command[0], command[1:]
        artifacts: list[dict[str, Any]] = []

        if "codex" in normalized:
            lines = [
                f"[mcp_servers.{name}]",
                f"command = {toml_string(command_path)}",
                f"args = {json.dumps(args, ensure_ascii=False)}",
                "enabled = false",
                "required = false",
                'default_tools_approval_mode = "prompt"',
                "startup_timeout_sec = 20",
                "tool_timeout_sec = 60",
            ]
            if cwd:
                lines.append(f"cwd = {toml_string(cwd)}")
            path = self.output_root / "codex" / ".codex" / "config.toml"
            write_text(path, "\n".join(lines))
            artifacts.append(self._describe(path, "CODEX_PROJECT_SCOPED_DISABLED"))

        if "vscode" in normalized:
            server: dict[str, Any] = {"type": "stdio", "command": command_path, "args": args}
            if cwd:
                server["cwd"] = cwd
            if os.name != "nt":
                server["sandboxEnabled"] = True
            payload: dict[str, Any] = {"servers": {name: server}, "inputs": []}
            path = self.output_root / "vscode" / ".vscode" / "mcp.json"
            write_json(path, payload)
            artifacts.append(
                self._describe(
                    path,
                    "VSCODE_WORKSPACE_STAGED_SANDBOXED"
                    if os.name != "nt"
                    else "VSCODE_WORKSPACE_STAGED_WINDOWS_SANDBOX_UNAVAILABLE",
                )
            )

        if "cline" in normalized:
            server = {"command": command_path, "args": args, "disabled": True, "autoApprove": []}
            if cwd:
                server["cwd"] = cwd
            path = self.output_root / "cline" / "cline_mcp_settings.json"
            write_json(path, {"mcpServers": {name: server}})
            artifacts.append(self._describe(path, "CLINE_STAGED_DISABLED_NO_AUTO_APPROVE"))

        if "opencode" in normalized:
            server = {"type": "local", "command": command, "enabled": False}
            if cwd:
                server["cwd"] = cwd
            path = self.output_root / "opencode" / "opencode.json"
            write_json(
                path,
                {
                    "$schema": "https://opencode.ai/config.json",
                    "mcp": {name: server},
                },
            )
            artifacts.append(self._describe(path, "OPENCODE_STAGED_DISABLED"))

        receipt = {
            "schema": "kch.host-adapter-compile-receipt.v0.1.0",
            "name": name,
            "targets": list(normalized),
            "artifacts": artifacts,
            "installation_authorized": False,
            "activation_authorized": False,
            "secrets_embedded": False,
            "host_semantic_equivalence": "NOT_ASSUMED",
            "receipt_hash": "",
        }
        receipt["receipt_hash"] = sha256_json(
            {key: value for key, value in receipt.items() if key != "receipt_hash"}
        )
        return receipt

    def _describe(self, path: Path, state: str) -> dict[str, Any]:
        raw = path.read_bytes()
        import hashlib

        return {
            "path": path.relative_to(self.output_root).as_posix(),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "state": state,
        }
