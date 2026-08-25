from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .contracts import ArtifactSpec
from .extension import ExtensionFabric, RuntimeInventory
from .mcp_server import StudioMCP
from .mcp_server import main as mcp_main
from .studio import Studio
from .ui import launch


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="kch-studio")
    result.add_argument("--root", default=os.environ.get("KCH_STUDIO_ROOT", ".kch-studio"))
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("doctor")
    ui = sub.add_parser("ui")
    ui.add_argument("--smoke", action="store_true")
    create = sub.add_parser("create")
    create.add_argument("spec_json")
    for name in ("generate", "validate", "seal"):
        item = sub.add_parser(name)
        item.add_argument("session_id")
    search = sub.add_parser("search")
    search.add_argument("provider")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    sub.add_parser("mcp")
    return result


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "doctor":
        server = StudioMCP(root)
        try:
            emit(
                {
                    "studio": server.studio.status(),
                    "kch": server.advanced.status(),
                    "runtime": RuntimeInventory().collect(),
                    "extension_fabric": server.fabric.describe(),
                }
            )
        finally:
            server.advanced.close()
    elif args.command == "status":
        server = StudioMCP(root)
        try:
            emit({"studio": server.studio.status(), "kch": server.advanced.status()})
        finally:
            server.advanced.close()
    elif args.command == "ui":
        value = launch(root, smoke=args.smoke)
        if value is not None:
            emit(value)
    elif args.command == "create":
        value = json.loads(Path(args.spec_json).read_text(encoding="utf-8"))
        emit(Studio(root).create_session(ArtifactSpec.from_dict(value)))
    elif args.command == "generate":
        emit(Studio(root).generate(args.session_id))
    elif args.command == "validate":
        emit(Studio(root).validate(args.session_id))
    elif args.command == "seal":
        emit(Studio(root).seal(args.session_id))
    elif args.command == "search":
        emit(
            ExtensionFabric(root / "extension_fabric").search(args.provider, args.query, args.limit)
        )
    elif args.command == "mcp":
        mcp_main()


if __name__ == "__main__":
    main()
