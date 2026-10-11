#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
from typing import Any

SOURCE_COMMIT = "e458afe20b8172db5a04194224cf21df5ec00dc4"
EXPECTED = {
    "compiler": "tools/freeze_null_perturbation_runtime.py",
    "runtime": "src/kch_helical_dynamic_v08/null_runtime.py",
    "tests": "tests_v0_8_4/test_null_runtime.py",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def unique_suffix(root: Path, suffix: str) -> Path:
    hits = [p for p in root.rglob(Path(suffix).name) if p.is_file() and p.as_posix().endswith(suffix)]
    if len(hits) != 1:
        raise RuntimeError(f"expected one {suffix}; got {len(hits)}")
    return hits[0]


def ast_surface(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []
    cli_options: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "") + ":" + ",".join(alias.name for alias in node.names))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("-"):
                    cli_options.append(arg.value)
    return {
        "functions": sorted(set(functions)),
        "classes": sorted(set(classes)),
        "imports": sorted(set(imports)),
        "cli_options": sorted(set(cli_options)),
        "source_sha256": sha256(path),
        "source_bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    root = args.root.resolve()
    scratch = args.scratch.resolve()
    controls = root / "controls"
    receipts = root / "receipts"
    recovered = root / "recovered_exact"
    receipts.mkdir(parents=True, exist_ok=True)
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    if recovered.exists():
        shutil.rmtree(recovered)
    recovered.mkdir(parents=True)

    contract = json.loads((controls / "FULL_NULL_AND_PERTURBATION_RUNTIME_CONTRACT_V0_13.json").read_text())
    summary = json.loads((controls / "NULL_PERTURBATION_JOB_LEDGER_SUMMARY_V0_13.json").read_text())
    status = json.loads((controls / "STATUS_V0_13.json").read_text())
    if contract["contract_id"] != "h13nullspec:bc68343eee99c797c27795b9c5e73b7bec63764f678ab4c195572281acf79dff":
        raise RuntimeError("v0.13 contract ID mismatch")
    if summary["ledger_id"] != "h13nullledger:6abcf3c64273d25a52d75fd423b6b825ee0b1a1b800aaf5d38acf98795179c2a":
        raise RuntimeError("v0.13 ledger ID mismatch")
    if status["freeze_id"] != "h13nullfreeze:1bc0b66c7030de5784f2a5c882b8b9e1069c628fef5919558c4415413cbea6d7":
        raise RuntimeError("v0.13 freeze ID mismatch")
    if summary["job_count"] != 6376 or summary["seed_unique_count"] != 6376:
        raise RuntimeError("v0.13 scheduled-job census mismatch")

    reconstructor = repo / "construct_successors/KCH_HELICAL_V0132_CALIBRATION_RUNTIME_QUALIFICATION_20261009/reconstruct_historical_v084_source.py"
    reconstructed = scratch / "historical_v084"
    reconstruction_receipt = receipts / "HISTORICAL_V084_SOURCE_RECONSTRUCTION_RECEIPT_V0_16_4.json"
    subprocess.run([
        sys.executable, str(reconstructor),
        "--repo-root", str(repo),
        "--output", str(reconstructed),
        "--receipt", str(reconstruction_receipt),
    ], check=True)

    reconstruction = json.loads(reconstruction_receipt.read_text())
    if reconstruction["source_commit"] != SOURCE_COMMIT:
        raise RuntimeError("historical source commit mismatch")
    if reconstruction["sealed_test_accessed"] is not False or reconstruction["scientific_execution_performed"] is not False:
        raise RuntimeError("historical recovery exceeded authority")

    materialized: dict[str, dict[str, Any]] = {}
    for label, suffix in EXPECTED.items():
        source = unique_suffix(reconstructed, suffix)
        destination = recovered / suffix
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        py_compile.compile(str(destination), doraise=True, cfile=str(scratch / f"{label}.pyc"))
        materialized[label] = {
            "historical_suffix": suffix,
            "materialized_path": destination.relative_to(repo).as_posix(),
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
            "ast_surface": ast_surface(destination),
        }

    compiler = recovered / EXPECTED["compiler"]
    help_run = subprocess.run([sys.executable, str(compiler), "--help"], text=True, capture_output=True)
    (receipts / "HISTORICAL_COMPILER_HELP_V0_16_4.txt").write_text(
        help_run.stdout + ("\n[stderr]\n" + help_run.stderr if help_run.stderr else ""), encoding="utf-8"
    )
    if help_run.returncode != 0:
        raise RuntimeError(f"historical compiler --help failed: {help_run.returncode}")

    surface = materialized["compiler"]["ast_surface"]
    if not surface["cli_options"]:
        raise RuntimeError("historical compiler exposes no argparse option surface")

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_16_4_HISTORICAL_NULL_RUNTIME_RECOVERY_RECEIPT",
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "source_commit": SOURCE_COMMIT,
        "v0_13_contract_id": contract["contract_id"],
        "v0_13_ledger_id": summary["ledger_id"],
        "v0_13_ledger_sha256_target": summary["ledger_sha256"],
        "v0_13_freeze_id": status["freeze_id"],
        "scheduled_job_count": summary["job_count"],
        "materialized": materialized,
        "compiler_help_sha256": sha256(receipts / "HISTORICAL_COMPILER_HELP_V0_16_4.txt"),
        "exact_compiler_materialized": True,
        "exact_null_runtime_materialized": True,
        "exact_historical_tests_materialized": True,
        "ledger_rows_regenerated": False,
        "calibration_executed": False,
        "scientific_data_accessed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "HISTORICAL_CODE_AND_LEDGER_COMPILER_RECOVERY_ONLY",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "status": "PASS",
        "next_gate": "EXACT_6376_ROW_LEDGER_REGENERATION_AND_IDENTITY_GATE",
    }
    body["receipt_id"] = "h164recovery:" + hashlib.sha256(canonical(body)).hexdigest()
    (receipts / "HISTORICAL_NULL_RUNTIME_RECOVERY_RECEIPT_V0_16_4.json").write_text(
        json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "receipt_id": body["receipt_id"],
        "compiler_sha256": materialized["compiler"]["sha256"],
        "runtime_sha256": materialized["runtime"]["sha256"],
        "tests_sha256": materialized["tests"]["sha256"],
        "cli_options": surface["cli_options"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
