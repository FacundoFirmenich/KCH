from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .ledger import KwanPromptsError, KwanPromptsLedger
from .service import KwanPromptsService


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


TOOLS = [
    {
        "name": "kwanprompts.status",
        "description": "Inspect KwanPrompts jurisdiction, separator and ledger state.",
        "inputSchema": _schema({}, []),
    },
    {
        "name": "kwanprompts.message.ingest",
        "description": "Preserve and structure one exact chat message without canonical promotion.",
        "inputSchema": _schema(
            {
                "message_id": {"type": "string", "minLength": 1},
                "thread_id": {"type": "string", "minLength": 1},
                "role": {"type": "string", "enum": ["system", "developer", "user", "assistant", "tool"]},
                "raw_text": {"type": "string", "minLength": 1},
                "ordinal": {"type": ["integer", "null"], "minimum": 0},
                "timestamp": {"type": ["string", "null"]},
                "source_uri": {"type": ["string", "null"]},
                "parent_message_id": {"type": ["string", "null"]},
            },
            ["message_id", "thread_id", "role", "raw_text"],
        ),
    },
    {
        "name": "kwanprompts.message.inspect",
        "description": "Return the exact preserved message and its explainable structure.",
        "inputSchema": _schema({"message_id": {"type": "string", "minLength": 1}}, ["message_id"]),
    },
    {
        "name": "kwanprompts.review.adjudicate",
        "description": "Append an explicit human review without mutating raw content or canonizing it.",
        "inputSchema": _schema(
            {
                "message_id": {"type": "string", "minLength": 1},
                "decision": {"type": "string", "enum": ["PROMOTE_STRATEGIC", "KEEP_INTERMEDIATE", "MARK_REVIEW"]},
                "actor": {"type": "string", "minLength": 1},
                "reason": {"type": "string", "minLength": 1},
            },
            ["message_id", "decision", "actor", "reason"],
        ),
    },
    {
        "name": "kwanprompts.kwandocs.envelope",
        "description": "Export a full raw message graph envelope; does not execute KwanDocs ingestion.",
        "inputSchema": _schema({"thread_id": {"type": "string", "minLength": 1}}, ["thread_id"]),
    },
    {
        "name": "kwanprompts.ledger.verify",
        "description": "Verify the append-only event chain and message/adjudication projections.",
        "inputSchema": _schema({}, []),
    },
]


def call(service: KwanPromptsService, name: str, arguments: dict[str, Any]) -> Any:
    if name == "kwanprompts.status":
        return service.status()
    if name == "kwanprompts.message.ingest":
        return service.ingest(arguments)
    if name == "kwanprompts.message.inspect":
        return service.inspect(str(arguments.get("message_id", "")))
    if name == "kwanprompts.review.adjudicate":
        return service.adjudicate(arguments)
    if name == "kwanprompts.kwandocs.envelope":
        return service.kwandocs_envelope(str(arguments.get("thread_id", "")))
    if name == "kwanprompts.ledger.verify":
        return service.ledger.verify()
    raise KwanPromptsError("unknown tool")


def handle(service: KwanPromptsService, message: dict[str, Any]) -> dict[str, Any]:
    request_id = message.get("id")
    try:
        method = message.get("method")
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "kwanprompts", "version": "0.1.0"},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = message.get("params") or {}
            payload = call(service, str(params.get("name", "")), dict(params.get("arguments") or {}))
            result = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, sort_keys=True)}]}
        else:
            raise KwanPromptsError("unsupported JSON-RPC method")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": f"{type(exc).__name__}: {exc}"},
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="kwanprompts.sqlite3")
    args = parser.parse_args(argv)
    service = KwanPromptsService(KwanPromptsLedger(Path(args.state)))
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = handle(service, message)
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

