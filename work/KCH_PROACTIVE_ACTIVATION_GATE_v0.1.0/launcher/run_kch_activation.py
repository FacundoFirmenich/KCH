from __future__ import annotations

import sys
from pathlib import Path


sys.stdin.reconfigure(encoding="utf-8", errors="strict")
sys.stdout.reconfigure(encoding="utf-8", errors="strict")

gate = Path(__file__).resolve().parents[1]
workspace = gate.parents[1]
base_deployment = workspace / "work" / "KCH_0.11_AGENT_SHADOW_DEPLOYMENT"
sys.path.insert(0, str(gate / "src"))

from kch_activation.bootstrap import prepare_environment

prepare_environment(gate, base_deployment)

from kch_activation.overlay_server import main


if __name__ == "__main__":
    main()
