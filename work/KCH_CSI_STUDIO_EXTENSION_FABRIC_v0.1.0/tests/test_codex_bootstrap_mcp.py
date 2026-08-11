from pathlib import Path

from kch_studio.codex_bootstrap_mcp import TOOLS, CodexBootstrapMCP


def test_bootstrap_lists_five_tools_without_materializing_runtime(tmp_path: Path) -> None:
    server = CodexBootstrapMCP(tmp_path / "bootstrap")
    try:
        initialized = server.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        assert "kch_governed_preflight" in initialized["result"]["instructions"][:512]
        listed = server.handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        assert len(listed["result"]["tools"]) == 5 == len(TOOLS)
        assert server.super_materialized is False
        assert server._catalog is None
    finally:
        server.close()


def test_bootstrap_status_is_bounded_and_does_not_load_catalog(tmp_path: Path) -> None:
    server = CodexBootstrapMCP(tmp_path / "bootstrap")
    try:
        status = server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "kch_bootstrap_status", "arguments": {}},
            }
        )["result"]["structuredContent"]
        assert status["state"] == "BOUNDED_FRONT_DOOR_READY"
        assert status["full_runtime_materialized"] is False
        assert status["phl_real_executed"] is False
        assert server._catalog is None
    finally:
        server.close()


def test_catalog_search_loads_descriptors_but_not_full_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("KCH_011_HMAC_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("KCH_011_STATE", str(tmp_path / "catalog-state.sqlite3"))
    server = CodexBootstrapMCP(tmp_path / "bootstrap")
    try:
        result = server.catalog_search("response authority", limit=10)
        assert result["full_catalog_count"] >= 247
        assert any(item["name"] == "response_authority_adjudicate" for item in result["matches"])
        assert result["tool_executed"] is False
        assert server.super_materialized is False
    finally:
        server.close()


def test_dispatch_rejects_unknown_and_recursive_bootstrap_tools(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KCH_011_HMAC_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("KCH_011_STATE", str(tmp_path / "dispatch-state.sqlite3"))
    server = CodexBootstrapMCP(tmp_path / "bootstrap")
    try:
        for name in ("missing_tool", "kch_dispatch"):
            response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "kch_dispatch",
                        "arguments": {"tool_name": name, "arguments": {}},
                    },
                }
            )
            assert response["error"]["code"] == -32602
        assert server.super_materialized is False
    finally:
        server.close()


def test_governed_preflight_dispatches_into_full_runtime(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KCH_011_HMAC_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("KCH_011_STATE", str(tmp_path / "preflight-state.sqlite3"))
    server = CodexBootstrapMCP(tmp_path / "bootstrap")
    try:
        response = server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "kch_governed_preflight", "arguments": {}},
            }
        )
        value = response["result"]["structuredContent"]
        assert value["gate"] == "PASS"
        assert value["phl"]["authorized"] is True
        assert value["phl"]["training_executed"] is False
        assert value["checks"]["full_read_source_order_default"] is True
        assert value["full_read_contract"]["default_inventory_order"] == "SOURCE_NATIVE_ORDER"
        assert value["governance"]["node_count"] == 20
        assert value["governance"]["rule_count"] == 11
        assert server.super_materialized is True
    finally:
        server.close()
