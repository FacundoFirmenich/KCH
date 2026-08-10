from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ledger_release import LearningLedger
from .service_release import LearningService


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="kch-obl", description="OBL one-line command box")
    root.add_argument("--state", type=Path, required=True)
    commands = root.add_subparsers(dest="command", required=True)
    launch = commands.add_parser("launch")
    launch.add_argument("decision_id")
    launch.add_argument("--initiator", choices=("USER", "MODEL"), required=True)
    launch.add_argument("--trigger", required=True)
    respond = commands.add_parser("respond")
    respond.add_argument("session_id")
    respond.add_argument("decision_id")
    respond.add_argument("verdict", choices=("ACCEPT", "CORRECT", "ABSTAIN"))
    respond.add_argument("--context", default="")
    respond.add_argument("--correction", default="")
    close = commands.add_parser("close")
    close.add_argument("session_id")
    commands.add_parser("verify")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    service = LearningService(LearningLedger(args.state))
    if args.command == "launch":
        result = service.launch_obl(args.decision_id, args.initiator, args.trigger)
    elif args.command == "respond":
        result = service.submit_obl(args.session_id, args.decision_id, args.verdict, args.context, args.correction)
    elif args.command == "close":
        result = service.close_session(args.session_id)
    else:
        result = service.ledger.verify()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
