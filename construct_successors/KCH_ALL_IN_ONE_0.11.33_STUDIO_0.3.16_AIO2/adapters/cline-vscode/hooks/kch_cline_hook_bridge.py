from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


EVENT_MAP = {
    "TaskStart": "SessionStart",
    "TaskResume": "SessionStart",
    "TaskCancel": "SessionEnd",
    "TaskComplete": "SessionEnd",
    "UserPromptSubmit": "UserPromptSubmit",
    "PreToolUse": "PreToolUse",
    "PostToolUse": "PostToolUse",
    "PreCompact": "PreCompact",
}


def emit(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def nested(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def to_codex(payload: dict[str, Any]) -> dict[str, Any]:
    cline_event = str(payload.get("hookName", ""))
    event = EVENT_MAP.get(cline_event)
    if event is None:
        raise ValueError(f"unsupported Cline hook: {cline_event!r}")
    roots = payload.get("workspaceRoots")
    cwd = str(roots[0]) if isinstance(roots, list) and roots else os.getcwd()
    task_id = str(payload.get("taskId", ""))
    timestamp = str(payload.get("timestamp", ""))
    result: dict[str, Any] = {
        "hook_event_name": event,
        "session_id": task_id,
        "turn_id": timestamp,
        "cwd": cwd,
        "cline_hook_name": cline_event,
        "cline_version": str(payload.get("clineVersion", "")),
    }
    if cline_event == "TaskStart":
        result["prompt"] = str(nested(nested(payload, "taskStart"), "taskMetadata").get("initialTask", ""))
    elif cline_event == "UserPromptSubmit":
        result["prompt"] = str(nested(payload, "userPromptSubmit").get("prompt", ""))
    elif cline_event == "PreToolUse":
        tool = nested(payload, "preToolUse")
        result["tool_name"] = str(tool.get("toolName", ""))
        result["tool_input"] = tool.get("parameters", {})
        result["tool_use_id"] = f"cline:{task_id}:{timestamp}"
    elif cline_event == "PostToolUse":
        tool = nested(payload, "postToolUse")
        result["tool_name"] = str(tool.get("toolName", ""))
        result["tool_input"] = tool.get("parameters", {})
        result["tool_response"] = {
            "result": tool.get("result"),
            "success": tool.get("success"),
            "execution_time_ms": tool.get("executionTimeMs"),
        }
    elif cline_event == "PreCompact":
        result["compaction"] = nested(payload, "preCompact")
    return result


def native_root() -> Path:
    configured = os.environ.get("KCH_AIO_CLINE_NATIVE_ROOT") or os.environ.get("KCH_AIO1_CLINE_NATIVE_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[2] / "kch-aio2" / "native"


def run_native(script_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    root = native_root()
    script = root / "scripts" / script_name
    if not script.is_file():
        raise FileNotFoundError(script)
    env = dict(os.environ)
    env["PLUGIN_ROOT"] = str(root)
    completed = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(script)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=12,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit={completed.returncode}"
        raise RuntimeError(f"{script_name}: {detail}")
    raw = completed.stdout.strip()
    if not raw:
        return None
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{script_name} returned non-object JSON")
    return value


def translate(values: list[dict[str, Any] | None]) -> dict[str, Any]:
    context_parts: list[str] = []
    errors: list[str] = []
    cancel = False
    for value in values:
        if not value:
            continue
        hook = value.get("hookSpecificOutput")
        if isinstance(hook, dict):
            context = hook.get("additionalContext")
            if context:
                context_parts.append(str(context))
            if hook.get("permissionDecision") == "deny":
                cancel = True
                errors.append(str(hook.get("permissionDecisionReason", "KCH blocked the operation")))
        if value.get("decision") == "block":
            cancel = True
            errors.append(str(value.get("reason", "KCH blocked the operation")))
    result: dict[str, Any] = {"cancel": cancel}
    if context_parts:
        result["contextModification"] = "\n\n".join(context_parts)
    if errors:
        result["errorMessage"] = "\n".join(errors)
    return result


def main() -> int:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("Cline hook input must be a JSON object")
    codex_payload = to_codex(payload)
    scripts = ["kch_native_hook.py"]
    if codex_payload["hook_event_name"] in {"SessionStart", "PreCompact"}:
        scripts.append("kch_r33_runtime.py")
    if codex_payload["hook_event_name"] in {"SessionStart", "UserPromptSubmit"}:
        scripts.append("kch_contractual_rigor.py")
    try:
        emit(translate([run_native(script, codex_payload) for script in scripts]))
    except Exception as exc:
        pretool = str(payload.get("hookName", "")) == "PreToolUse"
        emit(
            {
                "cancel": pretool,
                "errorMessage": f"KCH_CLINE_BRIDGE_FAILURE: {type(exc).__name__}: {exc}",
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
