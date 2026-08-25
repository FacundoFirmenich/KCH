from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


SCHEMA = "scpp.pentaxial.v0.1"
AXES = (
    "P1_CYBERSECURITY_LOCAL_GLOBAL_LOCAL",
    "P2_ENDOGENOUS_HIERARCHICAL_FOUNDATIONAL_COHERENCE",
    "P3_NANO_MICRO_MACRO_NANO_SEQUENTIAL_INTERSCALAR_COHERENCE",
    "P4_IRREVERSIBLE_CONFORMATIONAL_INVARIANT_PRESERVATION",
    "P5_LOGICAL_DEDUCTIVE_WHITEBOX_TRACEABILITY",
)
ACTIONS = ("TRANSMUTER_V032", "TRANSFORMER_PRENORM")


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Supercontract:
    schema: str
    lineage_id: str
    axes: tuple[str, ...]
    non_compensable: bool
    calibration_noise_threshold_bounds: tuple[float, float]
    content_hash: str


@dataclass(frozen=True)
class GeneralConstitution:
    parent_supercontract_hash: str
    allowed_observables: tuple[str, ...]
    prohibited_observables: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    fail_closed_action: str
    content_hash: str


@dataclass(frozen=True)
class LocalConstitution:
    parent_general_hash: str
    jurisdiction_id: str
    threat_rule: str
    threat_action: str
    ordinary_action: str
    content_hash: str


@dataclass(frozen=True)
class Calibration:
    noise_threshold: float


@dataclass(frozen=True)
class Genesis:
    supercontract: Supercontract
    general: GeneralConstitution
    local: LocalConstitution
    calibration: Calibration
    receipt_hash: str


@dataclass(frozen=True)
class Observation:
    current_query: bool
    delay: int
    noise_rms: float
    structurally_ambiguous: bool
    source_digest: str


@dataclass(frozen=True)
class AxisReceipt:
    axis_id: str
    passed: bool
    evidence: str


@dataclass(frozen=True)
class DecisionReceipt:
    observation_hash: str
    sensed_threat: bool
    ambiguous: bool
    proposed_action: str
    admitted: bool
    executed_action: str
    rationale: str
    stage_hashes: tuple[str, ...]
    axis_receipts: tuple[AxisReceipt, ...]
    receipt_hash: str


def _with_hash(payload: dict[str, Any]) -> str:
    return canonical_hash(payload)


def genesis(lineage_id: str, *, noise_threshold: float = 0.30) -> Genesis:
    if not lineage_id.strip():
        raise ValueError("lineage_id must be non-empty")
    bounds = (0.20, 0.40)
    if not bounds[0] <= noise_threshold <= bounds[1]:
        raise ValueError("noise threshold outside frozen calibration bounds")
    super_payload = {
        "schema": SCHEMA,
        "lineage_id": lineage_id,
        "axes": AXES,
        "non_compensable": True,
        "calibration_noise_threshold_bounds": bounds,
    }
    supercontract = Supercontract(**super_payload, content_hash=_with_hash(super_payload))
    general_payload = {
        "parent_supercontract_hash": supercontract.content_hash,
        "allowed_observables": ("input_tensor",),
        "prohibited_observables": ("target", "loss", "correctness", "cell_label", "counterfactual_logits"),
        "allowed_actions": ACTIONS,
        "fail_closed_action": "TRANSFORMER_PRENORM",
    }
    general = GeneralConstitution(**general_payload, content_hash=_with_hash(general_payload))
    local_payload = {
        "parent_general_hash": general.content_hash,
        "jurisdiction_id": "CURRENT_DELAY_LE_2_HIGH_NOISE",
        "threat_rule": "current_query AND delay<=2 AND noise_rms>threshold",
        "threat_action": "TRANSFORMER_PRENORM",
        "ordinary_action": "TRANSMUTER_V032",
    }
    local = LocalConstitution(**local_payload, content_hash=_with_hash(local_payload))
    calibration = Calibration(noise_threshold=noise_threshold)
    receipt_hash = canonical_hash({
        "supercontract": asdict(supercontract),
        "general": asdict(general),
        "local": asdict(local),
        "calibration": asdict(calibration),
    })
    return Genesis(supercontract, general, local, calibration, receipt_hash)


def validate_genesis(value: Genesis) -> None:
    if value.supercontract.axes != AXES or len(value.supercontract.axes) != 5:
        raise RuntimeError("FAIL_CLOSED_INVALID_PENTAXIAL_IDENTITY")
    if not value.supercontract.non_compensable:
        raise RuntimeError("FAIL_CLOSED_COMPENSATION_FORBIDDEN")
    rebuilt = genesis(value.supercontract.lineage_id, noise_threshold=value.calibration.noise_threshold)
    if rebuilt != value:
        raise RuntimeError("FAIL_CLOSED_GENESIS_HASH_CHAIN_MISMATCH")


def calibrate(value: Genesis, *, noise_threshold: float) -> tuple[Genesis, dict[str, Any]]:
    validate_genesis(value)
    low, high = value.supercontract.calibration_noise_threshold_bounds
    if not low <= noise_threshold <= high:
        raise ValueError("calibration outside frozen bounds; new lineage required")
    updated = genesis(value.supercontract.lineage_id, noise_threshold=noise_threshold)
    receipt = {
        "transition": "CALIBRATION_ONLY",
        "old_genesis_receipt": value.receipt_hash,
        "new_genesis_receipt": updated.receipt_hash,
        "axes_unchanged": updated.supercontract.axes == value.supercontract.axes,
        "categorical_identity_unchanged": updated.supercontract.content_hash == value.supercontract.content_hash,
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return updated, receipt


def decide(value: Genesis, observation: Observation) -> DecisionReceipt:
    validate_genesis(value)
    observation_hash = canonical_hash(asdict(observation))
    threat = (
        observation.current_query
        and observation.delay <= 2
        and observation.noise_rms > value.calibration.noise_threshold
    )
    proposed = (
        value.general.fail_closed_action
        if observation.structurally_ambiguous
        else value.local.threat_action if threat else value.local.ordinary_action
    )
    rationale = (
        "FAIL_CLOSED_STRUCTURAL_AMBIGUITY"
        if observation.structurally_ambiguous
        else "PREDECLARED_LOCAL_THREAT" if threat else "OUTSIDE_LOCAL_THREAT_PRESERVE_ORDINARY_BRANCH"
    )
    stage_hashes = (
        observation_hash,
        canonical_hash({"stage": "sensing", "threat": threat, "ambiguous": observation.structurally_ambiguous}),
        canonical_hash({"stage": "local_rule", "parent": value.local.content_hash, "action": proposed}),
        canonical_hash({"stage": "pentaxial_admission", "supercontract": value.supercontract.content_hash}),
        canonical_hash({"stage": "actuation", "single_branch": proposed}),
    )
    evidence = (
        proposed in value.general.allowed_actions,
        value.local.parent_general_hash == value.general.content_hash
        and value.general.parent_supercontract_hash == value.supercontract.content_hash,
        len(stage_hashes) == 5 and len(set(stage_hashes)) == 5,
        value.supercontract.axes == AXES and value.supercontract.non_compensable,
        bool(observation.source_digest) and bool(rationale),
    )
    axis_receipts = tuple(
        AxisReceipt(axis_id, passed, f"deterministic_check_{index + 1}")
        for index, (axis_id, passed) in enumerate(zip(AXES, evidence))
    )
    admitted = all(item.passed for item in axis_receipts)
    executed = proposed if admitted else value.general.fail_closed_action
    payload = {
        "observation_hash": observation_hash,
        "sensed_threat": threat,
        "ambiguous": observation.structurally_ambiguous,
        "proposed_action": proposed,
        "admitted": admitted,
        "executed_action": executed,
        "rationale": rationale,
        "stage_hashes": stage_hashes,
        "axis_receipts": tuple(asdict(item) for item in axis_receipts),
    }
    return DecisionReceipt(**{k: payload[k] for k in payload if k != "axis_receipts"}, axis_receipts=axis_receipts, receipt_hash=canonical_hash(payload))
