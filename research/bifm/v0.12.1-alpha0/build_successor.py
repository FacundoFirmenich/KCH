#!/usr/bin/env python3
"""Materialize the v0.12.1 future-only successor from frozen v0.12.0.

The script applies the committed minimal patch without modifying the v0.12.0
source. It fails closed when the patch cannot be applied exactly.
"""
from __future__ import annotations

import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
OLD = HERE.parent / "v0.12.0-alpha0" / "talamo_exact.py"
PATCH = HERE / "talamo_exact_nonfinite_guardrail.patch"
OUT = HERE / "talamo_exact.py"

if not OLD.exists():
    raise SystemExit(f"missing frozen predecessor: {OLD}")
if not PATCH.exists():
    raise SystemExit(f"missing successor patch: {PATCH}")

OUT.write_bytes(OLD.read_bytes())
result = subprocess.run(
    ["patch", "--batch", "--forward", str(OUT), str(PATCH)],
    text=True,
    capture_output=True,
)
if result.returncode != 0:
    OUT.unlink(missing_ok=True)
    raise SystemExit(
        "v0.12.1 patch failed closed\nSTDOUT:\n"
        + result.stdout
        + "\nSTDERR:\n"
        + result.stderr
    )
print(f"materialized {OUT}")
