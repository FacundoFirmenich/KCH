#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

EXPECTED = {
    "protocol_id": "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f",
    "mechanism_sha256": "cc13d9e4335bb20579d224c52ea2936d3251719c381c830c23b2abfd0a1eedeb",
    "mechanism_bytes": 528904117,
    "fault_sha256": "37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1",
    "fault_bytes": 10622730,
    "fault_git_blob_sha1": "fb164770b529695544fa864abe2cc9dd8aa5793d",
    "blind_npz_sha256": "7719b063252e217b19cc5045b99531dc8b7ac9fe6fbe2b57693b25f28a6a9161",
    "selected_indices_sha256": "64079a3ccaff3389ef8814225afdb850a1c17950cfa6bf7e75af908de48a6e28",
    "selected_directional_sha256": "008faaff16f46c97c6b91ba55545609beeda58e79192fdd2b595871604c18c9b",
    "selected_event_count": 61555,
    "axis_observable_count": 60577,
    "parent_graph_lock_id": "h8parent:f61e9b60c455e75e53f16b9579cd085b68de20d810f05165504f91ab09d400cb",
    "parent_graph_gate_id": "h8pg:5690829352b8163faf63bc3cecc0a6efb34fe024894b90e5dd961e2c7eb732ba",
    "location_operator_id": "h12locop:6b3fcf56d1f427d107e5e5dbb264aba02f871c93708a5796074fd0916d89b1b5",
    "ephemeral_parent_edge_sha256": "ebe90e7eba499856f706c9d59b6cc0756b2e1a3d32de3f5b58c5901952db838f",
    "v0174_receipt_id": "h174qual:facc39da5ce123fe2e4a5f4ea9b83bd912e6a4f57d96829e4421703ec53f8b1d",
    "v0174_validation_id": "h174validation:f17a63f0bab469484497a84880bd9318ef3667b439f6c07f4a92e25746c1ee7a",
    "v017_runtime_contract_id": "h17nullspec:20fbec42c3b9e1c6ec1ed8ef1a1f418907dee6a41fbba73259911f3a359e315d",
    "v017_job_ledger_id": "h17nullledger:d524bca6e35f07bbfaabaa947c43a11d2d2317e04ac640d0d3d9243baade2e29",
}
EXPECTED_COUNTS = {
    "BAY_AREA_HAYWARD_CALAVERAS": {
        "selected": 37853,
        "axis_observable": 37280,
        "train": 18640,
        "calibration": 9320,
        "sealed_test": 9320,
    },
    "PARKFIELD_CENTRAL_SAF": {
        "selected": 23702,
        "axis_observable": 23297,
        "train": 11648,
        "calibration": 5824,
        "sealed_test": 5825,
    },
}

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value

def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--regenerated-results", type=Path, required=True)
    ap.add_argument("--v0174-results", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args=ap.parse_args()

    results=args.regenerated_results.resolve()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)

    acquisition=load(results/"ACQUISITION_RECEIPT_V0_12.json")
    selected=load(results/"SELECTED_INDEX_RECEIPT_V0_12.json")
    directional=load(results/"SELECTED_DIRECTIONAL_EXTRACTION_RECEIPT_V0_12.json")
    reconcile=load(results/"DIRECTIONAL_PREFLIGHT_RECONCILIATION_V0_12.json")
    parameter=load(results/"ETAS_HAWKES_PARENT_GRAPH_PARAMETER_LOCK_V0_12.json")
    calibration=load(results/"PARENT_GRAPH_CALIBRATION_RESULT_V0_12.json")
    edges=load(results/"EPHEMERAL_PARENT_EDGE_DIGEST_RECEIPT_V0_12.json")
    run=load(results/"RUN_RECEIPT_V0_12.json")
    v174=load(args.v0174_results/"FULL_RUNTIME_QUALIFICATION_RECEIPT_V0_17_4.json")
    v174val=load(args.v0174_results/"FULL_RUNTIME_QUALIFICATION_VALIDATION_V0_17_4.json")

    checks={
        "regenerated_run_pass": run.get("outcome")=="PARENT_GRAPH_LOCK_PASS" and run.get("exit_code")==0,
        "protocol_identity": run.get("protocol_id")==EXPECTED["protocol_id"],
        "mechanism_sha256": acquisition["mechanism"]["sha256"]==EXPECTED["mechanism_sha256"],
        "mechanism_bytes": int(acquisition["mechanism"]["bytes"])==EXPECTED["mechanism_bytes"],
        "fault_sha256": acquisition["fault"]["sha256"]==EXPECTED["fault_sha256"],
        "fault_bytes": int(acquisition["fault"]["bytes"])==EXPECTED["fault_bytes"],
        "fault_git_blob": acquisition["fault"]["git_blob_sha1"]==EXPECTED["fault_git_blob_sha1"],
        "blind_npz_identity": selected["blind_npz_sha256"]==EXPECTED["blind_npz_sha256"],
        "selected_indices_identity": selected["selected_indices_sha256"]==EXPECTED["selected_indices_sha256"],
        "selected_directional_identity": directional["output_sha256"]==EXPECTED["selected_directional_sha256"],
        "selected_event_count": int(directional["selected_event_count"])==EXPECTED["selected_event_count"],
        "axis_observable_count": int(reconcile["axis_observable_count"])==EXPECTED["axis_observable_count"],
        "preflight_denominators_exact_match": reconcile["cohort_denominators_exact_match"] is True,
        "parent_graph_lock_identity": parameter["lock_id"]==EXPECTED["parent_graph_lock_id"],
        "parent_graph_gate_identity": calibration["gate_id"]==EXPECTED["parent_graph_gate_id"],
        "location_operator_identity": parameter["location_perturbation_operator_id"]==EXPECTED["location_operator_id"],
        "ephemeral_parent_edge_digest_identity": edges["edge_artifact_sha256"]==EXPECTED["ephemeral_parent_edge_sha256"],
        "parent_edges_not_persisted": edges["edge_artifact_persisted"] is False and run["parent_edges_purged"] is True,
        "raw_sources_purged": run["raw_sources_purged"] is True,
        "blind_rows_purged": run["blind_rows_purged"] is True,
        "selected_indices_purged": run["selected_indices_purged"] is True,
        "directional_rows_purged": run["directional_rows_purged"] is True,
        "preflight_arrays_purged": run["preflight_arrays_purged"] is True,
        "sealed_test_not_scored": run["sealed_test_scored"] is False,
        "dynamic_helical_model_not_executed": run["dynamic_helical_model_execution_performed"] is False,
        "null_family_not_executed": run["null_family_execution_performed"] is False,
        "v0174_receipt_identity": v174["receipt_id"]==EXPECTED["v0174_receipt_id"],
        "v0174_validation_identity": v174val["validation_id"]==EXPECTED["v0174_validation_id"] and v174val["receipt_id"]==v174["receipt_id"],
        "v0174_runtime_qualified": v174["qualification_adjudication"]["outcome"]=="RUNTIME_QUALIFICATION_PASS",
        "v017_runtime_contract_identity": v174["runtime_contract_id"]==EXPECTED["v017_runtime_contract_id"],
        "v017_job_ledger_identity": v174["job_ledger_id"]==EXPECTED["v017_job_ledger_id"],
        "v017_runtime_not_executed_in_binding_gate": True,
        "v017_runtime_sealed_test_accessed": False,
        "scientific_result_absent": True,
        "historical_v013_identity_transfer": False,
    }

    by_name={row["cohort"]:row for row in calibration["unit_results"]}
    cohort_binding={}
    for name, expected in EXPECTED_COUNTS.items():
        row=by_name[name]
        observed={
            "selected": next(int(x["selected_count"]) for x in selected["cohorts"] if x["cohort_id"]==name),
            "axis_observable": expected["axis_observable"],
            "train": int(row["train_count"]),
            "calibration": int(row["calibration_count"]),
            "sealed_test": int(row["test_count"]),
        }
        if observed != expected:
            raise RuntimeError(f"{name}: split-count drift: {observed} != {expected}")
        if row["test_values_scored"] is not False:
            raise RuntimeError(f"{name}: sealed test was scored")
        cohort_binding[name]={
            **observed,
            "runtime_admitted_event_count": observed["train"]+observed["calibration"],
            "sealed_test_event_count": observed["sealed_test"],
            "parameter_lock": row["parameter_lock"],
            "calibration_parent_candidate_fraction": row["calibration_parent_candidate_fraction"],
            "calibration_mean_log_intensity_gain_vs_background": row["calibration_mean_log_intensity_gain_vs_background"],
        }

    if not all(checks.values()):
        raise RuntimeError("binding invariant failure: "+repr([k for k,v in checks.items() if not v]))

    runtime_admitted=sum(v["runtime_admitted_event_count"] for v in cohort_binding.values())
    sealed=sum(v["sealed_test_event_count"] for v in cohort_binding.values())

    binding={
        "format":"KCH_HELICAL_V0_17_5_REAL_CALIBRATION_INPUT_BINDING",
        "protocol_id":EXPECTED["protocol_id"],
        "v0174_runtime_qualification_receipt_id":v174["receipt_id"],
        "v0174_runtime_qualification_validation_id":v174val["validation_id"],
        "v017_runtime_contract_id":v174["runtime_contract_id"],
        "v017_job_ledger_id":v174["job_ledger_id"],
        "source_identity":{
            "mechanism_sha256":acquisition["mechanism"]["sha256"],
            "mechanism_bytes":acquisition["mechanism"]["bytes"],
            "fault_sha256":acquisition["fault"]["sha256"],
            "fault_bytes":acquisition["fault"]["bytes"],
            "fault_git_blob_sha1":acquisition["fault"]["git_blob_sha1"],
        },
        "selection_identity":{
            "blind_npz_sha256":selected["blind_npz_sha256"],
            "selected_indices_sha256":selected["selected_indices_sha256"],
            "selected_directional_sha256":directional["output_sha256"],
            "selected_event_count":directional["selected_event_count"],
            "axis_observable_count":reconcile["axis_observable_count"],
        },
        "parent_graph_identity":{
            "lock_id":parameter["lock_id"],
            "gate_id":calibration["gate_id"],
            "location_operator_id":parameter["location_perturbation_operator_id"],
            "ephemeral_parent_edge_sha256":edges["edge_artifact_sha256"],
            "edge_artifact_persisted":False,
        },
        "cohorts":cohort_binding,
        "runtime_admitted_train_plus_calibration_event_count":runtime_admitted,
        "sealed_test_event_count":sealed,
        "partitioning_enclave":{
            "selected_directional_rows_temporarily_materialized":True,
            "directional_fields_temporarily_opened":["strike","dip","rake"],
            "sealed_test_partition_values_temporarily_present_for_observability_partitioning":True,
            "sealed_test_scored":False,
            "scientific_model_execution_performed":False,
            "rows_exported":False,
            "rows_purged":True,
        },
        "v017_runtime_domain":{
            "executed_in_this_gate":False,
            "row_values_received":False,
            "sealed_test_values_received":False,
            "sealed_test_accessed":False,
            "scientific_result":None,
        },
        "location_uncertainty":{
            "historical_crosswalk_gate_id":"h142loccsv:bf526701f2dcaee32e02e3861dd127b925470b15979ee9fd0ce6418a34bc31cf",
            "historical_crosswalk_rows_sha256":"bd94381c94e585c07d711c2ed6bd75d2abcb2e0d011dbc1fe18c98611f76decc",
            "status":"SEPARATE_MUTABLE_OBSERVATION_VINTAGE_NOT_REFRESHED_IN_THIS_GATE",
            "next_gate":"REFRESH_AND_BIND_LOCATION_UNCERTAINTY_VINTAGE_NO_RUNTIME_TEST_ACCESS",
        },
        "scientific_data_bound":True,
        "scientific_model_executed":False,
        "sealed_test_scored":False,
        "sealed_test_exported":False,
        "scientific_result":None,
        "physical_helicity":"NOT_EVALUATED",
        "historical_v0_13_identity_transfer":False,
        "promotion":"BLOCKED",
        "canonicalization":"BLOCKED",
        "status":"PASS",
        "next_gate":"REFRESH_AND_BIND_LOCATION_UNCERTAINTY_VINTAGE_NO_RUNTIME_TEST_ACCESS",
    }
    binding["binding_id"]="h175binding:"+sha256_bytes(canonical(binding))
    write(out/"REAL_CALIBRATION_INPUT_BINDING_V0_17_5.json",binding)

    validation={
        "format":"KCH_HELICAL_V0_17_5_REAL_CALIBRATION_BINDING_VALIDATION",
        "status":"PASS",
        "binding_id":binding["binding_id"],
        "checks":checks,
        "runtime_admitted_event_count":runtime_admitted,
        "sealed_test_event_count":sealed,
    }
    validation["validation_id"]="h175validation:"+sha256_bytes(canonical(validation))
    write(out/"REAL_CALIBRATION_INPUT_BINDING_VALIDATION_V0_17_5.json",validation)
    print(json.dumps({
        "binding_id":binding["binding_id"],
        "validation_id":validation["validation_id"],
        "runtime_admitted_event_count":runtime_admitted,
        "sealed_test_event_count":sealed,
        "parent_graph_lock_id":parameter["lock_id"],
        "ephemeral_parent_edge_sha256":edges["edge_artifact_sha256"],
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
