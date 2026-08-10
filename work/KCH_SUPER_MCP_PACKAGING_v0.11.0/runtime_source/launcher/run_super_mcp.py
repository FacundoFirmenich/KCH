from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"


def fail(message: str) -> None:
    print(f"KCH Super-MCP startup error: {message}", file=sys.stderr, flush=True)
    raise SystemExit(2)


if sys.version_info < (3, 11):
    fail(f"Python >= 3.11 is required; observed {sys.version.split()[0]}")

if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="strict")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")

wheels = sorted((BUNDLE / "dist").glob("*.whl")) + sorted((BUNDLE / "vendor").glob("*.whl"))
if len(wheels) != 8:
    fail(f"the sealed distribution requires exactly 8 wheels; observed {len(wheels)}")

registry = BUNDLE / "config" / "KCH_REGISTRY_v0.11.0.json"
if not registry.is_file():
    fail(f"registry unavailable: {registry}")

state = Path(os.environ.get("KCH_011_STATE", str(ROOT / "runtime" / "state" / "kch_011.sqlite3"))).expanduser().resolve()
state.parent.mkdir(parents=True, exist_ok=True)

sys.path[:0] = [str(path) for path in wheels]
os.environ.setdefault("KCH_011_HMAC_SECRET", secrets.token_hex(32))
os.environ.setdefault("KCH_011_BUNDLE_ROOT", str(BUNDLE))
os.environ.setdefault("KCH_011_REGISTRY", str(registry))
os.environ.setdefault("KCH_011_STATE", str(state))
os.environ.setdefault("KCH_011_PROFILE", "agent-shadow")

from kwancode_harness.mcp_server import main


if __name__ == "__main__":
    main()
