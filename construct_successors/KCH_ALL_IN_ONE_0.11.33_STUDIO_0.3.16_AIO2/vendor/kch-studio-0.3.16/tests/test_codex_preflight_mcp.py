from pathlib import Path

from kch_studio.codex_preflight_mcp import CodexPreflightMCP


def test_preflight_server_advertises_exactly_one_read_only_tool(tmp_path: Path) -> None:
    server = CodexPreflightMCP(tmp_path / "preflight")
    try:
        initialized = server.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        assert "exactly once" in initialized["result"]["instructions"][:512]
        listed = server.handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        assert len(listed["result"]["tools"]) == 1
        tool = listed["result"]["tools"][0]
        assert tool["name"] == "kch_governed_preflight"
        assert tool["annotations"]["readOnlyHint"] is True
        assert server.bootstrap.super_materialized is False
    finally:
        server.close()


def test_preflight_server_rejects_every_other_tool(tmp_path: Path) -> None:
    server = CodexPreflightMCP(tmp_path / "preflight")
    try:
        response = server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "kch_dispatch", "arguments": {}},
            }
        )
        assert response["error"]["code"] == -32602
        assert server.bootstrap.super_materialized is False
    finally:
        server.close()
