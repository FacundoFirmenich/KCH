from __future__ import annotations

import argparse
import json
from pathlib import Path

from transport_guard import TransportGuard


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--envelope", type=Path, required=True)
    sent = commands.add_parser("mark-sent")
    sent.add_argument("--dispatch-id", required=True)
    sent.add_argument("--native-request-turn-id", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("--dispatch-id", required=True)
    ingest.add_argument("--native-response-turn-id", required=True)
    ingest.add_argument("--response", type=Path, required=True)
    status = commands.add_parser("status")
    status.add_argument("--dispatch-id", required=True)
    commands.add_parser("verify")
    args = parser.parse_args()
    guard = TransportGuard(args.state)
    if args.command == "prepare":
        result = guard.prepare(json.loads(args.envelope.read_text(encoding="utf-8")))
    elif args.command == "mark-sent":
        result = guard.mark_sent(args.dispatch_id, args.native_request_turn_id)
    elif args.command == "ingest":
        result = guard.ingest(args.dispatch_id, args.native_response_turn_id, args.response.read_text(encoding="utf-8").strip())
    elif args.command == "status":
        result = guard.status(args.dispatch_id)
    else:
        result = guard.verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
