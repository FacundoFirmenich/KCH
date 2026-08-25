from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .canonical import attach_hash


Authority = Literal["NONE", "SHADOW", "LOCAL_OPERATIONAL"]


@dataclass(frozen=True, slots=True)
class JurisdictionContract:
    task: str
    operation: str
    horizon_delay: str
    interference: str
    phase: str
    block_id: int
    process_id: str
    seed_role: Literal["REPLICA_ONLY"] = "REPLICA_ONLY"
    jurisdiction_id: str = ""

    def __post_init__(self) -> None:
        for name in ("task", "operation", "horizon_delay", "interference", "phase", "process_id"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must be non-empty")
        if not 1 <= self.block_id <= 8:
            raise ValueError("block_id must be in 1..8")
        if self.seed_role != "REPLICA_ONLY":
            raise ValueError("seeds are replicas, never jurisdictions")
        expected = "|".join((self.task, self.operation, self.horizon_delay, self.interference, self.phase, self.process_id))
        if self.jurisdiction_id and self.jurisdiction_id != expected:
            raise ValueError("jurisdiction_id must equal the semantic coordinate and cannot encode a seed")
        object.__setattr__(self, "jurisdiction_id", expected)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OperatorLineage:
    operator: str
    version: str
    normalized_source_sha256: str
    transport_source_sha256: str
    authority: Authority
    claim_boundary: str
    lineage_id: str
    historical_verdict: str
    runtime_dependency: str | None = None

    def __post_init__(self) -> None:
        if len(self.normalized_source_sha256) != 64 or len(self.transport_source_sha256) != 64:
            raise ValueError("source hashes must be SHA-256 hex digests")
        if self.authority not in {"NONE", "SHADOW", "LOCAL_OPERATIONAL"}:
            raise ValueError("invalid authority")
        if not all((self.operator, self.version, self.claim_boundary, self.lineage_id, self.historical_verdict)):
            raise ValueError("lineage fields must be non-empty")

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CandidateReceipt:
    operator: str
    lineage_id: str
    jurisdiction: JurisdictionContract
    metrics: dict[str, float]
    uncertainty: dict[str, float]
    trace_sha256: str
    dependencies: tuple[str, ...]
    authority: Authority
    claim_boundary: str
    status: Literal["OBSERVED", "EXECUTED", "ABSTAIN", "TECHNICAL_FAILURE", "NOT_ESTIMABLE"]
    evidence_receipts: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if len(self.trace_sha256) != 64:
            raise ValueError("trace_sha256 must be a SHA-256 digest")
        if self.authority not in {"NONE", "SHADOW", "LOCAL_OPERATIONAL"}:
            raise ValueError("invalid authority")
        if self.operator == "mu_qe" and self.authority == "LOCAL_OPERATIONAL":
            raise ValueError("mu_QE is frozen SHADOW_ONLY after 8/8 losses versus GRU")

    def to_payload(self) -> dict[str, Any]:
        return attach_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class BlockBundle:
    jurisdiction: JurisdictionContract
    values: dict[str, Any]
    candidate_receipts: tuple[CandidateReceipt, ...] = field(default_factory=tuple)

    REQUIRED = frozenset({
        "mu_eq_obsolete", "gru_current", "gru_obsolete", "mu_qe_current",
        "mu_qe_obsolete", "mu_eq_current", "transformer", "transmuter_v02", "transmuter_v032",
    })

    def __post_init__(self) -> None:
        missing = self.REQUIRED - set(self.values)
        if missing:
            raise ValueError(f"missing block values: {sorted(missing)}")
        if self.jurisdiction.block_id not in range(1, 9):
            raise ValueError("invalid block")

