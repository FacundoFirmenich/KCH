from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
HOOK = SCRIPTS / "kch_native_hook.py"
sys.path.insert(0, str(SCRIPTS))

from kch_native_state import (  # noqa: E402
    connect,
    normalize_file,
    set_setting,
    utc_now,
    verify_chain,
)


def invoke(payload: dict[str, Any], state: Path) -> tuple[int, dict[str, Any] | None, str]:
    env = os.environ.copy()
    env["KCH_NATIVE_DATA"] = str(state)
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(HOOK)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    output = json.loads(completed.stdout) if completed.stdout else None
    return completed.returncode, output, completed.stderr


def payload(event: str, **extra: Any) -> dict[str, Any]:
    return {
        "hook_event_name": event,
        "session_id": "SESSION-R33-LOCAL",
        "turn_id": "TURN-1",
        **extra,
    }


def test_complete_local_lifecycle_and_lock_interposition(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "state"
    protected = tmp_path / "protected" / "HARNESS.md"
    protected.parent.mkdir(parents=True)
    protected.write_text("stable\n", encoding="utf-8")
    monkeypatch.setenv("KCH_NATIVE_DATA", str(state))
    with connect() as db:
        set_setting(db, "locks_enabled", "true")
        db.execute(
            "INSERT INTO locks(id,kind,pattern,enabled,created_at,baseline_sha256) VALUES(?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                "EXACT",
                normalize_file(str(protected), str(tmp_path)),
                1,
                utc_now(),
                None,
            ),
        )
        db.commit()

    code, start, error = invoke(payload("SessionStart"), state)
    assert code == 0 and not error
    assert "KCH 0.11.33" in start["hookSpecificOutput"]["additionalContext"]

    code, prompt, error = invoke(payload("UserPromptSubmit", prompt="prosigue"), state)
    assert code == 0 and not error
    assert prompt["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"

    code, read, error = invoke(
        payload(
            "PreToolUse",
            tool_name="shell_command",
            tool_input={"command": f"Get-Content -LiteralPath {protected}"},
            tool_use_id="READ-1",
            cwd=str(tmp_path),
        ),
        state,
    )
    assert code == 0 and not error
    assert "simple read" in read["hookSpecificOutput"]["additionalContext"]

    patch = (
        "*** Begin Patch\n"
        f"*** Update File: {protected}\n"
        "@@\n-stable\n+changed\n"
        "*** End Patch"
    )
    code, mutation, error = invoke(
        payload(
            "PreToolUse",
            tool_name="apply_patch",
            tool_input=patch,
            tool_use_id="MUTATE-1",
            cwd=str(tmp_path),
        ),
        state,
    )
    assert code == 0 and not error
    decision = mutation["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "operation=MUTATE" in decision["permissionDecisionReason"]
    assert protected.read_text(encoding="utf-8") == "stable\n"

    code, monitor, error = invoke(
        payload("PostToolUse", tool_response={"output": "Script running with cell ID 33"}),
        state,
    )
    assert code == 0 and not error
    assert "monitoriza" in monitor["hookSpecificOutput"]["additionalContext"]

    code, stop, error = invoke(payload("Stop", stop_hook_active=False), state)
    assert code == 0 and not error
    assert stop["decision"] == "block"

    code, ended, error = invoke(payload("SessionEnd"), state)
    assert code == 0 and not error and ended is None
    with connect() as db:
        valid, count = verify_chain(db)
        assert valid is True
        assert count == 7
        proposal = db.execute("SELECT status FROM proposals").fetchone()
        assert proposal[0] == "DRAFT"
