from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys
from typing import Any

import numpy as np

import helical_v017_comcat_location_gate as v17

core = v17.core
_ORIGINAL_DIRECTIONAL_PREFLIGHT = v17._ORIGINAL_DIRECTIONAL_PREFLIGHT

EXPECTED_PROTOCOL_ID = v17.EXPECTED_PROTOCOL_ID
EXPECTED_PARENT_GRAPH_LOCK_ID = v17.EXPECTED_PARENT_GRAPH_LOCK_ID
EXPECTED_LOCATION_OPERATOR_ID = v17.EXPECTED_LOCATION_OPERATOR_ID
PREDECESSOR_GATE_ID = "h17loc:045e0b12ce9dc2d7d23609a0384bbd70648cc8acb8015880912f4114d4fc039d"
PREDECESSOR_OUTCOME = "NOT_IDENTIFIABLE_LOCATION_UNCERTAINTY_COVERAGE"
CSV_ADAPTER_GIT_BLOB_SHA1 = "4b02d95db273f760274762522d18990beb3816e4"
CSV_ADAPTER_SHA256 = "d38876c5f82a6aebcbc645eb8634a9a4087999828815601a22926375344d84c4"
CSV_ADAPTER_PATH = (
    "construct_successors/"
    "KCH_HELICAL_V0171_COMCAT_CSV_LOCATION_CORRECTION_20261011/"
    "comcat_csv_location_crosswalk_v0171.py"
)
HISTORICAL_MATCH_OPERATOR_COMMIT = "e458afe20b8172db5a04194224cf21df5ec00dc4"
HISTORICAL_MATCH_OPERATOR_BLOB = "cfa0ee325d573679db497636e28fbc5b6e2b628e"
MINIMUM_BOTH_ERRORS_FRACTION = 0.80
COHORTS = v17.COHORTS
ALLOWED_CROSSWALK_FIELDS = v17.ALLOWED_CROSSWALK_FIELDS


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_id(prefix: str, value: Any) -> str:
    return prefix + ":" + hashlib.sha256(canonical(value)).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    indent=2, allow_nan=False) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def load_csv_adapter():
    source = Path(os.environ["KCH_V0171_COMCAT_CSV_ADAPTER"]).resolve()
    if not source.is_file():
        raise RuntimeError(f"CSV adapter missing: {source}")
    observed = sha256_path(source)
    if observed != CSV_ADAPTER_SHA256:
        raise RuntimeError(f"CSV adapter SHA-256 mismatch: {observed} != {CSV_ADAPTER_SHA256}")
    spec = importlib.util.spec_from_file_location("kch_v0171_comcat_csv_adapter", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load CSV adapter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, source


def finite_quantiles(values: list[float]) -> dict[str, float] | None:
    array = np.asarray([float(value) for value in values if value is not None], dtype=np.float64)
    array = array[np.isfinite(array)]
    if len(array) == 0:
        return None
    levels = np.asarray([0.0, 0.25, 0.50, 0.75, 0.95, 0.99, 1.0])
    observed = np.quantile(array, levels, method="linear")
    return {"count": int(len(array)), "min": float(observed[0]),
            "q25": float(observed[1]), "median": float(observed[2]),
            "q75": float(observed[3]), "q95": float(observed[4]),
            "q99": float(observed[5]), "max": float(observed[6])}


def rows_digest(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(canonical(row)); digest.update(b"\n")
    return digest.hexdigest()


def safe_query_receipts(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    safe_rows: list[dict[str, Any]] = []
    observed_columns: set[str] = set()
    for row in receipts:
        headers = row.get("headers") or {}
        columns = [str(value) for value in row.get("csv_columns", [])]
        observed_columns.update(columns)
        safe_rows.append({
            "cohort": row.get("cohort"), "year": int(row["year"]),
            "page": int(row["page"]), "offset": int(row["offset"]),
            "status": int(row["status"]), "bytes": int(row["bytes"]),
            "sha256": str(row["sha256"]), "row_count": int(row.get("row_count", 0)),
            "format": "csv", "csv_columns": columns,
            "etag": headers.get("ETag") or headers.get("Etag") or headers.get("etag"),
            "last_modified": headers.get("Last-Modified") or headers.get("last-modified"),
            "content_type": headers.get("Content-Type") or headers.get("content-type"),
        })
    body = {
        "format": "KCH_HELICAL_V0_17_1_COMCAT_CSV_QUERY_RECEIPT_MANIFEST",
        "page_count": len(safe_rows),
        "total_response_bytes": int(sum(row["bytes"] for row in safe_rows)),
        "total_response_rows": int(sum(row["row_count"] for row in safe_rows)),
        "observed_csv_columns": sorted(observed_columns), "pages": safe_rows,
        "raw_urls_exported": False, "raw_event_rows_exported": False,
        "credentials_supplied": False, "authenticated_api_used": False,
    }
    body["manifest_id"] = content_id("h171comcatqueries", body)
    return body


def execute_location_uncertainty_csv_gate(directional_npz: Path, output_dir: Path,
                                          v011_preflight: dict[str, Any]) -> dict[str, Any]:
    module, source = load_csv_adapter()
    ephemeral = output_dir.parent / "comcat_csv_location_crosswalk_ephemeral"
    shutil.rmtree(ephemeral, ignore_errors=True); ephemeral.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []; all_query_receipts: list[dict[str, Any]] = []
    cohort_results: dict[str, dict[str, Any]] = {}
    try:
        with np.load(directional_npz, allow_pickle=False) as loaded:
            missing = sorted(set(ALLOWED_CROSSWALK_FIELDS) - set(loaded.files))
            if missing:
                raise RuntimeError("selected directional schema missing crosswalk fields: " + repr(missing))
            selected_columns = {name: loaded[name] for name in ALLOWED_CROSSWALK_FIELDS}
        if any(value.dtype.hasobject or value.dtype.kind == "O" for value in selected_columns.values()):
            raise RuntimeError("object dtype forbidden in selected crosswalk columns")
        if len({len(value) for value in selected_columns.values()}) != 1:
            raise RuntimeError("selected crosswalk column length drift")
        if len(selected_columns["global_index"]) != core.EXPECTED_SELECTED_TOTAL:
            raise RuntimeError("selected crosswalk event count drift")

        for code, (name, bbox) in COHORTS.items():
            indices = np.flatnonzero(np.asarray(selected_columns["cohort_code"]) == code)
            selected = [{
                "global_index": int(selected_columns["global_index"][index]),
                "cohort_code": code, "evid": float(selected_columns["evid"][index]),
                "epoch": float(selected_columns["event_time_epoch"][index]),
                "lat": float(selected_columns["lat_reloc"][index]),
                "lon": float(selected_columns["lon_reloc"][index]),
                "depth": float(selected_columns["dep_reloc"][index]),
                "mag": float(selected_columns["mag"][index]),
                "nc_sc": str(selected_columns["nc_sc"][index]),
            } for index in indices]
            features, query_receipts = module.fetch_comcat(ephemeral, code, bbox)
            matched_rows, summary = module.match(selected, features)
            all_rows.extend(matched_rows); all_query_receipts.extend(query_receipts)
            matched = [row for row in matched_rows if row.get("matched")]
            horizontal = [row for row in matched if row.get("horizontalError_km") is not None and math.isfinite(float(row["horizontalError_km"]))]
            depth = [row for row in matched if row.get("depthError_km") is not None and math.isfinite(float(row["depthError_km"]))]
            both = [row for row in matched if row.get("horizontalError_km") is not None and row.get("depthError_km") is not None and math.isfinite(float(row["horizontalError_km"])) and math.isfinite(float(row["depthError_km"]))]
            alias_hits = [row for row in matched if row.get("alias_hit")]
            summary = {**summary, "comcat_events_in_bbox": len(features),
                       "matched_with_horizontal_error": len(horizontal),
                       "matched_with_depth_error": len(depth),
                       "matched_with_both_errors": len(both),
                       "both_errors_fraction_among_matches": len(both)/len(matched) if matched else 0.0,
                       "alias_hit_count": len(alias_hits),
                       "alias_hit_fraction_among_matches": len(alias_hits)/len(matched) if matched else 0.0,
                       "horizontal_error_km_quantiles": finite_quantiles([row["horizontalError_km"] for row in horizontal]),
                       "depth_error_km_quantiles": finite_quantiles([row["depthError_km"] for row in depth]),
                       "match_dt_seconds_quantiles": finite_quantiles([row["dt_seconds"] for row in matched]),
                       "match_horizontal_distance_km_quantiles": finite_quantiles([row["horizontal_distance_km"] for row in matched]),
                       "match_depth_difference_km_quantiles": finite_quantiles([row["depth_difference_km"] for row in matched]),
                       "match_magnitude_difference_quantiles": finite_quantiles([row["magnitude_difference"] for row in matched]),
                       "crosswalk_rows_sha256": rows_digest(matched_rows)}
            cohort_results[name] = summary

        query_manifest = safe_query_receipts(all_query_receipts)
        write_json(output_dir / "COMCAT_CSV_QUERY_RECEIPT_MANIFEST_V0_17_1.json", query_manifest)
        pass_coverage = all(float(cohort_results[name]["both_errors_fraction"]) >= MINIMUM_BOTH_ERRORS_FRACTION for name, _bbox in COHORTS.values())
        outcome = "LOCATION_UNCERTAINTY_CSV_CROSSWALK_PASS" if pass_coverage else "NOT_IDENTIFIABLE_LOCATION_UNCERTAINTY_CSV_COVERAGE"
        body = {
            "format": "KCH_HELICAL_V0_17_1_COMCAT_CSV_LOCATION_UNCERTAINTY_GATE_RESULT",
            "outcome": outcome, "protocol_id": EXPECTED_PROTOCOL_ID,
            "predecessor_gate_id": PREDECESSOR_GATE_ID,
            "predecessor_outcome": PREDECESSOR_OUTCOME,
            "predecessor_reclassified_as": "SOFTWARE_INTERFACE_SCHEMA_MISMATCH_NOT_SCIENTIFIC_NONIDENTIFIABILITY",
            "predecessor_parent_graph_lock_id": EXPECTED_PARENT_GRAPH_LOCK_ID,
            "predecessor_location_operator_id": EXPECTED_LOCATION_OPERATOR_ID,
            "v011_preflight_result_id": v011_preflight["preflight_result_id"],
            "v011_preflight_outcome": v011_preflight["outcome"],
            "interface_correction": {
                "predecessor_format": "geojson_summary", "corrected_format": "csv",
                "reason": "DECLARED_LOCATION_ERROR_FIELDS_ABSENT_FROM_GEOJSON_SUMMARY_SCHEMA_AND_PRESENT_IN_CSV_SCHEMA",
                "scientific_selection_changed": False, "matching_thresholds_changed": False,
                "ambiguity_rule_changed": False, "materiality_threshold_changed": False,
            },
            "csv_adapter": {"path": CSV_ADAPTER_PATH,
                            "git_blob_sha1": CSV_ADAPTER_GIT_BLOB_SHA1,
                            "sha256": sha256_path(source),
                            "required_columns": sorted(module.CSV_REQUIRED_COLUMNS)},
            "historical_matching_operator": {
                "source_commit": HISTORICAL_MATCH_OPERATOR_COMMIT,
                "git_blob_sha1": HISTORICAL_MATCH_OPERATOR_BLOB,
                "match_rule": {"time_seconds": 2.0, "horizontal_km": 15.0,
                               "depth_km": 20.0, "magnitude": 1.5,
                               "score": "(dt/1)^2+(h/5)^2+(dz/10)^2+(dmag/0.5)^2-4*alias_hit",
                               "ambiguity_margin": 0.25},
                "minimum_both_errors_fraction_per_cohort": MINIMUM_BOTH_ERRORS_FRACTION,
            },
            "selected_event_count": int(len(selected_columns["global_index"])),
            "cohorts": cohort_results, "crosswalk_all_rows_sha256": rows_digest(all_rows),
            "query_manifest_id": query_manifest["manifest_id"],
            "query_page_count": query_manifest["page_count"],
            "query_total_response_bytes": query_manifest["total_response_bytes"],
            "query_total_response_rows": query_manifest["total_response_rows"],
            "observed_csv_columns": query_manifest["observed_csv_columns"],
            "crosswalk_rows_exported": False, "event_identifiers_exported": False,
            "raw_comcat_rows_exported": False, "source_catalog_rows_exported": False,
            "directional_rows_exported": False, "sealed_test_accessed": False,
            "sealed_test_scored": False, "train_calibration_test_partition_constructed": False,
            "location_perturbation_draws_executed": False,
            "null_family_execution_performed": False,
            "scientific_model_execution_performed": False,
            "scientific_result": None, "physical_helicity": "NOT_EVALUATED",
            "authority_ceiling": "FINITE_LOCATION_UNCERTAINTY_CSV_CORRECTION_ONLY",
            "promotion": "BLOCKED", "canonicalization": "BLOCKED",
            "raw_comcat_rows_purged": True,
        }
        body["gate_id"] = content_id("h171loc", body)
        write_json(output_dir / "COMCAT_CSV_LOCATION_UNCERTAINTY_GATE_RESULT_V0_17_1.json", body)
        return body
    finally:
        shutil.rmtree(ephemeral, ignore_errors=True)


def patched_directional_preflight(directional_npz: Path, fault_path: Path,
                                  protocol: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    preflight = _ORIGINAL_DIRECTIONAL_PREFLIGHT(directional_npz, fault_path, protocol, output_dir)
    if not preflight.get("directional_execution_authorized"):
        return preflight
    location = execute_location_uncertainty_csv_gate(directional_npz, output_dir, preflight)
    combined = dict(preflight)
    combined.update({"v011_preflight_result_id": preflight["preflight_result_id"],
                     "v011_preflight_outcome": preflight["outcome"],
                     "location_gate_result_id": location["gate_id"],
                     "location_gate_outcome": location["outcome"],
                     "directional_execution_authorized": location["outcome"] == "LOCATION_UNCERTAINTY_CSV_CROSSWALK_PASS",
                     "outcome": location["outcome"],
                     "preflight_result_id": location["gate_id"],
                     "authority_ceiling": "FINITE_LOCATION_UNCERTAINTY_CSV_CORRECTION_ONLY"})
    return combined


def workspace_from_argv(argv: list[str]) -> Path:
    try:
        index = argv.index("--workspace"); return Path(argv[index + 1]).resolve()
    except (ValueError, IndexError) as error:
        raise RuntimeError("--workspace is required") from error


def main() -> int:
    workspace = workspace_from_argv(sys.argv[1:])
    core.directional_preflight = patched_directional_preflight
    core_exit = core.main()
    results = workspace / "results"
    location_path = results / "COMCAT_CSV_LOCATION_UNCERTAINTY_GATE_RESULT_V0_17_1.json"
    core_run_path = results / "RUN_RECEIPT_V0_11.json"
    location = json.loads(location_path.read_text(encoding="utf-8")) if location_path.exists() else None
    core_run = json.loads(core_run_path.read_text(encoding="utf-8")) if core_run_path.exists() else None
    if location is not None:
        outcome = location["outcome"]
        exit_code = 0 if outcome == "LOCATION_UNCERTAINTY_CSV_CROSSWALK_PASS" else 30
    else:
        outcome = "COMCAT_CSV_LOCATION_UNCERTAINTY_GATE_FAILED_CLOSED"; exit_code = 50
    receipt = {
        "format": "KCH_HELICAL_V0_17_1_COMCAT_CSV_LOCATION_UNCERTAINTY_RUN_RECEIPT",
        "outcome": outcome, "exit_code": exit_code, "core_exit_code": core_exit,
        "protocol_id": EXPECTED_PROTOCOL_ID, "predecessor_gate_id": PREDECESSOR_GATE_ID,
        "predecessor_parent_graph_lock_id": EXPECTED_PARENT_GRAPH_LOCK_ID,
        "predecessor_location_operator_id": EXPECTED_LOCATION_OPERATOR_ID,
        "location_gate_id": location.get("gate_id") if location else None,
        "query_manifest_id": location.get("query_manifest_id") if location else None,
        "v011_core_run_receipt_id": core_run.get("run_receipt_id") if core_run else None,
        "selected_event_count": location.get("selected_event_count") if location else None,
        "cohorts": location.get("cohorts") if location else None,
        "interface_correction": location.get("interface_correction") if location else None,
        "next_material_gate": "FULL_6376_JOB_CALIBRATION_ONLY_RUNTIME_EXECUTION_NO_TEST_ACCESS" if exit_code == 0 else "NEW_LOCATION_UNCERTAINTY_SOURCE_OR_PROTOCOL_AMENDMENT_REQUIRED",
        "raw_sources_purged": bool(core_run and core_run.get("raw_sources_purged")),
        "blind_rows_purged": bool(core_run and core_run.get("blind_npz_purged")),
        "selected_indices_purged": bool(core_run and core_run.get("selected_indices_purged")),
        "directional_rows_purged": bool(core_run and core_run.get("directional_rows_purged")),
        "raw_comcat_rows_purged": bool(location and location.get("raw_comcat_rows_purged")),
        "event_identifiers_exported": False, "crosswalk_rows_exported": False,
        "sealed_test_accessed": False, "sealed_test_scored": False,
        "train_calibration_test_partition_constructed": False,
        "location_perturbation_draws_executed": False,
        "null_family_execution_performed": False,
        "scientific_model_execution_performed": False,
        "scientific_result": None, "physical_helicity": "NOT_EVALUATED",
        "authority_consumed": True,
        "authority_terminal_status": "CONSUMED_SUCCESS" if exit_code in {0, 30} else "CONSUMED_FAIL_CLOSED",
        "authority_ceiling": "FINITE_LOCATION_UNCERTAINTY_CSV_CORRECTION_ONLY",
        "promotion": "BLOCKED", "canonicalization": "BLOCKED",
    }
    receipt["run_receipt_id"] = content_id("h171run", receipt)
    write_json(results / "RUN_RECEIPT_V0_17_1.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
