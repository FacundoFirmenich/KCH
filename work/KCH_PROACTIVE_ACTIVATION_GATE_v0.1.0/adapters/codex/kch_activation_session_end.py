from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    gate = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(gate / "src"))
    from kch_activation.ledger import ActivationLedger

    payload = json.load(sys.stdin)
    state = Path(os.environ.get("KCH_ACTIVATION_STATE", str(gate / "runtime" / "activation_ledger.sqlite3")))
    ActivationLedger(state).close_session(str(payload["session_id"]))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(1)
