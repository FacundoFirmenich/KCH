from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ledger_release import LearningLedger
from .phl_workbench_release import PHLWorkbench
from .service_release import LearningService


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="kch-phl", description="KCH Post Hoc Learning interactive workbench")
    root.add_argument("--state", type=Path, required=True)
    root.add_argument("--resume", help="resume an existing active PHL session")
    root.add_argument("--dashboard-json", action="store_true", help="noninteractive instrument probe")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    service = LearningService(LearningLedger(args.state))
    if args.resume:
        session = service.ledger.session(args.resume)
        if session["channel"] != "PHL" or session["state"] != "ACTIVE":
            raise SystemExit("--resume requires an active PHL session")
        session_id = args.resume
    else:
        active = service.ledger.active_phl_session()
        session_id = active or service.start_phl()["session_id"]
    workbench = PHLWorkbench(service, session_id)
    if args.dashboard_json:
        print(json.dumps(workbench.dashboard(), ensure_ascii=False, sort_keys=True))
        return 0
    return workbench.run()


if __name__ == "__main__":
    raise SystemExit(main())
