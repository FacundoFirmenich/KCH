from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

from .canonical import LearningError
from .ledger_release import LearningLedger
from .service import LearningService


HELP = """Commands:
  dashboard                         counts, lock and ledger state
  list [all|reviewed|unreviewed]    extensive paged decision inventory
  filter FIELD VALUE               component/type/gate/risk filter; * clears
  search TEXT                      full-text decision search; * clears
  sort FIELD                       id/component/type/risk/reviews
  page N                           select page (20 records per page)
  open DECISION_ID                 full evidence-rich decision card
  history DECISION_ID              all prior OBL/PHL feedback for decision
  compare ID_A ID_B                compare two full decision cards
  next | prev                      navigate current filtered inventory
  queue add|remove DECISION_ID      maintain personal review queue
  queue show                       show queued full records
  score DECISION_ID 000..100       score and enter informed contextual text
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
        self.filters: dict[str, str] = {}
        self.search_text: str | None = None
        self.reviewed: bool | None = None
        self.page = 1
        self.sort_field = "id"
        self.queue: list[str] = []
        self.cursor: str | None = None

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
            "filters": self.filters,
            "search_text": self.search_text,
            "sort_field": self.sort_field,
            "queue_size": len(self.queue),
            "ledger": self.service.ledger.verify(),
        }

    def _selected_rows(self) -> list[dict]:
        rows = self.service.ledger.list_decisions(reviewed=self.reviewed)
        field_map = {"component": "component", "type": "decision_type", "gate": "gate_status", "risk": "risk_level"}
        for field, value in self.filters.items():
            rows = [row for row in rows if str(row.get(field_map[field], "UNAVAILABLE")).casefold() == value.casefold()]
        if self.search_text:
            needle = self.search_text.casefold()
            rows = [row for row in rows if needle in json.dumps(row, ensure_ascii=False, sort_keys=True).casefold()]
        sort_map = {"id": "decision_id", "component": "component", "type": "decision_type", "risk": "risk_level", "reviews": "phl_reviews"}
        rows.sort(key=lambda row: (row.get(sort_map[self.sort_field], ""), row["decision_id"]))
        return rows

    def inventory(self) -> dict:
        rows = self._selected_rows()
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
        return {"page": self.page, "pages": pages, "total": len(rows), "filters": self.filters, "search": self.search_text, "sort": self.sort_field, "rows": compact}

    def open_decision(self, decision_id: str) -> dict:
        self.cursor = decision_id
        return self.service.ledger.decision(decision_id)

    def navigate(self, delta: int) -> dict:
        rows = self._selected_rows()
        if not rows:
            raise LearningError("current inventory is empty")
        ids = [row["decision_id"] for row in rows]
        index = ids.index(self.cursor) if self.cursor in ids else (-1 if delta > 0 else 0)
        index = max(0, min(len(ids) - 1, index + delta))
        return self.open_decision(ids[index])

    def score_interactive(self, decision_id: str, score: str) -> dict:
        print("Texto contextual superinformado (vacío permitido; termine con Enter):")
        context = input().strip()
        print("Corrección o conducta deseada explícita (vacío permitido; termine con Enter):")
        correction = input().strip()
        return self.service.score_phl(self.session_id, decision_id, score, context, correction)

    def execute(self, parts: list[str]) -> tuple[object | None, bool]:
        command = parts[0].lower()
        if command == "help":
            return HELP, False
        if command == "dashboard":
            return self.dashboard(), False
        if command == "list":
            mode = parts[1].lower() if len(parts) > 1 else "all"
            self.reviewed = {"all": None, "reviewed": True, "unreviewed": False}[mode]
            return self.inventory(), False
        if command == "filter":
            field, value = parts[1].lower(), parts[2]
            if field not in {"component", "type", "gate", "risk"}:
                raise LearningError("filter field must be component/type/gate/risk")
            if value == "*":
                self.filters.pop(field, None)
            else:
                self.filters[field] = value
            self.page = 1
            return self.inventory(), False
        if command == "search":
            value = " ".join(parts[1:])
            self.search_text = None if value == "*" else value
            self.page = 1
            return self.inventory(), False
        if command == "sort":
            if parts[1] not in {"id", "component", "type", "risk", "reviews"}:
                raise LearningError("sort field must be id/component/type/risk/reviews")
            self.sort_field = parts[1]
            return self.inventory(), False
        if command == "page":
            self.page = int(parts[1])
            return self.inventory(), False
        if command == "open":
            return self.open_decision(parts[1]), False
        if command == "history":
            return self.service.ledger.feedback_for_decision(parts[1]), False
        if command == "compare":
            return {parts[1]: self.open_decision(parts[1]), parts[2]: self.open_decision(parts[2])}, False
        if command == "next":
            return self.navigate(1), False
        if command == "prev":
            return self.navigate(-1), False
        if command == "queue":
            action = parts[1].lower()
            if action == "show":
                return [self.open_decision(item) for item in self.queue], False
            if action == "add":
                self.open_decision(parts[2])
                if parts[2] not in self.queue:
                    self.queue.append(parts[2])
                return {"queue": self.queue}, False
            if action == "remove":
                if parts[2] in self.queue:
                    self.queue.remove(parts[2])
                return {"queue": self.queue}, False
            raise LearningError("queue action must be add/remove/show")
        if command == "score":
            return self.score_interactive(parts[1], parts[2]), False
        if command == "packet":
            return self.service.compile_training_packet(self.session_id), False
        if command == "verify":
            return self.service.ledger.verify(), False
        if command == "close":
            return self.service.close_session(self.session_id), True
        if command == "quit":
            return "PHL UI closed; session remains active and ordinary KCH work remains locked.", True
        raise LearningError("unknown command; use help")

    def run(self) -> int:
        print("KCH PHL v0.1.0 | POST HOC LEARNING | ordinary KCH work LOCKED")
        print(HELP)
        while True:
            try:
                parts = shlex.split(input("PHL> "))
                if not parts:
                    continue
                result, stop = self.execute(parts)
                if isinstance(result, str):
                    print(result)
                elif result is not None:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                if stop:
                    return 0
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
