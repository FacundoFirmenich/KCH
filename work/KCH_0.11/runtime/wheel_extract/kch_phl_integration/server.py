from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .service import ConflictError, EffectiveIntegrationService, IntegrationError, RequestCollisionError


class IntegrationHTTPServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], service: EffectiveIntegrationService, token: str):
        super().__init__(address, IntegrationHandler)
        self.service = service
        self.token = token


class IntegrationHandler(BaseHTTPRequestHandler):
    server: IntegrationHTTPServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {self.server.token}"

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 1_000_000:
            raise IntegrationError("invalid request body length")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise IntegrationError("request body must be an object")
        return value

    def do_GET(self) -> None:
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "UNAUTHORIZED"})
            return
        if self.path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok", "service": "KCH_PHL_EFFECTIVE_INTEGRATION_v0.2.0"})
        elif self.path == "/v1/projection":
            self._json(HTTPStatus.OK, self.server.service.projection())
        elif self.path == "/v1/verify":
            self._json(HTTPStatus.OK, self.server.service.verify())
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "UNAUTHORIZED"})
            return
        try:
            envelope = self._body()
            common = {
                "client": envelope["client"],
                "request_id": envelope["request_id"],
                "expected_head_hash": envelope["expected_head_hash"],
            }
            payload = envelope["payload"]
            if self.path == "/v1/decisions":
                result = self.server.service.register_decision(payload, **common)
            elif self.path == "/v1/phl/start":
                result = self.server.service.start_phl(trigger=payload["trigger"], **common)
            elif self.path == "/v1/phl/close":
                result = self.server.service.close_phl(payload["session_id"], **common)
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})
                return
            self._json(HTTPStatus.OK, result)
        except (ConflictError, RequestCollisionError) as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
        except (IntegrationError, KeyError, ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="kch-phl-integration")
    root.add_argument("--state", type=Path, required=True)
    root.add_argument("--token-file", type=Path, required=True)
    root.add_argument("--host", default="127.0.0.1")
    root.add_argument("--port", type=int, default=8765)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("non-loopback binding is prohibited in v0.2.0")
    if not args.token_file.is_file():
        raise SystemExit("token file does not exist")
    token = args.token_file.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise SystemExit("token must contain at least 32 characters")
    server = IntegrationHTTPServer((args.host, args.port), EffectiveIntegrationService(args.state), token)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

