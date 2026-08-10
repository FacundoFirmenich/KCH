from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class ConfigClient:
    def __init__(self, command: str, args: list[str], cwd: str | None, environment: dict[str, str]):
        env = dict(os.environ)
        env.update(environment)
        self.process = subprocess.Popen(
            [command, *args],
            cwd=cwd or ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="strict",
            bufsize=1,
        )
        self.request_id = 0

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        assert self.process.stdin is not None and self.process.stdout is not None
        self.request_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": self.request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self.process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"no MCP response; exit={self.process.poll()}; stderr={stderr}")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(str(response["error"]))
        return response["result"]

    def notify(self) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        self.process.stdin.flush()

    def close(self) -> dict[str, Any]:
        if self.process.stdin:
            self.process.stdin.close()
        try:
            code = self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            code = self.process.wait(timeout=10)
        stderr = self.process.stderr.read() if self.process.stderr else ""
        return {"exit_code": code, "stderr": stderr}


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch KCH from each generated client configuration and validate its transport fields.")
    parser.add_argument("--config-dir", type=Path, default=ROOT / "generated_configs")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    cline = json.loads((args.config_dir / "cline_mcp_settings.json").read_text(encoding="utf-8"))["mcpServers"]["kch-super-mcp"]
    vscode = json.loads((args.config_dir / "vscode_mcp.json").read_text(encoding="utf-8"))["servers"]["kchSuperMcp"]
    codex = tomllib.loads((args.config_dir / "codex_config.toml").read_text(encoding="utf-8"))["mcp_servers"]["kch_super_mcp"]
    configs = {
        "cline": {"command": cline["command"], "args": cline["args"], "cwd": str(ROOT), "env": cline.get("env", {})},
        "vscode": {"command": vscode["command"], "args": vscode["args"], "cwd": vscode.get("cwd"), "env": vscode.get("env", {})},
        "codex": {"command": codex["command"], "args": codex["args"], "cwd": codex.get("cwd"), "env": codex.get("env", {})},
    }
    rows = []
    for name, config in configs.items():
        client = ConfigClient(config["command"], config["args"], config["cwd"], config["env"])
        try:
            initialized = client.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": f"kch-{name}-config-validator", "version": "0.11.0"}})
            client.notify()
            tools = client.request("tools/list")["tools"]
            resources = client.request("resources/list")["resources"]
            status_result = client.request("tools/call", {"name": "kch.super.status", "arguments": {}})
            status = json.loads(status_result["content"][0]["text"])
        finally:
            process = client.close()
        passed = (
            initialized.get("serverInfo") == {"name": "kwancode-harness", "version": "0.11.0"}
            and len(tools) == 49
            and len(resources) == 4
            and status.get("profile") == "agent-shadow"
            and status.get("mutating_execution_authorized") is False
            and process == {"exit_code": 0, "stderr": ""}
        )
        rows.append({"client_config": name, "gate": "PASS" if passed else "FAIL", "tools": len(tools), "resources": len(resources), "state": config["env"].get("KCH_011_STATE"), "process": process})

    states = [row["state"] for row in rows]
    checks = {
        "three_config_launches": all(row["gate"] == "PASS" for row in rows),
        "states_are_explicit_and_distinct": len(states) == 3 and None not in states and len(set(states)) == 3,
        "cline_auto_approve_empty": cline.get("autoApprove") == [],
        "codex_approval_prompt": codex.get("default_tools_approval_mode") == "prompt",
    }
    gate = "PASS" if all(checks.values()) else "FAIL"
    result = {
        "schema": "kch.super-mcp-generated-client-config-gate.v0.11.0",
        "gate": gate,
        "checks": checks,
        "clients": rows,
        "actual_cline_codex_vscode_host_invocation": "NOT_RUN_BY_THIS_GATE",
        "phl_real_session": "NOT_RUN",
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps({"gate": gate, "clients": {row["client_config"]: row["gate"] for row in rows}, "host_invocation": "NOT_RUN"}, ensure_ascii=False))
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

