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
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def literal_or_shape(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return {"name": node.id}
    if isinstance(node, ast.Attribute):
        return {"attribute": ast.unparse(node)}
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [literal_or_shape(item) for item in node.elts]
    if isinstance(node, ast.Dict):
        return {
            str(literal_or_shape(key)): literal_or_shape(value)
            for key, value in zip(node.keys, node.values)
            if key is not None
        }
    return {"ast": type(node).__name__, "source": ast.unparse(node)}


def ast_surface(source: str, filename: str) -> dict[str, Any]:
    tree = ast.parse(source, filename=filename)
    functions: list[dict[str, Any]] = []
    classes: list[str] = []
    imports: list[str] = []
    cli_options: list[str] = []
    option_calls: list[dict[str, Any]] = []
    top_level_calls: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(
                {
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "kwonlyargs": [arg.arg for arg in node.args.kwonlyargs],
                    "lineno": node.lineno,
                }
            )
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "") + ":" + ",".join(alias.name for alias in node.names))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            positional = [literal_or_shape(arg) for arg in node.args]
            keywords = {
                kw.arg: literal_or_shape(kw.value)
                for kw in node.keywords
                if kw.arg is not None
            }
            for value in positional:
                if isinstance(value, str) and value.startswith("-"):
                    cli_options.append(value)
            option_calls.append(
                {
                    "lineno": node.lineno,
                    "positional": positional,
                    "keywords": keywords,
                }
            )

    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            top_level_calls.append(ast.unparse(node.value.func))
        elif isinstance(node, ast.If):
            top_level_calls.append("if:" + ast.unparse(node.test))

    return {
        "module_docstring": ast.get_docstring(tree),
        "functions": sorted(functions, key=lambda item: (item["name"], item["lineno"])),
        "classes": sorted(set(classes)),
        "imports": sorted(set(imports)),
        "cli_options": sorted(set(cli_options)),
        "add_argument_calls": option_calls,
        "top_level_shapes": top_level_calls,
        "ast_dump_sha256": sha256_bytes(
            ast.dump(tree, annotate_fields=True, include_attributes=False).encode("utf-8")
        ),
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
    observed_blob = git(repo, "rev-parse", f"{COMMIT}:{TRANSPORT_PATH}").decode("ascii").strip()
    if observed_blob != EXPECTED_BLOB:
        raise RuntimeError(f"independent compiler blob mismatch: {observed_blob}")

    raw_transport = git(repo, "show", f"{COMMIT}:{TRANSPORT_PATH}")
    compact = b"".join(raw_transport.split())
    compressed = base64.b64decode(compact, validate=True)
    decoded = gzip.decompress(compressed)
    source = decoded.decode("utf-8", errors="strict")
    surface = ast_surface(source, TRANSPORT_PATH)

    function_names = {entry["name"] for entry in surface["functions"]}
    if not function_names:
        raise RuntimeError("decoded compiler contains no functions")
    if "main" not in function_names:
        raise RuntimeError("decoded compiler has no main function")
    if not surface["add_argument_calls"]:
        raise RuntimeError("decoded compiler exposes no argparse surface")

    compiler = recovered / "freeze_null_perturbation_runtime.py"
    compiler.write_bytes(decoded)
    bytecode_path = receipts / "compiler_v0164_2.pyc"
    py_compile.compile(str(compiler), doraise=True, cfile=str(bytecode_path))
    bytecode_sha256 = sha256_bytes(bytecode_path.read_bytes())
    bytecode_bytes = bytecode_path.stat().st_size
    bytecode_path.unlink()

    ast_path = receipts / "INDEPENDENT_COMPILER_AST_SURFACE_V0_16_4_2.json"
    ast_path.write_text(json.dumps(surface, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    diagnostic: dict[str, Any]
    try:
        help_run = subprocess.run(
            [sys.executable, str(compiler), "--help"],
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
            env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "LC_ALL": "C.UTF-8",
                "LANG": "C.UTF-8",
            },
        )
        diagnostic_text = (
            f"returncode={help_run.returncode}\n"
            "[stdout]\n"
            f"{help_run.stdout}"
            "\n[stderr]\n"
            f"{help_run.stderr}"
        )
        diagnostic = {
            "attempted": True,
            "authoritative": False,
            "timed_out": False,
            "returncode": help_run.returncode,
            "classification": "DIAGNOSTIC_PASS" if help_run.returncode == 0 else "DIAGNOSTIC_NONZERO",
        }
    except subprocess.TimeoutExpired as exc:
        diagnostic_text = (
            "returncode=TIMEOUT\n"
            "[stdout]\n"
            f"{exc.stdout or ''}"
            "\n[stderr]\n"
            f"{exc.stderr or ''}"
        )
        diagnostic = {
            "attempted": True,
            "authoritative": False,
            "timed_out": True,
            "returncode": None,
            "classification": "DIAGNOSTIC_TIMEOUT",
        }

    diagnostic_path = receipts / "INDEPENDENT_COMPILER_EXECUTION_DIAGNOSTIC_V0_16_4_2.txt"
    diagnostic_path.write_text(diagnostic_text, encoding="utf-8")
    diagnostic["sha256"] = sha256_bytes(diagnostic_path.read_bytes())
    diagnostic["bytes"] = diagnostic_path.stat().st_size

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_16_4_2_AST_ONLY_COMPILER_RECOVERY_RECEIPT",
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
        "utf8_strict_decode": "PASS",
        "python_ast_parse": "PASS",
        "python_bytecode_compile_without_import": "PASS",
        "ephemeral_bytecode_bytes": bytecode_bytes,
        "ephemeral_bytecode_sha256": bytecode_sha256,
        "ast_surface_sha256": sha256_bytes(ast_path.read_bytes()),
        "ast_dump_sha256": surface["ast_dump_sha256"],
        "cli_options": surface["cli_options"],
        "add_argument_call_count": len(surface["add_argument_calls"]),
        "function_names": sorted(function_names),
        "class_names": surface["classes"],
        "execution_diagnostic": diagnostic,
        "execution_diagnostic_governs_recovery": False,
        "exact_independent_compiler_materialized": True,
        "corrupt_multi_file_archive_repaired": False,
        "ledger_rows_regenerated": False,
        "scientific_data_accessed": False,
        "calibration_executed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "AST_ONLY_HISTORICAL_COMPILER_RECOVERY",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "status": "PASS",
        "next_gate": "EXACT_6376_ROW_LEDGER_REGENERATION_AND_IDENTITY_GATE",
    }
    body["receipt_id"] = "h1642compiler:" + sha256_bytes(canonical(body))
    receipt_path = receipts / "AST_ONLY_COMPILER_RECOVERY_RECEIPT_V0_16_4_2.json"
    receipt_path.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    validation = {
        "format": "KCH_HELICAL_V0_16_4_2_AST_ONLY_COMPILER_RECOVERY_VALIDATION",
        "status": "PASS",
        "receipt_id": body["receipt_id"],
        "checks": {
            "git_blob_identity": observed_blob == EXPECTED_BLOB,
            "strict_base64_decode": True,
            "gzip_decompression": True,
            "strict_utf8_decode": True,
            "python_ast_parse": True,
            "main_function_present": "main" in function_names,
            "argparse_surface_present": bool(surface["add_argument_calls"]),
            "bytecode_compile_without_import": True,
            "historical_execution_is_non_authoritative": True,
            "ledger_not_regenerated": True,
            "scientific_data_not_accessed": True,
            "sealed_test_not_accessed": True,
        },
    }
    validation["validation_id"] = "h1642validation:" + sha256_bytes(canonical(validation))
    (receipts / "AST_ONLY_COMPILER_RECOVERY_VALIDATION_V0_16_4_2.json").write_text(
        json.dumps(validation, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "receipt_id": body["receipt_id"],
                "validation_id": validation["validation_id"],
                "compiler_sha256": body["decoded_compiler_sha256"],
                "cli_options": body["cli_options"],
                "diagnostic_classification": diagnostic["classification"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
