from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
MODULE = ROOT / "null_perturbation_operators_v016.py"
TESTS = ROOT / "test_null_perturbation_operators_v016.py"
CONTRACT = ROOT / "OPERATOR_CONTRACT_V0_16.json"
LEASE = ROOT / "AUTHORITY_LEASE_V0_16.json"
PREDECESSOR = ROOT.parent / "KCH_HELICAL_V0154_LOCKED_SINGLE_CHAR_REPAIR_QUORUM_20261010" / "receipts" / "HISTORICAL_RUNTIME_SOURCE_QUORUM_RECEIPT_V0_15_4.json"

REQUIRED = [
    "circular_distance_degrees", "compute_parent_state", "draw_static_fields", "eval_intensity",
    "head_to_normal", "make_rewired_null", "moving_block_resample", "permute_within_bins",
    "posterior_mark_expectations", "propagate_mechanism_uncertainty", "reflected_rake",
    "rewire_parent_graph", "score_null_metrics", "seeded_rng", "simulate_catalog",
    "simulate_nonhelical_fixed_parent_weights", "static_logodds",
]
ALLOWED_IMPORT_ROOTS = {"__future__", "collections", "dataclasses", "hashlib", "json", "math", "typing", "numpy"}
FORBIDDEN_TEXT = ("socket.", "requests.", "urllib.", "subprocess.", "pathlib.", "open(", "exec(", "eval(")
EXPECTED_NUMPY_VERSION = "2.1.3"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_id(prefix: str, body: dict) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return prefix + hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    receipt = {
        "format": "KCH_HELICAL_V0_16_EXPLICIT_NULL_OPERATOR_QUALIFICATION_RECEIPT",
        "started_at_utc": started,
        "authority_ceiling": "FINITE_CODE_ONLY_OPERATOR_QUALIFICATION",
        "predecessor_receipt_id": None,
        "status": "FAIL_CLOSED",
        "scientific_data_accessed": False,
        "sealed_test_accessed": False,
        "calibration_runtime_executed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    try:
        contract = json.loads(CONTRACT.read_text())
        lease = json.loads(LEASE.read_text())
        predecessor = json.loads(PREDECESSOR.read_text())
        assert predecessor["receipt_id"] == lease["predecessor_receipt_id"]
        assert predecessor["outcome"] == "HISTORICAL_RUNTIME_PARTIAL_SOURCE_ONLY"
        assert predecessor["exit_code"] == 30
        assert predecessor["scientific_data_accessed"] is False
        assert predecessor["sealed_test_accessed"] is False
        assert sorted(predecessor["required_symbols_missing"]) == sorted(REQUIRED)
        assert lease["scientific_data_access_authorized"] is False
        assert lease["sealed_test_access_authorized"] is False
        assert lease["operator_symbols"] == REQUIRED
        receipt["predecessor_receipt_id"] = predecessor["receipt_id"]

        source = MODULE.read_text()
        lower = source.lower()
        forbidden_hits = [item for item in FORBIDDEN_TEXT if item in lower]
        if forbidden_hits:
            raise RuntimeError(f"forbidden runtime capability token(s): {forbidden_hits}")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append((node.module or "").split(".")[0])
        unexpected = sorted(set(imports) - ALLOWED_IMPORT_ROOTS)
        if unexpected:
            raise RuntimeError(f"unexpected imports: {unexpected}")
        definitions = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        missing = sorted(set(REQUIRED) - definitions)
        if missing:
            raise RuntimeError(f"required definitions missing: {missing}")

        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", TESTS.name],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        test_count = stdout.count(" ... ok") + stderr.count(" ... ok")
        if completed.returncode != 0:
            raise RuntimeError(f"qualification tests failed rc={completed.returncode}\n{stdout}\n{stderr}")
        expected_tests = int(contract["qualification"]["expected_test_count"])
        if test_count != expected_tests:
            raise RuntimeError(f"test count mismatch: observed {test_count}, expected {expected_tests}")

        spec = importlib.util.spec_from_file_location("operators", MODULE)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        callable_missing = [name for name in REQUIRED if not callable(getattr(module, name, None))]
        if callable_missing:
            raise RuntimeError(f"non-callable operator symbols: {callable_missing}")
        if module.np.__version__ != EXPECTED_NUMPY_VERSION:
            raise RuntimeError(
                f"NumPy version mismatch: observed {module.np.__version__}, expected {EXPECTED_NUMPY_VERSION}"
            )

        receipt.update({
            "status": "EXPLICIT_NULL_OPERATOR_QUALIFICATION_PASS",
            "operator_symbol_count": len(REQUIRED),
            "operator_symbols": REQUIRED,
            "all_required_operators_callable": True,
            "test_count": test_count,
            "test_failures": 0,
            "module_sha256": sha256(MODULE),
            "tests_sha256": sha256(TESTS),
            "contract_sha256": sha256(CONTRACT),
            "authority_lease_sha256": sha256(LEASE),
            "numpy_version": module.np.__version__,
            "allowed_import_roots": sorted(ALLOWED_IMPORT_ROOTS),
            "forbidden_runtime_capabilities_observed": [],
            "historical_identity_claim": "NONE_NEW_SUCCESSOR_OPERATOR_LINEAGE",
            "next_gate": "CALIBRATION_ONLY_FULL_RUNTIME_QUALIFICATION_6376_JOBS_NO_TEST_ACCESS",
            "test_stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
            "test_stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
        })
        rc = 0
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
        receipt["error"] = str(exc)
        rc = 40
    receipt["completed_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = dict(receipt)
    receipt["receipt_id"] = content_id("h16opqual:", payload)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
