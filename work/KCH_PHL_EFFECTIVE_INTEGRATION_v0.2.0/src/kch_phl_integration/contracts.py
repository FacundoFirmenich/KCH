from __future__ import annotations

import hashlib
import json
import re
from typing import Any


DECISION_SCHEMA = "kch.reviewable-decision.v0.2.0"
REQUIRED_FIELDS = (
    "schema",
    "decision_id",
    "emitted_at",
    "component_id",
    "decision_type",
    "initiator",
    "trigger",
    "objective_contract_sha256",
    "purpose_id",
    "jurisdiction",
    "input_provenance_ids",
    "source_event_ids",
    "evidence_ids",
    "active_rule_ids",
    "summary",
    "rationale",
    "alternatives_considered",
    "confidence_representation",
    "risk_class",
    "authority_granted",
    "authority_exercised",
    "claim_ceiling",
    "consequence",
    "reversibility",
    "stop_condition_ids",
    "source_uri",
)
LIST_FIELDS = (
    "input_provenance_ids",
    "source_event_ids",
    "evidence_ids",
    "active_rule_ids",
    "alternatives_considered",
    "authority_granted",
    "authority_exercised",
    "stop_condition_ids",
)
TEXT_FIELDS = tuple(field for field in REQUIRED_FIELDS if field not in LIST_FIELDS and field != "confidence_representation")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class DecisionContractError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _contains_unavailable(value: Any) -> bool:
    if value == "UNAVAILABLE":
        return True
    if isinstance(value, list):
        return any(_contains_unavailable(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_unavailable(item) for item in value.values())
    return False


def validate_reviewable_decision(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise DecisionContractError("decision record must be an object")
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        raise DecisionContractError(f"missing required fields: {','.join(missing)}")
    extras = sorted(set(record) - set(REQUIRED_FIELDS))
    if extras:
        raise DecisionContractError(f"undeclared fields: {','.join(extras)}")
    if record["schema"] != DECISION_SCHEMA:
        raise DecisionContractError(f"schema must be {DECISION_SCHEMA}")
    for field in TEXT_FIELDS:
        if not isinstance(record[field], str) or not record[field].strip():
            raise DecisionContractError(f"{field} must be non-empty text")
    for field in LIST_FIELDS:
        value = record[field]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise DecisionContractError(f"{field} must be a list of non-empty strings")
    confidence = record["confidence_representation"]
    if not isinstance(confidence, dict) or set(confidence) - {"kind", "value", "meaning"}:
        raise DecisionContractError("confidence_representation must contain only kind/value/meaning")
    if not isinstance(confidence.get("kind"), str) or not confidence["kind"].strip():
        raise DecisionContractError("confidence_representation.kind is required")
    objective_hash = record["objective_contract_sha256"]
    if objective_hash != "UNAVAILABLE" and not HEX64.fullmatch(objective_hash):
        raise DecisionContractError("objective_contract_sha256 must be lowercase SHA-256 or UNAVAILABLE")
    if not set(record["authority_exercised"]).issubset(set(record["authority_granted"])):
        raise DecisionContractError("authority_exercised must be a subset of authority_granted")
    unavailable_fields = [field for field in REQUIRED_FIELDS if _contains_unavailable(record[field])]
    normalized = json.loads(canonical_json(record))
    return {
        "record": normalized,
        "record_sha256": sha256_json(normalized),
        "contract_state": "CONFORMANT" if not unavailable_fields else "CONFORMANT_WITH_UNAVAILABLE",
        "unavailable_fields": unavailable_fields,
    }

