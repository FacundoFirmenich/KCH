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

import helical_v011_directional_pretest as v11

core = v11.core
_ORIGINAL_DIRECTIONAL_PREFLIGHT = core.directional_preflight

EXPECTED_PROTOCOL_ID = "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
EXPECTED_PARENT_GRAPH_LOCK_ID = "h8parent:f61e9b60c455e75e53f16b9579cd085b68de20d810f05165504f91ab09d400cb"
EXPECTED_LOCATION_OPERATOR_ID = "h12locop:6b3fcf56d1f427d107e5e5dbb264aba02f871c93708a5796074fd0916d89b1b5"
EXPECTED_CROSSWALK_COMMIT = "e458afe20b8172db5a04194224cf21df5ec00dc4"
EXPECTED_CROSSWALK_BLOB_SHA1 = "cfa0ee325d573679db497636e28fbc5b6e2b628e"
MINIMUM_BOTH_ERRORS_FRACTION = 0.80
COHORTS = {
    0: ("BAY_AREA_HAYWARD_CALAVERAS", (36.85, 38.45, -122.75, -121.15)),
    1: ("PARKFIELD_CENTRAL_SAF", (35.45, 36.25, -121.05, -119.95)),
}
ALLOWED_CROSSWALK_FIELDS = (
    "global_index", "cohort_code", "evid", "event_time_epoch",
    "lat_reloc", "lon_reloc", "dep_reloc", "mag", "nc_sc",
)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


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
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_crosswalk_module():
    source = Path(os.environ["KCH_V08_COMCAT_CROSSWALK_SOURCE"]).resolve()
    if not source.is_file():
        raise RuntimeError(f"frozen crosswalk source missing: {source}")
    spec = importlib.util.spec_from_file_location("kch_frozen_v08_comcat_crosswalk", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen crosswalk source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, source


def finite_quantiles(values: list[float]) -> dict[str, float] | None:
    array = np.asarray([float(value) for value in values if value is not None], dtype=np.float64)
    array = array[np.isfinite(array)]
    if len(array) == 0:
        return None
    levels = np.asarray([0.0, 0.25, 0.50, 0.75, 0.95, 0.99, 1.0], dtype=np.float64)
    observed = np.quantile(array, levels, method="linear")
    return {
        "count": int(len(array)),
        "min": float(observed[0]),
        "q25": float(observed[1]),
        "median": float(observed[2]),
        "q75": float(observed[3]),
        "q95": float(observed[4]),
        "q99": float(observed[5]),
        "max": float(observed[6]),
    }


def rows_digest(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(canonical(row))
        digest.update(b"\n")
    return digest.hexdigest()


def safe_query_receipts(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    safe_rows: list[dict[str, Any]] = []
    for row in receipts:
        headers = row.get("headers") or {}
        safe_rows.append({
            "cohort": row.get("cohort"),
            "year": int(row["year"]),
            "page": int(row["page"]),
            "offset": int(row["offset"]),
            "status": int(row["status"]),
            "bytes": int(row["bytes"]),
            "sha256": str(row["sha256"]),
            "etag": headers.get("ETag") or headers.get("Etag") or headers.get("etag"),
            "last_modified": headers.get("Last-Modified") or headers.get("last-modified"),
            "content_type": headers.get("Content-Type") or headers.get("content-type"),
        })
    body = {
        "format": "KCH_HELICAL_V0_17_COMCAT_QUERY_RECEIPT_MANIFEST",
        "page_count": len(safe_rows),
        "total_response_bytes": int(sum(row["bytes"] for row in safe_rows)),
        "pages": safe_rows,
        "raw_urls_exported": False,
        "raw_event_rows_exported": False,
        "credentials_supplied": False,
        "authenticated_api_used": False,
    }
    body["manifest_id"] = content_id("h17comcatqueries", body)
    return body


def execute_location_uncertainty_gate(
    directional_npz: Path,
    output_dir: Path,
    v011_preflight: dict[str, Any],
) -> dict[str, Any]:
    module, source = load_crosswalk_module()
    ephemeral = output_dir.parent / "comcat_location_crosswalk_ephemeral"
    shutil.rmtree(ephemeral, ignore_errors=True)
    ephemeral.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    all_query_receipts: list[dict[str, Any]] = []
    cohort_results: dict[str, dict[str, Any]] = {}
    try:
        with np.load(directional_npz, allow_pickle=False) as loaded:
            missing = sorted(set(ALLOWED_CROSSWALK_FIELDS) - set(loaded.files))
            if missing:
                raise RuntimeError(f"selected directional schema missing crosswalk fields: {missing}")
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
                "cohort_code": code,
                "evid": float(selected_columns["evid"][index]),
                "epoch": float(selected_columns["event_time_epoch"][index]),
                "lat": float(selected_columns["lat_reloc"][index]),
                "lon": float(selected_columns["lon_reloc"][index]),
                "depth": float(selected_columns["dep_reloc"][index]),
                "mag": float(selected_columns["mag"][index]),
                "nc_sc": str(selected_columns["nc_sc"][index]),
            } for index in indices]

            features, query_receipts = module.fetch_comcat(ephemeral, code, bbox)
            matched_rows, summary = module.match(selected, features)
            all_rows.extend(matched_rows)
            all_query_receipts.extend(query_receipts)

            both = [
                row for row in matched_rows
                if row.get("matched")
                and row.get("horizontalError_km") is not None
                and row.get("depthError_km") is not None
                and math.isfinite(float(row["horizontalError_km"]))
                and math.isfinite(float(row["depthError_km"]))
            ]
            matched = [row for row in matched_rows if row.get("matched")]
            alias_hits = [row for row in matched if row.get("alias_hit")]
            summary = {
                **summary,
                "comcat_events_in_bbox": len(features),
                "matched_with_both_errors": len(both),
                "alias_hit_count": len(alias_hits),
                "alias_hit_fraction_among_matches": (
                    len(alias_hits) / len(matched) if matched else 0.0
                ),
                "horizontal_error_km_quantiles": finite_quantiles(
                    [row["horizontalError_km"] for row in both]
                ),
                "depth_error_km_quantiles": finite_quantiles(
                    [row["depthError_km"] for row in both]
                ),
                "match_dt_seconds_quantiles": finite_quantiles(
                    [row["dt_seconds"] for row in matched]
                ),
                "match_horizontal_distance_km_quantiles": finite_quantiles(
                    [row["horizontal_distance_km"] for row in matched]
                ),
                "match_depth_difference_km_quantiles": finite_quantiles(
                    [row["depth_difference_km"] for row in matched]
                ),
                "match_magnitude_difference_quantiles": finite_quantiles(
                    [row["magnitude_difference"] for row in matched]
                ),
                "crosswalk_rows_sha256": rows_digest(matched_rows),
            }
            cohort_results[name] = summary

        query_manifest = safe_query_receipts(all_query_receipts)
        write_json(output_dir / "COMCAT_QUERY_RECEIPT_MANIFEST_V0_17.json", query_manifest)

        pass_coverage = all(
            float(cohort_results[name]["both_errors_fraction"]) >= MINIMUM_BOTH_ERRORS_FRACTION
            for name, _bbox in COHORTS.values()
        )
        outcome = (
            "LOCATION_UNCERTAINTY_CROSSWALK_PASS"
            if pass_coverage
            else "NOT_IDENTIFIABLE_LOCATION_UNCERTAINTY_COVERAGE"
        )
        body = {
            "format": "KCH_HELICAL_V0_17_COMCAT_LOCATION_UNCERTAINTY_GATE_RESULT",
            "outcome": outcome,
            "protocol_id": EXPECTED_PROTOCOL_ID,
            "predecessor_parent_graph_lock_id": EXPECTED_PARENT_GRAPH_LOCK_ID,
            "predecessor_location_operator_id": EXPECTED_LOCATION_OPERATOR_ID,
            "v011_preflight_result_id": v011_preflight["preflight_result_id"],
            "v011_preflight_outcome": v011_preflight["outcome"],
            "frozen_operator": {
                "source_commit": EXPECTED_CROSSWALK_COMMIT,
                "git_blob_sha1": EXPECTED_CROSSWALK_BLOB_SHA1,
                "source_sha256": sha256_path(source),
                "match_rule": {
                    "time_seconds": 2.0,
                    "horizontal_km": 15.0,
                    "depth_km": 20.0,
                    "magnitude": 1.5,
                    "score": "(dt/1)^2+(h/5)^2+(dz/10)^2+(dmag/0.5)^2-4*alias_hit",
                    "ambiguity_margin": 0.25,
                },
                "minimum_both_errors_fraction_per_cohort": MINIMUM_BOTH_ERRORS_FRACTION,
            },
            "selected_event_count": int(len(selected_columns["global_index"])),
            "cohorts": cohort_results,
            "crosswalk_all_rows_sha256": rows_digest(all_rows),
            "query_manifest_id": query_manifest["manifest_id"],
            "query_page_count": query_manifest["page_count"],
            "query_total_response_bytes": query_manifest["total_response_bytes"],
            "crosswalk_rows_exported": False,
            "event_identifiers_exported": False,
            "raw_comcat_rows_exported": False,
            "source_catalog_rows_exported": False,
            "directional_rows_exported": False,
            "sealed_test_accessed": False,
            "sealed_test_scored": False,
            "train_calibration_test_partition_constructed": False,
            "location_perturbation_draws_executed": False,
            "null_family_execution_performed": False,
            "scientific_model_execution_performed": False,
            "scientific_result": None,
            "physical_helicity": "NOT_EVALUATED",
            "authority_ceiling": "FINITE_LOCATION_UNCERTAINTY_CROSSWALK_ONLY",
            "promotion": "BLOCKED",
            "canonicalization": "BLOCKED",
            "raw_comcat_rows_purged": True,
        }
        body["gate_id"] = content_id("h17loc", body)
        write_json(output_dir / "COMCAT_LOCATION_UNCERTAINTY_GATE_RESULT_V0_17.json", body)
        return body
    finally:
        shutil.rmtree(ephemeral, ignore_errors=True)


def patched_directional_preflight(
    directional_npz: Path,
    fault_path: Path,
    protocol: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    preflight = _ORIGINAL_DIRECTIONAL_PREFLIGHT(
        directional_npz, fault_path, protocol, output_dir
    )
    if not preflight.get("directional_execution_authorized"):
        return preflight
    location = execute_location_uncertainty_gate(
        directional_npz, output_dir, preflight
    )
    combined = dict(preflight)
    combined.update({
        "v011_preflight_result_id": preflight["preflight_result_id"],
        "v011_preflight_outcome": preflight["outcome"],
        "location_gate_result_id": location["gate_id"],
        "location_gate_outcome": location["outcome"],
        "directional_execution_authorized": (
            location["outcome"] == "LOCATION_UNCERTAINTY_CROSSWALK_PASS"
        ),
        "outcome": location["outcome"],
        "preflight_result_id": location["gate_id"],
        "authority_ceiling": "FINITE_LOCATION_UNCERTAINTY_CROSSWALK_ONLY",
    })
    return combined


def workspace_from_argv(argv: list[str]) -> Path:
    try:
        index = argv.index("--workspace")
        return Path(argv[index + 1]).resolve()
    except (ValueError, IndexError) as error:
        raise RuntimeError("--workspace is required") from error


def main() -> int:
    workspace = workspace_from_argv(sys.argv[1:])
    core.directional_preflight = patched_directional_preflight
    core_exit = core.main()
    results = workspace / "results"
    location_path = results / "COMCAT_LOCATION_UNCERTAINTY_GATE_RESULT_V0_17.json"
    core_run_path = results / "RUN_RECEIPT_V0_11.json"
    location = json.loads(location_path.read_text(encoding="utf-8")) if location_path.exists() else None
    core_run = json.loads(core_run_path.read_text(encoding="utf-8")) if core_run_path.exists() else None

    if location is not None:
        outcome = location["outcome"]
        exit_code = 0 if outcome == "LOCATION_UNCERTAINTY_CROSSWALK_PASS" else 30
    else:
        outcome = "COMCAT_LOCATION_UNCERTAINTY_GATE_FAILED_CLOSED"
        exit_code = 50

    receipt = {
        "format": "KCH_HELICAL_V0_17_COMCAT_LOCATION_UNCERTAINTY_RUN_RECEIPT",
        "outcome": outcome,
        "exit_code": exit_code,
        "core_exit_code": core_exit,
        "protocol_id": EXPECTED_PROTOCOL_ID,
        "predecessor_parent_graph_lock_id": EXPECTED_PARENT_GRAPH_LOCK_ID,
        "predecessor_location_operator_id": EXPECTED_LOCATION_OPERATOR_ID,
        "location_gate_id": location.get("gate_id") if location else None,
        "query_manifest_id": location.get("query_manifest_id") if location else None,
        "v011_core_run_receipt_id": core_run.get("run_receipt_id") if core_run else None,
        "selected_event_count": location.get("selected_event_count") if location else None,
        "cohorts": location.get("cohorts") if location else None,
        "next_material_gate": (
            "FULL_6376_JOB_CALIBRATION_ONLY_RUNTIME_EXECUTION_NO_TEST_ACCESS"
            if exit_code == 0
            else "NEW_LOCATION_UNCERTAINTY_SOURCE_OR_PROTOCOL_AMENDMENT_REQUIRED"
        ),
        "raw_sources_purged": bool(core_run and core_run.get("raw_sources_purged")),
        "blind_rows_purged": bool(core_run and core_run.get("blind_npz_purged")),
        "selected_indices_purged": bool(core_run and core_run.get("selected_indices_purged")),
        "directional_rows_purged": bool(core_run and core_run.get("directional_rows_purged")),
        "raw_comcat_rows_purged": bool(location and location.get("raw_comcat_rows_purged")),
        "event_identifiers_exported": False,
        "crosswalk_rows_exported": False,
        "sealed_test_accessed": False,
        "sealed_test_scored": False,
        "train_calibration_test_partition_constructed": False,
        "location_perturbation_draws_executed": False,
        "null_family_execution_performed": False,
        "scientific_model_execution_performed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "authority_consumed": True,
        "authority_terminal_status": (
            "CONSUMED_SUCCESS" if exit_code in {0, 30} else "CONSUMED_FAIL_CLOSED"
        ),
        "authority_ceiling": "FINITE_LOCATION_UNCERTAINTY_CROSSWALK_ONLY",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    receipt["run_receipt_id"] = content_id("h17run", receipt)
    write_json(results / "RUN_RECEIPT_V0_17.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
