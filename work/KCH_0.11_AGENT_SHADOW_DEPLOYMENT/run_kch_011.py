from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path


sys.stdin.reconfigure(encoding="utf-8", errors="strict")
sys.stdout.reconfigure(encoding="utf-8", errors="strict")

deployment = Path(__file__).resolve().parent
bundle = deployment / "bundle"
wheels = sorted((bundle / "dist").glob("*.whl")) + sorted((bundle / "vendor").glob("*.whl"))
if len(wheels) != 8:
    raise SystemExit(f"Expected 8 sealed wheels, observed {len(wheels)}")

sys.path[:0] = [str(path) for path in wheels]
os.environ["KCH_011_HMAC_SECRET"] = secrets.token_hex(32)
os.environ["KCH_011_BUNDLE_ROOT"] = str(bundle)
os.environ["KCH_011_REGISTRY"] = str(bundle / "config" / "KCH_REGISTRY_v0.11.0.json")
os.environ["KCH_011_STATE"] = str(deployment / "runtime" / "state" / "kch_011_agent_shadow.sqlite3")
os.environ["KCH_011_PROFILE"] = "agent-shadow"

from kwancode_harness.mcp_server import main


if __name__ == "__main__":
    main()
