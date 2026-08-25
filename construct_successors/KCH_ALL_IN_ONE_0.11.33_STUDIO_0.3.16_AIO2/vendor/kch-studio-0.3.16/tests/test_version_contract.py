from __future__ import annotations

import tomllib
from pathlib import Path

from kch_studio import __version__
from kch_studio.codex_bootstrap_mcp import SERVER_INFO as BOOTSTRAP_INFO
from kch_studio.codex_preflight_mcp import CodexPreflightMCP
from kch_studio.mcp_server import SERVER_INFO as STUDIO_INFO


def test_package_and_mcp_surfaces_share_one_version(tmp_path: Path) -> None:
    project = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert project["project"]["version"] == __version__
    assert BOOTSTRAP_INFO["version"] == __version__
    assert STUDIO_INFO["version"] == __version__

    preflight = CodexPreflightMCP(tmp_path / "preflight")
    initialized = preflight.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert initialized is not None
    assert initialized["result"]["serverInfo"]["version"] == __version__
