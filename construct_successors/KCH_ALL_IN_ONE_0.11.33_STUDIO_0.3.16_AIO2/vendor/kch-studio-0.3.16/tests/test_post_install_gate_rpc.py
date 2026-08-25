from __future__ import annotations

import io
import json

import pytest

from scripts.post_install_gate import rpc


class _Input:
    def write(self, _value: str) -> int:
        return 1

    def flush(self) -> None:
        return None


class _Process:
    def __init__(self, response: dict[str, object]) -> None:
        self.stdin = _Input()
        self.stdout = io.StringIO(json.dumps(response) + "\n")
        self.stderr = io.StringIO("")

    def poll(self) -> int | None:
        return None


def test_rpc_rejects_jsonrpc_error_instead_of_reporting_stage_pass() -> None:
    process = _Process(
        {"jsonrpc": "2.0", "id": 4, "error": {"code": -32602, "message": "locked"}}
    )
    with pytest.raises(RuntimeError, match="locked"):
        rpc(
            process,  # type: ignore[arg-type]
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call"},
            label="kch_preflight",
            timeout_seconds=1,
        )


def test_rpc_rejects_mismatched_response_id() -> None:
    process = _Process({"jsonrpc": "2.0", "id": 5, "result": {}})
    with pytest.raises(RuntimeError, match="mismatched id"):
        rpc(
            process,  # type: ignore[arg-type]
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call"},
            label="kch_preflight",
            timeout_seconds=1,
        )


def test_rpc_accepts_matching_result() -> None:
    process = _Process({"jsonrpc": "2.0", "id": 4, "result": {"gate": "PASS"}})
    response = rpc(
        process,  # type: ignore[arg-type]
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call"},
        label="kch_preflight",
        timeout_seconds=1,
    )
    assert response["result"] == {"gate": "PASS"}