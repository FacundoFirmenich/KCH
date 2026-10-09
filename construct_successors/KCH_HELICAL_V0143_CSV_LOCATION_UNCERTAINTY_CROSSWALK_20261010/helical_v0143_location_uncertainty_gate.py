from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import helical_v014_location_uncertainty_gate as predecessor

CSV_SCOPE = "EXACT_COMCAT_CSV_LOCATION_UNCERTAINTY_CROSSWALK_ONLY"
EXPECTED_FAILED_PREDECESSOR = "h14run:73d8aad92ed4d15e493c2d1ecf6de29e5fbe91c42e1615c3c33a0635aad7e7b7"

# Preserve the narrow v0.14.1 software repair. This changes only the Python
# collection type used by the deny-list intersection, not its membership.
predecessor.CORE.REMAINING_SEALED = set(predecessor.CORE.REMAINING_SEALED)


def validate_authority(
    path: Path,
    protocol: Mapping[str, Any],
    eligibility: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    lease = json.loads(path.read_text(encoding="utf-8"))
    if lease.get("status") != "ACTIVE_UNTIL_SINGLE_SUCCESSOR_TERMINATES" or lease.get("single_use") is not True:
        raise RuntimeError("v0.14.3 authority is not active and single-use")
    exact = {
        "scope": CSV_SCOPE,
        "protocol_id": protocol.get("protocol_id"),
        "upstream_eligibility_result_id": eligibility.get("eligibility_result_id"),
        "upstream_parent_graph_run_receipt_id": predecessor.EXPECTED_PARENT_RUN_ID,
        "upstream_location_operator_id": predecessor.EXPECTED_LOCATION_OPERATOR_ID,
        "upstream_exact_source_schema_result_id": predecessor.EXPECTED_SCHEMA_RESULT_ID,
        "predecessor_failed_run_receipt_id": EXPECTED_FAILED_PREDECESSOR,
        "predecessor_failure_class": "CSV_SCOPE_REJECTED_BY_GEOJSON_VALIDATOR_BEFORE_SOURCE_ACCESS",
        "predecessor_authority_consumed": False,
        "predecessor_outcome": "FAIL_CLOSED",
        "observation_adapter_change": "USGS_FDSN_GEOJSON_SUMMARY_TO_USGS_FDSN_CSV_BULK",
        "scientific_matching_contract_changed": False,
        "coverage_threshold_changed": False,
    }
    for key, expected in exact.items():
        if lease.get(key) != expected:
            raise RuntimeError(f"v0.14.3 authority lineage mismatch at {key}: {lease.get(key)!r} != {expected!r}")
    forbidden = (
        "raw_source_export_authorized",
        "selected_row_export_authorized",
        "crosswalk_row_export_authorized",
        "directional_unsealing_authorized",
        "sealed_test_access_authorized",
        "sealed_test_scoring_authorized",
        "scientific_model_fit_authorized",
        "null_runtime_execution_authorized",
        "publication_authority",
        "promotion_authority",
        "canonicalization_authority",
        "retrospective_mutation_authority",
    )
    for key in forbidden:
        if lease.get(key) is not False:
            raise RuntimeError(f"v0.14.3 authority boundary drift at {key}")
    receipt = {
        "format": "KCH_HELICAL_V0_14_3_AUTHORITY_ACTIVATION_RECEIPT",
        "authority_id": lease["authority_id"],
        "authority_file_sha256": predecessor.sha256(path),
        "scope": CSV_SCOPE,
        "protocol_id": protocol["protocol_id"],
        "eligibility_result_id": eligibility["eligibility_result_id"],
        "location_operator_id": predecessor.EXPECTED_LOCATION_OPERATOR_ID,
        "predecessor_failed_run_receipt_id": EXPECTED_FAILED_PREDECESSOR,
        "activated_at_utc": predecessor.utc_now(),
        "single_use": True,
        "observation_adapter": "USGS_FDSN_CSV_BULK",
        "sealed_test_access_authorized": False,
        "scientific_model_fit_authorized": False,
        "null_runtime_execution_authorized": False,
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    return lease, {"receipt_id": predecessor.content_id("h143auth", receipt), **receipt}


_original_acquire_exact = predecessor.acquire_exact


def acquire_exact(raw: Path, timeout: int) -> dict[str, Any]:
    value = _original_acquire_exact(raw, timeout)
    value["authority_ceiling"] = CSV_SCOPE
    public = {key: item for key, item in value.items() if not key.startswith("_") and key != "receipt_id"}
    value["receipt_id"] = predecessor.content_id("h143acq", public)
    return value


_original_reconstruct_selection = predecessor.reconstruct_selection


def reconstruct_selection(
    blind_npz: Path,
    fault: Path,
    protocol: Mapping[str, Any],
    eligibility: Mapping[str, Any],
    output: Path,
):
    selected_npz, receipt = _original_reconstruct_selection(blind_npz, fault, protocol, eligibility, output)
    receipt["authority_ceiling"] = CSV_SCOPE
    receipt["successor_version"] = "0.14.3"
    receipt["observation_adapter"] = "USGS_FDSN_CSV_BULK"
    public = {key: item for key, item in receipt.items() if key != "receipt_id"}
    receipt["receipt_id"] = predecessor.content_id("h143select", public)
    return selected_npz, receipt


predecessor.validate_authority = validate_authority
predecessor.acquire_exact = acquire_exact
predecessor.reconstruct_selection = reconstruct_selection


if __name__ == "__main__":
    raise SystemExit(predecessor.main())
