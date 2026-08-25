from __future__ import annotations

import argparse
import json
from pathlib import Path

from .builder import build_bundle
from .rollout_audit import audit_rollout
from .validator import gate_receipt, verify_bundle


def make_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="kch-handoff")
    commands = root.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--snapshot", type=Path, required=True)
    build.add_argument("--state", type=Path, required=True)
    build.add_argument("--out", type=Path, required=True)
    build.add_argument("--no-zip", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("--bundle", type=Path, required=True)
    bootstrap = commands.add_parser("bootstrap")
    bootstrap.add_argument("--bundle", type=Path, required=True)
    gate = commands.add_parser("gate-receipt")
    gate.add_argument("--bundle", type=Path, required=True)
    gate.add_argument("--receipt", type=Path, required=True)
    gate.add_argument("--observation", type=Path, required=True)
    audit = commands.add_parser("audit-rollout")
    audit.add_argument("--rollout", type=Path, required=True)
    audit.add_argument("--contract", type=Path, required=True)
    audit.add_argument("--receipt", type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    if args.command == "build":
        result = build_bundle(args.snapshot, args.state, args.out, create_zip=not args.no_zip)
    elif args.command == "verify":
        result = verify_bundle(args.bundle)
    elif args.command == "bootstrap":
        print((args.bundle / "BOOTSTRAP_PROMPT.txt").read_text(encoding="utf-8"), end="")
        return 0
    elif args.command == "gate-receipt":
        result = gate_receipt(args.bundle, args.receipt, args.observation)
    else:
        result = audit_rollout(args.rollout, args.contract, args.receipt)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.get("passed", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
