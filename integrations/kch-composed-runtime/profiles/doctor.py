"""Probe a generated local profile using the official MCP Python SDK.

This starts only the bound KCH subprocess. It does not start QwenPaw/OpenClaw,
change their configuration, authenticate a human, or make model requests.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sys


def load_profile(path: Path):
    data = json.loads(path.read_text())
    if set(data) == {"mcpServers"}:
        host, entries = "qwenpaw", data["mcpServers"]
    elif set(data) == {"mcp"} and set(data["mcp"]) == {"servers"}:
        host, entries = "openclaw", data["mcp"]["servers"]
    else:
        raise ValueError("Expected one generated QwenPaw or OpenClaw fragment")
    if set(entries) != {"kch_composed"}:
        raise ValueError("The probe accepts only the isolated kch_composed entry")
    client = entries["kch_composed"]
    allowed_fields = {"command", "args", "cwd", "transport", "enabled"}
    if host == "qwenpaw":
        allowed_fields.add("name")
    if not isinstance(client, dict) or set(client) != allowed_fields:
        raise ValueError("Only unmodified generated profile fields are accepted")
    if client.get("transport") != "stdio" or client.get("enabled") is not True:
        raise ValueError("Expected an enabled stdio profile")
    argv = client.get("args", [])
    if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
        raise ValueError("Invalid argument list")
    if argv[:2] != ["-m", "kch_composed"] or argv[-1:] != ["mcp"]:
        raise ValueError("Expected the generated KCH module invocation")
    expected = {"--repository", "--state", "--workspace", "--principal", "--session"}
    if len(argv) != 13 or set(argv[2:-1:2]) != expected:
        raise ValueError("Only generated read-only profile arguments are accepted")
    values = dict(zip(argv[2:-1:2], argv[3:-1:2]))
    for field in ("command", "cwd"):
        if not Path(client[field]).is_absolute() or not Path(client[field]).exists():
            raise ValueError("Command and cwd must be existing absolute paths")
    if not Path(client["command"]).is_file() or not Path(client["cwd"]).is_dir():
        raise ValueError("Command must be a file and cwd must be a directory")
    return host, client, values


async def probe(profile: Path, source: str | None):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    host, config, values = load_profile(profile)
    report = {"host_profile": host, "boundary": "OFFICIAL_MCP_SDK_TO_KCH_SUBPROCESS",
              "user_host_activated": False, "model_inference": False,
              "host_configuration_modified": False,
              "session": values["--session"], "checks": []}
    params = StdioServerParameters(command=config["command"], args=config["args"],
                                   cwd=config["cwd"], env={})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=15)) as client:
            initialized = await client.initialize()
            report["protocol_version"] = initialized.protocolVersion
            report["server"] = initialized.serverInfo.model_dump()
            listed = await client.list_tools()
            report["catalog"] = sorted(item.name for item in listed.tools)
            if "read_file" not in report["catalog"] or "write_file" in report["catalog"]:
                raise ValueError("Unexpected read-only KCH catalog")
            report["checks"].append("initialize_and_catalog")
            if source is not None:
                workspace = Path(values["--workspace"]).resolve(strict=True)
                local = (workspace / source).resolve(strict=True)
                if not local.is_relative_to(workspace) or not local.is_file():
                    raise ValueError("Read check must name a real file inside the bound workspace")
                with local.open("rb") as stream:
                    expected = stream.read(65536)
                response = await client.call_tool("read_file", {"path": source, "max_bytes": 65536})
                value = json.loads(response.content[0].text)
                if response.isError or not value.get("ok"):
                    raise ValueError("KCH refused the requested read check")
                actual = base64.b64decode(value["value"]["content"]["data"], validate=True)
                if actual != expected:
                    raise ValueError("MCP read differs from bytes read directly in the same workspace")
                report["read_range_sha256"] = hashlib.sha256(actual).hexdigest()
                report["read_range_bytes"] = len(actual)
                report["checks"].append("workspace_read_exact_bytes")
    report["checks"].append("subprocess_closed")
    report["status"] = "PASS"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--read", help="Optional real workspace file; compares its first 65536 bytes")
    args = parser.parse_args(argv)
    try:
        report = asyncio.run(probe(args.profile, args.read))
    except ImportError:
        print(json.dumps({"status": "BLOCKED", "reason": "Install the optional mcp dependency: mcp>=1.28,<2"}))
        return 2
    except Exception as error:
        # Error text can contain host secrets or source content; emit type only.
        print(json.dumps({"status": "FAIL", "error_type": type(error).__name__}))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
