from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


def emit(value: dict) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def main() -> None:
    gate = Path(__file__).resolve().parents[2]
    workspace = gate.parents[1]
    base_deployment = workspace / "work" / "KCH_0.11_AGENT_SHADOW_DEPLOYMENT"
    sys.path.insert(0, str(gate / "src"))
    from kch_activation.bootstrap import prepare_environment

    prepare_environment(gate, base_deployment)
    from kch_activation.runtime import ActivationRuntime

    payload = json.load(sys.stdin)
    session_id = str(payload["session_id"])
    event_id = str(payload["turn_id"])
    prompt = str(payload["prompt"])
    decision = ActivationRuntime().engine.scan(session_id, event_id, "USER_PROMPT_SUBMIT", prompt)
    action = decision["action"]
    if action == "NO_ACTIVATION":
        return
    if action == "ASK_USER":
        emit({"decision": "block", "reason": decision["proposal"]["question"]})
        return

    original_prompt = decision.get("original_prompt", "")
    safe = copy.deepcopy(decision)
    safe.pop("original_prompt", None)
    if isinstance(safe.get("proposal"), dict):
        safe["proposal"].pop("source_text", None)

    if original_prompt:
        context = (
            "KCH ACTIVATION GATE: el mensaje actual es exclusivamente la respuesta de consentimiento a una consulta "
            "que bloqueó el turno anterior. Retoma y ejecuta ahora la petición original siguiente, respetando la decisión "
            "y la evidencia de activación adjunta.\n\nPETICIÓN ORIGINAL:\n"
            + original_prompt
            + "\n\nDECISIÓN/EVIDENCIA KCH:\n"
            + json.dumps(safe, ensure_ascii=False, sort_keys=True)
        )
    else:
        context = "KCH ACTIVATION GATE aplicó una política de esta sesión al turno actual:\n" + json.dumps(safe, ensure_ascii=False, sort_keys=True)
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            }
        }
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        emit(
            {
                "continue": True,
                "systemMessage": "KCH proactive activation gate no pudo evaluar este turno: " + type(exc).__name__ + ": " + str(exc),
            }
        )
