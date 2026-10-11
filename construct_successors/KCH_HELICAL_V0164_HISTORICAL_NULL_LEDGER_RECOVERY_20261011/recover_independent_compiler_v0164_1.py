#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys
from typing import Any

COMMIT = "e458afe20b8172db5a04194224cf21df5ec00dc4"
TRANSPORT_PATH = ".github/helical_v08_4/source_transport/freeze_null_perturbation_runtime_v2.py.gz.b64"
EXPECTED_BLOB = "ae09da82978c18a55afbe2811c04d9a9fc40849e"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def ast_surface(source: str, filename: str) -> dict[str, Any]:
    tree = ast.parse(source, filename=filename)
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []
    cli_options: list[str] = []
    option_calls: list[dict[str, Any]] = []
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
            positional: list[str] = []
            keywords: dict[str, Any] = {}
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    positional.append(arg.value)
                    if arg.value.startswith("-"):
                        cli_options.append(arg.value)
            for kw in node.keywords:
                if kw.arg is None:
                    continue
                if isinstance(kw.value, ast.Constant):
                    keywords[kw.arg] = kw.value.value
                elif isinstance(kw.value, ast.Name):
                    keywords[kw.arg] = {"name": kw.value.id}
                elif isinstance(kw.value, ast.Attribute):
                    keywords[kw.arg] = {"attribute": ast.unparse(kw.value)}
                else:
                    keywords[kw.arg] = {"ast": type(kw.value).__name__}
            option_calls.append({"positional": positional, "keywords": keywords})
    return {
        "functions": sorted(set(functions)),
        "classes": sorted(set(classes)),
        "imports": sorted(set(imports)),
        "cli_options": sorted(set(cli_options)),
        "add_argument_calls": option_calls,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    root = args.root.resolve()
    recovered = root / "recovered_exact" / "tools"
    receipts = root / "receipts"
    recovered.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)

    git(repo, "cat-file", "-e", f"{COMMIT}^{{commit}}")
    observed_blob = git(repo, "rev-parse", f"{COMMIT}:{TRANSPORT_PATH}").decode().strip()
    if observed_blob != EXPECTED_BLOB:
        raise RuntimeError(f"independent compiler blob mismatch: {observed_blob}")

    raw_transport = git(repo, "show", f"{COMMIT}:{TRANSPORT_PATH}")
    compact = b"".join(raw_transport.split())
    compressed = base64.b64decode(compact, validate=True)
    decoded = gzip.decompress(compressed)
    source = decoded.decode("utf-8", errors="strict")
    surface = ast_surface(source, TRANSPORT_PATH)
    if not surface["functions"]:
        raise RuntimeError("decoded compiler contains no functions")

    compiler = recovered / "freeze_null_perturbation_runtime.py"
    compiler.write_bytes(decoded)
    py_compile.compile(str(compiler), doraise=True, cfile=str(root / "receipts" / "compiler_v0164_1.pyc"))
    (root / "receipts" / "compiler_v0164_1.pyc").unlink(missing_ok=True)

    help_run = subprocess.run([sys.executable, str(compiler), "--help"], text=True, capture_output=True)
    help_text = help_run.stdout + ("\n[stderr]\n" + help_run.stderr if help_run.stderr else "")
    help_path = receipts / "INDEPENDENT_COMPILER_HELP_V0_16_4_1.txt"
    help_path.write_text(help_text, encoding="utf-8")
    if help_run.returncode != 0:
        raise RuntimeError(f"compiler --help failed with {help_run.returncode}")

    ast_path = receipts / "INDEPENDENT_COMPILER_AST_SURFACE_V0_16_4_1.json"
    ast_path.write_text(json.dumps(surface, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_16_4_1_INDEPENDENT_COMPILER_RECOVERY_RECEIPT",
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "source_commit": COMMIT,
        "transport_path": TRANSPORT_PATH,
        "expected_git_blob_sha1": EXPECTED_BLOB,
        "observed_git_blob_sha1": observed_blob,
        "transport_raw_bytes": len(raw_transport),
        "transport_raw_sha256": sha256_bytes(raw_transport),
        "compact_base64_bytes": len(compact),
        "compact_base64_sha256": sha256_bytes(compact),
        "compressed_bytes": len(compressed),
        "compressed_sha256": sha256_bytes(compressed),
        "decoded_compiler_bytes": len(decoded),
        "decoded_compiler_sha256": sha256_bytes(decoded),
        "compiler_help_sha256": sha256_bytes(help_text.encode()),
        "ast_surface_sha256": sha256_bytes(ast_path.read_bytes()),
        "cli_options": surface["cli_options"],
        "function_count": len(surface["functions"]),
        "class_count": len(surface["classes"]),
        "exact_independent_compiler_materialized": True,
        "corrupt_multi_file_archive_repaired": False,
        "ledger_rows_regenerated": False,
        "scientific_data_accessed": False,
        "calibration_executed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "INDEPENDENT_HISTORICAL_COMPILER_RECOVERY_ONLY",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "status": "PASS",
        "next_gate": "EXACT_6376_ROW_LEDGER_REGENERATION_AND_IDENTITY_GATE",
    }
    body["receipt_id"] = "h1641compiler:" + sha256_bytes(canonical(body))
    (receipts / "INDEPENDENT_COMPILER_RECOVERY_RECEIPT_V0_16_4_1.json").write_text(
        json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "receipt_id": body["receipt_id"],
        "compiler_sha256": body["decoded_compiler_sha256"],
        "cli_options": body["cli_options"],
        "function_count": body["function_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
