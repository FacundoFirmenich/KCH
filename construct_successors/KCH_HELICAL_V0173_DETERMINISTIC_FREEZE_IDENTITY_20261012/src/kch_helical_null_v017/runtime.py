"""Specification-derived KCH Helical null-runtime successor v0.17.

This module is intentionally *not* represented as the lost historical v0.8.4
``null_runtime.py``.  It reifies the frozen v0.13 job census and governance
contract under a new content-addressed identity.  It contains no scientific data,
performs no file/network/process I/O, and grants no authority to score sealed test
values.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

PROTOCOL_ID = "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
HISTORICAL_RUNTIME_CONTRACT_ID = "h13nullspec:bc68343eee99c797c27795b9c5e73b7bec63764f678ab4c195572281acf79dff"
HISTORICAL_LEDGER_ID = "h13nullledger:6abcf3c64273d25a52d75fd423b6b825ee0b1a1b800aaf5d38acf98795179c2a"
HISTORICAL_LEDGER_SHA256 = "ed9436709cc2eb61794e9d5235f99d261c2fd3642a22699a02e43783daa03d22"
HISTORICAL_FREEZE_ID = "h13nullfreeze:1bc0b66c7030de5784f2a5c882b8b9e1069c628fef5919558c4415413cbea6d7"

COHORTS = (
    "BAY_AREA_HAYWARD_CALAVERAS",
    "PARKFIELD_CENTRAL_SAF",
)

NULL_FAMILIES = (
    "MARK_PERMUTATION_WITHIN_FAULT_TIME_MAGNITUDE_QUALITY_BLOCKS",
    "PARENT_EDGE_REWIRING_PRESERVING_ETAS_WEIGHT_DISTRIBUTION",
    "STATIC_ORIENTATION_FIELD_SURROGATES",
    "PROPAGATION_DIRECTION_REVERSAL",
    "NONHELICAL_HAWKES_SIMULATIONS_MATCHED_TO_NETWORK_RATE_MAGNITUDE_UNCERTAINTY",
)

OPERATOR_BINDINGS: Mapping[str, tuple[str, ...]] = {
    "MARK_PERMUTATION_WITHIN_FAULT_TIME_MAGNITUDE_QUALITY_BLOCKS": (
        "permute_within_bins",
    ),
    "PARENT_EDGE_REWIRING_PRESERVING_ETAS_WEIGHT_DISTRIBUTION": (
        "rewire_parent_graph",
        "make_rewired_null",
    ),
    "STATIC_ORIENTATION_FIELD_SURROGATES": (
        "draw_static_fields",
        "static_logodds",
    ),
    "PROPAGATION_DIRECTION_REVERSAL": (
        "reflected_rake",
        "head_to_normal",
        "score_null_metrics",
    ),
    "NONHELICAL_HAWKES_SIMULATIONS_MATCHED_TO_NETWORK_RATE_MAGNITUDE_UNCERTAINTY": (
        "simulate_nonhelical_fixed_parent_weights",
        "simulate_catalog",
    ),
    "MECHANISM_UNCERTAINTY_PROPAGATION": (
        "propagate_mechanism_uncertainty",
        "posterior_mark_expectations",
    ),
    "PARENT_GRAPH_RESAMPLE": (
        "compute_parent_state",
        "eval_intensity",
    ),
    "MOVING_BLOCK_BOOTSTRAP_TRAIN_PLUS_CALIBRATION": (
        "moving_block_resample",
    ),
}

STAGE_COUNTS: Mapping[str, int] = {
    "OBSERVED_CALIBRATION_SCORE": 2,
    "NULL_CALIBRATION_REPLICATE": 1_990,
    "MECHANISM_UNCERTAINTY_PROPAGATION": 128,
    "PARENT_GRAPH_RESAMPLE": 128,
    "LOCATION_AND_FAULT_ASSIGNMENT_PERTURBATION": 128,
    "MOVING_BLOCK_BOOTSTRAP_TRAIN_PLUS_CALIBRATION": 3_998,
    "HOLM_MULTIPLICITY_AGGREGATION": 1,
    "RUNTIME_QUALIFICATION_ADJUDICATION": 1,
}
EXPECTED_JOB_COUNT = sum(STAGE_COUNTS.values())

REPLICATES = {
    "NULL_CALIBRATION_REPLICATE_EACH_FAMILY_COHORT": 199,
    "MECHANISM_UNCERTAINTY_EACH_COHORT": 64,
    "PARENT_GRAPH_RESAMPLE_EACH_COHORT": 64,
    "LOCATION_PERTURBATION_EACH_COHORT": 64,
    "MOVING_BLOCK_BOOTSTRAP_EACH_COHORT": 1_999,
}

STATUS_PASS = "PASS"
STATUS_NOT_RUN = "NOT_RUN"
STATUS_FAIL_CLOSED = "FAIL_CLOSED"
QUALIFICATION_PASS = "RUNTIME_QUALIFICATION_PASS"
QUALIFICATION_NOT_EXECUTED = "RUNTIME_QUALIFICATION_NOT_EXECUTED"
QUALIFICATION_FAIL_CLOSED = "RUNTIME_QUALIFICATION_FAIL_CLOSED"
_HEX = frozenset("0123456789abcdef")


def canonical_json_bytes(value: Any) -> bytes:
    """Return the sole canonical JSON representation used by this successor."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def content_id(prefix: str, value: Any) -> str:
    if not prefix or ":" in prefix:
        raise ValueError("prefix must be nonempty and must not contain ':'")
    return prefix + ":" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def stable_seed(value: Any) -> int:
    """Derive a deterministic positive 63-bit seed from canonical content."""

    raw = hashlib.sha256(canonical_json_bytes(value)).digest()
    seed = int.from_bytes(raw[:8], "big", signed=False) & ((1 << 63) - 1)
    return seed or 1


def _require_nonempty_string(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a nonempty string")
    return value


def runtime_contract(
    *,
    protocol_id: str,
    parent_graph_lock_id: str,
    location_operator_id: str,
    cohorts: Sequence[str] = COHORTS,
) -> dict[str, Any]:
    """Construct the v0.17 contract under a new, nonhistorical identity."""

    _require_nonempty_string("protocol_id", protocol_id)
    _require_nonempty_string("parent_graph_lock_id", parent_graph_lock_id)
    _require_nonempty_string("location_operator_id", location_operator_id)
    cohort_tuple = tuple(cohorts)
    if cohort_tuple != COHORTS:
        raise ValueError(f"cohorts must equal the frozen primary cohorts: {COHORTS!r}")

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_SPEC_DERIVED_NONIDENTICAL_RUNTIME_CONTRACT",
        "version": "0.17.0",
        "lineage_semantics": "NEW_SUCCESSOR_NOT_HISTORICAL_RUNTIME_IDENTITY",
        "derivation_basis": {
            "protocol_id": protocol_id,
            "historical_runtime_contract_id": HISTORICAL_RUNTIME_CONTRACT_ID,
            "historical_ledger_id": HISTORICAL_LEDGER_ID,
            "historical_ledger_sha256": HISTORICAL_LEDGER_SHA256,
            "historical_freeze_id": HISTORICAL_FREEZE_ID,
            "historical_source_recoverability": "NOT_RECOVERABLE_FROM_AVAILABLE_INDEPENDENT_TRANSPORTS",
            "historical_identity_transfer": "FORBIDDEN",
        },
        "parent_graph_lock_id": parent_graph_lock_id,
        "location_operator_id": location_operator_id,
        "cohorts": list(cohort_tuple),
        "null_families": list(NULL_FAMILIES),
        "operator_bindings": {key: list(value) for key, value in OPERATOR_BINDINGS.items()},
        "job_census": dict(STAGE_COUNTS),
        "job_count": EXPECTED_JOB_COUNT,
        "replicates": dict(REPLICATES),
        "seed_derivation": "LOW_63_BITS_SHA256_OF_CANONICAL_JOB_IDENTITY_NONZERO",
        "job_id_derivation": "SHA256_OF_CANONICAL_JOB_BODY_INCLUDING_SEED",
        "allowed_partitions": ["TRAIN", "CALIBRATION"],
        "sealed_test_access": "FORBIDDEN",
        "qualification_semantics": {
            "all_expected_jobs_pass": QUALIFICATION_PASS,
            "one_or_more_not_run_and_none_fail_closed": QUALIFICATION_NOT_EXECUTED,
            "missing_extra_duplicate_identity_mismatch_or_fail_closed": QUALIFICATION_FAIL_CLOSED,
        },
        "qualification_result_contract": {
            "required_fields": [
                "job_id",
                "seed",
                "runtime_contract_id",
                "protocol_id",
                "stage",
                "cohort",
                "family",
                "replicate",
                "status",
                "input_hashes",
                "output_sha256",
                "operator_diagnostics",
                "sealed_test_accessed",
                "scientific_result",
            ],
            "pass_requires_nonempty_input_hashes": True,
            "pass_requires_output_sha256": True,
            "pass_requires_nonempty_operator_diagnostics": True,
            "sealed_test_accessed": False,
            "scientific_result": None,
        },
        "authority_ceiling": "SOFTWARE_CANDIDATE_LOCAL_SHADOW",
        "publication": "BLOCKED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
    }
    contract = dict(body)
    contract["contract_id"] = content_id("h17nullspec", body)
    return contract


def _dependency_selector(stage: str, cohort: str) -> list[dict[str, Any]]:
    if stage == "OBSERVED_CALIBRATION_SCORE":
        return []
    if stage in {
        "NULL_CALIBRATION_REPLICATE",
        "MECHANISM_UNCERTAINTY_PROPAGATION",
        "PARENT_GRAPH_RESAMPLE",
        "LOCATION_AND_FAULT_ASSIGNMENT_PERTURBATION",
        "MOVING_BLOCK_BOOTSTRAP_TRAIN_PLUS_CALIBRATION",
    }:
        return [{"stage": "OBSERVED_CALIBRATION_SCORE", "cohort": cohort}]
    if stage == "HOLM_MULTIPLICITY_AGGREGATION":
        return [
            {"stage": "OBSERVED_CALIBRATION_SCORE", "cohort": "*"},
            {"stage": "NULL_CALIBRATION_REPLICATE", "cohort": "*"},
        ]
    if stage == "RUNTIME_QUALIFICATION_ADJUDICATION":
        return [
            {"stage": upstream, "cohort": "*"}
            for upstream in STAGE_COUNTS
            if upstream != "RUNTIME_QUALIFICATION_ADJUDICATION"
        ]
    raise ValueError(f"unknown stage: {stage}")


def _operator_binding(stage: str, family: str) -> list[str]:
    if stage == "NULL_CALIBRATION_REPLICATE":
        return list(OPERATOR_BINDINGS[family])
    return list(OPERATOR_BINDINGS.get(stage, ()))


def _job(
    *,
    protocol_id: str,
    runtime_contract_id: str,
    parent_graph_lock_id: str,
    location_operator_id: str,
    stage: str,
    cohort: str,
    family: str,
    replicate: int,
) -> dict[str, Any]:
    if not isinstance(replicate, int) or replicate < 0:
        raise ValueError("replicate must be a nonnegative integer")
    identity = {
        "format": "KCH_HELICAL_V0_17_JOB_IDENTITY",
        "protocol_id": protocol_id,
        "runtime_contract_id": runtime_contract_id,
        "parent_graph_lock_id": parent_graph_lock_id,
        "location_operator_id": location_operator_id,
        "stage": stage,
        "cohort": cohort,
        "family": family,
        "replicate": replicate,
    }
    seed = stable_seed({"domain": "KCH_HELICAL_V0_17_JOB_SEED", "identity": identity})
    body: dict[str, Any] = {
        **identity,
        "seed": seed,
        "allowed_partitions": ["TRAIN", "CALIBRATION"],
        "sealed_test_access": "FORBIDDEN",
        "dependency_selector": _dependency_selector(stage, cohort),
        "operator_binding": _operator_binding(stage, family),
        "initial_status": STATUS_NOT_RUN,
        "scientific_result": None,
        "authority_ceiling": "SOFTWARE_CANDIDATE_LOCAL_SHADOW",
        "publication": "BLOCKED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    job = dict(body)
    job["job_id"] = content_id("h17job", body)
    return job


def build_job_ledger(
    *,
    protocol_id: str,
    parent_graph_lock_id: str,
    location_operator_id: str,
    cohorts: Sequence[str] = COHORTS,
) -> list[dict[str, Any]]:
    """Build the exact 6,376-row v0.17 structural qualification ledger."""

    contract = runtime_contract(
        protocol_id=protocol_id,
        parent_graph_lock_id=parent_graph_lock_id,
        location_operator_id=location_operator_id,
        cohorts=cohorts,
    )
    contract_id = contract["contract_id"]
    jobs: list[dict[str, Any]] = []

    for cohort in COHORTS:
        jobs.append(
            _job(
                protocol_id=protocol_id,
                runtime_contract_id=contract_id,
                parent_graph_lock_id=parent_graph_lock_id,
                location_operator_id=location_operator_id,
                stage="OBSERVED_CALIBRATION_SCORE",
                cohort=cohort,
                family="OBSERVED_CALIBRATION",
                replicate=0,
            )
        )

    for cohort in COHORTS:
        for family in NULL_FAMILIES:
            for replicate in range(1, REPLICATES["NULL_CALIBRATION_REPLICATE_EACH_FAMILY_COHORT"] + 1):
                jobs.append(
                    _job(
                        protocol_id=protocol_id,
                        runtime_contract_id=contract_id,
                        parent_graph_lock_id=parent_graph_lock_id,
                        location_operator_id=location_operator_id,
                        stage="NULL_CALIBRATION_REPLICATE",
                        cohort=cohort,
                        family=family,
                        replicate=replicate,
                    )
                )

    repeated_stages = (
        (
            "MECHANISM_UNCERTAINTY_PROPAGATION",
            "MECHANISM_UNCERTAINTY",
            REPLICATES["MECHANISM_UNCERTAINTY_EACH_COHORT"],
        ),
        (
            "PARENT_GRAPH_RESAMPLE",
            "PARENT_GRAPH",
            REPLICATES["PARENT_GRAPH_RESAMPLE_EACH_COHORT"],
        ),
        (
            "LOCATION_AND_FAULT_ASSIGNMENT_PERTURBATION",
            "LOCATION_AND_FAULT_ASSIGNMENT",
            REPLICATES["LOCATION_PERTURBATION_EACH_COHORT"],
        ),
        (
            "MOVING_BLOCK_BOOTSTRAP_TRAIN_PLUS_CALIBRATION",
            "MOVING_BLOCK_BOOTSTRAP",
            REPLICATES["MOVING_BLOCK_BOOTSTRAP_EACH_COHORT"],
        ),
    )
    for stage, family, count in repeated_stages:
        for cohort in COHORTS:
            for replicate in range(1, count + 1):
                jobs.append(
                    _job(
                        protocol_id=protocol_id,
                        runtime_contract_id=contract_id,
                        parent_graph_lock_id=parent_graph_lock_id,
                        location_operator_id=location_operator_id,
                        stage=stage,
                        cohort=cohort,
                        family=family,
                        replicate=replicate,
                    )
                )

    jobs.append(
        _job(
            protocol_id=protocol_id,
            runtime_contract_id=contract_id,
            parent_graph_lock_id=parent_graph_lock_id,
            location_operator_id=location_operator_id,
            stage="HOLM_MULTIPLICITY_AGGREGATION",
            cohort="GLOBAL",
            family="HOLM_BONFERRONI",
            replicate=0,
        )
    )
    jobs.append(
        _job(
            protocol_id=protocol_id,
            runtime_contract_id=contract_id,
            parent_graph_lock_id=parent_graph_lock_id,
            location_operator_id=location_operator_id,
            stage="RUNTIME_QUALIFICATION_ADJUDICATION",
            cohort="GLOBAL",
            family="RUNTIME_QUALIFICATION",
            replicate=0,
        )
    )

    validate_job_ledger(jobs, expected_contract_id=contract_id)
    return jobs


def validate_job_ledger(
    jobs: Sequence[Mapping[str, Any]],
    *,
    expected_contract_id: str,
) -> dict[str, Any]:
    """Fail closed unless the complete structural ledger is internally coherent."""

    if len(jobs) != EXPECTED_JOB_COUNT:
        raise ValueError(f"job count mismatch: {len(jobs)} != {EXPECTED_JOB_COUNT}")
    required = {
        "job_id",
        "seed",
        "protocol_id",
        "runtime_contract_id",
        "parent_graph_lock_id",
        "location_operator_id",
        "stage",
        "cohort",
        "family",
        "replicate",
        "allowed_partitions",
        "sealed_test_access",
        "dependency_selector",
        "operator_binding",
        "initial_status",
        "scientific_result",
        "authority_ceiling",
        "publication",
        "promotion",
        "canonicalization",
    }
    stage_counts: Counter[str] = Counter()
    null_family_counts: Counter[str] = Counter()
    job_ids: set[str] = set()
    seeds: set[int] = set()
    for index, job in enumerate(jobs):
        missing = required - set(job)
        if missing:
            raise ValueError(f"job {index} missing fields: {sorted(missing)}")
        if job["runtime_contract_id"] != expected_contract_id:
            raise ValueError(f"job {index} runtime contract mismatch")
        if job["protocol_id"] != PROTOCOL_ID:
            raise ValueError(f"job {index} protocol mismatch")
        if job["allowed_partitions"] != ["TRAIN", "CALIBRATION"]:
            raise ValueError(f"job {index} partition firewall mismatch")
        if job["sealed_test_access"] != "FORBIDDEN":
            raise ValueError(f"job {index} sealed-test firewall mismatch")
        if job["scientific_result"] is not None:
            raise ValueError(f"job {index} contains a scientific result")
        if job["initial_status"] != STATUS_NOT_RUN:
            raise ValueError(f"job {index} initial status is not NOT_RUN")
        job_id = job["job_id"]
        seed = job["seed"]
        if not isinstance(job_id, str) or not job_id.startswith("h17job:"):
            raise ValueError(f"job {index} invalid ID")
        if not isinstance(seed, int) or seed <= 0 or seed >= 1 << 63:
            raise ValueError(f"job {index} invalid seed")
        if job_id in job_ids:
            raise ValueError(f"duplicate job ID: {job_id}")
        if seed in seeds:
            raise ValueError(f"duplicate seed: {seed}")
        job_ids.add(job_id)
        seeds.add(seed)
        stage_counts[job["stage"]] += 1
        if job["stage"] == "NULL_CALIBRATION_REPLICATE":
            null_family_counts[job["family"]] += 1

    if dict(stage_counts) != dict(STAGE_COUNTS):
        raise ValueError(f"stage census mismatch: {dict(stage_counts)!r}")
    expected_family_counts = {family: 2 * REPLICATES["NULL_CALIBRATION_REPLICATE_EACH_FAMILY_COHORT"] for family in NULL_FAMILIES}
    if dict(null_family_counts) != expected_family_counts:
        raise ValueError(f"null-family census mismatch: {dict(null_family_counts)!r}")
    return {
        "job_count": len(jobs),
        "job_id_unique_count": len(job_ids),
        "seed_unique_count": len(seeds),
        "stage_counts": dict(stage_counts),
        "null_family_counts": dict(null_family_counts),
        "sealed_test_accessed": False,
        "scientific_result": None,
    }


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in _HEX for ch in value)


def qualification_status(
    jobs: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Adjudicate structural runtime qualification without scientific interpretation."""

    try:
        if not jobs:
            raise ValueError("expected ledger is empty")
        contract_ids = {job["runtime_contract_id"] for job in jobs}
        if len(contract_ids) != 1:
            raise ValueError("expected ledger contains multiple contract IDs")
        validate_job_ledger(jobs, expected_contract_id=next(iter(contract_ids)))
    except Exception as exc:
        return {
            "outcome": QUALIFICATION_FAIL_CLOSED,
            "reason": "INVALID_EXPECTED_LEDGER",
            "detail": str(exc),
            "sealed_test_accessed": False,
            "scientific_result": None,
        }

    expected = {job["job_id"]: job for job in jobs}
    if len(records) != len(expected):
        return {
            "outcome": QUALIFICATION_FAIL_CLOSED,
            "reason": "RESULT_CARDINALITY_MISMATCH",
            "expected": len(expected),
            "observed": len(records),
            "sealed_test_accessed": False,
            "scientific_result": None,
        }

    seen: set[str] = set()
    status_counts: Counter[str] = Counter()
    identity_fields = (
        "job_id",
        "seed",
        "runtime_contract_id",
        "protocol_id",
        "stage",
        "cohort",
        "family",
        "replicate",
    )
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            return {
                "outcome": QUALIFICATION_FAIL_CLOSED,
                "reason": "NON_MAPPING_RESULT_RECORD",
                "index": index,
                "sealed_test_accessed": False,
                "scientific_result": None,
            }
        job_id = record.get("job_id")
        if job_id in seen:
            return {
                "outcome": QUALIFICATION_FAIL_CLOSED,
                "reason": "DUPLICATE_RESULT_JOB_ID",
                "job_id": job_id,
                "sealed_test_accessed": False,
                "scientific_result": None,
            }
        seen.add(job_id)
        job = expected.get(job_id)
        if job is None:
            return {
                "outcome": QUALIFICATION_FAIL_CLOSED,
                "reason": "UNKNOWN_RESULT_JOB_ID",
                "job_id": job_id,
                "sealed_test_accessed": False,
                "scientific_result": None,
            }
        for field in identity_fields:
            if record.get(field) != job.get(field):
                return {
                    "outcome": QUALIFICATION_FAIL_CLOSED,
                    "reason": "RESULT_IDENTITY_MISMATCH",
                    "job_id": job_id,
                    "field": field,
                    "expected": job.get(field),
                    "observed": record.get(field),
                    "sealed_test_accessed": False,
                    "scientific_result": None,
                }
        if record.get("sealed_test_accessed") is not False:
            return {
                "outcome": QUALIFICATION_FAIL_CLOSED,
                "reason": "SEALED_TEST_FIREWALL_VIOLATION",
                "job_id": job_id,
                "sealed_test_accessed": True,
                "scientific_result": None,
            }
        if record.get("scientific_result") is not None:
            return {
                "outcome": QUALIFICATION_FAIL_CLOSED,
                "reason": "SCIENTIFIC_RESULT_PRESENT_DURING_QUALIFICATION",
                "job_id": job_id,
                "sealed_test_accessed": False,
                "scientific_result": None,
            }
        status = record.get("status")
        if status not in {STATUS_PASS, STATUS_NOT_RUN, STATUS_FAIL_CLOSED}:
            return {
                "outcome": QUALIFICATION_FAIL_CLOSED,
                "reason": "INVALID_RESULT_STATUS",
                "job_id": job_id,
                "status": status,
                "sealed_test_accessed": False,
                "scientific_result": None,
            }
        status_counts[status] += 1
        if status == STATUS_PASS:
            input_hashes = record.get("input_hashes")
            diagnostics = record.get("operator_diagnostics")
            if not isinstance(input_hashes, Mapping) or not input_hashes:
                return {
                    "outcome": QUALIFICATION_FAIL_CLOSED,
                    "reason": "PASS_WITHOUT_INPUT_HASHES",
                    "job_id": job_id,
                    "sealed_test_accessed": False,
                    "scientific_result": None,
                }
            if not all(isinstance(key, str) and key and _is_sha256(value) for key, value in input_hashes.items()):
                return {
                    "outcome": QUALIFICATION_FAIL_CLOSED,
                    "reason": "INVALID_PASS_INPUT_HASH",
                    "job_id": job_id,
                    "sealed_test_accessed": False,
                    "scientific_result": None,
                }
            if not _is_sha256(record.get("output_sha256")):
                return {
                    "outcome": QUALIFICATION_FAIL_CLOSED,
                    "reason": "INVALID_PASS_OUTPUT_HASH",
                    "job_id": job_id,
                    "sealed_test_accessed": False,
                    "scientific_result": None,
                }
            if not isinstance(diagnostics, Mapping) or not diagnostics:
                return {
                    "outcome": QUALIFICATION_FAIL_CLOSED,
                    "reason": "PASS_WITHOUT_OPERATOR_DIAGNOSTICS",
                    "job_id": job_id,
                    "sealed_test_accessed": False,
                    "scientific_result": None,
                }

    if seen != set(expected):
        return {
            "outcome": QUALIFICATION_FAIL_CLOSED,
            "reason": "RESULT_JOB_SET_MISMATCH",
            "sealed_test_accessed": False,
            "scientific_result": None,
        }
    if status_counts[STATUS_FAIL_CLOSED]:
        outcome = QUALIFICATION_FAIL_CLOSED
        reason = "ONE_OR_MORE_JOBS_FAIL_CLOSED"
    elif status_counts[STATUS_NOT_RUN]:
        outcome = QUALIFICATION_NOT_EXECUTED
        reason = "ONE_OR_MORE_JOBS_NOT_RUN"
    elif status_counts[STATUS_PASS] == len(expected):
        outcome = QUALIFICATION_PASS
        reason = "ALL_EXPECTED_JOBS_PASS"
    else:
        outcome = QUALIFICATION_FAIL_CLOSED
        reason = "UNREACHABLE_STATUS_COMBINATION"
    return {
        "outcome": outcome,
        "reason": reason,
        "job_count": len(expected),
        "status_counts": dict(status_counts),
        "sealed_test_accessed": False,
        "scientific_result": None,
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }


def not_run_records(jobs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Construct structural NOT_RUN receipts; never a scientific execution."""

    output: list[dict[str, Any]] = []
    for job in jobs:
        output.append(
            {
                "job_id": job["job_id"],
                "seed": job["seed"],
                "runtime_contract_id": job["runtime_contract_id"],
                "protocol_id": job["protocol_id"],
                "stage": job["stage"],
                "cohort": job["cohort"],
                "family": job["family"],
                "replicate": job["replicate"],
                "status": STATUS_NOT_RUN,
                "input_hashes": {},
                "output_sha256": None,
                "operator_diagnostics": {"reason": "STRUCTURAL_FREEZE_ONLY_NO_EXECUTION"},
                "sealed_test_accessed": False,
                "scientific_result": None,
            }
        )
    return output
