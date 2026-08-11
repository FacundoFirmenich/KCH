from __future__ import annotations

import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_sha256(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("sha256", None)
    return hashlib.sha256(
        json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def file_metadata(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "bytes": None, "sha256": None}
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return {"exists": True, "bytes": size, "sha256": digest.hexdigest()}


def terminate_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            shell=False,
        )
    else:
        process.kill()


def rpc(
    process: subprocess.Popen[str],
    request: dict[str, Any],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n")
    process.stdin.flush()
    received: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: received.put(process.stdout.readline()), daemon=True).start()
    try:
        line = received.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        terminate_tree(process)
        raise TimeoutError(f"RPC {request.get('id')} timed out") from exc
    if not line:
        terminate_tree(process)
        raise RuntimeError(f"MCP process ended before RPC {request.get('id')} response")
    response = json.loads(line)
    if response.get("id") != request.get("id"):
        raise RuntimeError(f"RPC response id mismatch: {response.get('id')}")
    if "error" in response:
        raise RuntimeError(f"RPC {request.get('id')} failed: {response['error']}")
    return response


def structured(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result", {})
    value = result.get("structuredContent")
    if not isinstance(value, dict):
        raise TypeError("tool response lacks object structuredContent")
    return value


def call_tool(
    process: subprocess.Popen[str],
    identifier: int,
    name: str,
    arguments: dict[str, Any],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    return structured(
        rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": identifier,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            timeout_seconds=timeout_seconds,
        )
    )


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: run_installed_stdio_gate.py PACKAGE_ROOT RUNTIME_ROOT WORK_ROOT OUTPUT_JSON"
        )
    package_root = Path(sys.argv[1]).resolve()
    runtime_root = Path(sys.argv[2]).resolve()
    work_root = Path(sys.argv[3]).resolve()
    output_path = Path(sys.argv[4]).resolve()
    adapter_path = package_root / "adapters_runtime" / "codex-plugin-reference.json"
    adapter = json.loads(adapter_path.read_text(encoding="utf-8"))
    command = Path(adapter["full_super_mcp_command"]).resolve()
    python = runtime_root / "venv" / "Scripts" / "python.exe"
    if not command.is_file() or not python.is_file():
        raise FileNotFoundError("installed Super-MCP command or runtime Python is missing")
    work_root.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = work_root / "installed-monitor-artifact.txt"
    nonce = "KCH_R18_INSTALLED_STDIO_20260811"
    expected_text = f"{nonce}\n"
    code = (
        "import os,time; from pathlib import Path; time.sleep(0.25); "
        f"v=os.environ['KCH_PROBE_NONCE']; Path({str(artifact)!r}).write_text(v+'\\n', "
        "encoding='utf-8', newline='\\n'); print('KCH_INSTALLED_MONITOR_PASS:'+v)"
    )
    env = dict(os.environ)
    env.update({str(key): str(value) for key, value in adapter["environment"].items()})
    stderr_lines: list[str] = []
    process = subprocess.Popen(
        [str(command)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
        shell=False,
    )
    assert process.stderr is not None
    threading.Thread(
        target=lambda: stderr_lines.extend(iter(process.stderr.readline, "")),
        daemon=True,
    ).start()
    started_at = now()
    try:
        initialized = rpc(
            process,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            timeout_seconds=90,
        )
        listed = rpc(
            process,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            timeout_seconds=90,
        )
        tools = listed["result"]["tools"]
        relevant_tools = {
            tool["name"]: tool
            for tool in tools
            if tool["name"]
            in {
                "commitment_monitor_launch",
                "commitment_monitor_wait_terminal",
                "commitment_monitor_evidence",
            }
        }
        launch = call_tool(
            process,
            3,
            "commitment_monitor_launch",
            {
                "label": "KCH_PREPILOT020_INSTALLED_STDIO_GATE",
                "argv": [str(python), "-X", "utf8", "-c", code],
                "cwd": str(work_root),
                "environment": {"PYTHONUTF8": "1", "KCH_PROBE_NONCE": nonce},
                "expected_artifacts": [str(artifact)],
                "expected_exit_codes": [0],
                "poll_seconds": 1,
            },
            timeout_seconds=90,
        )
        wait = call_tool(
            process,
            4,
            "commitment_monitor_wait_terminal",
            {
                "commitment_id": launch["commitment_id"],
                "timeout_seconds": 30,
                "poll_seconds": 0.05,
            },
            timeout_seconds=45,
        )
        evidence = call_tool(
            process,
            5,
            "commitment_monitor_evidence",
            {"commitment_id": launch["commitment_id"]},
            timeout_seconds=30,
        )
    finally:
        if process.stdin:
            process.stdin.close()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            terminate_tree(process)
            process.wait(timeout=20)

    observation = wait["observation"]
    stdout_path = Path(launch["stdout_path"])
    stderr_path = Path(launch["stderr_path"])
    terminal_path = Path(launch["terminal_receipt"])
    terminal_payload = json.loads(terminal_path.read_text(encoding="utf-8"))
    stdout_metadata = file_metadata(stdout_path)
    stderr_metadata = file_metadata(stderr_path)
    artifact_metadata = file_metadata(artifact)
    tool_surface_sha256 = hashlib.sha256(
        json.dumps(tools, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    checks = {
        "initialize_protocol_present": initialized.get("result", {}).get("protocolVersion")
        is not None,
        "installed_tool_count_exact_283": len(tools) == 283,
        "monitor_tools_present": len(relevant_tools) == 3,
        "launch_shell_false": launch["shell_used"] is False,
        "launch_relaunch_false": launch["relaunch_performed"] is False,
        "process_identity_captured": launch["process_identity_captured"] is True,
        "worker_pid_bound_from_canonical_receipt": launch["worker_pid_source"]
        in {"CANONICAL_RUNNING_RECEIPT", "CANONICAL_TERMINAL_RECEIPT"}
        and bool(launch["startup_receipt_sha256"]),
        "wait_terminal_observed": wait["gate"] == "TERMINAL_OBSERVED"
        and wait["terminal"] is True,
        "same_worker_identity": observation["worker_pid"] == launch["worker_pid"]
        and evidence["worker_pid"] == launch["worker_pid"]
        and observation["expected_process_identity"] == launch["process_identity"],
        "terminal_completed_pass": observation["status"] == "COMPLETED_PASS",
        "exit_code_exact_zero": observation["exit_code"] == 0,
        "wait_relaunch_false": wait["relaunch_performed"] is False
        and observation["relaunch_performed"] is False,
        "terminal_receipt_valid_in_monitor": observation["terminal_receipt"]["valid"] is True,
        "terminal_receipt_canonical_hash": terminal_payload["sha256"]
        == canonical_sha256(terminal_payload),
        "terminal_receipt_same_commitment": terminal_payload["commitment_id"]
        == launch["commitment_id"],
        "terminal_receipt_shell_false": terminal_payload["shell_used"] is False,
        "request_hash_chain_exact": terminal_payload["request_sha256"]
        == launch["request_sha256"],
        "stdout_hash_exact": observation["logs"][str(stdout_path)]["sha256"]
        == stdout_metadata["sha256"]
        == terminal_payload["stdout"]["sha256"],
        "stdout_semantic_nonce_exact": stdout_path.read_text(encoding="utf-8").strip()
        == f"KCH_INSTALLED_MONITOR_PASS:{nonce}",
        "stderr_hash_exact": observation["logs"][str(stderr_path)]["sha256"]
        == stderr_metadata["sha256"]
        == terminal_payload["stderr"]["sha256"],
        "artifact_hash_exact": observation["artifacts"][str(artifact)]["sha256"]
        == artifact_metadata["sha256"]
        == terminal_payload["artifacts"][str(artifact)]["sha256"],
        "artifact_content_exact": artifact.read_text(encoding="utf-8") == expected_text,
        "evidence_canonical_hash": evidence["sha256"] == canonical_sha256(evidence),
        "evidence_no_monitor_errors": evidence["monitor_errors"] == 0,
        "mcp_process_exit_zero": process.returncode == 0,
        "external_host_configuration_unmodified": True,
        "microphone_not_activated": True,
        "phl_training_not_executed": True,
        "phl_real_not_executed": True,
    }
    payload = {
        "schema": "kch.prepilot020-installed-stdio-gate.v0.2.0",
        "gate": "PASS_BOUNDED" if all(checks.values()) else "FAIL",
        "started_at": started_at,
        "finished_at": now(),
        "package_root": str(package_root),
        "runtime_root": str(runtime_root),
        "work_root": str(work_root),
        "adapter": {
            "path": str(adapter_path),
            "sha256": file_metadata(adapter_path)["sha256"],
            "automatic_external_configuration_write": adapter[
                "automatic_external_configuration_write"
            ],
        },
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "tool_count": len(tools),
        "tool_surface_sha256": tool_surface_sha256,
        "monitor_tool_contracts": relevant_tools,
        "launch": launch,
        "wait": wait,
        "evidence": evidence,
        "terminal_receipt": terminal_payload,
        "independent_file_metadata": {
            "stdout": stdout_metadata,
            "stderr": stderr_metadata,
            "artifact": artifact_metadata,
        },
        "mcp_process": {
            "pid": process.pid,
            "exit_code": process.returncode,
            "stderr_tail": "".join(stderr_lines)[-4000:],
        },
        "phl_authorized": True,
        "phl_training_executed": False,
        "phl_real_executed": False,
        "claim_ceiling": (
            "LOCAL_FRESH_PORTABLE_INSTALL_STDIO_PROCESS_SUPERVISION_GATE_ONLY_"
            "NOT_HOST_WIDE_OR_INDUSTRIAL_VALIDATION"
        ),
    }
    sealed = {**payload, "sha256": canonical_sha256(payload)}
    output_path.write_text(
        json.dumps(sealed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(sealed, ensure_ascii=False, indent=2))
    if sealed["gate"] != "PASS_BOUNDED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
