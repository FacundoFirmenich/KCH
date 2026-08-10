from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .atoms import AtomRegistry, SemanticAtom
from .canonical import sha256_file, sha256_payload


KHC_SCHEMA = "KHC_TWO_BATTERY_COMPARATIVE_8x8_v2.0.7"
KHC_MODELS = ("Luna", "Sol", "Terra")
KHC_ACTION_NAMES = ("ABSTAIN", "APPLY", "ESCALATE", "QUERY", "TOP_2", "WITHHOLD")


def khc_action_registry() -> AtomRegistry:
    registry = AtomRegistry()
    skins = {
        "ABSTAIN": "PARA",
        "APPLY": "ACTUA",
        "ESCALATE": "ELEVA",
        "QUERY": "PIDE",
        "TOP_2": "DOBLE",
        "WITHHOLD": "VETA",
    }
    for action in KHC_ACTION_NAMES:
        registry.register(
            SemanticAtom(
                atom_id=f"mis.action.{action.lower()}.v1",
                kind="bayes_action",
                skins={"canonical": action, "es": skins[action], "khc": action},
            )
        )
    return registry


@dataclass(frozen=True, slots=True)
class KHCDecisionRecord:
    round_index: int
    version: str
    model: str
    task_id: str
    action: str
    answer: str
    numeric_value: int | None
    evidence_ids: tuple[str, ...]
    question: str | None
    uncertainty: str

    def __post_init__(self) -> None:
        if self.round_index < 1 or self.round_index > 8:
            raise ValueError("KHC round index outside 1..8")
        if self.model not in KHC_MODELS:
            raise ValueError(f"unknown KHC model: {self.model}")
        if self.action not in KHC_ACTION_NAMES:
            raise ValueError(f"unknown KHC action: {self.action}")
        if isinstance(self.numeric_value, bool) or (
            self.numeric_value is not None and not isinstance(self.numeric_value, int)
        ):
            raise ValueError("KHC numeric_value must be an exact integer or null in this corpus")

    def coordinate(self) -> str:
        return f"B/R{self.round_index}/{self.model}/{self.task_id}"

    def to_payload(self) -> dict[str, object]:
        return {
            "round_index": self.round_index,
            "version": self.version,
            "model": self.model,
            "task_id": self.task_id,
            "action": self.action,
            "answer": self.answer,
            "numeric_value": self.numeric_value,
            "evidence_ids": list(self.evidence_ids),
            "question": self.question,
            "uncertainty": self.uncertainty,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "KHCDecisionRecord":
        expected = {
            "round_index",
            "version",
            "model",
            "task_id",
            "action",
            "answer",
            "numeric_value",
            "evidence_ids",
            "question",
            "uncertainty",
        }
        if set(payload) != expected:
            raise ValueError("KHC record fields differ from the strict v0.3 bridge contract")
        evidence_ids = payload["evidence_ids"]
        if not isinstance(evidence_ids, list) or not all(isinstance(item, str) for item in evidence_ids):
            raise ValueError("invalid evidence_ids")
        return cls(
            round_index=int(payload["round_index"]),
            version=str(payload["version"]),
            model=str(payload["model"]),
            task_id=str(payload["task_id"]),
            action=str(payload["action"]),
            answer=str(payload["answer"]),
            numeric_value=payload["numeric_value"],  # type: ignore[arg-type]
            evidence_ids=tuple(evidence_ids),
            question=None if payload["question"] is None else str(payload["question"]),
            uncertainty=str(payload["uncertainty"]),
        )


@dataclass(frozen=True, slots=True)
class MISKHCDecisionUnit:
    source_schema: str
    source_file_sha256: str
    coordinate: str
    action_atom_id: str
    record: KHCDecisionRecord
    explain_clauses: tuple[tuple[str, str], ...]
    unit_hash: str

    @classmethod
    def constitute(
        cls,
        record: KHCDecisionRecord,
        *,
        source_file_sha256: str,
        registry: AtomRegistry,
    ) -> "MISKHCDecisionUnit":
        atom = registry.parse(record.action, "khc")
        clauses = (
            ("source", record.coordinate()),
            ("action", atom.atom_id),
            ("support", ",".join(record.evidence_ids) if record.evidence_ids else "NONE"),
            ("uncertainty", record.uncertainty),
            ("question", record.question if record.question is not None else "NONE"),
        )
        core = {
            "schema": "MIS_KHC_DECISION_UNIT_v0.3",
            "source_schema": KHC_SCHEMA,
            "source_file_sha256": source_file_sha256,
            "coordinate": record.coordinate(),
            "action_atom_id": atom.atom_id,
            "record": record.to_payload(),
            "explain_clauses": [list(item) for item in clauses],
        }
        return cls(
            KHC_SCHEMA,
            source_file_sha256,
            record.coordinate(),
            atom.atom_id,
            record,
            clauses,
            sha256_payload(core),
        )

    def core_payload(self) -> dict[str, object]:
        return {
            "schema": "MIS_KHC_DECISION_UNIT_v0.3",
            "source_schema": self.source_schema,
            "source_file_sha256": self.source_file_sha256,
            "coordinate": self.coordinate,
            "action_atom_id": self.action_atom_id,
            "record": self.record.to_payload(),
            "explain_clauses": [list(item) for item in self.explain_clauses],
        }

    def to_payload(self) -> dict[str, object]:
        return {**self.core_payload(), "unit_hash": self.unit_hash}

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "MISKHCDecisionUnit":
        expected = {
            "schema",
            "source_schema",
            "source_file_sha256",
            "coordinate",
            "action_atom_id",
            "record",
            "explain_clauses",
            "unit_hash",
        }
        if set(payload) != expected or payload["schema"] != "MIS_KHC_DECISION_UNIT_v0.3":
            raise ValueError("invalid MIS-KHC unit payload")
        record_payload = payload["record"]
        clauses_payload = payload["explain_clauses"]
        if not isinstance(record_payload, dict) or not isinstance(clauses_payload, list):
            raise ValueError("invalid MIS-KHC record or clauses")
        clauses: list[tuple[str, str]] = []
        for item in clauses_payload:
            if not isinstance(item, list) or len(item) != 2 or not all(isinstance(v, str) for v in item):
                raise ValueError("invalid explain clause")
            clauses.append((item[0], item[1]))
        unit = cls(
            source_schema=str(payload["source_schema"]),
            source_file_sha256=str(payload["source_file_sha256"]),
            coordinate=str(payload["coordinate"]),
            action_atom_id=str(payload["action_atom_id"]),
            record=KHCDecisionRecord.from_payload(record_payload),
            explain_clauses=tuple(clauses),
            unit_hash=str(payload["unit_hash"]),
        )
        expected_atom_id = khc_action_registry().parse(unit.record.action, "khc").atom_id
        expected_clauses = (
            ("source", unit.record.coordinate()),
            ("action", expected_atom_id),
            ("support", ",".join(unit.record.evidence_ids) if unit.record.evidence_ids else "NONE"),
            ("uncertainty", unit.record.uncertainty),
            ("question", unit.record.question if unit.record.question is not None else "NONE"),
        )
        if (
            unit.coordinate != unit.record.coordinate()
            or unit.action_atom_id != expected_atom_id
            or unit.explain_clauses != expected_clauses
            or sha256_payload(unit.core_payload()) != unit.unit_hash
        ):
            raise ValueError("MIS-KHC unit integrity failure")
        return unit

    def sense_form(self, registry: AtomRegistry, language: str = "es") -> str:
        return registry.get(self.action_atom_id).render(language)

    def explain_form(self, registry: AtomRegistry, language: str = "es") -> str:
        action = registry.get(self.action_atom_id).render(language)
        support = ", ".join(self.record.evidence_ids) if self.record.evidence_ids else "ningÃºn evidence_id"
        question = self.record.question if self.record.question is not None else "no corresponde pregunta"
        return (
            f"Unidad {self.coordinate}. AcciÃ³n canÃ³nica: {action}. "
            f"Soporte registrado: {support}. Incertidumbre registrada: {self.record.uncertainty} "
            f"Pregunta: {question}."
        )


@dataclass(frozen=True, slots=True)
class KHCCorpus:
    path: Path
    source_sha256: str
    records: tuple[KHCDecisionRecord, ...]
    key_actions: Mapping[str, str]


def load_khc_corpus(path: str | Path) -> KHCCorpus:
    source_path = Path(path)
    data = json.loads(source_path.read_text(encoding="utf-8-sig"))
    if data.get("schema") != KHC_SCHEMA:
        raise ValueError(f"unexpected KHC schema: {data.get('schema')!r}")
    campaign = data.get("campaign_b")
    if not isinstance(campaign, dict):
        raise ValueError("campaign_b is missing")
    rounds = campaign.get("rounds")
    key = campaign.get("key")
    if not isinstance(rounds, dict) or tuple(sorted(rounds, key=int)) != tuple(str(i) for i in range(1, 9)):
        raise ValueError("KHC corpus must contain exactly rounds 1..8")
    if not isinstance(key, dict) or set(key) != {f"N{i:02d}" for i in range(1, 21)}:
        raise ValueError("KHC frozen key must contain exactly N01..N20")
    records: list[KHCDecisionRecord] = []
    for round_key in sorted(rounds, key=int):
        round_payload = rounds[round_key]
        models = round_payload.get("models") if isinstance(round_payload, dict) else None
        if not isinstance(models, dict) or set(models) != set(KHC_MODELS):
            raise ValueError(f"round {round_key} must contain the three KHC models")
        for model in KHC_MODELS:
            model_payload = models[model]
            output = model_payload.get("output") if isinstance(model_payload, dict) else None
            result_items = output.get("results") if isinstance(output, dict) else None
            if not isinstance(result_items, list) or len(result_items) != 20:
                raise ValueError(f"round {round_key}/{model} must contain 20 results")
            for item in result_items:
                if not isinstance(item, dict):
                    raise ValueError("KHC result must be an object")
                records.append(
                    KHCDecisionRecord(
                        round_index=int(round_key),
                        version=str(round_payload.get("version")),
                        model=model,
                        task_id=str(item.get("task_id")),
                        action=str(item.get("action")),
                        answer=str(item.get("answer")),
                        numeric_value=item.get("numeric_value"),
                        evidence_ids=tuple(item.get("evidence_ids", [])),
                        question=item.get("question"),
                        uncertainty=str(item.get("uncertainty")),
                    )
                )
    if len(records) != 480 or len({record.coordinate() for record in records}) != 480:
        raise ValueError("KHC bridge requires 480 unique real decision coordinates")
    key_actions = {task_id: str(value["action"]) for task_id, value in key.items()}
    if any(action not in KHC_ACTION_NAMES for action in key_actions.values()):
        raise ValueError("KHC key contains an unknown action")
    return KHCCorpus(source_path, sha256_file(source_path), tuple(records), key_actions)


def constitute_units(corpus: KHCCorpus) -> tuple[MISKHCDecisionUnit, ...]:
    registry = khc_action_registry()
    return tuple(
        MISKHCDecisionUnit.constitute(
            record,
            source_file_sha256=corpus.source_sha256,
            registry=registry,
        )
        for record in corpus.records
    )


def integration_audit(corpus: KHCCorpus) -> dict[str, object]:
    registry = khc_action_registry()
    units = constitute_units(corpus)
    roundtripped = tuple(MISKHCDecisionUnit.from_payload(unit.to_payload()) for unit in units)
    action_counts = Counter(record.action for record in corpus.records)
    key_roundtrips = sum(
        registry.parse(action, "khc").render("khc") == action
        for action in corpus.key_actions.values()
    )
    return {
        "schema": "MIS_KHC_INTEGRATION_AUDIT_v0.3",
        "source_schema": KHC_SCHEMA,
        "source_sha256": corpus.source_sha256,
        "records": len(corpus.records),
        "coordinates_unique": len({record.coordinate() for record in corpus.records}),
        "units_unique": len({unit.unit_hash for unit in units}),
        "roundtrips_exact": sum(a == b for a, b in zip(units, roundtripped, strict=True)),
        "key_roundtrips_exact": key_roundtrips,
        "action_counts": dict(sorted(action_counts.items())),
        "atom_ids": list(registry.atom_ids("bayes_action")),
        "claim_boundary": (
            "Structural, lossless MIS representation and replay only; this audit does not establish "
            "causal performance improvement over KHC."
        ),
    }


def records_by_stream(records: Iterable[KHCDecisionRecord]) -> dict[str, tuple[KHCDecisionRecord, ...]]:
    grouped: dict[str, list[KHCDecisionRecord]] = {}
    for record in records:
        stream_id = f"{record.model}/{record.task_id}"
        grouped.setdefault(stream_id, []).append(record)
    result: dict[str, tuple[KHCDecisionRecord, ...]] = {}
    for stream_id, items in grouped.items():
        ordered = tuple(sorted(items, key=lambda record: record.round_index))
        if tuple(record.round_index for record in ordered) != tuple(range(1, 9)):
            raise ValueError(f"non-contiguous KHC stream: {stream_id}")
        result[stream_id] = ordered
    if len(result) != 60:
        raise ValueError("expected 60 KHC model/task streams")
    return dict(sorted(result.items()))
