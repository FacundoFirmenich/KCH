"""Execute the unmodified QwenPaw stdio client against a real KCH subprocess.

Requires a pinned QwenPaw checkout and its MCP dependency. This deliberately
loads the client component, not the full agent app, persisted envs or models.
No client, model, transport, file, or server is mocked.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types


def load_client(upstream):
    # Namespace packages locate original source while avoiding the application
    # bootstrap, which loads a real user's persisted environment on import.
    for name, relative in (("qwenpaw", "src/qwenpaw"),
                           ("qwenpaw.drivers", "src/qwenpaw/drivers"),
                           ("qwenpaw.drivers.handlers", "src/qwenpaw/drivers/handlers")):
        module = types.ModuleType(name)
        module.__path__ = [str(upstream / relative)]
        sys.modules[name] = module
    return importlib.import_module(
        "qwenpaw.drivers.handlers.mcp_stateful_client").StdIOStatefulClient


async def accept(repository, upstream, output):
    sys.path.insert(0, str(repository / "integrations/kch-composed-runtime/profiles"))
    from generate import profiles
    Client = load_client(upstream)
    source = repository / "integrations/kch-composed-runtime/README.md"
    expected = source.read_bytes()
    client_source = upstream / "src/qwenpaw/drivers/handlers/mcp_stateful_client.py"
    receipt = {"host": "qwenpaw", "boundary": "ORIGINAL_CLIENT_COMPONENT_TO_KCH_SUBPROCESS",
               "executed_at": datetime.now(timezone.utc).isoformat(),
               "upstream_commit": subprocess.check_output(
                   ["git", "rev-parse", "HEAD"], cwd=upstream, text=True).strip(),
               "source_sha256": hashlib.sha256(client_source.read_bytes()).hexdigest(),
               "mcp_package": importlib.metadata.version("mcp"),
               "model_inference": False, "user_host_activated": False, "checks": []}
    with tempfile.TemporaryDirectory(prefix="kch-qwenpaw-acceptance-") as temporary:
        root = Path(temporary)
        config = profiles(repository=repository, workspace=repository, state=root / "state",
                          principal="host-acceptance", session_prefix="original-client"
                          )["qwenpaw.local.json"]["mcpServers"]["kch_composed"]
        def make_client():
            return Client(name=config["name"], command=config["command"], args=config["args"],
                          cwd=config["cwd"], env={}, read_timeout_seconds=15)
        client = make_client()
        async def call(name, arguments):
            result = await client.call_tool(name, arguments)
            return result, json.loads(result.content[0].text)
        try:
            await client.connect(timeout=15)
            listed = await client.list_tools()
            names = sorted(tool.name for tool in listed)
            assert "read_file" in names and "write_file" not in names
            receipt["catalog"] = names
            receipt["checks"].append("original_client_discovery")
            _, result = await call("read_file", {"path": str(source.relative_to(repository)),
                                                "max_bytes": 65536})
            assert result["ok"] is True
            assert base64.b64decode(result["value"]["content"]["data"]) == expected[:65536]
            receipt["read_sha256"] = result["value"]["range_sha256"]
            receipt["checks"].append("real_repository_bytes_equal")
            rejected, denied = await call("read_file", {"path": "/etc/passwd"})
            assert rejected.isError is True and denied["ok"] is False
            receipt["checks"].append("out_of_workspace_read_denied")
            rejected, denied = await call("write_file", {"path": "acceptance-must-not-exist.txt",
                                                       "content": "not authorized"})
            assert rejected.isError is True and denied["ok"] is False
            assert not (repository / "acceptance-must-not-exist.txt").exists()
            receipt["checks"].append("disabled_write_denied_without_effect")
            _, result = await call("memory_ingest", {"path": str(source.relative_to(repository)),
                                                    "source_id": "acceptance/readme"})
            assert result["ok"] is True
            receipt["checks"].append("real_file_memory_ingest")
        finally:
            await client.close(ignore_errors=False)
        assert not client.is_connected
        receipt["checks"].append("first_client_closed")
        client = make_client()
        try:
            await client.connect(timeout=15)
            _, result = await call("memory_recall", {"source_id": "acceptance/readme"})
            assert result["ok"] is True
            assert base64.b64decode(result["value"]["content"]["data"]) == expected
            receipt["checks"].append("new_client_process_same_session_exact_memory")
        finally:
            await client.close(ignore_errors=False)
        assert not client.is_connected
        receipt["checks"].append("restarted_client_closed")
        state = subprocess.run([config["command"], *config["args"][:-1], "inspect"],
                               cwd=config["cwd"], text=True, capture_output=True, check=True)
        status = json.loads(state.stdout)
        assert status["journal"] is True
        assert len(status["calls"]) == 5
        receipt["journal"] = status["journal"]
        receipt["bound_session"] = status["scope"]["session"]
        receipt["durable_calls"] = len(status["calls"])
    receipt["status"] = "PASS"
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        asyncio.run(accept(args.repository.resolve(), args.upstream.resolve(), args.output.resolve()))
    except Exception as error:
        args.output.write_text(json.dumps({"status": "FAIL", "host": "qwenpaw",
                                          "error_type": type(error).__name__}) + "\n")
        raise
