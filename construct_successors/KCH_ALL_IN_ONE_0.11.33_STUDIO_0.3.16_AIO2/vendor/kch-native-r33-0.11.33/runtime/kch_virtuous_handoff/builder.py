from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes, deterministic_zip, logical_digest, sha256_bytes, sha256_file, write_json
from .contracts import RECEIPT_SCHEMA, SCHEMA, validate_snapshot, validate_state


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} debe contener un objeto JSON")
    return value


def _ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["id"]) for row in rows]


def _mission_digest(state: dict[str, Any]) -> str:
    payload = {
        "project_id": state["project_id"],
        "governing_objective": state["governing_objective"],
        "mission_provenance": state["mission_provenance"],
        "invariants": state["invariants"],
        "corrections": state["corrections"],
        "binding_decisions": state["binding_decisions"],
        "evidence_boundaries": state["evidence_boundaries"],
        "next_actions": state["next_actions"],
    }
    return sha256_bytes(canonical_bytes(payload))


def make_bootstrap_prompt(contract: dict[str, Any]) -> str:
    sources = ", ".join(source["source_uri"] for source in contract["sources"])
    return (
        "Actua como sesion sucesora fresca bajo KCH. Antes de ejecutar, disenar o corregir: "
        "abre START_HERE.md; verifica artifact_manifest.json y continuity_contract.json; lee la "
        f"primera linea hasta la ultima de TODAS estas fuentes nativas: {sources}. Pagina cada una "
        "hasta EOF, conserva la cronologia interchat y usa herramientas nativas de lectura para que "
        "la sesion fuente pueda observar la traza. Trata el paquete como indice subordinado, nunca "
        "como sustituto. Luego devuelve UNICAMENTE un JSON "
        f"con schema={RECEIPT_SCHEMA!r}, handoff_id={contract['handoff_id']!r}, "
        f"bundle_digest={contract['bundle_digest']!r}, mission_digest={contract['mission_digest']!r}, "
        "acknowledged_invariants, acknowledged_corrections, understanding_map, probe_answers, "
        "acknowledged_binding_decisions, acknowledged_evidence_boundaries, next_action_id, "
        "action_taken=false, unresolved_conflicts y concise_understanding_es. understanding_map DEBE "
        "ser una lista exacta de {id,explanation_es,provenance}; probe_answers DEBE ser una lista "
        "exacta de {probe_id,answer_es,provenance}. Verifica destination_receipt.schema.json. No actues antes de que "
        "ese recibo sea validado por la fuente."
    )


def _start_here(contract: dict[str, Any], state: dict[str, Any]) -> str:
    action = state["next_actions"][0]
    source_rows = "\n".join(f"- `{source['source_id']}`: `{source['source_uri']}`" for source in contract["sources"])
    return f"""# START HERE - KCH Virtuous Handoff

## Identidad

- Handoff: `{contract['handoff_id']}`
- Proyecto: `{state['project_name']}` (`{state['project_id']}`)
- Fuentes nativas primarias, todas obligatorias:
{source_rows}
- Digest lógico del bundle: `{contract['bundle_digest']}`
- Digest de misión: `{contract['mission_digest']}`

## Regla de autoridad

Este paquete transporta estado estructurado y evidencia; no sustituye la conversación nativa.
La cronología posterior corrige formulaciones anteriores sin borrar su rastro. Antes de cualquier
acción, la sesión destino debe leer la fuente completa hasta EOF, verificar el manifiesto y emitir
el recibo JSON definido en `continuity_contract.json`.

## Misión gobernante

{state['governing_objective']}

## Próxima acción crítica predeclarada

`{action['id']}` — {action['text']}

## Orden de lectura

1. `artifact_manifest.json` y `continuity_contract.json`.
2. Cada fuente nativa completa, desde el primer turno hasta EOF, con traza observable.
3. `source_snapshot.json` como recibo de transporte, no como autoridad superior.
4. `project_state.json`, `mission_register.json` y `state_graph.json`.
5. Artefactos declarados, verificando sus hashes cuando estén disponibles.
6. Respuesta a las sondas cronologicas y emision del recibo sin acciones materiales.

## Límite

Un PASS de transporte demuestra continuidad informacional y abstención inicial. No demuestra que
el proyecto, sus componentes o sus hipótesis científicas estén validados o desplegados.
"""


def build_bundle(snapshot_path: Path, state_path: Path, out_dir: Path, *, create_zip: bool = True) -> dict[str, Any]:
    snapshot = load_json(snapshot_path)
    state = load_json(state_path)
    validate_snapshot(snapshot)
    validate_state(state)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"destino no vacío: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    handoff_id = f"KCH-HO-{uuid.uuid4()}"
    write_json(out_dir / "source_snapshot.json", snapshot)
    write_json(out_dir / "project_state.json", state)
    mission_register = {
        "schema": SCHEMA,
        "handoff_id": handoff_id,
        "project_id": state["project_id"],
        "project_name": state["project_name"],
        "governing_objective": state["governing_objective"],
        "mission_provenance": state["mission_provenance"],
        "invariants": state["invariants"],
        "corrections": state["corrections"],
        "binding_decisions": state["binding_decisions"],
        "open_decisions": state["open_decisions"],
        "inference_errors": state["inference_errors"],
        "next_actions": state["next_actions"],
        "assimilation_probes": state["assimilation_probes"],
    }
    write_json(out_dir / "mission_register.json", mission_register)
    graph = {
        "schema": "kch.handoff-state-graph.v0.1.0",
        "nodes": state["components"],
        "edges": state.get("component_edges", []),
        "rule": "capability != support != permission != authority != execution != training",
    }
    write_json(out_dir / "state_graph.json", graph)
    mission_digest = _mission_digest(state)
    precontract = {
        "schema": SCHEMA,
        "handoff_id": handoff_id,
        "created_at": utc_now(),
        "sources": [
            {
                "source_id": source["source_id"],
                "source_uri": source["source_uri"],
                "verification_mode": source["verification_mode"],
                "required_item_ids": source.get("required_item_ids", []),
                "truncation_signal_count": source.get("truncation_signal_count", 0),
                "page_receipts": [
                    {
                        "page_index": page["page_index"],
                        "requested_cursor": page["requested_cursor"],
                        "next_cursor": page["next_cursor"],
                        "response_sha256": page["response_sha256"],
                        "response_bytes": page["response_bytes"],
                    }
                    for page in source["pages"]
                ],
            }
            for source in snapshot["sources"]
        ],
        "source_snapshot_sha256": sha256_file(out_dir / "source_snapshot.json"),
        "mission_digest": mission_digest,
        "required_invariant_ids": _ids(state["invariants"]),
        "required_correction_ids": _ids(state["corrections"]),
        "required_binding_decision_ids": _ids(state["binding_decisions"]),
        "required_evidence_boundary_ids": _ids(state["evidence_boundaries"]),
        "allowed_next_action_ids": _ids(state["next_actions"]),
        "required_assimilation_probe_ids": _ids(state["assimilation_probes"]),
        "receipt_schema": RECEIPT_SCHEMA,
        "observation_schema": "kch.virtuous-handoff.destination-observation.v0.2.0",
        "destination_read_trace_required": True,
        "dialogue_must_be_complete": True,
        "bounded_tool_outputs_must_be_disclosed": True,
        "promotion_policy": "SOURCE_VALIDATES_RECEIPT_THEN_USER_OR_GOVERNED_POLICY_PROMOTES",
        "automatic_promotion": False,
    }
    provisional_entries = [
        {"path": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for name, path in (
            ("source_snapshot.json", out_dir / "source_snapshot.json"),
            ("project_state.json", out_dir / "project_state.json"),
            ("mission_register.json", out_dir / "mission_register.json"),
            ("state_graph.json", out_dir / "state_graph.json"),
        )
    ]
    precontract["bundle_digest"] = logical_digest(provisional_entries)
    write_json(out_dir / "continuity_contract.json", precontract)
    receipt_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": RECEIPT_SCHEMA,
        "type": "object",
        "required": [
            "schema", "handoff_id", "bundle_digest", "mission_digest", "acknowledged_invariants",
            "acknowledged_corrections", "understanding_map", "probe_answers",
            "acknowledged_binding_decisions", "acknowledged_evidence_boundaries", "next_action_id",
            "action_taken", "unresolved_conflicts", "concise_understanding_es",
        ],
        "properties": {
            "schema": {"const": RECEIPT_SCHEMA},
            "handoff_id": {"const": handoff_id},
            "bundle_digest": {"const": precontract["bundle_digest"]},
            "mission_digest": {"const": mission_digest},
            "understanding_map": {
                "type": "array",
                "items": {"type": "object", "required": ["id", "explanation_es", "provenance"]},
            },
            "probe_answers": {
                "type": "array",
                "items": {"type": "object", "required": ["probe_id", "answer_es", "provenance"]},
            },
            "action_taken": {"const": False},
        },
    }
    write_json(out_dir / "destination_receipt.schema.json", receipt_schema)
    (out_dir / "START_HERE.md").write_text(_start_here(precontract, state), encoding="utf-8", newline="\n")
    (out_dir / "BOOTSTRAP_PROMPT.txt").write_text(make_bootstrap_prompt(precontract) + "\n", encoding="utf-8", newline="\n")
    entries = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "artifact_manifest.json":
            entries.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    manifest = {
        "schema": "kch.handoff-artifact-manifest.v0.1.0",
        "handoff_id": handoff_id,
        "logical_digest": logical_digest(entries),
        "files": entries,
    }
    write_json(out_dir / "artifact_manifest.json", manifest)
    result = {
        "handoff_id": handoff_id,
        "bundle_dir": str(out_dir.resolve()),
        "logical_digest": manifest["logical_digest"],
        "mission_digest": mission_digest,
        "files": len(entries) + 1,
    }
    if create_zip:
        zip_path = out_dir.with_suffix(".zip")
        if zip_path.exists():
            raise FileExistsError(f"ZIP ya existe: {zip_path}")
        result["zip_path"] = str(zip_path.resolve())
        result["zip_sha256"] = deterministic_zip(out_dir, zip_path)
        result["zip_bytes"] = zip_path.stat().st_size
    return result
