from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ledger import KwanPromptsLedger
from .mcp_server import handle
from .service_final import KwanPromptsService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="kwanprompts.sqlite3")
    args = parser.parse_args(argv)
    service = KwanPromptsService(KwanPromptsLedger(Path(args.state)))
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle(service, json.loads(line))
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

