from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any


RUNTIMES = {
    "kwandisk": "kwandisk",
    "tokenmaster": "tokenmaster",
    "mis031_full_csi": "kch_mis031_full_csi",
    "mu_transmuter_scpp": "kch_mu_transmuter_scpp",
    "virtuous_handoff": "kch_virtuous_handoff",
}


def plugin_root() -> Path:
    configured = os.environ.get("PLUGIN_ROOT")
    return Path(configured).resolve() if configured else Path(__file__).resolve().parents[1]


def runtime_status() -> dict[str, Any]:
    runtime = plugin_root() / "runtime"
    sys.path.insert(0, str(runtime))
    modules: dict[str, dict[str, Any]] = {}
    for component, module_name in RUNTIMES.items():
        try:
            module = importlib.import_module(module_name)
            modules[component] = {
                "available": True,
                "version": str(getattr(module, "__version__", "UNDECLARED")),
                "module": module_name,
            }
        except Exception as exc:
            modules[component] = {
                "available": False,
                "error": f"{type(exc).__name__}: {exc}",
                "module": module_name,
            }
    return {
        "schema": "kch.native-r33.runtime-status.v0.1.0",
        "release": "KCH 0.11.33",
        "runtime_root": str(runtime),
        "modules": modules,
        "all_available": all(row["available"] for row in modules.values()),
        "phl_authorized": True,
        "phl_training_executed": False,
    }


def emit_context(event: str, text: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}, ensure_ascii=False))


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps(runtime_status(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    payload = json.load(sys.stdin)
    event = str(payload.get("hook_event_name", "UNKNOWN"))
    if event == "SessionStart":
        status = runtime_status()
        available = ", ".join(name for name, row in status["modules"].items() if row["available"])
        missing = ", ".join(name for name, row in status["modules"].items() if not row["available"])
        message = f"KCH R33 runtime observado. Disponibles: {available or 'ninguno'}."
        if missing:
            message += f" No disponibles: {missing}; no los trates como activos."
        message += " Virtuous Handoff exige lectura completa multi-chat, traza nativa, recibo exacto y validacion desde la fuente antes de actuar."
        emit_context(event, message)
    elif event == "PreCompact":
        emit_context(
            event,
            "KCH R33 PreCompact: conserva mision, correcciones, decisiones, limites de evidencia, procesos vivos y proxima accion. "
            "La compactacion no valida un traspaso: si se abre una sesion fresca, activa kch-virtuous-handoff y exige EOF de todas las fuentes, observacion externa y recibo promovible.",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
