from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from doctor import Client, ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the exact live KCH 0.11 MCP tool and resource schemas.")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime" / "KCH_SUPER_MCP_INTERFACE.json")
    args = parser.parse_args()
    client: Client | None = None
    try:
        with tempfile.TemporaryDirectory() as directory:
            client = Client(Path(directory) / "interface_export.sqlite3")
            initialized = client.request(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "kch-super-mcp-interface-exporter", "version": "0.11.0"},
                },
            )
            client.notify("notifications/initialized")
            tools = client.request("tools/list")["tools"]
            resources = client.request("resources/list")["resources"]
    finally:
        receipt = client.close() if client is not None else {"exit_code": None, "stderr": "client unavailable"}
    if receipt != {"exit_code": 0, "stderr": ""}:
        raise SystemExit(f"server did not close cleanly: {receipt}")
    result = {
        "schema": "kch.super-mcp-live-interface.v0.11.0",
        "initialized": initialized,
        "tool_count": len(tools),
        "resource_count": len(resources),
        "tools": tools,
        "resources": resources,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "tools": len(tools), "resources": len(resources)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

