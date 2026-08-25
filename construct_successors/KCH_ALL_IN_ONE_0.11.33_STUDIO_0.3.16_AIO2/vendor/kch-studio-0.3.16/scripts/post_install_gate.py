from __future__ import annotations

import atexit
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any


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
    label: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    assert process.stdin is not None and process.stdout is not None
    print(f"KCH_GATE_STAGE_START {label}", file=sys.stderr, flush=True)
    process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    process.stdin.flush()
    received: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: received.put(process.stdout.readline()), daemon=True).start()
    try:
        line = received.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        terminate_tree(process)
        raise TimeoutError(f"RPC stage timed out after {timeout_seconds}s: {label}") from exc
    if not line:
        terminate_tree(process)
        stderr = "" if process.stderr is None else process.stderr.read()
        raise RuntimeError(f"MCP process closed without response: {stderr[-4000:]}")
    result = json.loads(line)
    if not isinstance(result, dict):
        raise RuntimeError(f"RPC stage returned a non-object response: {label}")
    if "error" in result:
        raise RuntimeError(
            f"RPC stage returned an error for {label}: "
            + json.dumps(result["error"], ensure_ascii=False, sort_keys=True)
        )
    if result.get("id") != request.get("id"):
        raise RuntimeError(
            f"RPC stage returned mismatched id for {label}: "
            f"expected={request.get('id')!r} observed={result.get('id')!r}"
        )
    if "result" not in result:
        raise RuntimeError(f"RPC stage returned neither result nor error: {label}")
    print(f"KCH_GATE_STAGE_PASS {label}", file=sys.stderr, flush=True)
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_runtime(root: Path) -> Path:
    for variable in ("KCH_RUNTIME_ROOT", "KCH_PORTABLE_RUNTIME"):
        explicit = os.environ.get(variable)
        if explicit:
            return Path(explicit).resolve()
    runtime_paths = root / "runtime_paths.cmd"
    if runtime_paths.is_file():
        for line in runtime_paths.read_text(encoding="utf-8").splitlines():
            matched = re.fullmatch(
                r'set\s+"KCH_RUNTIME_ROOT=(.+)"', line.strip(), flags=re.IGNORECASE
            )
            if matched:
                return Path(matched.group(1)).resolve()
    return (root / ".runtime").resolve()


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
    runtime = resolve_runtime(root)
    command = runtime / "venv" / "Scripts" / "kch-super-mcp-studio.exe"
    bootstrap_command = runtime / "venv" / "Scripts" / "kch-codex-bootstrap-mcp.exe"
    preflight_command = runtime / "venv" / "Scripts" / "kch-codex-preflight-mcp.exe"
    if not command.is_file() or not bootstrap_command.is_file() or not preflight_command.is_file():
        raise FileNotFoundError("run INSTALL_KCH.cmd first")
    env = dict(os.environ)
    # The portable gate validates the native discovery contract without
    # borrowing availability from an independently installed Codex plugin.
    env.pop("KCH_NATIVE_PLUGIN_ROOT", None)
    env.pop("PLUGIN_ROOT", None)
    explicit_gate_state = os.environ.get("KCH_GATE_STATE_ROOT")
    gate_state = (
        Path(explicit_gate_state).resolve()
        if explicit_gate_state
        else runtime / "gate-runs" / f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    gate_state.mkdir(parents=True, exist_ok=False)
    if explicit_gate_state is None:
        atexit.register(shutil.rmtree, gate_state, ignore_errors=True)
    env.update(
        {
            "PYTHONUTF8": "1",
            "KCH_STUDIO_RUNTIME": str(gate_state),
            "KCH_MIS_ROOT": str(root / "mis"),
            "KCH_CONSTRUCT_STABLE_ROOT": str(root / "source" / "kch-studio"),
        }
    )
    preflight_process = subprocess.Popen(
        [str(preflight_command)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    try:
        preflight_initialized = rpc(
            preflight_process,
            {"jsonrpc": "2.0", "id": 91, "method": "initialize", "params": {}},
            label="codex_read_only_preflight_initialize",
            timeout_seconds=10,
        )
        preflight_listed = rpc(
            preflight_process,
            {"jsonrpc": "2.0", "id": 92, "method": "tools/list", "params": {}},
            label="codex_read_only_preflight_tools_list",
            timeout_seconds=10,
        )
    finally:
        if preflight_process.stdin:
            preflight_process.stdin.close()
        try:
            preflight_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            terminate_tree(preflight_process)
            preflight_process.wait(timeout=10)

    bootstrap_process = subprocess.Popen(
        [str(bootstrap_command)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    try:
        bootstrap_initialized = rpc(
            bootstrap_process,
            {"jsonrpc": "2.0", "id": 101, "method": "initialize", "params": {}},
            label="codex_bootstrap_initialize",
            timeout_seconds=10,
        )
        bootstrap_listed = rpc(
            bootstrap_process,
            {"jsonrpc": "2.0", "id": 102, "method": "tools/list", "params": {}},
            label="codex_bootstrap_tools_list",
            timeout_seconds=10,
        )
        bootstrap_status = rpc(
            bootstrap_process,
            {
                "jsonrpc": "2.0",
                "id": 103,
                "method": "tools/call",
                "params": {"name": "kch_bootstrap_status", "arguments": {}},
            },
            label="codex_bootstrap_status",
            timeout_seconds=10,
        )
        bootstrap_search = rpc(
            bootstrap_process,
            {
                "jsonrpc": "2.0",
                "id": 104,
                "method": "tools/call",
                "params": {
                    "name": "kch_catalog_search",
                    "arguments": {"query": "KwanDisk", "limit": 10},
                },
            },
            label="codex_bootstrap_native_catalog_search",
            timeout_seconds=20,
        )
        bootstrap_native = rpc(
            bootstrap_process,
            {
                "jsonrpc": "2.0",
                "id": 105,
                "method": "tools/call",
                "params": {"name": "kch_native_surface_status", "arguments": {}},
            },
            label="codex_bootstrap_native_surface_status",
            timeout_seconds=20,
        )
    finally:
        if bootstrap_process.stdin:
            bootstrap_process.stdin.close()
        try:
            bootstrap_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            terminate_tree(bootstrap_process)
            bootstrap_process.wait(timeout=10)

    process = subprocess.Popen(
        [str(command)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    try:
        initialized = rpc(
            process,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            label="initialize",
            timeout_seconds=60,
        )
        listed = rpc(
            process,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            label="tools_list",
            timeout_seconds=60,
        )
        resource_list = rpc(
            process,
            {"jsonrpc": "2.0", "id": 7, "method": "resources/list", "params": {}},
            label="resources_list",
            timeout_seconds=60,
        )
        status_resource_response = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "resources/read",
                "params": {"uri": "kch://super-mcp/status"},
            },
            label="resources_read_status",
            timeout_seconds=60,
        )
        ping = rpc(
            process,
            {"jsonrpc": "2.0", "id": 9, "method": "ping", "params": {}},
            label="ping",
            timeout_seconds=60,
        )
        status = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "kch_next_status", "arguments": {}},
            },
            label="kch_next_status",
            timeout_seconds=120,
        )
        preflight = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "kch_preflight", "arguments": {}},
            },
            label="kch_preflight",
            timeout_seconds=120,
        )
        workbench = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "workbench_status", "arguments": {}},
            },
            label="workbench_status",
            timeout_seconds=60,
        )
        mis = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "mis_historical_audit", "arguments": {}},
            },
            label="mis_historical_audit",
            timeout_seconds=180,
        )
    finally:
        if process.stdin:
            process.stdin.close()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            terminate_tree(process)
            process.wait(timeout=20)
    tools = listed["result"]["tools"]
    names = {item["name"] for item in tools}
    runtime_status = status["result"]["structuredContent"]
    canonical_preflight = preflight["result"]["structuredContent"]
    workbench_status = workbench["result"]["structuredContent"]
    audit = mis["result"]["structuredContent"]
    bootstrap_tools = bootstrap_listed["result"]["tools"]
    bootstrap_state = bootstrap_status["result"]["structuredContent"]
    bootstrap_search_state = bootstrap_search["result"]["structuredContent"]
    bootstrap_native_state = bootstrap_native["result"]["structuredContent"]
    preflight_tools = preflight_listed["result"]["tools"]
    resources = resource_list["result"]["resources"]
    resource_uris = {item["uri"] for item in resources}
    status_resource = json.loads(
        status_resource_response["result"]["contents"][0]["text"]
    )
    checks = {
        "codex_read_only_preflight_protocol": preflight_initialized.get("result", {}).get(
            "protocolVersion"
        )
        is not None,
        "codex_read_only_preflight_single_tool": len(preflight_tools) == 1
        and preflight_tools[0]["name"] == "kch_governed_preflight"
        and preflight_tools[0]["annotations"]["readOnlyHint"] is True,
        "codex_bootstrap_initialize_protocol": bootstrap_initialized.get("result", {}).get(
            "protocolVersion"
        )
        is not None,
        "codex_bootstrap_six_tool_surface": len(bootstrap_tools) == 6,
        "codex_bootstrap_advertises_six_tools": bootstrap_state[
            "advertised_tool_count"
        ]
        == 6,
        "codex_bootstrap_search_space_294_plus_5": bootstrap_search_state[
            "full_catalog_count"
        ]
        == 294
        and bootstrap_search_state["native_surface_count"] == 5
        and bootstrap_search_state["searchable_entry_count"] == 299,
        "codex_bootstrap_kwandisk_native_not_dispatchable": any(
            row.get("name") == "kwandisk"
            and row.get("kind") == "native_runtime"
            and row.get("dispatchable") is False
            and row.get("native_skill") == "kch-kwandisk"
            for row in bootstrap_search_state["matches"]
        ),
        "codex_bootstrap_native_reference_only": bootstrap_native_state[
            "plugin_root_observed"
        ]
        is False
        and bootstrap_native_state["all_observed_available"] is None
        and bootstrap_native_state["count"] == 5,
        "codex_bootstrap_native_not_imported_or_executed": bootstrap_native_state[
            "runtime_imported"
        ]
        is False
        and bootstrap_native_state["runtime_executed"] is False
        and bootstrap_native_state["authority_created"] is False,
        "codex_bootstrap_runtime_deferred": bootstrap_state["full_runtime_materialized"]
        is False,
        "initialize_protocol": initialized.get("result", {}).get("protocolVersion") is not None,
        "super_mcp_server_identity": initialized["result"]["serverInfo"] == {
            "name": "kch-super-mcp",
            "version": "0.3.16",
        },
        "super_mcp_resources_standard": resource_uris
        == {
            "kch://super-mcp/status",
            "kch://super-mcp/integration",
            "kch://super-mcp/preflight",
        },
        "super_mcp_status_boundary": status_resource["surfaceRole"]
        == "FEDERATED_DISCOVERY_AND_INVOCATION_NOT_GOVERNING_SYSTEM"
        and status_resource["storagePolicy"]["authoritativeStore"] == "GOOGLE_DRIVE"
        and status_resource["authorityInherited"] is False
        and status_resource["automaticPromotion"] is False,
        "super_mcp_ping": ping["result"] == {},
        "combined_tool_surface": len(tools) >= 247,
        "advanced_tools_present": {
            "constitution_effective",
            "checkpoint_estimate",
            "mis_exact_decide",
            "kwandata_ingest",
            "persistence_superchat_create",
            "lock_governor_status",
            "lock_change_propose",
            "lock_tool_call_propose",
            "lock_authorized_execute",
            "construct_file_write_propose",
        }
        <= names,
        "lock_authority_not_exposed_to_mcp": {
            "lock_user_enable",
            "lock_user_create",
            "lock_user_deactivate",
            "lock_user_authorize",
        }.isdisjoint(names),
        "constitutional_locks_default_off": runtime_status["components"]["locks"][
            "enabled"
        ]
        is False
        and runtime_status["components"]["locks"]["default_enabled"] is False
        and runtime_status["components"]["locks"]["session_wide_unlock_supported"]
        is False,
        "constitutional_lock_chain_pass": runtime_status["components"]["locks"][
            "integrity"
        ]["gate"]
        == "PASS",
        "launcher_running": runtime_status["background_launcher_running"] is True,
        "launcher_blind_spots_zero": runtime_status["capability_blind_spots"] == [],
        "strategic_surface_complete": runtime_status["strategic_surface_gate"] == "PASS",
        "canonical_preflight_pass": canonical_preflight["gate"] == "PASS"
        and canonical_preflight["canonical_entrypoint"]
        == "kch_studio.mcp_server:StudioMCP"
        and all(canonical_preflight["checks"].values()),
        "workbench_integrity_pass": workbench_status["integrity"]["gate"] == "PASS",
        "workbench_scheduler_bound": workbench_status["automatic_scheduler_binding"]["state"]
        == "DEFAULT_ENABLED_USER_CUSTOMIZABLE",
        "phl_authorized": runtime_status["phl_authorized"] is True,
        "phl_training_not_executed": runtime_status["phl_training_executed"] is False,
        "mis_480_records": audit["records"] == 480,
        "mis_60_ledgers": audit["persisted_ledgers_verified"] == 60,
        "mis_authority_false": audit["authority_created"] is False
        and audit["execution_authorized"] is False,
    }
    receipt = {
        "schema": "kch.portable-post-install-gate.v0.3.16",
        "gate": "PASS_BOUNDED" if all(checks.values()) else "FAIL",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "combined_tool_count": len(tools),
        "codex_bootstrap_tool_count": len(bootstrap_tools),
        "codex_bootstrap_searchable_entry_count": bootstrap_search_state[
            "searchable_entry_count"
        ],
        "codex_bootstrap_native_surface_count": bootstrap_native_state["count"],
        "codex_read_only_preflight_tool_count": len(preflight_tools),
        "super_mcp_resource_count": len(resources),
        "super_mcp_server_info": initialized["result"]["serverInfo"],
        "canonical_preflight": canonical_preflight,
        "workbench_integrity": workbench_status["integrity"],
        "mis_certificate_sha256": audit["certificate_sha256"],
        "wheel_hashes": {
            path.name: sha256(path) for path in sorted((root / "wheelhouse").glob("*.whl"))
        },
        "external_host_configuration_modified": False,
        "microphone_activated": False,
        "phl_authorized": True,
        "phl_training_executed": False,
        "phl_real_executed": False,
        "claim_ceiling": (
            "LOCAL_PORTABLE_INSTALLATION_STDIO_COMPOSITION_BOUNDED_MIS_REPLAY_"
            "AND_NATIVE_REFERENCE_DISCOVERY_WITHOUT_HOST_ACTIVATION"
        ),
    }
    target = runtime / "POST_INSTALL_GATE.json"
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["gate"] != "PASS_BOUNDED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
