from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from kwancode_harness.gateway import Gateway
from kwancode_harness.mcp_server import MCPServer, TOOLS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.bundle_root.resolve()
    registry = root / "config" / "KCH_REGISTRY_v0.11.0.json"
    checks: list[dict[str, object]] = []

    def check(name: str, condition: bool, observed: object) -> None:
        checks.append({"check": name, "state": "PASS" if condition else "FAIL", "observed": observed})

    with tempfile.TemporaryDirectory() as directory:
        gateway = Gateway(Path(directory) / "state.sqlite3", registry, b"k" * 32, bundle_root=root)
        status = gateway.status()
        check("CANONICAL_IDENTITY", status["release"] == "KCH 0.11" and status["package_version"] == "0.11.0", {"release": status["release"], "version": status["package_version"]})
        check("CONTROL_COUNT", status["reflexive_controls"] == 28, status["reflexive_controls"])
        check("MCP_TOOL_COUNT", len(TOOLS) == 49, len(TOOLS))
        names = [tool["name"] for tool in TOOLS]
        check("DIRECT_CONTROL_TOOLS", len([name for name in names if name.startswith("kch.control.R")]) == 28, names)
        registry_audit = gateway.registry.audit_evidence(root)
        check("REGISTRY_EVIDENCE", registry_audit["totals"] == {"PASS": 19, "FAIL": 0, "UNAVAILABLE": 0}, registry_audit["totals"])
        component_status = gateway.adapters.component_status()
        check("SOVEREIGN_PACKAGES", component_status["available"] == 7 and component_status["unavailable"] == 0, component_status)
        phl = gateway.adapters.phl_projection()
        check("PHL_EFFECTIVE_STATE", phl.get("state") == "AVAILABLE" and phl.get("integrity", {}).get("gate") == "PASS", phl)
        sco = gateway.adapters.sco_projection()
        check("SCO_STATE", sco.get("state") == "AVAILABLE" and sco.get("integrity", {}).get("gate") == "PASS", sco)
        mis = gateway.adapters.mis_certificate_verify()
        check("MIS_CERTIFICATE", mis.get("state") == "AVAILABLE" and mis.get("verification", {}).get("valid") is True, mis)
        mcp = MCPServer(gateway)
        initialized = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        check("MCP_INITIALIZE", initialized.get("result", {}).get("serverInfo", {}).get("version") == "0.11.0", initialized)
        listed = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        check("MCP_LIST", len(listed.get("result", {}).get("tools", [])) == 49, len(listed.get("result", {}).get("tools", [])))
        check("LEDGER_INTEGRITY", gateway.ledger.verify()["gate"] == "PASS", gateway.ledger.verify())
        check("ENFORCED_PROHIBITED", status["enforced_profile"] == "PROHIBITED_UNTIL_GATES_PASS", status["enforced_profile"])

    gate = "PASS_KCH_0.11_LOCAL_BOUNDED" if all(row["state"] == "PASS" for row in checks) else "FAIL_KCH_0.11_LOCAL"
    result = {
        "schema": "kch.release-gate-result.v0.11.0",
        "release": "KCH 0.11",
        "gate": gate,
        "checks_passed": sum(row["state"] == "PASS" for row in checks),
        "checks_total": len(checks),
        "checks": checks,
        "claims_established": [
            "CANONICAL_PACKAGE_AND_MCP_IDENTITY",
            "28_INVOKABLE_CONTROL_CONTRACTS",
            "LOCAL_READ_ONLY_FEDERATED_COMPOSITION",
            "PORTABLE_REGISTRY_EVIDENCE_CUSTODY",
            "FAIL_CLOSED_MUTATING_AUTHORITY",
        ],
        "not_demonstrated": [
            "EFFECTIVENESS_OF_ALL_28_CONTROLS_IN_REAL_USE",
            "CAUSAL_KCH_IMPROVEMENT",
            "PAIRED_SHADOW_SUPERIORITY",
            "EXTERNAL_LINUX_REPLICATION",
            "TYPESCRIPT_CONFORMANCE_FOR_0.11",
            "ENFORCED_PROFILE_SAFETY",
            "LIVE_CROSS_PROVIDER_DISPATCH",
            "COMPLETE_KWANFORKS",
            "CSI_17_OF_17",
            "MIS_LUNA_ESTIMABILITY",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate": gate, "checks": f"{result['checks_passed']}/{result['checks_total']}"}))
    return 0 if gate.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
