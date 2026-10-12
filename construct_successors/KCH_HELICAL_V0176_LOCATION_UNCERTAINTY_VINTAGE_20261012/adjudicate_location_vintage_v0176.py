#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
from typing import Any

THRESHOLD=0.8
EXPECTED_SELECTED={"BAY_AREA_HAYWARD_CALAVERAS":37853,"PARKFIELD_CENTRAL_SAF":23702}
EXPECTED_MECH="cc13d9e4335bb20579d224c52ea2936d3251719c381c830c23b2abfd0a1eedeb"
EXPECTED_FAULT="37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1"
EXPECTED_BLIND="7719b063252e217b19cc5045b99531dc8b7ac9fe6fbe2b57693b25f28a6a9161"
EXPECTED_INDICES="64079a3ccaff3389ef8814225afdb850a1c17950cfa6bf7e75af908de48a6e28"
BINDING_ID="h1752binding:70e47780a528f21209a03e983fbe1d70a0055aae8f0ae82f552050d8f4047135"
VALIDATION_ID="h1752validation:46dbf20746c018d30d3c7a8ef20ef283786bca62579084cb18cea6f62d9cf7bb"

def canon(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
def dig(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def load(p:Path)->dict[str,Any]:
    v=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(v,dict):raise RuntimeError(f"object required: {p}")
    return v
def write(p:Path,v:Any):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,sort_keys=True,indent=2)+"\n",encoding="utf-8")

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,required=True)
    ap.add_argument("--gate-results",type=Path,required=True)
    ap.add_argument("--binding-root",type=Path,required=True)
    ap.add_argument("--historical-results",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    x=ap.parse_args();g=x.gate_results.resolve();out=x.output.resolve();out.mkdir(parents=True,exist_ok=True)
    binding=load(x.binding_root/"results/FROZEN_LOCK_REAL_INPUT_BINDING_V0_17_5_2.json")
    binding_val=load(x.binding_root/"results/FROZEN_LOCK_BINDING_VALIDATION_V0_17_5_2.json")
    result=load(g/"COMCAT_LOCATION_UNCERTAINTY_GATE_RESULT_V0_14.json")
    query=load(g/"COMCAT_QUERY_SUMMARY_RECEIPT_V0_14.json")
    select=load(g/"SELECTED_NONDIRECTIONAL_RECONSTRUCTION_RECEIPT_V0_14.json")
    acq=load(g/"EXACT_SOURCE_ACQUISITION_RECEIPT_V0_14.json")
    run=load(g/"RUN_RECEIPT_V0_14.json")
    hist=load(x.historical_results/"COMCAT_LOCATION_UNCERTAINTY_GATE_RESULT_V0_14.json")
    histq=load(x.historical_results/"COMCAT_QUERY_SUMMARY_RECEIPT_V0_14.json")

    checks={
      "upstream_binding_pass":binding["status"]=="PASS" and binding["binding_id"]==BINDING_ID,
      "upstream_validation_pass":binding_val["status"]=="PASS" and binding_val["validation_id"]==VALIDATION_ID and binding_val["binding_id"]==binding["binding_id"],
      "gate_pass":result["outcome"]=="LOCATION_UNCERTAINTY_CROSSWALK_PASS" and run["outcome"]=="LOCATION_UNCERTAINTY_CROSSWALK_PASS",
      "mechanism_identity":acq["mechanism"]["sha256"]==EXPECTED_MECH and int(acq["mechanism"]["bytes"])==528904117,
      "fault_identity":acq["fault_network"]["sha256"]==EXPECTED_FAULT and acq["fault_network"]["git_blob_sha1"]=="fb164770b529695544fa864abe2cc9dd8aa5793d",
      "blind_identity":select["blind_npz_sha256"]==EXPECTED_BLIND and result["source_blind_npz_sha256"]==EXPECTED_BLIND,
      "selection_identity":select["selected_indices_sha256"]==EXPECTED_INDICES and result["selected_indices_sha256"]==EXPECTED_INDICES,
      "selected_total":int(select["selected_total"])==61555 and int(result["crosswalk_row_count"])==61555,
      "query_plan_count":int(query["query_count"])==82 and int(result["query_count"])==82,
      "representation":query["representation"]=="USGS_FDSN_CSV" and result["representation"]=="USGS_FDSN_CSV",
      "threshold_unchanged":float(result["minimum_both_errors_fraction"])==THRESHOLD and result["coverage_threshold_changed_from_v0_14_1"] is False,
      "directional_fields_not_accessed":result["directional_fields_accessed"] is False and run["directional_fields_accessed"] is False,
      "sealed_test_not_accessed":result["sealed_test_accessed"] is False and run["sealed_test_accessed"] is False and run["sealed_test_scored"] is False,
      "no_model_execution":result["scientific_model_execution_performed"] is False and run["scientific_model_execution_performed"] is False and run["null_runtime_execution_performed"] is False,
      "raw_purged":run["raw_sources_purged"] is True and run["blind_rows_purged"] is True and run["selected_indices_purged"] is True and run["crosswalk_rows_purged"] is True,
    }
    coverage={};coverage_pass=True
    for cohort,expected in EXPECTED_SELECTED.items():
        cur=result["cohorts"][cohort];old=hist["cohorts"][cohort]
        ok=(int(cur["selected"])==expected and float(cur["both_errors_fraction"])>=THRESHOLD)
        coverage_pass=coverage_pass and ok
        coverage[cohort]={
          "pass":ok,"selected":int(cur["selected"]),"matched":int(cur["matched"]),
          "both_errors_count":int(cur["both_errors_count"]),"both_errors_fraction":float(cur["both_errors_fraction"]),
          "historical_both_errors_fraction":float(old["both_errors_fraction"]),
          "both_errors_fraction_delta":float(cur["both_errors_fraction"])-float(old["both_errors_fraction"]),
          "catalog_row_count_current":int(cur["comcat_events_in_bbox"]),
          "catalog_row_count_historical":int(old["comcat_events_in_bbox"])}
    checks["coverage_threshold_pass"]=coverage_pass
    if not all(checks.values()):raise RuntimeError("location vintage failed: "+repr([k for k,v in checks.items() if not v]))

    vintage={
      "format":"KCH_HELICAL_V0_17_6_LOCATION_UNCERTAINTY_VINTAGE",
      "github_run_id":os.environ.get("GITHUB_RUN_ID"),"github_sha":os.environ.get("GITHUB_SHA"),
      "upstream_binding_id":binding["binding_id"],"upstream_binding_validation_id":binding_val["validation_id"],
      "gate_id":result["gate_id"],"run_receipt_id":run["run_receipt_id"],"query_summary_receipt_id":query["receipt_id"],
      "query_receipts_sha256":query["query_receipts_sha256"],"crosswalk_rows_sha256":result["crosswalk_rows_sha256"],
      "query_count":query["query_count"],"representation":query["representation"],
      "historical_vintage":{"gate_id":hist["gate_id"],"query_summary_receipt_id":histq["receipt_id"],"query_receipts_sha256":histq["query_receipts_sha256"],"crosswalk_rows_sha256":hist["crosswalk_rows_sha256"]},
      "historical_response_hash_identity_required":False,"vintage_semantics":"NEW_MUTABLE_OBSERVATION_VINTAGE",
      "cohorts":coverage,"minimum_both_errors_fraction":THRESHOLD,
      "raw_rows_persisted":False,"crosswalk_rows_persisted":False,"directional_fields_accessed":False,
      "sealed_test_accessed":False,"scientific_model_executed":False,"scientific_result":None,"physical_helicity":"NOT_EVALUATED",
      "promotion":"BLOCKED","canonicalization":"BLOCKED","status":"PASS",
      "next_gate":"REAL_TRAIN_CALIBRATION_RUNTIME_EXECUTION_WITH_CURRENT_LOCATION_VINTAGE_NO_SEALED_TEST_ACCESS"}
    vintage["vintage_id"]="h176vintage:"+dig(canon(vintage));write(out/"LOCATION_UNCERTAINTY_VINTAGE_V0_17_6.json",vintage)
    validation={"format":"KCH_HELICAL_V0_17_6_LOCATION_UNCERTAINTY_VINTAGE_VALIDATION","status":"PASS","vintage_id":vintage["vintage_id"],"checks":checks,"scientific_result":None}
    validation["validation_id"]="h176validation:"+dig(canon(validation));write(out/"LOCATION_UNCERTAINTY_VINTAGE_VALIDATION_V0_17_6.json",validation)
    print(json.dumps({"vintage_id":vintage["vintage_id"],"validation_id":validation["validation_id"],"gate_id":vintage["gate_id"],"crosswalk_rows_sha256":vintage["crosswalk_rows_sha256"],"coverage":coverage},sort_keys=True))
    return 0
if __name__=="__main__":raise SystemExit(main())
