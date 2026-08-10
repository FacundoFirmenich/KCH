from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from .csi import lower_superchat
from .ledger import SCOService


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise SystemExit("input JSON must be an object")
    return value


def save(path: Path, value) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="sco", description="KCH SuperChats Orchestrators")
    root.add_argument("--state", type=Path, required=True)
    root.add_argument("--actor", default="sco-cli")
    root.add_argument("--command-id", default=None)
    root.add_argument("--expected-head", default=None)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("create", "add-node", "add-edge", "issue", "receipt", "conflict"):
        item = commands.add_parser(name)
        item.add_argument("--json", type=Path, required=True)
    retire = commands.add_parser("retire-node")
    retire.add_argument("--sco-id", required=True)
    retire.add_argument("--node-id", required=True)
    projection = commands.add_parser("projection")
    projection.add_argument("--sco-id")
    for name in ("schedule", "graph", "export", "lower-csi", "envelopes"):
        item = commands.add_parser(name)
        item.add_argument("--sco-id", required=True)
        if name in {"export", "lower-csi", "envelopes"}:
            item.add_argument("--output", type=Path, required=True)
    commands.add_parser("verify")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    service = SCOService(args.state)
    command_id = args.command_id or str(uuid4())
    expected = args.expected_head or service.head()
    common = {"actor": args.actor, "command_id": command_id, "expected_head_hash": expected}
    if args.command == "create":
        result = service.create_superchat(load(args.json), **common)
    elif args.command == "add-node":
        result = service.add_node(load(args.json), **common)
    elif args.command == "add-edge":
        result = service.add_edge(load(args.json), **common)
    elif args.command == "issue":
        result = service.issue_work_order(load(args.json), **common)
    elif args.command == "receipt":
        result = service.ingest_receipt(load(args.json), **common)
    elif args.command == "conflict":
        result = service.declare_conflict(load(args.json), **common)
    elif args.command == "retire-node":
        result = service.retire_node(args.sco_id, args.node_id, **common)
    elif args.command == "projection":
        result = service.projection(args.sco_id)
    elif args.command == "schedule":
        result = service.schedule(args.sco_id)
    elif args.command == "graph":
        result = service.graph_diagnostics(args.sco_id)
    elif args.command == "verify":
        result = service.verify()
    elif args.command == "export":
        result = service.export_bundle(args.sco_id)
        save(args.output, result)
    elif args.command == "lower-csi":
        result = lower_superchat(service.export_bundle(args.sco_id))
        save(args.output, result)
    elif args.command == "envelopes":
        result = service.dispatch_envelopes(args.sco_id)
        save(args.output, result)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
