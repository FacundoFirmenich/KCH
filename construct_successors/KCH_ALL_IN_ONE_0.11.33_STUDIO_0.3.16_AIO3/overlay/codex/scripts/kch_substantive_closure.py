from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "config" / "substantive_closure.v1.json"
SUPPORTED_EVENTS = {"SessionStart", "UserPromptSubmit"}


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "kch.csi.output-contract.v1":
        raise ValueError("unsupported substantive-closure contract schema")
    if payload.get("id") != "KCH_SUBSTANTIVE_CLOSURE_V1":
        raise ValueError("unexpected substantive-closure contract id")
    return payload


def render_context(contract: dict[str, Any]) -> str:
    closure = contract["closure"]
    archive = contract["archivistics"]
    if closure["language"] != "es" or closure["default_paragraphs"] != {"minimum": 1, "maximum": 2}:
        raise ValueError("closure defaults do not match the governed Spanish interface")
    if archive["chat_reference_lines_maximum"] != 1 or not archive["consolidate_in_one_artifact"]:
        raise ValueError("archivistic condensation is not governed")
    return (
        "KCH contrato universal de cierre sustantivo: todo checkpoint o cierre material debe terminar "
        "con uno o dos parrafos cohesivos en castellano que expliquen objetivo gobernante, posicion frente "
        "al checkpoint anterior, resultado observado, significado, frontera de evidencia, incertidumbre, "
        "reparabilidad, consecuencia y proxima accion decisiva. Una tabla compacta se admite solo si aclara "
        "scoring o comparacion y siempre se interpreta en prosa. Custodia, hashes, manifests, commits, URLs, "
        "inventarios y recuentos se concentran en un unico MD/TXT y se enlazan en como maximo una linea; son "
        "soporte, no prueba de validez cientifica, correccion semantica, completitud, utilidad ni autoridad. "
        "Conserva evidencia adversa, gates fallidos, abstenciones y NOT_ESTIMABLE. No firmes ni cierres con "
        "etiquetas, hashes, inventarios o ceremonial: eso constituye fallo de interfaz y debe repararse."
    )


def response(event: str, text: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        }
    }


def main() -> int:
    payload = json.load(sys.stdin)
    event = str(payload.get("hook_event_name", "UNKNOWN"))
    if event not in SUPPORTED_EVENTS:
        return 0
    json.dump(response(event, render_context(load_contract())), sys.stdout, ensure_ascii=False, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())