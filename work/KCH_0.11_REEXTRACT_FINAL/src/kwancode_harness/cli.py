from __future__ import annotations

import argparse
import json
from pathlib import Path

from .controls import describe_controls, evaluate_control
from .mcp_server import build_gateway


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="kch", description="KCH 0.11 canonical federated runtime")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("status", "registry", "controls", "audit", "audit-evidence", "components", "phl", "mis"):
        commands.add_parser(name)
    sco = commands.add_parser("sco")
    sco.add_argument("--sco-id")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("control_id", choices=sorted(describe_controls()["controls"][i]["control_id"] for i in range(28)))
    evaluate.add_argument("context", type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    gateway = build_gateway()
    if args.command == "status":
        value = gateway.status()
    elif args.command == "registry":
        value = gateway.registry.describe()
    elif args.command == "controls":
        value = gateway.control_catalog()
    elif args.command == "audit":
        value = gateway.audit_export()
    elif args.command == "audit-evidence":
        value = gateway.registry.audit_evidence(gateway.adapters.bundle_root)
    elif args.command == "components":
        value = gateway.adapters.component_status()
    elif args.command == "phl":
        value = gateway.adapters.phl_projection()
    elif args.command == "sco":
        value = gateway.adapters.sco_projection(args.sco_id)
    elif args.command == "mis":
        value = gateway.adapters.mis_certificate_verify()
    elif args.command == "evaluate":
        context = json.loads(args.context.read_text(encoding="utf-8-sig"))
        value = evaluate_control(args.control_id, context)
    else:
        raise AssertionError(args.command)
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
