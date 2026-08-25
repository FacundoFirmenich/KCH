from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .canonical import attach_hash, sha256_json


AXES = (
    "P1_CYBERSECURITY_LOCAL_GLOBAL_LOCAL",
    "P2_ENDOGENOUS_HIERARCHICAL_FOUNDATIONAL_COHERENCE",
    "P3_NANO_MICRO_MACRO_NANO_SEQUENTIAL_INTERSCALAR_COHERENCE",
    "P4_IRREVERSIBLE_CONFORMATIONAL_INVARIANT_PRESERVATION",
    "P5_LOGICAL_DEDUCTIVE_WHITEBOX_TRACEABILITY",
)


@dataclass(frozen=True, slots=True)
class AxisEvidence:
    axis_id: str
    passed: bool
    evidence: str


class PentaxialGate:
    """Pre-action non-compensable SCPP gate; a blocked transition is never executed."""

    def __init__(self, lineage_id: str, *, policy_hash: str | None = None) -> None:
        if not lineage_id.strip():
            raise ValueError("lineage_id must be non-empty")
        self.lineage_id = lineage_id
        self.policy_hash = policy_hash or sha256_json({"lineage_id": lineage_id, "axes": AXES, "non_compensable": True})

    def evaluate(self, transition: dict[str, Any], evidence: dict[str, AxisEvidence]) -> dict[str, Any]:
        if tuple(evidence) != AXES:
            raise ValueError("axis evidence must be supplied once and in the frozen pentaxial order")
        receipts = []
        for axis in AXES:
            item = evidence[axis]
            if item.axis_id != axis or not item.evidence.strip():
                raise ValueError(f"invalid evidence for {axis}")
            receipts.append({"axis_id": axis, "passed": item.passed, "evidence": item.evidence})
        admitted = all(item["passed"] for item in receipts)
        return attach_hash({
            "schema": "kch.scpp-preaction.v0.1.0",
            "lineage_id": self.lineage_id,
            "policy_hash": self.policy_hash,
            "transition_sha256": sha256_json(transition),
            "non_compensable": True,
            "axis_receipts": receipts,
            "admitted": admitted,
            "effect_executed": False,
            "status": "ADMITTED_PREACTION" if admitted else "BLOCKED_BEFORE_EFFECT",
        })

    def execute(
        self,
        transition: dict[str, Any],
        evidence: dict[str, AxisEvidence],
        action: Callable[[], Any],
    ) -> tuple[dict[str, Any], Any | None]:
        preflight = self.evaluate(transition, evidence)
        if preflight["admitted"] is not True:
            return preflight, None
        result = action()
        completed_core = {key: value for key, value in preflight.items() if key != "receipt_sha256"}
        completed_core.update({"effect_executed": True, "status": "ADMITTED_AND_EXECUTED", "result_sha256": sha256_json(result)})
        return attach_hash(completed_core), result

