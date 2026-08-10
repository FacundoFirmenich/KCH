from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import normalize_text, sha256_json


READ_ONLY_TOOL_ALLOWLIST = {
    "kch.super.status",
    "kch.super.registry.evidence.audit",
    "kch.super.controls",
    "kch.component.status",
    "kch.phl.projection",
    "kch.sco.projection",
    "kch.mis.certificate.verify",
    "kch.kwanprompts.probe",
    "kch.rgg.probe",
    "kch.obl_phl.probe",
}


@dataclass(frozen=True, slots=True)
class ActivationRule:
    rule_id: str
    version: str
    target_tool: str
    arguments: dict[str, Any]
    reason_es: str
    event_types: tuple[str, ...]
    anchors_any: tuple[str, ...]
    signals_any: tuple[str, ...]
    excluded_any: tuple[str, ...]
    priority: int
    confidence: float
    cooldown_seconds: int
    max_queries_per_session: int

    @classmethod
    def parse(cls, value: dict[str, Any]) -> "ActivationRule":
        required = {
            "rule_id", "version", "target_tool", "arguments", "reason_es", "event_types", "anchors_any",
            "signals_any", "excluded_any", "priority", "confidence", "cooldown_seconds", "max_queries_per_session",
        }
        if set(value) != required:
            raise ValueError(f"activation rule fields mismatch: {value.get('rule_id', 'UNKNOWN')}")
        if value["target_tool"] not in READ_ONLY_TOOL_ALLOWLIST:
            raise ValueError(f"activation target is not allowlisted read-only: {value['target_tool']}")
        if not isinstance(value["arguments"], dict):
            raise ValueError("activation arguments must be an object")
        confidence = float(value["confidence"])
        if not 0 < confidence <= 1:
            raise ValueError("activation confidence must be within (0,1]")
        if int(value["cooldown_seconds"]) < 0 or int(value["max_queries_per_session"]) < 1:
            raise ValueError("activation cooldown/query budget invalid")
        return cls(
            rule_id=str(value["rule_id"]),
            version=str(value["version"]),
            target_tool=str(value["target_tool"]),
            arguments=dict(value["arguments"]),
            reason_es=str(value["reason_es"]),
            event_types=tuple(map(str, value["event_types"])),
            anchors_any=tuple(normalize_text(item) for item in value["anchors_any"]),
            signals_any=tuple(normalize_text(item) for item in value["signals_any"]),
            excluded_any=tuple(normalize_text(item) for item in value["excluded_any"]),
            priority=int(value["priority"]),
            confidence=confidence,
            cooldown_seconds=int(value["cooldown_seconds"]),
            max_queries_per_session=int(value["max_queries_per_session"]),
        )

    def matches(self, event_type: str, text: str) -> bool:
        if event_type not in self.event_types:
            return False
        normalized = normalize_text(text)
        if any(term and term in normalized for term in self.excluded_any):
            return False
        anchor = not self.anchors_any or any(term and term in normalized for term in self.anchors_any)
        signal = not self.signals_any or any(term and term in normalized for term in self.signals_any)
        return anchor and signal

    def describe(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "version": self.version,
            "target_tool": self.target_tool,
            "arguments": self.arguments,
            "reason_es": self.reason_es,
            "event_types": list(self.event_types),
            "priority": self.priority,
            "confidence": self.confidence,
            "cooldown_seconds": self.cooldown_seconds,
            "max_queries_per_session": self.max_queries_per_session,
            "action_class": "READ_ONLY",
        }


class RuleCatalog:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if value.get("schema") != "kch.activation-rules.v0.1.0":
            raise ValueError("activation rule catalog schema mismatch")
        self.proposal_ttl_seconds = int(value.get("proposal_ttl_seconds", 900))
        if not 1 <= self.proposal_ttl_seconds <= 3600:
            raise ValueError("proposal_ttl_seconds must be within 1..3600")
        rules = [ActivationRule.parse(row) for row in value.get("rules", [])]
        if not rules or len({row.rule_id for row in rules}) != len(rules):
            raise ValueError("activation rules must be non-empty and uniquely identified")
        self.rules = tuple(sorted(rules, key=lambda row: (-row.priority, -row.confidence, row.rule_id)))
        self.hash = sha256_json(value)

    def match(self, event_type: str, text: str) -> list[ActivationRule]:
        return [rule for rule in self.rules if rule.matches(event_type, text)]

    def describe(self) -> dict[str, Any]:
        return {
            "schema": "kch.activation-rule-catalog-description.v0.1.0",
            "catalog_sha256": self.hash,
            "rule_count": len(self.rules),
            "proposal_ttl_seconds": self.proposal_ttl_seconds,
            "rules": [row.describe() for row in self.rules],
            "mutating_targets": 0,
            "phl_real_execution_targets": 0,
        }

