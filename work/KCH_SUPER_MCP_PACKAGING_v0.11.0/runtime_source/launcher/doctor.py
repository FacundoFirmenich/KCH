from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"
LAUNCHER = ROOT / "launcher" / "run_super_mcp.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class Client:
    def __init__(self, state: Path):
        env = dict(__import__("os").environ)
        env["KCH_011_STATE"] = str(state)
        env["KCH_011_PROFILE"] = "agent-shadow"
        self.process = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-u", str(LAUNCHER)],
            cwd=ROOT,
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
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"MCP server ended without response; exit={self.process.poll()}; stderr={stderr}")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(f"MCP error for {method}: {response['error']}")
        return response["result"]

    def notify(self, method: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.process.stdin.flush()

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        if result.get("isError") is not False:
            raise RuntimeError(f"tool returned isError: {name}")
        return json.loads(result["content"][0]["text"])

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
    parser = argparse.ArgumentParser(description="Verify the complete portable KCH 0.11 Super-MCP distribution.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, observed: Any) -> None:
        checks.append({"check": name, "state": "PASS" if condition else "FAIL", "observed": observed})

    manifest_process = subprocess.run(
        [sys.executable, str(BUNDLE / "scripts" / "verify_bundle.py"), str(BUNDLE)],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
    )
    check("CANONICAL_BUNDLE_66", manifest_process.returncode == 0, manifest_process.stdout.strip())
    check("PYTHON_VERSION", sys.version_info >= (3, 11), sys.version.split()[0])
    wheels = sorted((BUNDLE / "dist").glob("*.whl")) + sorted((BUNDLE / "vendor").glob("*.whl"))
    check("SEALED_WHEEL_COUNT", len(wheels) == 8, [path.name for path in wheels])

    phl_state = BUNDLE / "evidence" / "KCH_CURRENT_INTEGRATION_STATE_v0.6.0.sqlite3"
    phl_before = sha256_file(phl_state)
    client: Client | None = None
    process_receipt: dict[str, Any] = {}
    try:
        with tempfile.TemporaryDirectory() as directory:
            client = Client(Path(directory) / "doctor_state.sqlite3")
            initialized = client.request(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "kch-super-mcp-doctor", "version": "0.11.0"},
                },
            )
            client.notify("notifications/initialized")
            tools = client.request("tools/list")["tools"]
            resources = client.request("resources/list")["resources"]
            names = [row["name"] for row in tools]
            status = client.call("kch.super.status")
            registry_audit = client.call("kch.super.registry.evidence.audit")
            phl = client.call("kch.phl.projection")

            check("MCP_IDENTITY", initialized.get("serverInfo") == {"name": "kwancode-harness", "version": "0.11.0"}, initialized)
            check("MCP_PROTOCOL", initialized.get("protocolVersion") == "2025-06-18", initialized.get("protocolVersion"))
            check("MCP_TOOL_COUNT", len(tools) == 49, len(tools))
            check("DIRECT_CONTROL_COUNT", len([name for name in names if name.startswith("kch.control.R")]) == 28, len([name for name in names if name.startswith("kch.control.R")]))
            check("MCP_RESOURCE_COUNT", len(resources) == 4, len(resources))
            check("AGENT_SHADOW", status.get("profile") == "agent-shadow", status.get("profile"))
            check("NO_MUTATING_EXECUTION", status.get("mutating_execution_authorized") is False, status.get("mutating_execution_authorized"))
            check("ENFORCED_PROHIBITED", status.get("enforced_profile") == "PROHIBITED_UNTIL_GATES_PASS", status.get("enforced_profile"))
            check("COMPONENT_PACKAGES", status.get("component_packages", {}).get("available") == 7 and status.get("component_packages", {}).get("unavailable") == 0, status.get("component_packages"))
            check("LEDGER_INTEGRITY", status.get("ledger", {}).get("gate") == "PASS", status.get("ledger"))
            check("REGISTRY_EVIDENCE_19", registry_audit.get("totals") == {"PASS": 19, "FAIL": 0, "UNAVAILABLE": 0}, registry_audit.get("totals"))
            check("NO_PHL_MUTATION_TOOLS", not any(token in name.lower() for name in names for token in ("phl.start", "start_phl", "phl.feedback", "phl.close", "phl.commit")), names)
            check("PHL_PROJECTION_ONLY", phl.get("state") == "AVAILABLE" and phl.get("integrity", {}).get("gate") == "PASS" and phl.get("projection", {}).get("feedback") == 0 and phl.get("projection", {}).get("active_phl_session_id") is None, phl)
    finally:
        if client is not None:
            process_receipt = client.close()

    phl_after = sha256_file(phl_state)
    check("PHL_BYTES_UNCHANGED", phl_before == phl_after, {"before": phl_before, "after": phl_after})
    check("SERVER_PROCESS_CLOSED_CLEANLY", process_receipt.get("exit_code") == 0 and not process_receipt.get("stderr"), process_receipt)

    gate = "PASS" if all(row["state"] == "PASS" for row in checks) else "FAIL"
    result = {
        "schema": "kch.super-mcp-portable-doctor.v0.11.0",
        "release": "KCH 0.11",
        "gate": gate,
        "checks_passed": sum(row["state"] == "PASS" for row in checks),
        "checks_total": len(checks),
        "checks": checks,
        "phl_real_session": "NOT_RUN",
        "claim_ceiling": "PORTABLE_LOCAL_STDIO_DEPLOYMENT_VALIDATED_WITH_AGENT_SHADOW_AND_READ_ONLY_FEDERATION",
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps({"gate": gate, "checks": f"{result['checks_passed']}/{result['checks_total']}", "phl_real_session": "NOT_RUN"}, ensure_ascii=False))
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
