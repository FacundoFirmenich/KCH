from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


DEPLOYMENT = Path(__file__).resolve().parents[1]
PROJECT = DEPLOYMENT.parents[1]
BUNDLE = DEPLOYMENT / "bundle"
RESULT = DEPLOYMENT / "results" / "KCH_0.11_REAL_SHADOW_DEPLOYMENT_GATE_RESULT.json"
LAUNCHER = DEPLOYMENT / "run_kch_011.ps1"
PYTHON_LAUNCHER = DEPLOYMENT / "run_kch_011.py"
OBJECTIVE = DEPLOYMENT / "OBJECTIVE_CONTRACT_KCH_0.11_REAL_SHADOW_DEPLOYMENT_v0.1.0.json"
PHL_FREEZE = DEPLOYMENT / "PHL_REAL_SESSION_FREEZE_v0.1.0.json"
PHL_STATE = BUNDLE / "evidence" / "KCH_CURRENT_INTEGRATION_STATE_v0.6.0.sqlite3"
CANONICAL_ZIP = PROJECT / "outputs" / "KCH_0.11_CANONICAL_MACRORELEASE.zip"
PROJECT_CONFIG = PROJECT / ".codex" / "config.toml"
POWERSHELL = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
PYTHON = Path(r"C:\Python314\python.exe")
JURISDICTION = "LOCAL_CODEX_PROJECT_AGENT_SHADOW"
PROJECT_ID = "KCH_PRE2G_CONTINUACION_INTEGRAL"
OBJECTIVE_ID = "KCH_0.11_REAL_SHADOW_DEPLOYMENT_GATE"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class MCPClient:
    def __init__(self) -> None:
        self.process = subprocess.Popen(
            [
                str(PYTHON),
                "-X",
                "utf8",
                "-u",
                str(PYTHON_LAUNCHER),
            ],
            cwd=DEPLOYMENT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self.request_id = 0

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("MCP process pipes are unavailable")
        self.request_id += 1
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": self.request_id, "method": method}
        if params is not None:
            message["params"] = params
        self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"MCP process ended without a response; exit={self.process.poll()}; stderr={stderr}")
        response = json.loads(line)
        if response.get("id") != self.request_id:
            raise RuntimeError(f"MCP response id mismatch: {response.get('id')} != {self.request_id}")
        if "error" in response:
            raise RuntimeError(f"MCP {method} error: {response['error']}")
        return response["result"]

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        if self.process.stdin is None:
            raise RuntimeError("MCP process stdin is unavailable")
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        if result.get("isError") is not False:
            raise RuntimeError(f"MCP tool returned an error state: {name}")
        content = result.get("content")
        if not isinstance(content, list) or len(content) != 1 or content[0].get("type") != "text":
            raise RuntimeError(f"MCP tool returned an invalid content envelope: {name}")
        return json.loads(content[0]["text"])

    def close(self) -> dict[str, Any]:
        if self.process.stdin:
            self.process.stdin.close()
        try:
            return_code = self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            return_code = self.process.wait(timeout=10)
        stderr = self.process.stderr.read() if self.process.stderr else ""
        return {"return_code": return_code, "stderr": stderr}


def check(condition: bool, label: str, assertions: list[dict[str, Any]], observed: Any = None) -> None:
    assertions.append({"assertion": label, "pass": bool(condition), "observed": observed})
    if not condition:
        raise AssertionError(f"gate assertion failed: {label}; observed={observed!r}")


def main() -> int:
    started = utc_now()
    assertions: list[dict[str, Any]] = []
    payload: dict[str, Any] = {
        "schema": "kch.real-shadow-deployment-gate-result.v0.1.0",
        "release": "KCH 0.11",
        "started_at": started,
        "gate": "RUNNING",
        "profile": "agent-shadow",
        "jurisdiction": JURISDICTION,
        "phl_real_session": "PROHIBITED_AND_NOT_RUN",
        "pre_gate_adverse_observations": [
            {
                "state": "REPAIRED_BEFORE_SERVER_START",
                "defect": "Windows PowerShell 5 lacks static RandomNumberGenerator.GetBytes(int)",
                "consequence": "first launcher probe stopped before MCP initialization",
            },
            {
                "state": "REPAIRED_BEFORE_SERVER_START",
                "defect": "Windows PowerShell 5 lacks Convert.ToHexString(byte[])",
                "consequence": "second launcher probe stopped before MCP initialization",
            },
            {
                "state": "REPAIRED_OBSERVER_ASSERTION",
                "defect": "first full gate expected a synthetic top-level registry audit gate field instead of evaluating the returned totals contract",
                "consequence": "observer stopped after MCP handshake and a real 19 PASS, 0 FAIL, 0 UNAVAILABLE registry audit; no governed KCH session had been opened",
            },
            {
                "state": "PROVISIONAL_LOCALIZATION_SUPERSEDED",
                "defect": "Windows PowerShell native-pipeline transcoding was initially suspected after autorización arrived as autorizaci\\ufffdn",
                "consequence": "KCH correctly emitted CONTROL_RECEIPT_INTEGRITY_FAILURE and BLOCK; direct Python reproduction showed the deeper cause was the Python Windows stdio encoding",
            },
            {
                "state": "REPAIRED_AND_PRESERVED_FAIL_CLOSED_BLOCK",
                "defect": "Python emitted MCP JSON in Windows CP1252 (byte F3) instead of UTF-8 (bytes C3 B3)",
                "consequence": "active bootstrap now forces Python UTF-8 mode and reconfigures stdin/stdout defensively",
            },
            {
                "state": "REPAIRED_OBSERVER_ASSERTION_AFTER_SUCCESSFUL_EXECUTION",
                "defect": "observer expected ledger integrity inside audit.export although the API exposes it through status.ledger",
                "consequence": "the attempt had already completed ALLOW_READ_ONLY execution, ALLOW_SHADOW_PRECOMMIT and outcome registration; final observer now verifies both the status ledger gate and audit export content hash",
            },
        ],
    }
    client: MCPClient | None = None
    phl_hash_before = sha256_file(PHL_STATE)
    try:
        required_files = [PYTHON_LAUNCHER, OBJECTIVE, PHL_FREEZE, PHL_STATE, CANONICAL_ZIP, PROJECT_CONFIG]
        check(all(path.is_file() for path in required_files), "ALL_DEPLOYMENT_INPUTS_EXIST", assertions, [str(path) for path in required_files])

        import tomllib

        with PROJECT_CONFIG.open("rb") as stream:
            parsed_config = tomllib.load(stream)
        server_config = parsed_config.get("mcp_servers", {}).get("kch_0_11", {})
        check(server_config.get("enabled") is True, "PROJECT_MCP_CONFIG_ENABLED", assertions, server_config)
        check(server_config.get("required") is True, "PROJECT_MCP_CONFIG_REQUIRED", assertions, server_config)

        hashes = {
            "canonical_zip_sha256": sha256_file(CANONICAL_ZIP),
            "objective_contract_sha256": sha256_file(OBJECTIVE),
            "project_mcp_config_sha256": sha256_file(PROJECT_CONFIG),
            "phl_freeze_sha256": sha256_file(PHL_FREEZE),
            "phl_state_before_sha256": phl_hash_before,
        }
        check(
            hashes["canonical_zip_sha256"] == "a4e08bb2833dffbfe3a3f2036579d1c8e56c20ea67ec94d4685a3618d528ee02",
            "CANONICAL_ZIP_HASH_EXACT",
            assertions,
            hashes["canonical_zip_sha256"],
        )

        client = MCPClient()
        initialized = client.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "kch-0.11-real-shadow-gate", "version": "0.1.0"},
            },
        )
        client.notify("notifications/initialized")
        tools = client.request("tools/list")["tools"]
        resources = client.request("resources/list")["resources"]
        tool_names = [tool["name"] for tool in tools]
        control_names = [name for name in tool_names if name.startswith("kch.control.R")]
        check(initialized["serverInfo"] == {"name": "kwancode-harness", "version": "0.11.0"}, "MCP_SERVER_IDENTITY_EXACT", assertions, initialized)
        check(initialized["protocolVersion"] == "2025-06-18", "MCP_PROTOCOL_NEGOTIATED", assertions, initialized["protocolVersion"])
        check(len(tool_names) == 49, "MCP_EXACTLY_49_TOOLS", assertions, len(tool_names))
        check(len(control_names) == 28, "MCP_EXACTLY_28_DIRECT_CONTROLS", assertions, len(control_names))
        check(len(resources) == 4, "MCP_EXACTLY_4_RESOURCES", assertions, len(resources))

        prohibited_phl_tools = sorted(
            name
            for name in tool_names
            if any(token in name.lower() for token in ("phl.start", "start_phl", "phl.feedback", "phl.close", "phl.commit"))
        )
        check(not prohibited_phl_tools, "NO_PHL_MUTATION_TOOL_EXPOSED", assertions, prohibited_phl_tools)

        status = client.call("kch.super.status")
        check(status["profile"] == "agent-shadow", "AGENT_SHADOW_PROFILE_ACTIVE", assertions, status["profile"])
        check(status["mutating_execution_authorized"] is False, "MUTATING_EXECUTION_NOT_AUTHORIZED", assertions, status["mutating_execution_authorized"])
        check(status["enforced_profile"] == "PROHIBITED_UNTIL_GATES_PASS", "ENFORCED_PROFILE_PROHIBITED", assertions, status["enforced_profile"])

        registry_audit = client.call("kch.super.registry.evidence.audit")
        component_status_direct = client.call("kch.component.status")
        phl_before = client.call("kch.phl.projection")
        sco_projection = client.call("kch.sco.projection")
        mis_verification = client.call("kch.mis.certificate.verify")
        component_probes = {
            "kwanprompts": client.call("kch.kwanprompts.probe"),
            "rgg": client.call("kch.rgg.probe"),
            "obl_phl": client.call("kch.obl_phl.probe"),
        }
        registry_totals = registry_audit.get("totals", {})
        check(
            registry_totals.get("PASS") == len(registry_audit.get("rows", []))
            and registry_totals.get("FAIL") == 0
            and registry_totals.get("UNAVAILABLE") == 0,
            "REGISTRY_EVIDENCE_AUDIT_PASS",
            assertions,
            registry_totals,
        )
        check(component_status_direct.get("available") == 7 and component_status_direct.get("unavailable") == 0, "SEVEN_FEDERATED_COMPONENT_PACKAGES_AVAILABLE", assertions, component_status_direct)
        check(phl_before.get("state") == "AVAILABLE", "PHL_PROJECTION_AVAILABLE_READ_ONLY", assertions, phl_before.get("state"))
        check(phl_before["integrity"].get("gate") == "PASS", "PHL_EXISTING_LEDGER_INTEGRITY_PASS", assertions, phl_before["integrity"])
        check(phl_before["projection"].get("feedback") == 0, "PHL_ZERO_REAL_USER_FEEDBACK_BEFORE", assertions, phl_before["projection"].get("feedback"))
        check(phl_before["projection"].get("active_phl_session_id") is None, "PHL_NO_ACTIVE_SESSION_BEFORE", assertions, phl_before["projection"].get("active_phl_session_id"))
        check(sco_projection.get("state") == "AVAILABLE", "SCO_PROJECTION_AVAILABLE", assertions, sco_projection.get("state"))
        check(mis_verification.get("state") == "AVAILABLE", "MIS_CERTIFICATE_ADAPTER_AVAILABLE", assertions, mis_verification.get("state"))
        check(all(row.get("state") == "AVAILABLE" for row in component_probes.values()), "KWANPROMPTS_RGG_OBL_PHL_PROBES_AVAILABLE", assertions, component_probes)

        for resource in resources:
            read = client.request("resources/read", {"uri": resource["uri"]})
            check(bool(read.get("contents")), f"RESOURCE_READ_{resource['uri']}", assertions, len(read.get("contents", [])))

        controls = client.call(
            "kch.super.context.compile",
            {
                "controls": {
                    "R01": {"governing_objective_id": OBJECTIVE_ID, "candidate_objective_id": OBJECTIVE_ID},
                    "R02": {
                        "source_project_id": PROJECT_ID,
                        "target_project_id": PROJECT_ID,
                        "transfer_contract_verified": True,
                        "authority_inherited": False,
                    },
                    "R03": {
                        "requested_authority": ["READ"],
                        "granted_authority": ["READ", "REGISTER_EVIDENCE", "APPEND_LEDGER"],
                        "action_classified": True,
                    },
                    "R27": {"transport_complete": True, "unit_failures": []},
                    "R28": {"evidence_available": True, "authority_after_loss": "SHADOW"},
                }
            },
        )
        check(controls["composition_state"] == "PASS", "FIVE_ACTUAL_CONTROLS_COMPOSE_TO_PASS", assertions, controls["verdict_counts"])

        session_id = "KCH011-DEPLOY-" + str(uuid4())
        session = client.call(
            "kch.super.session.open",
            {
                "session_id": session_id,
                "actor": "USER",
                "objective_id": OBJECTIVE_ID,
                "objective_contract_sha256": hashes["objective_contract_sha256"],
                "project_id": PROJECT_ID,
                "jurisdiction": JURISDICTION,
                "authority_granted": ["READ", "REGISTER_EVIDENCE", "APPEND_LEDGER"],
                "stop_condition_ids": [
                    "STOP_ON_MUTATING_ROUTE",
                    "STOP_ON_ENFORCED_PROFILE",
                    "STOP_ON_PHL_REAL_SESSION_OR_FEEDBACK",
                    "STOP_ON_EVIDENCE_HASH_DIVERGENCE",
                ],
                "expected_evidence_ids": ["KCH011_CANONICAL_ZIP", "PROJECT_MCP_CONFIG", "PHL_REAL_SESSION_FREEZE"],
                "ttl_seconds": 1800,
            },
        )

        evidence_specs = {
            "KCH011_CANONICAL_ZIP": (hashes["canonical_zip_sha256"], "DIRECT", ["KCH_0.11_RELEASE_SEAL"]),
            "PROJECT_MCP_CONFIG": (hashes["project_mcp_config_sha256"], "EXECUTION", ["OPENAI_CODEX_PROJECT_MCP_CONFIG"]),
            "PHL_REAL_SESSION_FREEZE": (hashes["phl_freeze_sha256"], "DIRECT", ["USER_DIRECTIVE_2026-08-09"]),
        }
        admitted: dict[str, Any] = {}
        for evidence_id, (source_hash, role, provenance_ids) in evidence_specs.items():
            admitted[evidence_id] = client.call(
                "kch.super.evidence.admit",
                {
                    "session_id": session_id,
                    "evidence_id": evidence_id,
                    "source_sha256": source_hash,
                    "jurisdiction": JURISDICTION,
                    "role": role,
                    "provenance_ids": provenance_ids,
                    "capability": session["evidence_capabilities"][evidence_id],
                },
            )
        check(all(row.get("admitted") is True for row in admitted.values()), "ALL_PREREGISTERED_EVIDENCE_ADMITTED", assertions, list(admitted))

        proposal = client.call(
            "kch.super.action.propose",
            {
                "session_id": session_id,
                "route": "kch.component.status",
                "action_class": "READ_ONLY",
                "requested_authority": ["READ"],
                "evidence_ids": list(evidence_specs),
                "arguments": {},
                "capability": session["proposal_capability"],
                "ttl_seconds": 1800,
            },
        )
        authorization = client.call(
            "kch.super.action.authorize",
            {
                "session_id": session_id,
                "proposal_id": proposal["proposal"]["proposal_id"],
                "control_receipts": controls["receipts"],
                "capability": proposal["authorization_capability"],
                "ttl_seconds": 1800,
            },
        )
        check(authorization["decision"] == "ALLOW_READ_ONLY", "ACTION_AUTHORIZED_READ_ONLY", assertions, authorization["decision"])
        execution = client.call(
            "kch.super.action.execute",
            {
                "session_id": session_id,
                "proposal_id": proposal["proposal"]["proposal_id"],
                "capability": authorization["execution_capability"],
            },
        )
        check(execution.get("executed") is True and execution.get("execution_class") == "READ_ONLY", "GOVERNED_ACTION_EXECUTED_READ_ONLY", assertions, execution)

        precommit = client.call(
            "kch.super.precommit.verify",
            {
                "session_id": session_id,
                "objective_contract_sha256": hashes["objective_contract_sha256"],
                "jurisdiction": JURISDICTION,
                "evidence_ids": list(evidence_specs),
                "candidate_artifact_sha256": hashes["project_mcp_config_sha256"],
                "observed_artifact_sha256": sha256_file(PROJECT_CONFIG),
                "external_observer_verdict": "PASS",
                "capability": session["precommit_capability"],
            },
        )
        check(precommit["decision"] == "ALLOW_SHADOW_PRECOMMIT", "SHADOW_PRECOMMIT_ALLOWED", assertions, precommit)

        outcome = client.call(
            "kch.super.outcome.register",
            {
                "session_id": session_id,
                "outcome_id": "KCH_0.11_PROJECT_SCOPED_AGENT_SHADOW_DEPLOYMENT",
                "state": "PASS_BOUNDED_REAL_MCP_SHADOW_DEPLOYMENT_NO_PHL_SESSION",
                "evidence_ids": list(evidence_specs),
                "adverse": False,
                "interpretation": "The sealed KCH 0.11 MCP initialized and governed one real local read-only action; this establishes bounded project-scoped shadow execution only and excludes PHL real use, enforced governance, mutation, production, and outcome superiority.",
                "capability": session["outcome_capability"],
            },
        )

        audit = client.call("kch.super.audit.export")
        status_after = client.call("kch.super.status")
        phl_after = client.call("kch.phl.projection")
        phl_hash_after = sha256_file(PHL_STATE)
        check(status_after["ledger"].get("gate") == "PASS", "KCH_APPEND_ONLY_LEDGER_INTEGRITY_PASS", assertions, status_after["ledger"])
        audit_core = {key: value for key, value in audit.items() if key != "export_sha256"}
        check(audit.get("export_sha256") == sha256_json(audit_core), "KCH_AUDIT_EXPORT_HASH_EXACT", assertions, audit.get("export_sha256"))
        check(phl_hash_after == phl_hash_before, "PHL_SOURCE_BYTES_UNCHANGED", assertions, {"before": phl_hash_before, "after": phl_hash_after})
        check(phl_after["projection"].get("feedback") == 0, "PHL_ZERO_REAL_USER_FEEDBACK_AFTER", assertions, phl_after["projection"].get("feedback"))
        check(phl_after["projection"].get("active_phl_session_id") is None, "PHL_NO_ACTIVE_SESSION_AFTER", assertions, phl_after["projection"].get("active_phl_session_id"))
        check(phl_after["projection"].get("head_hash") == phl_before["projection"].get("head_hash"), "PHL_LEDGER_HEAD_UNCHANGED", assertions, phl_after["projection"].get("head_hash"))

        payload.update(
            {
                "gate": "PASS",
                "completed_at": utc_now(),
                "hashes": {**hashes, "phl_state_after_sha256": phl_hash_after},
                "mcp": {
                    "initialize": initialized,
                    "tool_count": len(tool_names),
                    "direct_control_count": len(control_names),
                    "resource_count": len(resources),
                    "tool_names": tool_names,
                    "resources": resources,
                },
                "direct_read_only_surfaces": {
                    "status": status,
                    "registry_evidence_audit": registry_audit,
                    "component_status": component_status_direct,
                    "phl_before": phl_before,
                    "phl_after": phl_after,
                    "sco_projection": sco_projection,
                    "mis_verification": mis_verification,
                    "component_probes": component_probes,
                },
                "governed_execution": {
                    "session": session["session"],
                    "session_contract_sha256": session["session_contract_sha256"],
                    "controls": controls,
                    "admitted_evidence": admitted,
                    "proposal": proposal["proposal"],
                    "proposal_sha256": proposal["proposal_sha256"],
                    "authorization": {key: value for key, value in authorization.items() if key != "execution_capability"},
                    "execution": execution,
                    "precommit": precommit,
                    "outcome": outcome,
                    "audit": audit,
                    "status_after": status_after,
                },
                "assertions": assertions,
                "claim_ceiling": "REAL_LOCAL_PROJECT_SCOPED_MCP_DEPLOYMENT_AND_BOUNDED_AGENT_SHADOW_EXECUTION_WITHOUT_PHL_REAL_USE",
                "not_demonstrated": [
                    "PRODUCTION_DEPLOYMENT",
                    "MUTATING_EXECUTION",
                    "ENFORCED_GOVERNANCE",
                    "ALL_28_CONTROLS_EFFECTIVE_IN_REAL_USE",
                    "PHL_REAL_USER_SESSION_OR_LEARNING",
                    "CROSS_PROVIDER_LIVE_ORCHESTRATION",
                    "EXTERNAL_INDEPENDENT_LAB_VALIDATION",
                ],
            }
        )
        return_code = 0
    except Exception as exc:
        payload.update(
            {
                "gate": "FAIL",
                "completed_at": utc_now(),
                "failure": {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()},
                "assertions": assertions,
                "phl_state_before_sha256": phl_hash_before,
                "phl_state_after_sha256": sha256_file(PHL_STATE) if PHL_STATE.is_file() else None,
            }
        )
        return_code = 1
    finally:
        if client is not None:
            payload["mcp_process"] = client.close()
        RESULT.parent.mkdir(parents=True, exist_ok=True)
        RESULT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"gate": payload["gate"], "result": str(RESULT), "assertions": len(assertions)}, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
