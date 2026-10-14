from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .broker import AuthorityBroker, AuthorityError


METHODS = {
    "kch.authority.verify": "verify",
    "kch.authority.prepare": "prepare",
    "kch.authority.commit": "commit",
    "kch.authority.receipt": "receipt",
    "kch.authority.abort": "abort",
    "kch.authority.indoubt": "indoubt",
    "kch.authority.status": "status",
}


def handle_request(broker: AuthorityBroker, request: dict[str, Any]) -> dict[str, Any]:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})
    if not isinstance(method, str) or method not in METHODS:
        return {
            "id": request_id,
            "ok": False,
            "error": {"code": "METHOD_NOT_FOUND", "message": "unknown authority method"},
        }
    if not isinstance(params, dict):
        return {
            "id": request_id,
            "ok": False,
            "error": {"code": "INVALID_REQUEST", "message": "params must be an object"},
        }
    try:
        result = getattr(broker, METHODS[method])(params)
        return {"id": request_id, "ok": True, "result": result}
    except AuthorityError as exc:
        return {
            "id": request_id,
            "ok": False,
            "error": {
                "code": exc.code,
                "message": str(exc),
                "retryable": exc.retryable,
            },
        }
    except Exception:
        return {
            "id": request_id,
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "authority broker failed closed",
                "retryable": False,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="KCH ↔ KwanTau authority stdio broker")
    parser.add_argument("--database", help="Explicit KCH Native SQLite database path")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Read one JSON request from stdin and exit",
    )
    args = parser.parse_args()
    broker = AuthorityBroker(args.database)

    if args.once:
        raw = sys.stdin.readline()
        if not raw:
            return 0
        request = json.loads(raw)
        sys.stdout.write(json.dumps(handle_request(broker, request), separators=(",", ":")) + "\n")
        sys.stdout.flush()
        return 0

    for raw in sys.stdin:
        if not raw.strip():
            continue
        try:
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise TypeError
            response = handle_request(broker, request)
        except Exception:
            response = {
                "id": None,
                "ok": False,
                "error": {
                    "code": "INVALID_JSON",
                    "message": "request must be one JSON object",
                    "retryable": False,
                },
            }
        sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
