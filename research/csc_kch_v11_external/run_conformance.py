#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, **kwargs)


def opa_decision(opa: str, policy: Path, payload: dict[str, Any]) -> dict[str, Any]:
    result = run(
        [opa, "eval", "--format=json", "--data", str(policy), "--stdin-input", "data.csc.kch.support.decision"],
        input=json.dumps(payload),
    )
    if result.returncode != 0:
        raise RuntimeError(f"OPA failed: {result.stdout}\n{result.stderr}")
    document = json.loads(result.stdout)
    return document["result"][0]["expressions"][0]["value"]


def cedar_decision(cedar: str, policy: Path, request: dict[str, Any], directory: Path) -> bool:
    request_path = directory / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    result = run([cedar, "authorize", "--policies", str(policy), "--request-json", str(request_path)])
    stdout = result.stdout.upper()
    if "ALLOW" in stdout:
        return True
    if "DENY" in stdout:
        return False
    raise RuntimeError(f"Unexpected Cedar result rc={result.returncode}: {result.stdout}\n{result.stderr}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vectors", type=Path, required=True)
    parser.add_argument("--rego", type=Path, required=True)
    parser.add_argument("--cedar-policy", type=Path, required=True)
    parser.add_argument("--opa", required=True)
    parser.add_argument("--cedar", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    vectors = json.loads(args.vectors.read_text(encoding="utf-8"))
    mismatches = []
    counts = {"vectors": len(vectors), "expected_support": 0, "opa_support": 0, "cedar_support": 0}

    opa_check = run([args.opa, "check", "--strict", str(args.rego)])
    if opa_check.returncode != 0:
        raise RuntimeError(f"OPA check failed: {opa_check.stdout}\n{opa_check.stderr}")
    cedar_check = run([args.cedar, "check-parse", "--policies", str(args.cedar_policy)])
    if cedar_check.returncode != 0:
        raise RuntimeError(f"Cedar parse failed: {cedar_check.stdout}\n{cedar_check.stderr}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for row in vectors:
            expected = bool(row["expected"]["support"])
            counts["expected_support"] += int(expected)
            opa = opa_decision(args.opa, args.rego, row["rego_input"])
            opa_support = opa.get("result") == "SUPPORT"
            counts["opa_support"] += int(opa_support)
            cedar_support = cedar_decision(args.cedar, args.cedar_policy, row["cedar_request"], tmp_path)
            counts["cedar_support"] += int(cedar_support)
            if expected != opa_support or expected != cedar_support:
                mismatches.append({"vector_id": row["vector_id"], "expected": expected, "opa": opa, "cedar": cedar_support})

    output = {**counts, "mismatch_count": len(mismatches), "mismatches": mismatches[:100], "passed": not mismatches}
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
