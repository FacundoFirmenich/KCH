from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import FileSystemAdapter, KwanDisk, SyncPolicy


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def write_result(value: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="kwandisk")
    root.add_argument("--state-root", type=Path, required=True)
    root.add_argument("--policy-id", default="kwandisk-default")
    commands = root.add_subparsers(dest="command", required=True)

    advisory = commands.add_parser("advisory")
    advisory.add_argument("paths", nargs="+", type=Path)
    advisory.add_argument("--output", type=Path)

    inventory = commands.add_parser("inventory")
    inventory.add_argument("root", type=Path)
    inventory.add_argument("--exclude-prefix", action="append", default=[])
    inventory.add_argument("--output", type=Path)

    analyze = commands.add_parser("analyze")
    analyze.add_argument("snapshot", type=Path)
    analyze.add_argument("--output", type=Path)

    sync = commands.add_parser("sync-filesystem")
    sync.add_argument("snapshot", type=Path)
    sync.add_argument("remote_root", type=Path)
    sync.add_argument("namespace")
    sync.add_argument("--authority", required=True)
    sync.add_argument("--encrypted", action="store_true")
    sync.add_argument("--authorize-sensitive", action="store_true")
    sync.add_argument("--output", type=Path)

    reconstruct = commands.add_parser("reconstruct-filesystem")
    reconstruct.add_argument("receipt", type=Path)
    reconstruct.add_argument("remote_root", type=Path)
    reconstruct.add_argument("destination", type=Path)
    reconstruct.add_argument("--output", type=Path)

    quarantine = commands.add_parser("quarantine")
    quarantine.add_argument("root", type=Path)
    quarantine.add_argument("receipt", type=Path)
    quarantine.add_argument("paths", nargs="+")
    quarantine.add_argument("--authorization-id", required=True)
    quarantine.add_argument("--output", type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    policy = SyncPolicy(
        policy_id=args.policy_id,
        cloud_target_encrypted=bool(getattr(args, "encrypted", False)),
    )
    engine = KwanDisk(args.state_root, policy)
    if args.command == "advisory":
        result = engine.startup_advisory(args.paths)
    elif args.command == "inventory":
        result = engine.inventory(args.root, excluded_prefixes=args.exclude_prefix)
    elif args.command == "analyze":
        result = engine.analyze(load_json(args.snapshot))
    elif args.command == "sync-filesystem":
        adapter = FileSystemAdapter("kwandisk-filesystem-cli", args.remote_root)
        result = engine.sync(
            load_json(args.snapshot),
            adapter,
            args.namespace,
            authority=args.authority,
            sensitive_upload_authorized=args.authorize_sensitive,
        )
    elif args.command == "reconstruct-filesystem":
        adapter = FileSystemAdapter("kwandisk-filesystem-cli", args.remote_root)
        result = engine.reconstruct(load_json(args.receipt), adapter, args.destination, actor="USER")
    else:
        result = engine.quarantine_paths(
            args.root,
            args.paths,
            load_json(args.receipt),
            actor="USER",
            exact_authorization_id=args.authorization_id,
        )
    write_result(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
