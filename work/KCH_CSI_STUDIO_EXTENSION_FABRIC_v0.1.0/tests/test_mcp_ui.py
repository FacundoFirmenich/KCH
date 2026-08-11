from __future__ import annotations

from pathlib import Path

from kch_studio.mcp_server import TOOLS, StudioMCP
from kch_studio.super_mcp_overlay import IntegratedSuperMCP
from kch_studio.ui import launch


def test_integrated_mcp_initialize_list_and_status(tmp_path: Path) -> None:
    server = StudioMCP(tmp_path / "runtime")
    initialized = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert initialized["result"]["serverInfo"]["name"] == "kch-csi-studio"
    listed = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools = listed["result"]["tools"]
    assert server.advanced is None
    assert len(tools) == len(TOOLS)
    assert any(
        tool["name"] == "isolated_install_execute" and tool["annotations"]["readOnlyHint"] is False
        for tool in tools
    )
    status = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "studio_status", "arguments": {}},
        }
    )
    assert status["result"]["structuredContent"]["installation_authorized"] is False
    governance = status["result"]["structuredContent"]["governance"]
    assert governance["node_count"] == 23
    assert governance["source_nodes_verified"] == 23
    assert governance["rule_count"] == 13
    assert governance["all_strategic_invariant"] is True
    advanced = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "kch_next_status", "arguments": {}},
        }
    )
    assert advanced["result"]["structuredContent"]["phl_real_executed"] is False
    assert advanced["result"]["structuredContent"]["capability_blind_spots"] == []
    response_modes = advanced["result"]["structuredContent"]["components"]["response_modes"]
    assert response_modes["default_profile"] == "builtin.explicativo"
    assert response_modes["integrity"]["gate"] == "PASS"
    server.advanced.close()


def test_super_mcp_lists_tools_before_heavy_runtime_materialization(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KCH_011_HMAC_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("KCH_011_STATE", str(tmp_path / "lazy-kch-011.sqlite3"))
    server = IntegratedSuperMCP(tmp_path / "lazy-integrated")
    try:
        assert server.studio.advanced is None
        listed = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        assert len(listed["result"]["tools"]) == len(TOOLS) + len(server.base_tool_names)
        assert server.studio.advanced is None
    finally:
        server.close()


def test_response_authority_is_callable_through_canonical_mcp(tmp_path: Path) -> None:
    server = StudioMCP(tmp_path / "runtime")
    try:
        listed = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        names = {tool["name"] for tool in listed["result"]["tools"]}
        assert {"response_authority_register", "response_authority_adjudicate", "response_authority_status"} <= names
        registered = server.handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "response_authority_register",
                    "arguments": {
                        "constraint": {
                            "constraint_id": "MCP-SCOPE-LOCAL",
                            "dimension": "JURISDICTION",
                            "key": "scope",
                            "operator": "EQ",
                            "expected": "LOCAL",
                            "authority_source": "user-turn",
                        }
                    },
                },
            }
        )
        assert registered["result"]["structuredContent"]["constraint"]["active"] is True
        blocked = server.handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "response_authority_adjudicate",
                    "arguments": {
                        "candidate": {
                            "text": "promoted",
                            "assertions": [{"dimension": "JURISDICTION", "key": "scope", "value": "GLOBAL"}],
                        }
                    },
                },
            }
        )
        assert blocked["result"]["structuredContent"]["gate"] == "BLOCK"
    finally:
        server.advanced.close()


def test_tk_visual_client_smoke(tmp_path: Path) -> None:
    value = launch(tmp_path / "ui-runtime", smoke=True)
    assert value["passed"] is True
    assert value["providers"] == 11
    assert value["tabs"] == 13


def test_frozen_kch_super_mcp_overlay_composition(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KCH_011_HMAC_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("KCH_011_STATE", str(tmp_path / "kch-011.sqlite3"))
    server = IntegratedSuperMCP(tmp_path / "integrated")
    receipt = server.receipt()
    assert receipt["base_modified"] is False
    assert receipt["tool_collisions"] == []
    assert receipt["phl_real_executed"] is False
    listed = server.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}})
    assert len(listed["result"]["tools"]) == receipt["combined_tool_count"]
    assert any(tool["name"] == "kch.super.status" for tool in listed["result"]["tools"])
    assert any(tool["name"] == "studio_status" for tool in listed["result"]["tools"])
    assert any(tool["name"] == "mis_exact_decide" for tool in listed["result"]["tools"])
    server.close()
