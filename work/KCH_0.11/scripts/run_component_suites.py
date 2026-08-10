from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def run_one(spec: str) -> dict[str, object]:
    name, root_text, tests = spec.split("|", 2)
    root = Path(root_text).resolve()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    started = time.monotonic()
    process = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", tests, "-v"],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    duration = round(time.monotonic() - started, 3)
    matches = re.findall(r"Ran (\d+) tests?", process.stdout)
    count = int(matches[-1]) if matches else None
    return {
        "suite": name,
        "root": str(root),
        "test_directory": tests,
        "exit_code": process.returncode,
        "tests": count,
        "duration_seconds": duration,
        "state": "PASS" if process.returncode == 0 and count is not None else "FAIL",
        "tail": process.stdout.splitlines()[-12:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", action="append", required=True, help="NAME|ROOT|TEST_DIRECTORY")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=min(7, len(args.suite))) as pool:
        suites = list(pool.map(run_one, args.suite))
    result = {
        "schema": "kch.component-suite-aggregate.v0.11.0",
        "release": "KCH 0.11",
        "gate": "PASS" if all(row["state"] == "PASS" for row in suites) else "FAIL",
        "suite_count": len(suites),
        "test_total": sum(int(row["tests"] or 0) for row in suites),
        "aggregation_warning": "Counts are execution totals across distinct suites; they are not asserted statistically independent.",
        "suites": suites,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate": result["gate"], "suites": result["suite_count"], "tests": result["test_total"]}))
    return 0 if result["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
