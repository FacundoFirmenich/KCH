from __future__ import annotations

import json
import sys
from typing import Any, Callable

from .core import (
    CLAIM_RANK,
    CONSTRAINTS,
    ORIGINS,
    PROFILES,
    PURPOSE_PROFILE,
    RISK_FLOOR,
    SCOPES,
    VALID_ACTIONS,
    AUDIENCE_FLOOR,
    RigorError,
    adjudicate_action,
    audit_review,
    resolve_profile,
    transition_plan,
)

SERVER_NAME = "kch-rigor-gradient-governor"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-06-18"
STR = {"type": "string", "minLength": 1}
BOOL = {"type": "boolean"}


def obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


PROTOCOL = obj(
    {
        "protocol_id": STR,
        "scope": {"enum": sorted(SCOPES)},
        "origin": {"enum": sorted(ORIGINS)},
        "constraints": {"type": "array", "items": {"enum": sorted(CONSTRAINTS)}, "minItems": 1, "uniqueItems": True},
    },
    ["protocol_id", "scope", "origin", "constraints"],
)

TOOLS = (
    {
        "name": "kch.rigor.profile.resolve",
        "description": "Resolve a purpose-, audience- and risk-calibrated epistemic regime.",
        "inputSchema": obj(
            {
                "purpose": {"enum": sorted(PURPOSE_PROFILE)},
                "audience": {"enum": sorted(AUDIENCE_FLOOR)},
                "risk": {"enum": sorted(RISK_FLOOR)},
                "requested_profile": {"enum": sorted(PROFILES)},
            },
            ["purpose", "audience", "risk"],
        ),
    },
    {
        "name": "kch.rigor.action.adjudicate",
        "description": "Adjudicate research or generative latitude separately from claim authority.",
        "inputSchema": obj(
            {
                "profile_id": {"enum": sorted(PROFILES)},
                "action": {"enum": sorted(VALID_ACTIONS)},
                "requested_claim": {"enum": sorted(CLAIM_RANK)},
                "parent_frozen": BOOL,
                "after_results": BOOL,
                "explicit_user_authority": BOOL,
                "reversible": BOOL,
                "new_branch_id": {"type": "string"},
                "evidence_use": {"enum": ["NOT_APPLICABLE", "INSTRUMENT_TEST", "EMPIRICAL_EFFECT"]},
                "protocols": {"type": "array", "items": PROTOCOL},
            },
            ["profile_id", "action", "requested_claim", "parent_frozen", "after_results", "explicit_user_authority", "reversible", "evidence_use", "protocols"],
        ),
    },
    {
        "name": "kch.rigor.review.audit",
        "description": "Audit overclaiming, downward evidence distortion and claim/action conflation.",
        "inputSchema": obj(
            {
                "governing_purpose": {"enum": sorted(PURPOSE_PROFILE)},
                "observed_signal": BOOL,
                "confirmatory_authority": BOOL,
                "extension_requested": BOOL,
                "parent_preserved": BOOL,
                "new_branch_id": {"type": "string"},
                "protocol_gate_status": STR,
                "proposed_action_disposition": STR,
                "review_assertions": {"type": "array", "items": STR, "uniqueItems": True},
                "judgments_present": {"type": "array", "items": {"enum": ["FACT", "CLAIM", "ACTION"]}, "uniqueItems": True},
            },
            ["governing_purpose", "observed_signal", "confirmatory_authority", "extension_requested", "parent_preserved", "protocol_gate_status", "proposed_action_disposition", "review_assertions", "judgments_present"],
        ),
    },
    {
        "name": "kch.rigor.transition.plan",
        "description": "Plan a regime transition without mutating a frozen parent artifact.",
        "inputSchema": obj(
            {
                "from_profile": {"enum": sorted(PROFILES)},
                "to_profile": {"enum": sorted(PROFILES)},
                "trigger": STR,
                "parent_frozen": BOOL,
                "new_branch_id": {"type": "string"},
            },
            ["from_profile", "to_profile", "trigger", "parent_frozen"],
        ),
    },
)

HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "kch.rigor.profile.resolve": resolve_profile,
    "kch.rigor.action.adjudicate": adjudicate_action,
    "kch.rigor.review.audit": audit_review,
    "kch.rigor.transition.plan": transition_plan,
}


def handle(message: dict[str, Any]) -> dict[str, Any]:
    request_id = message.get("id")
    try:
        method = message.get("method")
        if method == "initialize":
            result = {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}}, "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}}
        elif method == "tools/list":
            result = {"tools": list(TOOLS)}
        elif method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            if name not in HANDLERS:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "unknown tool"}}
            payload = HANDLERS[name](params.get("arguments") or {})
            result = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, sort_keys=True)}], "isError": False}
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "unknown method"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except RigorError as exc:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32001, "message": str(exc)}}
    except Exception:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": "internal error"}}


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = handle(message)
        except Exception:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
