from __future__ import annotations

import json
from pathlib import Path

from kch_studio.adapters import HostAdapterCompiler


def test_opencode_adapter_matches_current_official_schema(tmp_path: Path) -> None:
    compiler = HostAdapterCompiler(tmp_path / "compiled")

    receipt = compiler.compile(
        name="kch-test",
        command=[r"C:\KCH\kch-super-mcp-studio.exe"],
        targets=["opencode"],
    )

    path = tmp_path / "compiled" / receipt["artifacts"][0]["path"]
    document = json.loads(path.read_text(encoding="utf-8"))
    assert set(document["mcp"]) == {"kch-test"}
    server = document["mcp"]["kch-test"]
    assert server == {
        "type": "local",
        "command": [r"C:\KCH\kch-super-mcp-studio.exe"],
        "enabled": False,
    }
    assert "servers" not in document["mcp"]
    assert "disabled" not in server
    assert "codemode" not in server
