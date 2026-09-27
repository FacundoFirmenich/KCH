from __future__ import annotations

import importlib
import json
import os
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable

from .surface import EXPECTED_WHEEL_SHA256, scan_wheel


class MISBridgeError(RuntimeError):
    pass


class MISPermissionError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class PathPolicy:
    read_roots: tuple[Path, ...] = ()
    write_roots: tuple[Path, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        read_roots: Iterable[str | Path] = (),
        write_roots: Iterable[str | Path] = (),
    ) -> "PathPolicy":
        return cls(
            tuple(Path(item).resolve() for item in read_roots),
            tuple(Path(item).resolve() for item in write_roots),
        )

    @staticmethod
    def _inside(path: Path, roots: tuple[Path, ...]) -> bool:
        return any(path == root or root in path.parents for root in roots)

    def readable(self, path: str | Path) -> Path:
        resolved = Path(path).resolve(strict=True)
        if not resolved.is_file() or not self._inside(resolved, self.read_roots):
            raise MISPermissionError(f"MIS read outside declared roots: {resolved}")
        return resolved

    def writable_directory(self, path: str | Path) -> Path:
        candidate = Path(path)
        resolved = candidate.resolve(strict=False)
        parent = resolved.parent.resolve(strict=True)
        if not self._inside(parent, self.write_roots):
            raise MISPermissionError(f"MIS write outside declared roots: {resolved}")
        if resolved.exists() and any(resolved.iterdir()):
            raise FileExistsError(f"MIS output directory must be absent or empty: {resolved}")
        return resolved


class MISFullCSIBridge:
    """Stateless CSI façade over every public MIS 0.3.1 capability.

    Stateful MIS objects cross the boundary as canonical payloads. Each mutation
    rehydrates a fresh object and returns a successor payload, so callers never
    receive an opaque process-local handle or hidden authority.
    """

    SCHEMA = "kch.mis031.full-csi-result.v0.2.0"

    def __init__(self, wheel: str | Path, *, path_policy: PathPolicy | None = None) -> None:
        self.wheel = Path(wheel).resolve(strict=True)
        self.surface = scan_wheel(self.wheel)
        if self.surface["unclassified"]:
            raise MISBridgeError(f"unclassified MIS public symbols: {self.surface['unclassified']}")
        self.path_policy = path_policy or PathPolicy()
        self._load_modules()
        self._operations = self._bind_operations()

    def _load_modules(self) -> None:
        wheel_text = str(self.wheel)
        if wheel_text not in sys.path:
            sys.path.insert(0, wheel_text)
        self.mis = importlib.import_module("mis_v03")
        if getattr(self.mis, "__version__", None) != "0.3.1":
            raise MISBridgeError("loaded MIS version is not 0.3.1")
        origin = str(Path(self.mis.__file__).resolve(strict=False))
        if self.wheel.name not in origin:
            raise MISBridgeError(f"MIS imported from an unsealed origin: {origin}")
        self.atoms = importlib.import_module("mis_v03.atoms")
        self.canonical = importlib.import_module("mis_v03.canonical")
        self.decision = importlib.import_module("mis_v03.decision")
        self.exact = importlib.import_module("mis_v03.exact")
        self.experiments = importlib.import_module("mis_v03.experiments")
        self.freeze = importlib.import_module("mis_v03.freeze")
        self.khc = importlib.import_module("mis_v03.khc")

    @staticmethod
    def _require(arguments: dict[str, Any], permission: str) -> None:
        if arguments.get("permission") != permission:
            raise MISPermissionError(f"exact permission required: {permission}")

    def _fraction(self, value: Any) -> Fraction:
        if isinstance(value, bool):
            raise TypeError("booleans are not exact numeric inputs")
        if isinstance(value, int):
            return Fraction(value)
        if isinstance(value, str):
            return self.canonical.parse_fraction(value)
        raise TypeError("exact values must be integers or canonical fraction strings")

    def _decode_exact(self, value: Any) -> Any:
        if isinstance(value, dict):
            if set(value) == {"$fraction"}:
                return self._fraction(value["$fraction"])
            return {key: self._decode_exact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._decode_exact(item) for item in value]
        return value

    def _encode_exact(self, value: Any) -> Any:
        return self.canonical.canonical_value(value)

    def _distribution(self, payload: dict[str, Any]) -> Any:
        return self.exact.ExactDistribution.from_payload(payload)

    def _atom(self, payload: dict[str, Any]) -> Any:
        return self.atoms.SemanticAtom(
            atom_id=str(payload["atom_id"]),
            kind=str(payload["kind"]),
            skins=dict(payload["skins"]),
        )

    def _registry(self, payload: list[dict[str, Any]]) -> Any:
        registry = self.atoms.AtomRegistry()
        for item in payload:
            registry.register(self._atom(item))
        return registry

    def _loss_table(self, payload: dict[str, Any]) -> Any:
        if payload.get("schema") != "MIS_LOSS_TABLE_v0.3.1":
            raise ValueError("invalid MIS loss table schema")
        actions = tuple(payload["actions"])
        states = tuple(payload["states"])
        nested = payload["losses"]
        losses = {
            (action, state): self._fraction(nested[action][state])
            for action in actions
            for state in states
        }
        return self.decision.LossTable(actions, states, losses)

    def _ledger(self, payload: dict[str, Any]) -> Any:
        return self.freeze.FutureOnlyLedger.from_payload(payload)

    def _frozen(self, payload: dict[str, Any]) -> Any:
        return self.freeze.FrozenRound.from_payload(payload)

    def _outcome(self, payload: dict[str, Any]) -> Any:
        return self.freeze.OutcomeReceipt.from_payload(payload)

    def _record(self, payload: dict[str, Any]) -> Any:
        return self.khc.KHCDecisionRecord.from_payload(payload)

    def _unit(self, payload: dict[str, Any]) -> Any:
        return self.khc.MISKHCDecisionUnit.from_payload(payload)

    def _read_path(self, arguments: dict[str, Any], key: str = "path") -> Path:
        self._require(arguments, "READ_SCOPED")
        return self.path_policy.readable(arguments[key])

    def _bind_operations(self) -> dict[str, Callable[[dict[str, Any]], Any]]:
        return {
            "mis_status": self._status,
            "mis_surface_inventory": lambda _a: self.surface,
            "mis_canonical_exact_fraction": self._canonical_exact_fraction,
            "mis_canonical_validate_identifiers": self._canonical_validate_identifiers,
            "mis_canonical_fraction_text": self._canonical_fraction_text,
            "mis_canonical_parse_fraction": self._canonical_parse_fraction,
            "mis_canonical_value": self._canonical_value,
            "mis_canonical_json": self._canonical_json,
            "mis_canonical_sha256_payload": self._canonical_sha256_payload,
            "mis_canonical_sha256_file": self._canonical_sha256_file,
            "mis_atom_create": self._atom_create,
            "mis_atom_render": self._atom_render,
            "mis_atom_registry_register": self._atom_registry_register,
            "mis_atom_registry_get": self._atom_registry_get,
            "mis_atom_registry_parse": self._atom_registry_parse,
            "mis_atom_registry_ids": self._atom_registry_ids,
            "mis_atom_registry_payload": self._atom_registry_payload,
            "mis_distribution_create": self._distribution_create,
            "mis_distribution_uniform": self._distribution_uniform,
            "mis_distribution_mapping": self._distribution_mapping,
            "mis_distribution_probability": self._distribution_probability,
            "mis_distribution_update": self._distribution_update,
            "mis_dirichlet_predictive": self._dirichlet_predictive,
            "mis_categorical_brier": self._categorical_brier,
            "mis_loss_table_create": self._loss_table_create,
            "mis_loss_risk": self._loss_risk,
            "mis_bayes_decide": self._bayes_decide,
            "mis_frozen_round_create": self._frozen_round_create,
            "mis_frozen_round_verify": self._frozen_round_verify,
            "mis_outcome_receipt_create": self._outcome_receipt_create,
            "mis_outcome_receipt_verify": self._outcome_receipt_verify,
            "mis_ledger_create": self._ledger_create,
            "mis_ledger_status": self._ledger_status,
            "mis_ledger_counts_before": self._ledger_counts_before,
            "mis_ledger_prior_for": self._ledger_prior_for,
            "mis_ledger_freeze": self._ledger_freeze,
            "mis_ledger_observe": self._ledger_observe,
            "mis_ledger_verify": self._ledger_verify,
            "mis_khc_action_registry": self._khc_action_registry,
            "mis_khc_record_validate": self._khc_record_validate,
            "mis_khc_unit_constitute": self._khc_unit_constitute,
            "mis_khc_unit_verify": self._khc_unit_verify,
            "mis_khc_unit_sense": self._khc_unit_sense,
            "mis_khc_unit_explain": self._khc_unit_explain,
            "mis_khc_load_corpus": self._khc_load_corpus,
            "mis_khc_constitute_units": self._khc_constitute_units,
            "mis_khc_integration_audit": self._khc_integration_audit,
            "mis_khc_records_by_stream": self._khc_records_by_stream,
            "mis_exact_structural_exhaustion": lambda _a: self.experiments.exact_structural_exhaustion(),
            "mis_exact_loss_example": lambda _a: self.experiments.exact_loss_example(),
            "mis_khc_future_only_replay": self._khc_future_only_replay,
            "mis_experiments_run_all": self._experiments_run_all,
        }

    @property
    def operation_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._operations))

    def handlers(self) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
        return {name: (lambda args, op=name: self.dispatch(op, args)) for name in self.operation_names}

    def descriptors(self) -> list[dict[str, Any]]:
        mutating = {"mis_experiments_run_all"}
        read_paths = {
            "mis_canonical_sha256_file",
            "mis_khc_load_corpus",
            "mis_khc_constitute_units",
            "mis_khc_integration_audit",
            "mis_khc_future_only_replay",
            "mis_experiments_run_all",
        }
        return [
            {
                "name": name,
                "readOnly": name not in mutating,
                "filesystemRead": name in read_paths,
                "filesystemWrite": name in mutating,
                "authorityCreated": False,
                "executionAuthorizedByResult": False,
                "automaticPromotion": False,
            }
            for name in self.operation_names
        ]

    def dispatch(self, operation: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if operation not in self._operations:
            raise KeyError(f"unknown MIS operation: {operation}")
        args = dict(arguments or {})
        result = self._operations[operation](args)
        return {
            "schema": self.SCHEMA,
            "mis_version": "0.3.1",
            "bridge_version": "0.2.0",
            "wheel_sha256": EXPECTED_WHEEL_SHA256,
            "operation": operation,
            "result": self._encode_exact(result),
            "capability_available": True,
            "permission_inferred": False,
            "authority_created": False,
            "execution_authorized": False,
            "training_executed": False,
            "automatic_promotion": False,
        }

    def _status(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": "kch.mis031.full-csi-status.v0.2.0",
            "mis_version": self.mis.__version__,
            "wheel_sha256": self.surface["wheel_sha256"],
            "surface_manifest_sha256": self.surface["manifest_sha256"],
            "public_symbols": len(self.surface["symbols"]),
            "unclassified_symbols": self.surface["unclassified"],
            "operations": list(self.operation_names),
            "claim_ceiling": "SEALED_PUBLIC_SURFACE_EXHAUSTIVELY_ROUTED_LOCAL_CSI_SUCCESSOR_NOT_NATIVE_HOST_ACTIVATED",
        }

    def _canonical_exact_fraction(self, a: dict[str, Any]) -> Any:
        value = a["value"]
        if isinstance(value, str):
            value = self._fraction(value)
        return self.canonical.exact_fraction(value, field=str(a.get("field", "value")))

    def _canonical_validate_identifiers(self, a: dict[str, Any]) -> Any:
        return self.canonical.validate_identifier_tuple(
            tuple(a["values"]), field=str(a["field"]), require_sorted=bool(a.get("require_sorted", False))
        )

    def _canonical_fraction_text(self, a: dict[str, Any]) -> str:
        return self.canonical.fraction_text(self._fraction(a["value"]))

    def _canonical_parse_fraction(self, a: dict[str, Any]) -> Any:
        return self.canonical.parse_fraction(a["value"])

    def _canonical_value(self, a: dict[str, Any]) -> Any:
        return self.canonical.canonical_value(self._decode_exact(a["value"]))

    def _canonical_json(self, a: dict[str, Any]) -> str:
        return self.canonical.canonical_json(self._decode_exact(a["value"]))

    def _canonical_sha256_payload(self, a: dict[str, Any]) -> str:
        return self.canonical.sha256_payload(self._decode_exact(a["value"]))

    def _canonical_sha256_file(self, a: dict[str, Any]) -> str:
        return self.canonical.sha256_file(self._read_path(a))

    def _atom_create(self, a: dict[str, Any]) -> Any:
        return self._atom(a["atom"]).to_payload()

    def _atom_render(self, a: dict[str, Any]) -> str:
        return self._atom(a["atom"]).render(str(a.get("language", "canonical")))

    def _atom_registry_register(self, a: dict[str, Any]) -> Any:
        registry = self._registry(a.get("registry", []))
        registry.register(self._atom(a["atom"]))
        return registry.to_payload()

    def _atom_registry_get(self, a: dict[str, Any]) -> Any:
        return self._registry(a["registry"]).get(str(a["atom_id"])).to_payload()

    def _atom_registry_parse(self, a: dict[str, Any]) -> Any:
        return self._registry(a["registry"]).parse(
            str(a["skin"]), str(a.get("language", "canonical"))
        ).to_payload()

    def _atom_registry_ids(self, a: dict[str, Any]) -> Any:
        return self._registry(a["registry"]).atom_ids(a.get("kind"))

    def _atom_registry_payload(self, a: dict[str, Any]) -> Any:
        return self._registry(a["registry"]).to_payload()

    def _distribution_create(self, a: dict[str, Any]) -> Any:
        if "payload" in a:
            return self._distribution(a["payload"]).to_payload()
        masses = {key: self._fraction(value) for key, value in a["masses"].items()}
        return self.exact.ExactDistribution.from_mapping(masses).to_payload()

    def _distribution_uniform(self, a: dict[str, Any]) -> Any:
        return self.exact.ExactDistribution.uniform(tuple(a["states"])).to_payload()

    def _distribution_mapping(self, a: dict[str, Any]) -> Any:
        return self._distribution(a["distribution"]).as_mapping()

    def _distribution_probability(self, a: dict[str, Any]) -> Any:
        return self._distribution(a["distribution"]).probability(str(a["state"]))

    def _distribution_update(self, a: dict[str, Any]) -> Any:
        likelihood = {key: self._fraction(value) for key, value in a["likelihood"].items()}
        return self._distribution(a["distribution"]).update(likelihood).to_payload()

    def _dirichlet_predictive(self, a: dict[str, Any]) -> Any:
        alpha = {key: self._fraction(value) for key, value in a["alpha"].items()}
        return self.exact.dirichlet_predictive(tuple(a["states"]), alpha, dict(a["counts"])).to_payload()

    def _categorical_brier(self, a: dict[str, Any]) -> Any:
        return self.exact.categorical_brier(self._distribution(a["distribution"]), str(a["observed_state"]))

    def _loss_table_create(self, a: dict[str, Any]) -> Any:
        if "payload" in a:
            return self._loss_table(a["payload"]).to_payload()
        actions = tuple(a["actions"])
        states = tuple(a["states"])
        losses = {
            (action, state): self._fraction(a["losses"][action][state])
            for action in actions
            for state in states
        }
        return self.decision.LossTable(actions, states, losses).to_payload()

    def _loss_risk(self, a: dict[str, Any]) -> Any:
        return self._loss_table(a["loss_table"]).risk(
            str(a["action"]), self._distribution(a["posterior"])
        )

    def _bayes_decide(self, a: dict[str, Any]) -> Any:
        return self.decision.bayes_decide(
            self._distribution(a["posterior"]),
            self._loss_table(a["loss_table"]),
            tie_action=a.get("tie_action"),
        ).to_payload()

    def _frozen_round_create(self, a: dict[str, Any]) -> Any:
        return self.freeze.FrozenRound.create(
            stream_id=str(a["stream_id"]),
            sequence=int(a["sequence"]),
            jurisdiction=str(a["jurisdiction"]),
            available_evidence_through=int(a["available_evidence_through"]),
            prior=self._distribution(a["prior"]),
            policy_hash=str(a["policy_hash"]),
            parent_freeze_hash=a.get("parent_freeze_hash"),
            source_receipt_hashes=tuple(a.get("source_receipt_hashes", [])),
            frozen_at=str(a["frozen_at"]),
        ).to_payload()

    def _frozen_round_verify(self, a: dict[str, Any]) -> dict[str, Any]:
        frozen = self._frozen(a["frozen"])
        return {"valid": frozen.verify(), "core": frozen.core_payload(), "payload": frozen.to_payload()}

    def _outcome_receipt_create(self, a: dict[str, Any]) -> Any:
        return self.freeze.OutcomeReceipt.create(
            stream_id=str(a["stream_id"]),
            sequence=int(a["sequence"]),
            freeze_hash=str(a["freeze_hash"]),
            observed_state=str(a["observed_state"]),
            source_unit_hash=str(a["source_unit_hash"]),
            observed_at=str(a["observed_at"]),
        ).to_payload()

    def _outcome_receipt_verify(self, a: dict[str, Any]) -> dict[str, Any]:
        outcome = self._outcome(a["outcome"])
        return {"valid": outcome.verify(), "core": outcome.core_payload(), "payload": outcome.to_payload()}

    def _ledger_create(self, a: dict[str, Any]) -> Any:
        ledger = self.freeze.FutureOnlyLedger(
            stream_id=str(a["stream_id"]),
            states=tuple(a["states"]),
            alpha={key: self._fraction(value) for key, value in a["alpha"].items()},
            jurisdiction=str(a["jurisdiction"]),
            policy_hash=str(a["policy_hash"]),
        )
        return ledger.to_payload()

    def _ledger_status(self, a: dict[str, Any]) -> Any:
        ledger = self._ledger(a["ledger"])
        return {
            "payload": ledger.to_payload(),
            "freezes": [item.to_payload() for item in ledger.freezes],
            "outcomes": [item.to_payload() for item in ledger.outcomes],
        }

    def _ledger_counts_before(self, a: dict[str, Any]) -> Any:
        return self._ledger(a["ledger"]).counts_before(int(a["sequence"]))

    def _ledger_prior_for(self, a: dict[str, Any]) -> Any:
        return self._ledger(a["ledger"]).prior_for(int(a["sequence"])).to_payload()

    def _ledger_freeze(self, a: dict[str, Any]) -> Any:
        ledger = self._ledger(a["ledger"])
        frozen = ledger.freeze(sequence=int(a["sequence"]), frozen_at=str(a["frozen_at"]))
        return {"ledger": ledger.to_payload(), "frozen": frozen.to_payload()}

    def _ledger_observe(self, a: dict[str, Any]) -> Any:
        ledger = self._ledger(a["ledger"])
        outcome = ledger.observe(
            sequence=int(a["sequence"]),
            observed_state=str(a["observed_state"]),
            source_unit_hash=str(a["source_unit_hash"]),
            observed_at=str(a["observed_at"]),
        )
        return {"ledger": ledger.to_payload(), "outcome": outcome.to_payload()}

    def _ledger_verify(self, a: dict[str, Any]) -> dict[str, Any]:
        ledger = self._ledger(a["ledger"])
        return {"valid": ledger.verify(), "payload": ledger.to_payload()}

    def _khc_action_registry(self, _a: dict[str, Any]) -> Any:
        return self.khc.khc_action_registry().to_payload()

    def _khc_record_validate(self, a: dict[str, Any]) -> Any:
        record = self._record(a["record"])
        return {"coordinate": record.coordinate(), "record": record.to_payload()}

    def _khc_unit_constitute(self, a: dict[str, Any]) -> Any:
        unit = self.khc.MISKHCDecisionUnit.constitute(
            self._record(a["record"]),
            source_file_sha256=str(a["source_file_sha256"]),
            registry=self.khc.khc_action_registry(),
        )
        return unit.to_payload()

    def _khc_unit_verify(self, a: dict[str, Any]) -> Any:
        unit = self._unit(a["unit"])
        return {"valid": True, "core": unit.core_payload(), "payload": unit.to_payload()}

    def _khc_unit_sense(self, a: dict[str, Any]) -> str:
        return self._unit(a["unit"]).sense_form(
            self.khc.khc_action_registry(), str(a.get("language", "es"))
        )

    def _khc_unit_explain(self, a: dict[str, Any]) -> str:
        return self._unit(a["unit"]).explain_form(
            self.khc.khc_action_registry(), str(a.get("language", "es"))
        )

    @staticmethod
    def _corpus_payload(corpus: Any, *, include_records: bool) -> dict[str, Any]:
        return {
            "path": str(corpus.path),
            "source_sha256": corpus.source_sha256,
            "record_count": len(corpus.records),
            "key_actions": dict(corpus.key_actions),
            "records": [record.to_payload() for record in corpus.records] if include_records else None,
        }

    def _khc_load_corpus(self, a: dict[str, Any]) -> Any:
        corpus = self.khc.load_khc_corpus(self._read_path(a))
        return self._corpus_payload(corpus, include_records=bool(a.get("include_records", True)))

    def _khc_constitute_units(self, a: dict[str, Any]) -> Any:
        corpus = self.khc.load_khc_corpus(self._read_path(a))
        return [unit.to_payload() for unit in self.khc.constitute_units(corpus)]

    def _khc_integration_audit(self, a: dict[str, Any]) -> Any:
        return self.khc.integration_audit(self.khc.load_khc_corpus(self._read_path(a)))

    def _khc_records_by_stream(self, a: dict[str, Any]) -> Any:
        records = [self._record(item) for item in a["records"]]
        grouped = self.khc.records_by_stream(records)
        return {key: [record.to_payload() for record in value] for key, value in grouped.items()}

    def _khc_future_only_replay(self, a: dict[str, Any]) -> Any:
        return self.experiments.khc_future_only_replay(
            self._read_path(a), include_ledgers=bool(a.get("include_ledgers", True))
        )

    def _experiments_run_all(self, a: dict[str, Any]) -> Any:
        self._require(a, "WRITE_SCOPED")
        khc_path = self.path_policy.readable(a["path"])
        output = self.path_policy.writable_directory(a["output"])
        report = self.experiments.run_all(khc_path, output)
        return {
            "report": report,
            "output": str(output),
            "files": sorted(str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()),
        }
