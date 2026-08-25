from pathlib import Path

from kch_studio.codex_bootstrap_mcp import NATIVE_SURFACES, TOOLS, CodexBootstrapMCP


def test_bootstrap_lists_six_tools_without_materializing_runtime(tmp_path: Path) -> None:
    server = CodexBootstrapMCP(tmp_path / "bootstrap")
    try:
        initialized = server.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        assert "kch_governed_preflight" in initialized["result"]["instructions"][:512]
        listed = server.handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        assert len(listed["result"]["tools"]) == 6 == len(TOOLS)
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


def test_catalog_search_discovers_native_surfaces_without_mcp_promotion(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("KCH_011_HMAC_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("KCH_011_STATE", str(tmp_path / "native-search-state.sqlite3"))
    server = CodexBootstrapMCP(tmp_path / "bootstrap")
    try:
        result = server.catalog_search("kwandisk", limit=10)
        assert result["native_surface_count"] == len(NATIVE_SURFACES) == 5
        assert result["searchable_entry_count"] == result["full_catalog_count"] + 5
        assert result["matches"] == [
            {
                "name": "kwandisk",
                "description": NATIVE_SURFACES[0]["description"],
                "read_only": True,
                "kind": "native_runtime",
                "dispatchable": False,
                "native_skill": "kch-kwandisk",
            }
        ]
        assert result["tool_executed"] is False
        assert result["authority_created"] is False
        assert server.super_materialized is False
    finally:
        server.close()


def test_native_surface_status_observes_files_without_import_or_execution(
    tmp_path: Path, monkeypatch
) -> None:
    plugin_root = tmp_path / "plugin"
    for descriptor in NATIVE_SURFACES:
        (plugin_root / str(descriptor["runtime_path"])).mkdir(parents=True)
    monkeypatch.setenv("KCH_NATIVE_PLUGIN_ROOT", str(plugin_root))
    server = CodexBootstrapMCP(tmp_path / "bootstrap")
    try:
        result = server.native_surface_status()
        assert result["count"] == 5
        assert result["plugin_root_observed"] is True
        assert result["all_observed_available"] is True
        assert result["runtime_imported"] is False
        assert result["runtime_executed"] is False
        assert all(row["available"] is True for row in result["surfaces"])
        assert all(row["mcp_dispatchable"] is False for row in result["surfaces"])
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
        assert value["governance"]["node_count"] == 23
        assert value["governance"]["rule_count"] == 13
        assert server.super_materialized is True
    finally:
        server.close()
