from __future__ import annotations

import hashlib
import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


ADAPTER_VERSION = "0.1.0"
MIS_VERSION = "0.3.1"
EXPECTED = {
    "wheel": "be03cb2b594e22f662da5b74d8689384de8c1bde3d466fe18772dedbf0c89157",
    "corpus": "e25563e37e40ed6e2b8d2a80f415f1e641786894708bbdafb4634511fe6fb12c",
    "report": "de2de79d320ade464c2727b6525cdad41694f3305c5021fa5f6014c5bea71b83",
    "ledgers": "605cdac85d554ecd282799dcfe91f0c9ab79aff54d36fef74093feb6a3d3eaca",
    "manifest": "57ae25461c6c1eca1694a4cd24d79450e07e1ccca0b87d7f3a357f55379b5419",
}


class AdapterContractError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise AdapterContractError(f"{label} fields differ from contract")


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdapterContractError(f"{label} must be non-empty text")
    return value


def _require_text_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise AdapterContractError(f"{label} must be a {'possibly empty ' if allow_empty else ''}list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise AdapterContractError(f"{label} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise AdapterContractError(f"{label} must be unique")
    return value


def _certificate(core: dict[str, Any]) -> dict[str, Any]:
    return {**core, "certificate_sha256": sha256_json(core)}


def _verify_certificate_hash(value: Mapping[str, Any]) -> None:
    supplied = value.get("certificate_sha256")
    if not isinstance(supplied, str) or len(supplied) != 64:
        raise AdapterContractError("certificate_sha256 is malformed")
    core = {key: item for key, item in value.items() if key != "certificate_sha256"}
    if sha256_json(core) != supplied:
        raise AdapterContractError("certificate integrity failure")


@dataclass(frozen=True, slots=True)
class MISPaths:
    wheel: Path
    corpus: Path
    report: Path
    ledgers: Path
    manifest: Path


class MISV03Adapter:
    """Loads the sealed pure-Python MIS wheel and exposes bounded KCH-facing calls."""

    def __init__(self, *, wheel: Path, corpus: Path, report: Path, ledgers: Path, manifest: Path):
        self.paths = MISPaths(*(Path(item).resolve() for item in (wheel, corpus, report, ledgers, manifest)))
        self._verify_input_hashes()
        self.backend = self._load_backend()

    def _verify_input_hashes(self) -> None:
        observed = {
            "wheel": sha256_file(self.paths.wheel),
            "corpus": sha256_file(self.paths.corpus),
            "report": sha256_file(self.paths.report),
            "ledgers": sha256_file(self.paths.ledgers),
            "manifest": sha256_file(self.paths.manifest),
        }
        if observed != EXPECTED:
            mismatches = [key for key in EXPECTED if observed[key] != EXPECTED[key]]
            raise AdapterContractError(f"MIS v0.3.1 custody hash mismatch: {','.join(mismatches)}")

    def _load_backend(self) -> Any:
        wheel_text = str(self.paths.wheel)
        if wheel_text not in sys.path:
            sys.path.insert(0, wheel_text)
        module = importlib.import_module("mis_v03")
        if getattr(module, "__version__", None) != MIS_VERSION:
            raise AdapterContractError("loaded MIS version differs from 0.3.1")
        origin = str(getattr(module, "__file__", ""))
        if wheel_text.lower() not in origin.lower():
            raise AdapterContractError(f"MIS imported from non-custodied origin: {origin}")
        return module

    def describe(self) -> dict[str, Any]:
        return {
            "schema": "kch.mis.v03.service-description.v0.1.0",
            "adapter_version": ADAPTER_VERSION,
            "mis_version": MIS_VERSION,
            "role": "FEDERATED_EXACT_MATHEMATICAL_SEMANTIC_DECISION_SUPPORT",
            "methods": ["describe", "audit_historical_khc", "exact_decide", "verify_certificate"],
            "authority_created": False,
            "execution_authorized": False,
            "automatic_promotion": False,
            "claim_ceiling": "EXACT_CALCULATION_STRUCTURAL_REPLAY_AND_CERTIFICATION_ONLY",
        }

    def audit_historical_khc(self) -> dict[str, Any]:
        khc = importlib.import_module("mis_v03.khc")
        experiments = importlib.import_module("mis_v03.experiments")
        freeze = importlib.import_module("mis_v03.freeze")

        report = json.loads(self.paths.report.read_text(encoding="utf-8-sig"))
        persisted = json.loads(self.paths.ledgers.read_text(encoding="utf-8-sig"))
        manifest = json.loads(self.paths.manifest.read_text(encoding="utf-8-sig"))
        if manifest.get("schema") != "MIS_RELEASE_MANIFEST_v0.3.1" or manifest.get("file_count") != 32:
            raise AdapterContractError("MIS release manifest contract mismatch")

        corpus = khc.load_khc_corpus(self.paths.corpus)
        units = khc.constitute_units(corpus)
        audit = khc.integration_audit(corpus)
        replay = experiments.khc_future_only_replay(self.paths.corpus, include_ledgers=False)
        if audit != report.get("khc_integration"):
            raise AdapterContractError("live integration audit differs from frozen v0.3.1 report")
        if replay != report.get("khc_future_only_replay"):
            raise AdapterContractError("live future-only replay differs from frozen v0.3.1 report")

        ledger_rows = persisted.get("ledgers")
        if not isinstance(ledger_rows, list) or len(ledger_rows) != 60:
            raise AdapterContractError("persisted MIS ledger cardinality mismatch")
        verified_ledgers: list[dict[str, str]] = []
        for row in ledger_rows:
            rebuilt = freeze.FutureOnlyLedger.from_payload(row)
            if not rebuilt.verify():
                raise AdapterContractError(f"MIS ledger verification failed: {rebuilt.stream_id}")
            verified_ledgers.append({"stream_id": rebuilt.stream_id, "payload_sha256": sha256_json(row)})
        verified_ledgers.sort(key=lambda item: item["stream_id"])

        core = {
            "schema": "kch.mis.v03.historical-certificate.v0.1.0",
            "adapter_version": ADAPTER_VERSION,
            "mis_version": MIS_VERSION,
            "custody": dict(EXPECTED),
            "source_schema": audit["source_schema"],
            "records": audit["records"],
            "coordinates_unique": audit["coordinates_unique"],
            "units_unique": audit["units_unique"],
            "unit_hash_sequence_sha256": sha256_json([unit.unit_hash for unit in units]),
            "streams": replay["streams"],
            "freezes": replay["freezes"],
            "outcomes": replay["outcomes"],
            "persisted_ledgers_verified": len(verified_ledgers),
            "persisted_ledger_set_sha256": sha256_json(verified_ledgers),
            "policy_hash": replay["policy_hash"],
            "live_audit_sha256": sha256_json(audit),
            "live_replay_sha256": sha256_json(replay),
            "frozen_report_exact_match": True,
            "future_only_chronology_verified": True,
            "authority_created": False,
            "execution_authorized": False,
            "automatic_promotion": False,
            "claim_ceiling": "STRUCTURAL_LOSSLESS_REPRESENTATION_EXACT_REPLAY_AND_FUTURE_ONLY_INTEGRITY_ONLY",
            "not_demonstrated": [
                "CAUSAL_KCH_IMPROVEMENT",
                "PROSPECTIVE_PREDICTIVE_SUPERIORITY",
                "HUMAN_UTILITY",
                "OPEN_DOMAIN_SCALABILITY",
                "GLOBAL_WINNER",
            ],
        }
        return _certificate(core)

    def exact_decide(self, request: Mapping[str, Any]) -> dict[str, Any]:
        _require_exact_keys(
            request,
            {"schema", "request_id", "purpose_id", "jurisdiction", "evidence_ids", "states", "prior", "likelihood", "actions", "losses", "tie_action"},
            "exact decision request",
        )
        if request["schema"] != "kch.mis.v03.exact-decision-request.v0.1.0":
            raise AdapterContractError("exact decision request schema mismatch")
        request_id = _require_text(request["request_id"], "request_id")
        purpose_id = _require_text(request["purpose_id"], "purpose_id")
        jurisdiction = _require_text(request["jurisdiction"], "jurisdiction")
        evidence_ids = _require_text_list(request["evidence_ids"], "evidence_ids", allow_empty=True)
        states = tuple(sorted(_require_text_list(request["states"], "states")))
        actions = tuple(sorted(_require_text_list(request["actions"], "actions")))
        for label in ("prior", "likelihood", "losses"):
            if not isinstance(request[label], dict):
                raise AdapterContractError(f"{label} must be an object")
        if set(request["prior"]) != set(states) or set(request["likelihood"]) != set(states):
            raise AdapterContractError("prior and likelihood must cover the exact state space")
        if set(request["losses"]) != set(actions):
            raise AdapterContractError("losses must cover the exact action space")

        canonical = importlib.import_module("mis_v03.canonical")
        exact = importlib.import_module("mis_v03.exact")
        decision = importlib.import_module("mis_v03.decision")
        prior = exact.ExactDistribution.from_mapping({state: canonical.parse_fraction(request["prior"][state]) for state in states})
        posterior = prior.update({state: canonical.parse_fraction(request["likelihood"][state]) for state in states})
        flat_losses: dict[tuple[str, str], Any] = {}
        for action in actions:
            row = request["losses"][action]
            if not isinstance(row, dict) or set(row) != set(states):
                raise AdapterContractError(f"losses[{action}] must cover the exact state space")
            for state in states:
                flat_losses[(action, state)] = canonical.parse_fraction(row[state])
        table = decision.LossTable(actions, states, flat_losses)
        tie_action = request["tie_action"]
        if tie_action is not None:
            tie_action = _require_text(tie_action, "tie_action")
        result = decision.bayes_decide(posterior, table, tie_action=tie_action)
        request_normalized = json.loads(canonical_json(dict(request)))
        core = {
            "schema": "kch.mis.v03.exact-decision-certificate.v0.1.0",
            "adapter_version": ADAPTER_VERSION,
            "mis_version": MIS_VERSION,
            "request_id": request_id,
            "request_sha256": sha256_json(request_normalized),
            "purpose_id": purpose_id,
            "jurisdiction": jurisdiction,
            "evidence_ids": evidence_ids,
            "prior": prior.to_payload(),
            "likelihood": {state: request["likelihood"][state] for state in states},
            "posterior": posterior.to_payload(),
            "loss_table": table.to_payload(),
            "decision": result.to_payload(),
            "authority_created": False,
            "execution_authorized": False,
            "automatic_promotion": False,
            "claim_ceiling": "EXACT_DECISION_CALCULATION_FOR_DECLARED_INPUTS_ONLY",
        }
        return _certificate(core)

    @staticmethod
    def verify_certificate(value: Mapping[str, Any]) -> dict[str, Any]:
        schema = value.get("schema")
        if schema == "kch.mis.v03.historical-certificate.v0.1.0":
            return verify_historical_certificate(value)
        if schema == "kch.mis.v03.exact-decision-certificate.v0.1.0":
            return verify_exact_decision_certificate(value)
        raise AdapterContractError("unknown MIS-KCH certificate schema")


def verify_historical_certificate(value: Mapping[str, Any]) -> dict[str, Any]:
    _verify_certificate_hash(value)
    if value.get("schema") != "kch.mis.v03.historical-certificate.v0.1.0":
        raise AdapterContractError("historical certificate schema mismatch")
    if value.get("custody") != EXPECTED or value.get("mis_version") != MIS_VERSION:
        raise AdapterContractError("historical certificate custody mismatch")
    if (value.get("records"), value.get("coordinates_unique"), value.get("units_unique")) != (480, 480, 480):
        raise AdapterContractError("historical certificate unit cardinality mismatch")
    if (value.get("streams"), value.get("freezes"), value.get("outcomes"), value.get("persisted_ledgers_verified")) != (60, 480, 480, 60):
        raise AdapterContractError("historical certificate ledger cardinality mismatch")
    if value.get("authority_created") or value.get("execution_authorized") or value.get("automatic_promotion"):
        raise AdapterContractError("historical certificate cannot create authority or promotion")
    return {"valid": True, "schema": value["schema"], "certificate_sha256": value["certificate_sha256"]}


def verify_exact_decision_certificate(value: Mapping[str, Any]) -> dict[str, Any]:
    _verify_certificate_hash(value)
    if value.get("schema") != "kch.mis.v03.exact-decision-certificate.v0.1.0":
        raise AdapterContractError("exact decision certificate schema mismatch")
    if value.get("mis_version") != MIS_VERSION:
        raise AdapterContractError("exact decision certificate MIS version mismatch")
    if value.get("authority_created") or value.get("execution_authorized") or value.get("automatic_promotion"):
        raise AdapterContractError("exact decision certificate cannot create authority or promotion")
    return {"valid": True, "schema": value["schema"], "certificate_sha256": value["certificate_sha256"]}

