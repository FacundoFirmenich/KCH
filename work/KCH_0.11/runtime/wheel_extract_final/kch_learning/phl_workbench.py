from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

from .canonical import LearningError
from .ledger import LearningLedger
from .service import LearningService


HELP = """Commands:
  dashboard                         counts, lock and ledger state
  list [all|reviewed|unreviewed]    extensive paged decision inventory
  component NAME                   filter inventory by KCH component
  page N                           select page (20 records per page)
  open DECISION_ID                 full evidence-rich decision card
  score DECISION_ID 000..100       record score; prompts for informed text
  packet                            compile future-only training packet
  verify                            verify custody chain and projections
  close                             close PHL session and release KCH lock
  quit                              leave UI; active session remains locked
"""


class PHLWorkbench:
    page_size = 20

    def __init__(self, service: LearningService, session_id: str):
        self.service = service
        self.session_id = session_id
        self.component: str | None = None
        self.reviewed: bool | None = None
        self.page = 1

    def dashboard(self) -> dict:
        all_rows = self.service.ledger.list_decisions()
        reviewed = self.service.ledger.list_decisions(reviewed=True)
        return {
            "session_id": self.session_id,
            "mode": "PHL_POST_HOC_LEARNING",
            "exclusive_lock": self.service.ordinary_work_gate(),
            "decision_count": len(all_rows),
            "reviewed_decision_count": len(reviewed),
            "unreviewed_decision_count": len(all_rows) - len(reviewed),
            "filter_component": self.component,
            "ledger": self.service.ledger.verify(),
        }

    def inventory(self) -> dict:
        rows = self.service.ledger.list_decisions(component=self.component, reviewed=self.reviewed)
        pages = max(1, (len(rows) + self.page_size - 1) // self.page_size)
        self.page = min(max(1, self.page), pages)
        start = (self.page - 1) * self.page_size
        selected = rows[start : start + self.page_size]
        compact = [
            {
                "decision_id": row["decision_id"],
                "component": row["component"],
                "type": row["decision_type"],
                "summary": row["summary"],
                "gate": row.get("gate_status", "UNAVAILABLE"),
                "risk": row.get("risk_level", "UNAVAILABLE"),
                "phl_reviews": row["phl_reviews"],
            }
            for row in selected
        ]
        return {"page": self.page, "pages": pages, "total": len(rows), "rows": compact}

    def open_decision(self, decision_id: str) -> dict:
        return self.service.ledger.decision(decision_id)

    def score_interactive(self, decision_id: str, score: str) -> dict:
        print("Texto contextual superinformado (vacío permitido; termine con Enter):")
        context = input().strip()
        print("Corrección o conducta deseada explícita (vacío permitido; termine con Enter):")
        correction = input().strip()
        return self.service.score_phl(self.session_id, decision_id, score, context, correction)

    def run(self) -> int:
        print("KCH PHL v0.1.0 | POST HOC LEARNING | ordinary KCH work LOCKED")
        print(HELP)
        while True:
            try:
                parts = shlex.split(input("PHL> "))
                if not parts:
                    continue
                command = parts[0].lower()
                if command == "help":
                    print(HELP)
                elif command == "dashboard":
                    print(json.dumps(self.dashboard(), ensure_ascii=False, indent=2))
                elif command == "list":
                    mode = parts[1].lower() if len(parts) > 1 else "all"
                    self.reviewed = {"all": None, "reviewed": True, "unreviewed": False}[mode]
                    print(json.dumps(self.inventory(), ensure_ascii=False, indent=2))
                elif command == "component":
                    self.component = None if len(parts) == 1 or parts[1] == "*" else parts[1]
                    self.page = 1
                elif command == "page":
                    self.page = int(parts[1])
                    print(json.dumps(self.inventory(), ensure_ascii=False, indent=2))
                elif command == "open":
                    print(json.dumps(self.open_decision(parts[1]), ensure_ascii=False, indent=2))
                elif command == "score":
                    print(json.dumps(self.score_interactive(parts[1], parts[2]), ensure_ascii=False, indent=2))
                elif command == "packet":
                    print(json.dumps(self.service.compile_training_packet(self.session_id), ensure_ascii=False, indent=2))
                elif command == "verify":
                    print(json.dumps(self.service.ledger.verify(), ensure_ascii=False, indent=2))
                elif command == "close":
                    print(json.dumps(self.service.close_session(self.session_id), ensure_ascii=False, indent=2))
                    return 0
                elif command == "quit":
                    print("PHL UI closed; session remains active and ordinary KCH work remains locked.")
                    return 0
                else:
                    print("Unknown command. Use help.")
            except (LearningError, ValueError, IndexError, KeyError) as exc:
                print(f"ERROR: {exc}")
            except EOFError:
                print("EOF: session remains active. Reopen or explicitly close it.")
                return 0


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
