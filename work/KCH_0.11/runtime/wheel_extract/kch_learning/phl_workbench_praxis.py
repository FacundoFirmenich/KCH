from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .ledger_praxis import PraxisLearningLedger
from .phl_workbench_release import PHLWorkbench
from .service_release import LearningService


class PraxisPHLWorkbench(PHLWorkbench):
    service: LearningService

    def __init__(self, service: LearningService, session_id: str):
        super().__init__(service, session_id)
        saved = service.ledger.load_workbench_state(session_id)
        if saved:
            self.filters = dict(saved.get("filters", {}))
            self.search_text = saved.get("search_text")
            self.reviewed = saved.get("reviewed")
            self.page = int(saved.get("page", 1))
            self.sort_field = saved.get("sort_field", "id")
            self.queue = list(saved.get("queue", []))
            self.cursor = saved.get("cursor")

    def state_payload(self) -> dict[str, Any]:
        return {
            "filters": self.filters,
            "search_text": self.search_text,
            "reviewed": self.reviewed,
            "page": self.page,
            "sort_field": self.sort_field,
            "queue": self.queue,
            "cursor": self.cursor,
        }

    def execute(self, parts: list[str]) -> tuple[object | None, bool]:
        command = parts[0].lower()
        if command == "close":
            self.service.ledger.save_workbench_state(self.session_id, self.state_payload())
            return super().execute(parts)
        result = super().execute(parts)
        self.service.ledger.save_workbench_state(self.session_id, self.state_payload())
        return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="kch-phl", description="KCH Post Hoc Learning praxis workbench")
    root.add_argument("--state", type=Path, required=True)
    root.add_argument("--resume", help="resume an existing active PHL session")
    root.add_argument("--dashboard-json", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    service = LearningService(PraxisLearningLedger(args.state))
    if args.resume:
        session = service.ledger.session(args.resume)
        if session["channel"] != "PHL" or session["state"] != "ACTIVE":
            raise SystemExit("--resume requires an active PHL session")
        session_id = args.resume
    else:
        active = service.ledger.active_phl_session()
        session_id = active or service.start_phl()["session_id"]
    workbench = PraxisPHLWorkbench(service, session_id)
    if args.dashboard_json:
        print(json.dumps(workbench.dashboard(), ensure_ascii=False, sort_keys=True))
        return 0
    return workbench.run()


if __name__ == "__main__":
    raise SystemExit(main())
