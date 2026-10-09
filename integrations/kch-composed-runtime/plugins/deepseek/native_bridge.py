"""Bounded JSON transport to the pinned, unmodified KCH native policy.

This program is a host adapter, never a user-authorization endpoint.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import sys

PINNED = {
    "kch_native_hook.py": "cad2913d9cb1a482afd78ec1a377dd55db52e98cf644be72ab6fae6a4c2c340c",
    "kch_native_state.py": "2b8c6cdaec6a682a63bca8c875103c355ea8f4d3948ef14ca4c4e4e77f81398c",
}


def main() -> None:
    request = json.load(sys.stdin)
    host = request.get('host', 'deepseek')
    if host not in {'deepseek', 'kch-composed'}:
        raise ValueError('KCH_UNSUPPORTED_HOST')
    scripts = Path(request["nativeRoot"]) / "scripts"
    for name, expected in PINNED.items():
        if hashlib.sha256((scripts / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"KCH_SOURCE_PIN_MISMATCH: {name}")
    os.environ["KCH_NATIVE_DATA"] = request["dataDir"]
    sys.path.insert(0, str(scripts))
    state = importlib.import_module("kch_native_state")
    db = state.connect()
    try:
        if request["action"] == "probe":
            valid, count = state.verify_chain(db)
            result = {"locksEnabled": state.setting(db, "locks_enabled") == "true",
                      "chainValid": valid, "events": count,
                      "exactToolLocks": [row[0] for row in db.execute(
                          "SELECT pattern FROM locks WHERE enabled=1 AND kind='EXACT' AND pattern LIKE 'tool:%' ORDER BY pattern")]}
        elif request["action"] == "receipt":
            event_name = 'DSHToolResult' if host == 'deepseek' else 'KCHComposedToolResult'
            digest = state.log_event(db, event_name, request["payload"])
            result = {"recorded": True, "eventHash": digest}
        elif request["action"] == "pre":
            payload = request["payload"]
            if payload.get('hook_event_name') != 'PreToolUse':
                raise ValueError('KCH_PRETOOL_EVENT_REQUIRED')
            for field in ('session_id', 'tool_use_id', 'tool_name', 'cwd'):
                if not isinstance(payload.get(field), str) or not payload[field]:
                    raise ValueError(f'KCH_REQUIRED_FIELD:{field}')
            if not Path(payload['cwd']).is_absolute():
                raise ValueError('KCH_ABSOLUTE_CWD_REQUIRED')
            if state.setting(db, "locks_enabled") != "true":
                raise ValueError("KCH_LOCKS_DISABLED")
            # An arbitrary shell must be protected by a tool-wide lock: static
            # path extraction cannot establish all effects of shell programs.
            if payload["tool_name"] == "exec_command":
                locked = db.execute("SELECT 1 FROM locks WHERE enabled=1 AND kind='EXACT' "
                                    "AND pattern='tool:exec_command'").fetchone()
                if not locked:
                    raise ValueError("KCH_SHELL_TOOL_LOCK_REQUIRED")
            if host == 'kch-composed' and payload['tool_name'] == 'write':
                locked = db.execute("SELECT 1 FROM locks WHERE enabled=1 AND kind='EXACT' "
                                    "AND pattern='tool:write'").fetchone()
                if not locked:
                    raise ValueError('KCH_WRITE_TOOL_LOCK_REQUIRED')
            db.close()
            db = None
            hook = importlib.import_module("kch_native_hook")
            output = io.StringIO()
            previous_stdin = sys.stdin
            try:
                sys.stdin = io.StringIO(json.dumps(payload, ensure_ascii=False))
                with contextlib.redirect_stdout(output):
                    code = hook.main()
            finally:
                sys.stdin = previous_stdin
            if code != 0:
                raise ValueError(f"KCH_HOOK_EXIT:{code}")
            response = json.loads(output.getvalue()) if output.getvalue().strip() else {}
            decision = response.get("hookSpecificOutput", {})
            denied = decision.get("permissionDecision") == "deny"
            result = {"allowed": not denied,
                      "reason": decision.get("permissionDecisionReason", ""),
                      "nativeOutput": response}
        else:
            raise ValueError("KCH_UNSUPPORTED_BRIDGE_ACTION")
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    main()
