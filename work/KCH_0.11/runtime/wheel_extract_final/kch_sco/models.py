from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class ContractError(ValueError):
    pass


HEX64 = re.compile(r"^[0-9a-f]{64}$")
PROVIDERS = {"CODEX", "CLINE", "COWORK", "OPENCODE", "CHATGPT", "CUSTOM"}
URI_PREFIXES = {
    "CODEX": "codex://threads/",
    "CLINE": "cline://tasks/",
    "COWORK": "cowork://tasks/",
    "OPENCODE": "opencode://sessions/",
    "CHATGPT": "chatgpt://threads/",
}
AUTONOMY_LEVELS = {
    "OBSERVE_ONLY",
    "RESPOND_WITHIN_SCOPE",
    "PROPOSE_WITHIN_SCOPE",
    "EXECUTE_WITHIN_SCOPE",
    "SUBORCHESTRATE_WITHIN_SCOPE",
}
CONNECTOR_STATES = {
    "HOST_VERIFIED_REFERENCE",
    "LIVE_READ_WRITE_VERIFIED",
    "REFERENCE_ONLY_NO_LIVE_BRIDGE",
    "UNAVAILABLE",
}
RELATIONS = {
    "SUPPLIES_EVIDENCE",
    "IMPLEMENTS",
    "REVIEWS",
    "ADJUDICATES",
    "MONITORS",
    "SYNCHRONIZES",
    "CHALLENGES",
    "GATES",
}
RECEIPT_OUTCOMES = {"SUCCEEDED", "FAILED", "BLOCKED", "ABSTAINED"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _exact(record: Any, schema: str, fields: set[str]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ContractError("record must be an object")
    missing = sorted(fields - set(record))
    extras = sorted(set(record) - fields)
    if missing or extras:
        raise ContractError(f"schema fields mismatch; missing={missing}; extras={extras}")
    if record.get("schema") != schema:
        raise ContractError(f"schema must be {schema}")
    return json.loads(canonical_json(record))


def _text(record: dict[str, Any], *fields: str) -> None:
    for field in fields:
        if not isinstance(record[field], str) or not record[field].strip():
            raise ContractError(f"{field} must be non-empty text")


def _text_list(record: dict[str, Any], *fields: str) -> None:
    for field in fields:
        value = record[field]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ContractError(f"{field} must be a list of non-empty strings")


def validate_superchat(record: dict[str, Any]) -> dict[str, Any]:
    value = _exact(record, "kch.sco.superchat.v0.1.0", {"schema", "sco_id", "name", "objective", "non_goals", "jurisdiction", "claim_ceiling"})
    _text(value, "sco_id", "name", "objective", "jurisdiction", "claim_ceiling")
    _text_list(value, "non_goals")
    return value


def validate_node(record: dict[str, Any]) -> dict[str, Any]:
    value = _exact(
        record,
        "kch.sco.node.v0.1.0",
        {
            "schema", "sco_id", "node_id", "provider", "native_uri", "title", "role",
            "responsibilities", "capabilities", "authority_granted", "autonomy_level",
            "context_policy", "memory_policy", "connector_state", "source_provenance",
        },
    )
    _text(value, "sco_id", "node_id", "provider", "native_uri", "title", "role", "autonomy_level", "context_policy", "memory_policy", "connector_state", "source_provenance")
    _text_list(value, "responsibilities", "capabilities", "authority_granted")
    if value["provider"] not in PROVIDERS:
        raise ContractError("unsupported provider")
    expected = URI_PREFIXES.get(value["provider"])
    if expected and not value["native_uri"].startswith(expected):
        raise ContractError(f"native_uri must start with {expected}")
    if value["provider"] == "CUSTOM" and "://" not in value["native_uri"]:
        raise ContractError("CUSTOM native_uri must be an explicit URI")
    if value["autonomy_level"] not in AUTONOMY_LEVELS:
        raise ContractError("unsupported autonomy_level")
    if value["context_policy"] != "SCOPED_DISCLOSURE_ONLY":
        raise ContractError("SCO prohibits merged or ambient context")
    if value["memory_policy"] != "NATIVE_MEMORY_PRESERVED":
        raise ContractError("SCO must preserve native node memory")
    if value["connector_state"] not in CONNECTOR_STATES:
        raise ContractError("unsupported connector_state")
    return value


def validate_disclosure(record: Any) -> dict[str, Any]:
    value = _exact(record, "kch.sco.scoped-disclosure.v0.1.0", {"schema", "allowed_ref_kinds", "maximum_payload_bytes", "forbidden_transfers"})
    _text_list(value, "allowed_ref_kinds", "forbidden_transfers")
    if not isinstance(value["maximum_payload_bytes"], int) or value["maximum_payload_bytes"] < 0:
        raise ContractError("maximum_payload_bytes must be a non-negative integer")
    required_forbidden = {"FULL_CONTEXT_MERGE", "NATIVE_MEMORY_COPY", "IMPLICIT_AUTHORITY_TRANSFER"}
    if not required_forbidden.issubset(value["forbidden_transfers"]):
        raise ContractError("disclosure contract lacks mandatory prohibitions")
    return value


def validate_edge(record: dict[str, Any]) -> dict[str, Any]:
    value = _exact(record, "kch.sco.edge.v0.1.0", {"schema", "sco_id", "edge_id", "source_node_id", "target_node_id", "relation", "disclosure_contract", "activation_condition", "gate_id"})
    _text(value, "sco_id", "edge_id", "source_node_id", "target_node_id", "relation", "activation_condition", "gate_id")
    if value["source_node_id"] == value["target_node_id"]:
        raise ContractError("self edges are prohibited")
    if value["relation"] not in RELATIONS:
        raise ContractError("unsupported relation")
    value["disclosure_contract"] = validate_disclosure(value["disclosure_contract"])
    return value


def validate_fragment(value: Any) -> dict[str, Any]:
    result = _exact(value, "kch.sco.disclosed-fragment-ref.v0.1.0", {"schema", "fragment_id", "source_node_id", "locator", "content_sha256", "purpose"})
    _text(result, "fragment_id", "source_node_id", "locator", "content_sha256", "purpose")
    if not HEX64.fullmatch(result["content_sha256"]):
        raise ContractError("fragment content_sha256 must be lowercase SHA-256")
    if any(key in result for key in ("content", "full_context", "memory")):
        raise ContractError("disclosed fragments are references, not merged content")
    return result


def validate_work_order(record: dict[str, Any]) -> dict[str, Any]:
    value = _exact(
        record,
        "kch.sco.work-order.v0.1.0",
        {"schema", "sco_id", "order_id", "target_node_id", "objective", "input_refs", "disclosed_fragments", "required_outputs", "authority_granted", "depends_on", "termination", "claim_ceiling"},
    )
    _text(value, "sco_id", "order_id", "target_node_id", "objective", "termination", "claim_ceiling")
    _text_list(value, "input_refs", "required_outputs", "authority_granted", "depends_on")
    if not isinstance(value["disclosed_fragments"], list):
        raise ContractError("disclosed_fragments must be a list")
    value["disclosed_fragments"] = [validate_fragment(item) for item in value["disclosed_fragments"]]
    return value


def validate_receipt(record: dict[str, Any]) -> dict[str, Any]:
    value = _exact(
        record,
        "kch.sco.receipt.v0.1.0",
        {"schema", "receipt_id", "order_id", "node_id", "outcome", "output_refs", "evidence_ids", "claims", "limitations", "authority_exercised", "completed_at"},
    )
    _text(value, "receipt_id", "order_id", "node_id", "outcome", "completed_at")
    _text_list(value, "output_refs", "evidence_ids", "claims", "limitations", "authority_exercised")
    if value["outcome"] not in RECEIPT_OUTCOMES:
        raise ContractError("unsupported receipt outcome")
    if value["outcome"] == "SUCCEEDED" and not value["output_refs"]:
        raise ContractError("a successful receipt requires at least one output reference")
    return value


def validate_conflict(record: dict[str, Any]) -> dict[str, Any]:
    value = _exact(record, "kch.sco.conflict.v0.1.0", {"schema", "sco_id", "conflict_id", "receipt_ids", "question", "state", "adjudicator_node_id", "resolution_ref"})
    _text(value, "sco_id", "conflict_id", "question", "state", "adjudicator_node_id", "resolution_ref")
    _text_list(value, "receipt_ids")
    if len(set(value["receipt_ids"])) < 2:
        raise ContractError("a conflict requires at least two distinct receipts")
    if value["state"] not in {"OPEN_PRESERVED", "RESOLVED_PRESERVING_DIVERGENCE"}:
        raise ContractError("unsupported conflict state")
    return value
