from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SCHEMA = "kch.virtuous-handoff.v0.2.0"
RECEIPT_SCHEMA = "kch.virtuous-handoff.destination-receipt.v0.2.0"
OBSERVATION_SCHEMA = "kch.virtuous-handoff.destination-observation.v0.2.0"


class ContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def require_keys(value: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    missing = [key for key in keys if key not in value]
    require(not missing, f"{label}: faltan claves {missing}")


def validate_ref_rows(rows: Any, label: str, *, allow_empty: bool = False) -> list[dict[str, Any]]:
    require(isinstance(rows, list), f"{label} debe ser una lista")
    require(allow_empty or bool(rows), f"{label} no puede estar vacío")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        require(isinstance(row, dict), f"{label}[{index}] debe ser un objeto")
        require_keys(row, ("id", "text", "provenance"), f"{label}[{index}]")
        identifier = str(row["id"]).strip()
        require(identifier and identifier not in seen, f"{label}: id vacío o duplicado {identifier!r}")
        require(str(row["text"]).strip() != "", f"{label}[{index}].text vacío")
        require(isinstance(row["provenance"], list) and row["provenance"], f"{label}[{index}] sin procedencia")
        seen.add(identifier)
        normalized.append(row)
    return normalized


def _validate_source(source: dict[str, Any], index: int) -> None:
    label = f"sources[{index}]"
    require_keys(source, ("source_id", "source_uri", "verification_mode", "pages", "eof_verified"), label)
    require(str(source["source_uri"]).startswith(("codex://", "chatgpt-conversation://", "cline://", "opencode://", "cowork://")), f"{label}: URI no soportada")
    require(source["eof_verified"] is True, f"{label}: EOF no verificado")
    pages = source["pages"]
    require(isinstance(pages, list) and pages, f"{label}: sin paginas")
    require([page.get("page_index") for page in pages] == list(range(len(pages))), f"{label}: paginacion no contigua")
    for page_index, page in enumerate(pages):
        require_keys(page, ("page_index", "requested_cursor", "next_cursor", "response_sha256", "response_bytes"), f"{label}.pages[{page_index}]")
        if page_index:
            require(page["requested_cursor"] == pages[page_index - 1]["next_cursor"], f"{label}: cadena de cursor rota")
    require(pages[-1]["next_cursor"] in (None, ""), f"{label}: EOF declarado con cursor posterior")
    require(source["verification_mode"] in ("EXACT_PAGE_HASH", "DIALOGUE_EXACT_OUTPUTS_BOUNDED", "LIVE_PREFIX", "LIVE_PREFIX_OUTPUTS_BOUNDED"), f"{label}: modo de verificacion invalido")
    if source["verification_mode"].startswith("LIVE_PREFIX"):
        require(isinstance(source.get("required_item_ids"), list) and source["required_item_ids"], f"{label}: LIVE_PREFIX sin cutoff verificable")
    if source["verification_mode"].endswith("OUTPUTS_BOUNDED"):
        require(int(source.get("truncation_signal_count", 0)) > 0, f"{label}: outputs acotados sin frontera cuantificada")


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    require_keys(snapshot, ("schema", "sources"), "snapshot")
    require(snapshot["schema"] == "kch.native-source-collection.v0.2.0", "schema de snapshot no soportado")
    sources = snapshot["sources"]
    require(isinstance(sources, list) and sources, "snapshot sin fuentes")
    source_ids = [str(source.get("source_id", "")) for source in sources]
    require(all(source_ids) and len(source_ids) == len(set(source_ids)), "source_id vacio o duplicado")
    for index, source in enumerate(sources):
        require(isinstance(source, dict), f"sources[{index}] debe ser objeto")
        _validate_source(source, index)


def validate_state(state: dict[str, Any]) -> None:
    require_keys(
        state,
        (
            "schema", "project_id", "project_name", "governing_objective", "mission_provenance",
            "invariants", "corrections", "binding_decisions", "open_decisions", "inference_errors",
            "components", "evidence_boundaries", "claims", "gates", "next_actions", "artifacts",
            "assimilation_probes",
        ),
        "state",
    )
    require(state["schema"] == "kch.project-state.v0.1.0", "schema de estado no soportado")
    require(str(state["governing_objective"]).strip() != "", "objetivo gobernante vacío")
    require(isinstance(state["mission_provenance"], list) and state["mission_provenance"], "objetivo sin procedencia")
    validate_ref_rows(state["invariants"], "invariants")
    validate_ref_rows(state["corrections"], "corrections", allow_empty=True)
    validate_ref_rows(state["binding_decisions"], "binding_decisions")
    validate_ref_rows(state["open_decisions"], "open_decisions", allow_empty=True)
    validate_ref_rows(state["inference_errors"], "inference_errors", allow_empty=True)
    validate_ref_rows(state["evidence_boundaries"], "evidence_boundaries")
    validate_ref_rows(state["next_actions"], "next_actions")
    require(isinstance(state["components"], list) and state["components"], "components vacío")
    required_axes = {"capability", "support", "permission", "authority", "execution", "training"}
    for index, component in enumerate(state["components"]):
        require_keys(component, ("id", "name", "status", "provenance"), f"components[{index}]")
        require(isinstance(component["status"], dict), f"components[{index}].status debe ser objeto")
        require(required_axes <= set(component["status"]), f"components[{index}] confunde ejes de estado")
    require(isinstance(state["claims"], list), "claims debe ser lista")
    require(isinstance(state["gates"], list), "gates debe ser lista")
    require(isinstance(state["artifacts"], list), "artifacts debe ser lista")
    validate_ref_rows(state["assimilation_probes"], "assimilation_probes")


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}
