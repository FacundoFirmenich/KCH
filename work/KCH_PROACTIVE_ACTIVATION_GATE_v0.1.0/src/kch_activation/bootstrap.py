from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path


def prepare_environment(gate_root: str | Path, base_deployment: str | Path) -> dict[str, str]:
    gate = Path(gate_root).resolve()
    deployment = Path(base_deployment).resolve()
    bundle = deployment / "bundle"
    wheels = sorted((bundle / "dist").glob("*.whl")) + sorted((bundle / "vendor").glob("*.whl"))
    if len(wheels) != 8:
        raise RuntimeError(f"KCH 0.11 sealed dependency count mismatch: expected 8, observed {len(wheels)}")
    sys.path[:0] = [str(gate / "src"), *(str(path) for path in wheels)]
    runtime = gate / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("KCH_011_HMAC_SECRET", secrets.token_hex(32))
    os.environ.setdefault("KCH_011_BUNDLE_ROOT", str(bundle))
    os.environ.setdefault("KCH_011_REGISTRY", str(bundle / "config" / "KCH_REGISTRY_v0.11.0.json"))
    os.environ.setdefault("KCH_011_STATE", str(runtime / "kch_011_activation_overlay.sqlite3"))
    os.environ.setdefault("KCH_011_PROFILE", "agent-shadow")
    os.environ.setdefault("KCH_ACTIVATION_STATE", str(runtime / "activation_ledger.sqlite3"))
    os.environ.setdefault("KCH_ACTIVATION_RULES", str(gate / "config" / "activation_rules.v0.1.0.json"))
    return {
        "gate_root": str(gate),
        "base_deployment": str(deployment),
        "bundle_root": str(bundle),
        "activation_state": os.environ["KCH_ACTIVATION_STATE"],
        "activation_rules": os.environ["KCH_ACTIVATION_RULES"],
    }
