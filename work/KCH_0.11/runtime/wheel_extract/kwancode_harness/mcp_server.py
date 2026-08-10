from __future__ import annotations

import json
import os
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any

from .controls import CONTROL_CATALOG, evaluate_control
from .gateway import CapabilityError, Gateway

SERVER_NAME = "kwancode-harness"
SERVER_VERSION = "0.11.0"
PROTOCOL_VERSION = "2025-06-18"


def obj(properties: dict[str, Any], required: list[str], *, extra: bool = False) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": extra}


STR = {"type": "string", "minLength": 1}
SHA = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
STRINGS = {"type": "array", "items": STR, "uniqueItems": True}
BOOL = {"type": "boolean"}
INTEGER = {"type": "integer"}
ARRAY = {"type": "array"}
OBJECT = {"type": "object"}

FIELD_SCHEMAS: dict[str, dict[str, Any]] = {
    "transfer_contract_verified": BOOL, "authority_inherited": BOOL, "action_classified": BOOL,
    "external_observer": BOOL, "observer_independence_verified": BOOL, "probe_applicable": BOOL,
    "probe_executed": BOOL, "boundary_explicit": BOOL, "commercial_readiness_claimed": BOOL,
    "collision_free": BOOL, "human_interrupt_pending": BOOL, "decision_equivalent": BOOL,
    "evidence_contract_equivalent": BOOL, "metric_discriminates": BOOL, "transport_complete": BOOL,
    "evidence_available": BOOL,
    "token_budget": INTEGER, "fanout_budget": INTEGER, "projected_tokens": INTEGER,
    "projected_fanout": INTEGER, "sample_count": INTEGER, "unique_values": INTEGER,
    "requested_authority": STRINGS, "granted_authority": STRINGS, "planned_artifacts": STRINGS,
    "necessary_artifacts": STRINGS, "contamination_hits": ARRAY, "corrections": ARRAY,
    "claims": ARRAY, "options": ARRAY, "adverse_results": ARRAY, "repairs": ARRAY,
    "unit_failures": ARRAY,
    "handoff": OBJECT, "evidence_roles": OBJECT, "readiness_evidence": OBJECT,
}


def control_tool(control_id: str) -> dict[str, Any]:
    control = CONTROL_CATALOG[control_id]
    properties = {field: FIELD_SCHEMAS.get(field, STR) for field in control.required_fields}
    optional = {
        "transfer_conditions": ARRAY,
        "redundancy_justification": STR,
    }
    properties.update(optional)
    return {
        "name": "kch.control." + control_id,
        "description": control.name + ". Returns a signed-by-content governance receipt; never creates authority.",
        "inputSchema": obj(properties, list(control.required_fields), extra=False),
    }


BASE_TOOLS = [
    {"name": "kch.super.status", "description": "Return KCH 0.11 runtime, profile, ledger, component and claim-boundary status.", "inputSchema": obj({}, [])},
    {"name": "kch.super.registry", "description": "Return the canonical KCH 0.11 federated registry without merging service authority.", "inputSchema": obj({}, [])},
    {"name": "kch.super.controls", "description": "Return the exact catalog of 28 reflexive controls and evidence ceiling.", "inputSchema": obj({}, [])},
    {
        "name": "kch.super.session.open", "description": "Open a governed session and issue one-use objective-bound capabilities.",
        "inputSchema": obj({"session_id": STR, "actor": {"enum": ["USER", "SYSTEM_AUTHORITY"]}, "objective_id": STR, "objective_contract_sha256": SHA, "project_id": STR, "jurisdiction": STR, "authority_granted": STRINGS, "stop_condition_ids": STRINGS, "expected_evidence_ids": STRINGS, "ttl_seconds": {"type": "integer", "minimum": 1, "maximum": 3600}}, ["session_id", "actor", "objective_id", "objective_contract_sha256", "project_id", "jurisdiction", "authority_granted", "stop_condition_ids", "expected_evidence_ids"]),
    },
    {
        "name": "kch.super.evidence.admit", "description": "Admit one preregistered evidence record with explicit role, provenance and jurisdiction.",
        "inputSchema": obj({"session_id": STR, "evidence_id": STR, "source_sha256": SHA, "jurisdiction": STR, "role": {"enum": ["DIRECT", "DERIVED", "TRANSPORT", "EXECUTION", "OUTCOME"]}, "provenance_ids": STRINGS, "capability": STR}, ["session_id", "evidence_id", "source_sha256", "jurisdiction", "role", "provenance_ids", "capability"]),
    },
    {
        "name": "kch.super.context.compile", "description": "Evaluate an explicit subset of R01-R28 and compose their receipts without creating authority.",
        "inputSchema": obj({"controls": {"type": "object", "minProperties": 1, "additionalProperties": {"type": "object"}}}, ["controls"]),
    },
    {
        "name": "kch.super.action.propose", "description": "Record a governed action proposal; proposal is not authorization.",
        "inputSchema": obj({"session_id": STR, "route": STR, "action_class": {"enum": ["READ_ONLY", "MUTATING"]}, "requested_authority": STRINGS, "evidence_ids": STRINGS, "arguments": OBJECT, "capability": STR, "ttl_seconds": {"type": "integer", "minimum": 1, "maximum": 3600}}, ["session_id", "route", "action_class", "requested_authority", "evidence_ids", "arguments", "capability"]),
    },
    {
        "name": "kch.super.action.authorize", "description": "Authorize only evidence-complete read-only proposals; mutating execution remains unavailable.",
        "inputSchema": obj({"session_id": STR, "proposal_id": STR, "control_receipts": {"type": "array", "minItems": 1, "items": OBJECT}, "capability": STR, "ttl_seconds": {"type": "integer", "minimum": 1, "maximum": 3600}}, ["session_id", "proposal_id", "control_receipts", "capability"]),
    },
    {
        "name": "kch.super.action.execute", "description": "Execute a one-use authorized read-only federated route. Mutating routes are prohibited in KCH 0.11.",
        "inputSchema": obj({"session_id": STR, "proposal_id": STR, "capability": STR}, ["session_id", "proposal_id", "capability"]),
    },
    {
        "name": "kch.super.precommit.verify", "description": "Verify objective, jurisdiction, evidence, artifact identity and external observer before shadow precommit.",
        "inputSchema": obj({"session_id": STR, "objective_contract_sha256": SHA, "jurisdiction": STR, "evidence_ids": STRINGS, "candidate_artifact_sha256": SHA, "observed_artifact_sha256": SHA, "external_observer_verdict": {"enum": ["PASS", "BLOCK", "UNAVAILABLE"]}, "capability": STR}, ["session_id", "objective_contract_sha256", "jurisdiction", "evidence_ids", "candidate_artifact_sha256", "observed_artifact_sha256", "external_observer_verdict", "capability"]),
    },
    {
        "name": "kch.super.rollback", "description": "Append an immutable compensating rollback record; it never rewrites history or silently mutates files.",
        "inputSchema": obj({"session_id": STR, "target_event_hash": SHA, "reason": STR, "human_authorized": BOOL, "capability": STR}, ["session_id", "target_event_hash", "reason", "human_authorized", "capability"]),
    },
    {
        "name": "kch.super.outcome.register", "description": "Register an outcome, including adverse results, without rewriting historical evidence.",
        "inputSchema": obj({"session_id": STR, "outcome_id": STR, "state": STR, "evidence_ids": STRINGS, "adverse": BOOL, "interpretation": STR, "capability": STR}, ["session_id", "outcome_id", "state", "evidence_ids", "adverse", "interpretation", "capability"]),
    },
    {"name": "kch.super.audit.export", "description": "Export the append-only KCH 0.11 event chain and content hash.", "inputSchema": obj({}, [])},
    {"name": "kch.super.registry.evidence.audit", "description": "Rehash the portable evidence copies referenced by the registry.", "inputSchema": obj({}, [])},
    {"name": "kch.component.status", "description": "Probe installed sovereign component distributions without invoking mutations.", "inputSchema": obj({}, [])},
    {"name": "kch.phl.projection", "description": "Read and verify the effectively integrated PHL/KCH state projection.", "inputSchema": obj({}, [])},
    {"name": "kch.sco.projection", "description": "Read and verify an SCO graph projection while preserving chat sovereignty.", "inputSchema": obj({"sco_id": STR}, [])},
    {"name": "kch.mis.certificate.verify", "description": "Verify the sealed MIS v0.3.1 historical integration certificate; creates no KCH authority.", "inputSchema": obj({}, [])},
    {"name": "kch.kwanprompts.probe", "description": "Probe KwanPrompts package availability only.", "inputSchema": obj({}, [])},
    {"name": "kch.rgg.probe", "description": "Probe Rigor Gradient Governor package availability only.", "inputSchema": obj({}, [])},
    {"name": "kch.obl_phl.probe", "description": "Probe OBL/PHL learning package availability only.", "inputSchema": obj({}, [])},
]

TOOLS = tuple(BASE_TOOLS + [control_tool(control_id) for control_id in sorted(CONTROL_CATALOG)])

RESOURCES = (
    {"uri": "kch://registry/current", "name": "KCH 0.11 canonical federated registry", "mimeType": "application/json"},
    {"uri": "kch://controls/28", "name": "KCH 0.11 reflexive control catalog", "mimeType": "application/json"},
    {"uri": "kch://status/current", "name": "KCH 0.11 runtime status", "mimeType": "application/json"},
    {"uri": "kch://audit/current", "name": "KCH 0.11 append-only audit export", "mimeType": "application/json"},
)


class MCPServer:
    def __init__(self, gateway: Gateway):
        self.gateway = gateway
        self.handlers = {
            "kch.super.status": lambda _: gateway.status(),
            "kch.super.registry": lambda _: gateway.registry.describe(),
            "kch.super.controls": lambda _: gateway.control_catalog(),
            "kch.super.session.open": gateway.open_session,
            "kch.super.evidence.admit": gateway.admit_evidence,
            "kch.super.context.compile": gateway.compile_context,
            "kch.super.action.propose": gateway.propose_action,
            "kch.super.action.authorize": gateway.authorize_action,
            "kch.super.action.execute": gateway.execute_action,
            "kch.super.precommit.verify": gateway.precommit_verify,
            "kch.super.rollback": gateway.record_rollback,
            "kch.super.outcome.register": gateway.register_outcome,
            "kch.super.audit.export": lambda _: gateway.audit_export(),
            "kch.super.registry.evidence.audit": lambda _: gateway.registry.audit_evidence(gateway.adapters.bundle_root),
            "kch.component.status": lambda _: gateway.adapters.component_status(),
            "kch.phl.projection": lambda _: gateway.adapters.phl_projection(),
            "kch.sco.projection": lambda value: gateway.adapters.sco_projection(value.get("sco_id")),
            "kch.mis.certificate.verify": lambda _: gateway.adapters.mis_certificate_verify(),
            "kch.kwanprompts.probe": lambda _: gateway.adapters.probe_module("KWANPROMPTS"),
            "kch.rgg.probe": lambda _: gateway.adapters.probe_module("RGG"),
            "kch.obl_phl.probe": lambda _: gateway.adapters.probe_module("OBL_PHL"),
        }
        for control_id in CONTROL_CATALOG:
            self.handlers["kch.control." + control_id] = lambda value, cid=control_id: evaluate_control(cid, value)

    def _resource(self, uri: str) -> dict[str, Any]:
        values = {
            "kch://registry/current": self.gateway.registry.describe,
            "kch://controls/28": self.gateway.control_catalog,
            "kch://status/current": self.gateway.status,
            "kch://audit/current": self.gateway.audit_export,
        }
        if uri not in values:
            raise ValueError("unknown resource URI")
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(values[uri](), ensure_ascii=False, sort_keys=True)}]}

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if message.get("method") == "notifications/initialized":
            return None
        request_id = message.get("id")
        method = message.get("method")
        try:
            if method == "initialize":
                result = {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}, "resources": {}}, "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}}
            elif method == "tools/list":
                result = {"tools": list(TOOLS)}
            elif method == "resources/list":
                result = {"resources": list(RESOURCES)}
            elif method == "resources/read":
                result = self._resource((message.get("params") or {}).get("uri", ""))
            elif method == "tools/call":
                params = message.get("params") or {}
                name = params.get("name")
                if name not in self.handlers:
                    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "tool unavailable in KCH 0.11"}}
                payload = self.handlers[name](params.get("arguments") or {})
                result = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, sort_keys=True)}], "isError": False}
            else:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "unknown method"}}
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except (ValueError, CapabilityError) as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32001, "message": str(exc)}}
        except Exception:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": "internal error"}}


def default_registry() -> Path:
    return Path(str(files("kwancode_harness").joinpath("data/KCH_REGISTRY_v0.11.0.json")))


def build_gateway() -> Gateway:
    secret = os.environ.get("KCH_011_HMAC_SECRET", "").encode("utf-8")
    if len(secret) < 32:
        raise SystemExit("KCH_011_HMAC_SECRET must contain at least 32 bytes")
    state = Path(os.environ.get("KCH_011_STATE", ".kch_011/state.sqlite3"))
    registry = Path(os.environ.get("KCH_011_REGISTRY", str(default_registry())))
    profile = os.environ.get("KCH_011_PROFILE", "agent-shadow")
    bundle_root = os.environ.get("KCH_011_BUNDLE_ROOT")
    return Gateway(state, registry, secret, profile=profile, bundle_root=bundle_root)


def main() -> None:
    server = MCPServer(build_gateway())
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = server.handle(request)
            if response is not None:
                print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
        except json.JSONDecodeError:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}), flush=True)


if __name__ == "__main__":
    main()
