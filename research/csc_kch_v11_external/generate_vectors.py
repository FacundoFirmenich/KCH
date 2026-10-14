#!/usr/bin/env python3
from __future__ import annotations

import itertools
import json
from pathlib import Path


def milli(value: float) -> int:
    return int(round(value * 1000))


def support(request: dict) -> dict:
    workspace = (
        request["action_type"] == "TOOL_CALL"
        and request["resource"].startswith("kwan://workspace/")
        and request["effect_class"] == "E0_READ_ONLY"
        and request["risk"] <= 0.10
        and request["cost"] <= 0.10
    )
    liveops = (
        request["action_type"] == "DISPATCH_LOCAL_COMMAND"
        and request["resource"].startswith("liveops:zone:")
        and request["effect_class"] == "E1_REVERSIBLE_LOCAL"
        and request["risk"] <= 0.20
        and request["cost"] <= 0.20
        and request["context"]["severity"] == "NON_CRITICAL"
    )
    if workspace:
        return {"support": True, "reason": "RULE:workspace-read", "requested_decision": "APPLY", "authority_granted": False, "execution_granted": False}
    if liveops:
        return {"support": True, "reason": "RULE:liveops-noncritical-dispatch", "requested_decision": "APPLY", "authority_granted": False, "execution_granted": False}
    return {"support": False, "reason": "NO_MATCHING_RULE", "requested_decision": "DENY", "authority_granted": False, "execution_granted": False}


def main() -> None:
    vectors = []
    values = itertools.product(
        ("TOOL_CALL", "DISPATCH_LOCAL_COMMAND"),
        ("kwan://workspace/output", "liveops:zone:north_bar", "other://x"),
        ("E0_READ_ONLY", "E1_REVERSIBLE_LOCAL", "E3_IRREVERSIBLE"),
        (0.05, 0.25),
        (0.05, 0.25),
        ("IN_SCOPE", "UNKNOWN", "OUT_OF_SCOPE"),
        (True, False),
        (True, False),
        ("PRESENT", "SHADOW"),
        (True, False),
    )
    for index, row in enumerate(values):
        action_type, resource, effect, risk, cost, jurisdiction, cas, stable, plane, mandate = row
        request = {
            "action_type": action_type,
            "resource": resource,
            "effect_class": effect,
            "risk": risk,
            "cost": cost,
            "jurisdiction": jurisdiction,
            "cas_sufficient": cas,
            "cas_stable": stable,
            "plane": plane,
            "mandate_present": mandate,
            "context": {"severity": "NON_CRITICAL"},
        }
        rego_input = {
            **request,
            "risk_milli": milli(risk),
            "cost_milli": milli(cost),
            "authority_granted": False,
            "execution_granted": False,
        }
        cedar_request = {
            "principal": 'Principal::"candidate"',
            "action": 'Action::"support"',
            "resource": 'Resource::"candidate"',
            "context": {
                "action_type": action_type,
                "resource": resource,
                "effect_class": effect,
                "risk_milli": milli(risk),
                "cost_milli": milli(cost),
                "authority_granted": False,
                "execution_granted": False,
                "severity": "NON_CRITICAL",
            },
        }
        vectors.append({
            "vector_id": f"support_{index:05d}",
            "reference_request": request,
            "rego_input": rego_input,
            "cedar_request": cedar_request,
            "expected": support(request),
        })
    output = Path(__file__).resolve().parent / "PORTABLE_SUPPORT_VECTORS.json"
    output.write_text(json.dumps(vectors, indent=2), encoding="utf-8")
    print(json.dumps({"vectors": len(vectors), "supported": sum(v["expected"]["support"] for v in vectors), "path": str(output)}, indent=2))


if __name__ == "__main__":
    main()
