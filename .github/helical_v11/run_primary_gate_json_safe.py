from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


def normalize(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    return value


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("kch_terminal_primary_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--directional", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    module = load_module(args.script)
    original_dumps = json.dumps

    def safe_dumps(value: Any, *positional: Any, **kwargs: Any) -> str:
        return original_dumps(normalize(value), *positional, **kwargs)

    def canonical(value: Any) -> bytes:
        return original_dumps(
            normalize(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    def write_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            original_dumps(
                normalize(value),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            ) + "\n",
            encoding="utf-8",
        )

    module.canonical = canonical
    module.write_json = write_json
    module.json.dumps = safe_dumps
    sys.argv = [
        str(args.script),
        "--directional", str(args.directional),
        "--preflight", str(args.preflight),
        "--protocol", str(args.protocol),
        "--out", str(args.out),
    ]
    try:
        code = int(module.main())
    except SystemExit as exc:
        code = int(exc.code or 0)
    receipt = {
        "format": "KCH_NUMPY_JSON_CANONICALIZATION_REPAIR_V1_1",
        "scientific_model_changed": False,
        "thresholds_changed": False,
        "only_numpy_scalars_and_arrays_converted_to_native_json_types": True,
        "stdout_json_serialization_intercepted": True,
        "base_script_sha256": hashlib.sha256(args.script.read_bytes()).hexdigest(),
        "authority_ceiling": "NONE",
    }
    receipt["receipt_id"] = "s11json:" + hashlib.sha256(canonical(receipt)).hexdigest()
    write_json(args.out / "JSON_CANONICALIZATION_REPAIR_RECEIPT.json", receipt)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
