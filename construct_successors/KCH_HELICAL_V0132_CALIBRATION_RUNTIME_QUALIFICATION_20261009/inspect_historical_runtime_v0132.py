from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_id(prefix: str, body: dict[str, Any]) -> str:
    material = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return f"{prefix}:{hashlib.sha256(material).hexdigest()}"


def inspect_python(path: Path, root: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imports: set[str] = set()
    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    cli_arguments: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({"name": node.name, "line": node.lineno, "arguments": [arg.arg for arg in node.args.args], "async": isinstance(node, ast.AsyncFunctionDef)})
        elif isinstance(node, ast.ClassDef):
            classes.append({"name": node.name, "line": node.lineno})
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_argument" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    cli_arguments.append(first.value)

    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "imports": sorted(imports),
        "functions": sorted(functions, key=lambda item: (item["line"], item["name"])),
        "classes": sorted(classes, key=lambda item: (item["line"], item["name"])),
        "cli_arguments": sorted(set(cli_arguments)),
    }


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return {"command": command, "exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.source_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)

    files = sorted(path for path in root.rglob("*") if path.is_file())
    python_files = [path for path in files if path.suffix == ".py"]
    inventory = [{"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in files]
    python_inventory = [inspect_python(path, root) for path in python_files]

    required = {
        "null_runtime": root / "src/kch_helical_dynamic_v08/null_runtime.py",
        "tests": root / "tests_v0_8_4/test_null_runtime.py",
        "freeze_compiler": root / "tools/freeze_null_perturbation_runtime.py",
    }
    missing = sorted(name for name, path in required.items() if not path.is_file())
    if missing:
        raise RuntimeError(f"missing reconstructed files: {missing}")

    py_compile = run_command([sys.executable, "-m", "py_compile", *[str(path) for path in python_files]], cwd=root)
    pytest = run_command([sys.executable, "-m", "pytest", "-q", "tests_v0_8_4/test_null_runtime.py", "--disable-warnings", "--maxfail=1"], cwd=root)
    freeze_help = run_command([sys.executable, str(required["freeze_compiler"]), "--help"], cwd=root)

    all_pass = py_compile["exit_code"] == 0 and pytest["exit_code"] == 0 and freeze_help["exit_code"] == 0
    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_13_2_HISTORICAL_RUNTIME_INSPECTION",
        "source_file_count": len(files),
        "python_file_count": len(python_files),
        "inventory": inventory,
        "python_inventory": python_inventory,
        "required_paths": {name: path.relative_to(root).as_posix() for name, path in required.items()},
        "py_compile": py_compile,
        "pytest": pytest,
        "freeze_compiler_help": freeze_help,
        "all_pass": all_pass,
        "scientific_execution_performed": False,
        "calibration_data_accessed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "authority_ceiling": "SOURCE_RECONSTRUCTION_AND_SOFTWARE_INSPECTION_ONLY"
    }
    body["inspection_id"] = canonical_id("h132inspect", body)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"inspection_id": body["inspection_id"], "all_pass": all_pass}, sort_keys=True))
    return 0 if all_pass else 20


if __name__ == "__main__":
    raise SystemExit(main())
