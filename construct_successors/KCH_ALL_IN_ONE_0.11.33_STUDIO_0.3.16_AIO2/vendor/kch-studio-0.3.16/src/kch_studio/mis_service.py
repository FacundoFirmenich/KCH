from __future__ import annotations

import importlib
import json
import os
import re
import sqlite3
import sys
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .contracts import canonical_json, sha256_bytes, sha256_json, sqlite_connection

HEX64 = re.compile(r"^[0-9a-f]{64}$")

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    emitted_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    parent_hash TEXT,
    event_hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS certificates (
    certificate_sha256 TEXT PRIMARY KEY,
    schema TEXT NOT NULL,
    request_id TEXT,
    purpose_id TEXT,
    jurisdiction TEXT NOT NULL,
    certificate_json TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    event_hash TEXT NOT NULL REFERENCES events(event_hash)
);
CREATE TABLE IF NOT EXISTS studies (
    study_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    purpose_id TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    claim_ceiling TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    closed_at TEXT
);
CREATE TABLE IF NOT EXISTS ledgers (
    study_id TEXT PRIMARY KEY REFERENCES studies(study_id),
    ledger_json TEXT NOT NULL,
    ledger_sha256 TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rounds (
    study_id TEXT NOT NULL REFERENCES studies(study_id),
    sequence INTEGER NOT NULL,
    freeze_hash TEXT NOT NULL UNIQUE,
    decision_certificate_sha256 TEXT NOT NULL REFERENCES certificates(certificate_sha256),
    evidence_ids_json TEXT NOT NULL,
    outcome_receipt_hash TEXT,
    created_at TEXT NOT NULL,
    observed_at TEXT,
    PRIMARY KEY(study_id,sequence)
);
CREATE TABLE IF NOT EXISTS atoms (
    atom_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    skins_json TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    atom_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviewable_decisions (
    decision_id TEXT PRIMARY KEY,
    certificate_sha256 TEXT NOT NULL REFERENCES certificates(certificate_sha256),
    record_json TEXT NOT NULL,
    record_sha256 TEXT NOT NULL,
    phl_state TEXT NOT NULL,
    phl_receipt_json TEXT
);
CREATE TABLE IF NOT EXISTS bridges (
    bridge_id TEXT PRIMARY KEY,
    bridge_kind TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    target_ref TEXT NOT NULL,
    receipt_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class MISService:
    """Persistent KCH federation around the byte-frozen MIS v0.3.1 engine.

    MIS performs exact semantic/Bayesian calculations.  This service adds KCH
    custody, prospective chronology and explicit bridges, but never converts a
    calculation or certificate into execution authority.
    """

    SERVICE_VERSION = "0.2.0"

    def __init__(
        self,
        evidence_root: str | Path | None = None,
        runtime_root: str | Path | None = None,
    ) -> None:
        candidates = [
            Path(os.environ["KCH_MIS_ROOT"]).resolve() if os.environ.get("KCH_MIS_ROOT") else None,
            Path(evidence_root).resolve() if evidence_root else None,
            Path(__file__).resolve().parents[3] / "KCH_MIS03_REEXTRACT_v0.1.0",
        ]
        self.root = next(
            (path for path in candidates if path and (path / "evidence").is_dir()),
            None,
        )
        self.runtime_root = Path(
            runtime_root or os.environ.get("KCH_MIS_RUNTIME", Path.cwd() / ".kch-mis-runtime")
        ).resolve()
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.path = self.runtime_root / "mis-federation.sqlite3"
        self.export_root = self.runtime_root / "exports"
        self.export_root.mkdir(exist_ok=True)
        self._adapter: Any | None = None
        self._error: str | None = None
        with closing(self.connect()) as connection:
            connection.executescript(DDL)
            connection.commit()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _paths(self) -> dict[str, Path]:
        if self.root is None:
            raise FileNotFoundError("MIS v0.3.1 evidence root unavailable")
        return {
            "wheel": self.root / "vendor" / "mis_qualitative_bayes-0.3.1-py3-none-any.whl",
            "corpus": self.root / "evidence" / "KHC_TWO_BATTERY_MASTER_RESULTS_v2.0.7.json",
            "report": self.root / "evidence" / "MIS_v0_3_EXPERIMENT_REPORT.json",
            "ledgers": self.root / "evidence" / "MIS_v0_3_KHC_FUTURE_ONLY_LEDGERS.json",
            "manifest": self.root / "evidence" / "MIS_RELEASE_MANIFEST_v0.3.1.json",
            "historical_certificate": self.root
            / "results"
            / "KCH_MIS_V03_HISTORICAL_CERTIFICATE_v0.1.0.json",
            "csi_lowering": self.root / "results" / "KCH_MIS_V03_CSI_LOWERING_v0.1.0.json",
            "gate_result": self.root
            / "results"
            / "KCH_MIS_V03_EFFECTIVE_INTEGRATION_RESULT_v0.1.0.json",
        }

    def _load(self) -> Any:
        if self._adapter is not None:
            return self._adapter
        try:
            try:
                from kch_mis_v03_integration import MISV03Adapter
            except ImportError:
                if self.root is None:
                    raise
                candidates = [
                    self.root / "dist" / "kch_mis_v03_integration-0.1.0-py3-none-any.whl",
                    self.root / "src",
                ]
                source = next((path for path in candidates if path.exists()), None)
                if source is None:
                    raise
                if str(source) not in sys.path:
                    sys.path.insert(0, str(source))
                from kch_mis_v03_integration import MISV03Adapter

            paths = self._paths()
            self._adapter = MISV03Adapter(
                **{
                    key: value
                    for key, value in paths.items()
                    if key in {"wheel", "corpus", "report", "ledgers", "manifest"}
                }
            )
            return self._adapter
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            raise

    def _backend(self, module: str) -> Any:
        self._load()
        return importlib.import_module(f"mis_v03.{module}")

    @staticmethod
    def _append(
        connection: sqlite3.Connection,
        kind: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        row = connection.execute(
            "SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        parent_hash = None if row is None else str(row["event_hash"])
        event_id = f"MIS-EVENT-{uuid.uuid4()}"
        emitted_at = utc_now()
        body = {
            "event_id": event_id,
            "emitted_at": emitted_at,
            "kind": kind,
            "payload": dict(payload),
            "parent_hash": parent_hash,
        }
        event_hash = sha256_json(body)
        connection.execute(
            "INSERT INTO events(event_id,emitted_at,kind,payload_json,parent_hash,event_hash) "
            "VALUES(?,?,?,?,?,?)",
            (
                event_id,
                emitted_at,
                kind,
                canonical_json(dict(payload)),
                parent_hash,
                event_hash,
            ),
        )
        return {**body, "event_hash": event_hash}

    def _store_certificate(
        self,
        connection: sqlite3.Connection,
        certificate: dict[str, Any],
    ) -> dict[str, Any]:
        verification = self.verify_certificate(certificate)
        digest = str(certificate["certificate_sha256"])
        existing = connection.execute(
            "SELECT * FROM certificates WHERE certificate_sha256=?", (digest,)
        ).fetchone()
        if existing is not None:
            if str(existing["certificate_json"]) != canonical_json(certificate):
                raise ValueError("MIS certificate digest collision")
            return {
                "certificate_sha256": digest,
                "registered_at": str(existing["registered_at"]),
                "event_hash": str(existing["event_hash"]),
                "idempotent": True,
                "verification": verification,
            }
        event = self._append(
            connection,
            "MIS_CERTIFICATE_REGISTERED",
            {"certificate_sha256": digest, "schema": certificate["schema"]},
        )
        registered_at = str(event["emitted_at"])
        connection.execute(
            "INSERT INTO certificates VALUES(?,?,?,?,?,?,?,?)",
            (
                digest,
                certificate["schema"],
                certificate.get("request_id"),
                certificate.get("purpose_id"),
                str(certificate.get("jurisdiction", "HISTORICAL_BOUNDED_REPLAY")),
                canonical_json(certificate),
                registered_at,
                event["event_hash"],
            ),
        )
        return {
            "certificate_sha256": digest,
            "registered_at": registered_at,
            "event_hash": event["event_hash"],
            "idempotent": False,
            "verification": verification,
        }

    def status(self) -> dict[str, Any]:
        paths: dict[str, Path] = {}
        missing: list[str] = []
        if self.root is not None:
            paths = self._paths()
            missing = [key for key, path in paths.items() if not path.is_file()]
        adapter_available = False
        if not missing and self.root is not None:
            try:
                self._load()
                adapter_available = True
            except Exception:
                adapter_available = False
        with closing(self.connect()) as connection:
            counts = {
                name: int(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
                for name in (
                    "events",
                    "certificates",
                    "studies",
                    "rounds",
                    "atoms",
                    "reviewable_decisions",
                    "bridges",
                )
            }
            active = int(
                connection.execute("SELECT COUNT(*) FROM studies WHERE state='ACTIVE'").fetchone()[
                    0
                ]
            )
        return {
            "schema": "kch.mis.federated-service-status.v0.2.0",
            "service_version": self.SERVICE_VERSION,
            "mis_version": "0.3.1",
            "root": None if self.root is None else str(self.root),
            "runtime_root": str(self.runtime_root),
            "evidence_files": {
                key: {"path": str(path), "available": path.is_file()} for key, path in paths.items()
            },
            "missing": missing,
            "adapter_available": adapter_available,
            "adapter_error": self._error,
            "surface": [
                "describe",
                "exact_decide",
                "audit_historical_khc",
                "verify_certificate",
                "historical_csi_lowering",
                "semantic_atoms",
                "prospective_studies",
                "reviewable_decisions",
                "dynamic_csi_lowering",
                "kwandata_archive",
                "sco_work_order",
                "rgg_envelope",
                "phl_registration",
            ],
            "KCH_0_11_original_surface": ["certificate.verify"],
            "previous_overlay_surface": [
                "status",
                "describe",
                "exact_decide",
                "audit_historical_khc",
                "verify_certificate",
                "csi_lowering",
            ],
            "counts": counts,
            "active_prospective_studies": active,
            "integration_assessment": "PERSISTENT_SYNERGISTIC_FEDERATION_CANDIDATE",
            "authority_created": False,
            "execution_authorized": False,
            "automatic_promotion": False,
            "training_executed": False,
            "claim_boundary": {
                "historical": "STRUCTURAL_EXACT_REPLAY_ONLY",
                "prospective": "LOCAL_FUTURE_ONLY_OBSERVATION_UNTIL_SEPARATE_ADJUDICATION",
                "not_demonstrated": [
                    "CAUSAL_KCH_IMPROVEMENT",
                    "PROSPECTIVE_PREDICTIVE_SUPERIORITY",
                    "HUMAN_UTILITY",
                    "OPEN_DOMAIN_SCALABILITY",
                    "GLOBAL_WINNER",
                ],
            },
        }

    def describe(self) -> dict[str, Any]:
        return {
            **self._load().describe(),
            "kch_federation_version": self.SERVICE_VERSION,
            "persistent_prospective_workflow": "CREATE_FREEZE_DECIDE_OBSERVE_VERIFY",
            "synergistic_bridges": ["CSI", "PHL", "SCO", "RGG", "KWANDATA"],
        }

    def exact_decide(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._load().exact_decide(request)

    def audit_historical(self) -> dict[str, Any]:
        return self._load().audit_historical_khc()

    def verify_certificate(self, certificate: dict[str, Any] | None = None) -> dict[str, Any]:
        if certificate is None:
            path = self._paths()["historical_certificate"]
            certificate = json.loads(path.read_text(encoding="utf-8-sig"))
        return self._load().verify_certificate(certificate)

    def csi_lowering(self, certificate: dict[str, Any] | None = None) -> dict[str, Any]:
        if certificate is not None:
            return self.lower_certificate_to_csi(certificate)
        path = self._paths()["csi_lowering"]
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        observed = sha256_bytes(
            json.dumps(
                value["raw_csi_program"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if observed != value["raw_csi_program_sha256"]:
            raise ValueError("MIS CSI lowering hash mismatch")
        return {
            **value,
            "operational_assessment": (
                "BOUNDED_HISTORICAL_FOUR_INSTRUCTION_LOWERING; "
                "USE_DYNAMIC_LOWERING_FOR_NEW_CERTIFICATES"
            ),
        }

    def _atom_registry(self) -> Any:
        atoms_module = self._backend("atoms")
        registry = atoms_module.AtomRegistry()
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM atoms WHERE status='ACTIVE' ORDER BY atom_id"
            ).fetchall()
        if not rows:
            source = self._backend("khc").khc_action_registry()
            with closing(self.connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                for item in source.to_payload():
                    payload = {
                        "atom_id": item["atom_id"],
                        "kind": item["kind"],
                        "skins": item["skins"],
                    }
                    connection.execute(
                        "INSERT OR IGNORE INTO atoms VALUES(?,?,?,?,?,?,?)",
                        (
                            item["atom_id"],
                            item["kind"],
                            canonical_json(item["skins"]),
                            "MIS_V0_3_1_KHC_FROZEN",
                            "ACTIVE",
                            utc_now(),
                            sha256_json(payload),
                        ),
                    )
                connection.commit()
            return self._atom_registry()
        for row in rows:
            registry.register(
                atoms_module.SemanticAtom(
                    str(row["atom_id"]),
                    str(row["kind"]),
                    json.loads(str(row["skins_json"])),
                )
            )
        return registry

    def atoms(self, kind: str | None = None) -> dict[str, Any]:
        registry = self._atom_registry()
        selected = set(registry.atom_ids(kind))
        return {
            "schema": "kch.mis.semantic-atom-registry.v0.2.0",
            "kind": kind,
            "atoms": [item for item in registry.to_payload() if item["atom_id"] in selected],
            "atom_count": len(selected),
            "authority_created": False,
        }

    def register_atom(
        self,
        *,
        atom_id: str,
        kind: str,
        skins: dict[str, str],
        user_authored: bool,
    ) -> dict[str, Any]:
        if user_authored is not True:
            raise PermissionError("new MIS semantic atoms require user authorship")
        atoms_module = self._backend("atoms")
        atom = atoms_module.SemanticAtom(atom_id, kind, skins)
        registry = self._atom_registry()
        registry.register(atom)
        payload = atom.to_payload()
        digest = sha256_json(payload)
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT atom_sha256 FROM atoms WHERE atom_id=?", (atom_id,)
            ).fetchone()
            if existing is not None:
                if str(existing["atom_sha256"]) != digest:
                    raise ValueError("atom_id collision with different semantics")
                connection.rollback()
                return {**payload, "atom_sha256": digest, "idempotent": True}
            event = self._append(
                connection,
                "MIS_SEMANTIC_ATOM_REGISTERED",
                {"atom_id": atom_id, "atom_sha256": digest},
            )
            connection.execute(
                "INSERT INTO atoms VALUES(?,?,?,?,?,?,?)",
                (
                    atom_id,
                    kind,
                    canonical_json(skins),
                    "USER_DECLARED",
                    "ACTIVE",
                    event["emitted_at"],
                    digest,
                ),
            )
            connection.commit()
        return {
            **payload,
            "atom_sha256": digest,
            "idempotent": False,
            "event_hash": event["event_hash"],
            "authorship_attestation": "DECLARED_BY_CALLER_NOT_CRYPTOGRAPHIC_HOST_IDENTITY",
            "authority_created": False,
        }

    def resolve_atom(self, skin: str, language: str = "canonical") -> dict[str, Any]:
        atom = self._atom_registry().parse(skin, language)
        return {
            "schema": "kch.mis.semantic-atom-resolution.v0.2.0",
            "input": skin,
            "language": language,
            "atom": atom.to_payload(),
            "rendered": atom.render(language),
        }

    def create_study(
        self,
        *,
        study_id: str,
        title: str,
        purpose_id: str,
        jurisdiction: str,
        states: list[str],
        alpha: dict[str, str],
        policy: dict[str, Any],
        claim_ceiling: str,
    ) -> dict[str, Any]:
        for label, value in {
            "study_id": study_id,
            "title": title,
            "purpose_id": purpose_id,
            "jurisdiction": jurisdiction,
            "claim_ceiling": claim_ceiling,
        }.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be non-empty text")
        normalized_states = sorted(set(states))
        if states != normalized_states or not states or set(alpha) != set(states):
            raise ValueError("states must be sorted unique and alpha must cover them exactly")
        canonical = self._backend("canonical")
        parsed_alpha = {state: canonical.parse_fraction(alpha[state]) for state in states}
        ledger = self._backend("freeze").FutureOnlyLedger(
            stream_id=study_id,
            states=tuple(states),
            alpha=parsed_alpha,
            jurisdiction=jurisdiction,
            policy_hash=sha256_json(policy),
        )
        payload = ledger.to_payload()
        created_at = utc_now()
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM studies WHERE study_id=?", (study_id,)
            ).fetchone()
            if existing is not None:
                connection.rollback()
                raise ValueError("study_id already exists")
            event = self._append(
                connection,
                "MIS_PROSPECTIVE_STUDY_CREATED",
                {
                    "study_id": study_id,
                    "purpose_id": purpose_id,
                    "jurisdiction": jurisdiction,
                    "policy_hash": ledger.policy_hash,
                },
            )
            connection.execute(
                "INSERT INTO studies VALUES(?,?,?,?,?,?,?,?)",
                (
                    study_id,
                    title,
                    purpose_id,
                    jurisdiction,
                    claim_ceiling,
                    "ACTIVE",
                    created_at,
                    None,
                ),
            )
            connection.execute(
                "INSERT INTO ledgers VALUES(?,?,?,?)",
                (study_id, canonical_json(payload), sha256_json(payload), created_at),
            )
            connection.commit()
        return {
            "schema": "kch.mis.prospective-study.v0.2.0",
            "study_id": study_id,
            "state": "ACTIVE",
            "purpose_id": purpose_id,
            "jurisdiction": jurisdiction,
            "states": states,
            "alpha": alpha,
            "policy_hash": ledger.policy_hash,
            "claim_ceiling": claim_ceiling,
            "event_hash": event["event_hash"],
            "future_only": True,
            "no_outcomes_recorded": True,
            "authority_created": False,
        }

    def _study_locked(
        self, connection: sqlite3.Connection, study_id: str
    ) -> tuple[sqlite3.Row, Any]:
        study = connection.execute("SELECT * FROM studies WHERE study_id=?", (study_id,)).fetchone()
        ledger_row = connection.execute(
            "SELECT * FROM ledgers WHERE study_id=?", (study_id,)
        ).fetchone()
        if study is None or ledger_row is None:
            raise KeyError(study_id)
        if study["state"] != "ACTIVE":
            raise ValueError("MIS prospective study is not active")
        ledger = self._backend("freeze").FutureOnlyLedger.from_payload(
            json.loads(str(ledger_row["ledger_json"]))
        )
        return study, ledger

    def freeze_decision(
        self,
        *,
        study_id: str,
        request: dict[str, Any],
        frozen_at: str | None = None,
    ) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            study, ledger = self._study_locked(connection, study_id)
            sequence = len(ledger.freezes) + 1
            if len(ledger.outcomes) != sequence - 1:
                raise ValueError("previous MIS freeze has no outcome")
            if request.get("purpose_id") != study["purpose_id"]:
                raise ValueError("MIS request purpose differs from prospective study")
            if request.get("jurisdiction") != study["jurisdiction"]:
                raise ValueError("MIS request jurisdiction differs from prospective study")
            expected_prior = ledger.prior_for(sequence).to_payload()["masses"]
            if request.get("prior") != expected_prior:
                raise ValueError("MIS request prior differs from the pre-outcome frozen prior")
            frozen = ledger.freeze(sequence=sequence, frozen_at=frozen_at or utc_now())
            certificate = self.exact_decide(request)
            stored = self._store_certificate(connection, certificate)
            evidence_ids = list(certificate.get("evidence_ids", []))
            connection.execute(
                "INSERT INTO rounds VALUES(?,?,?,?,?,?,?,?)",
                (
                    study_id,
                    sequence,
                    frozen.freeze_hash,
                    certificate["certificate_sha256"],
                    canonical_json(evidence_ids),
                    None,
                    utc_now(),
                    None,
                ),
            )
            ledger_payload = ledger.to_payload()
            connection.execute(
                "UPDATE ledgers SET ledger_json=?,ledger_sha256=?,updated_at=? WHERE study_id=?",
                (
                    canonical_json(ledger_payload),
                    sha256_json(ledger_payload),
                    utc_now(),
                    study_id,
                ),
            )
            event = self._append(
                connection,
                "MIS_PROSPECTIVE_DECISION_FROZEN",
                {
                    "study_id": study_id,
                    "sequence": sequence,
                    "freeze_hash": frozen.freeze_hash,
                    "certificate_sha256": certificate["certificate_sha256"],
                },
            )
            connection.commit()
        return {
            "schema": "kch.mis.prospective-freeze-receipt.v0.2.0",
            "study_id": study_id,
            "sequence": sequence,
            "freeze": frozen.to_payload(),
            "decision_certificate": certificate,
            "certificate_registration": stored,
            "event_hash": event["event_hash"],
            "outcome_known_when_frozen": False,
            "future_only": True,
            "execution_authorized": False,
        }

    def observe(
        self,
        *,
        study_id: str,
        observed_state: str,
        source_unit_hash: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        if not HEX64.fullmatch(source_unit_hash):
            raise ValueError("source_unit_hash must be lowercase SHA-256")
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            _study, ledger = self._study_locked(connection, study_id)
            sequence = len(ledger.outcomes) + 1
            if len(ledger.freezes) != sequence:
                raise ValueError("outcome requires exactly one pending MIS freeze")
            timestamp = observed_at or utc_now()
            receipt = ledger.observe(
                sequence=sequence,
                observed_state=observed_state,
                source_unit_hash=source_unit_hash,
                observed_at=timestamp,
            )
            ledger_payload = ledger.to_payload()
            connection.execute(
                "UPDATE ledgers SET ledger_json=?,ledger_sha256=?,updated_at=? WHERE study_id=?",
                (
                    canonical_json(ledger_payload),
                    sha256_json(ledger_payload),
                    utc_now(),
                    study_id,
                ),
            )
            connection.execute(
                "UPDATE rounds SET outcome_receipt_hash=?,observed_at=? "
                "WHERE study_id=? AND sequence=?",
                (receipt.receipt_hash, timestamp, study_id, sequence),
            )
            event = self._append(
                connection,
                "MIS_PROSPECTIVE_OUTCOME_OBSERVED",
                {
                    "study_id": study_id,
                    "sequence": sequence,
                    "outcome_receipt_hash": receipt.receipt_hash,
                    "source_unit_hash": source_unit_hash,
                },
            )
            connection.commit()
        return {
            "schema": "kch.mis.prospective-outcome-receipt.v0.2.0",
            "study_id": study_id,
            "sequence": sequence,
            "outcome": receipt.to_payload(),
            "event_hash": event["event_hash"],
            "observed_at_source": "USER_SUPPLIED" if observed_at else "KCH_RECORDING_TIME",
            "future_only": True,
            "causal_quality_adjudicated": False,
            "automatic_promotion": False,
        }

    def study_projection(self, study_id: str | None = None) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            if study_id is None:
                rows = connection.execute(
                    "SELECT * FROM studies ORDER BY created_at,study_id"
                ).fetchall()
                return {
                    "schema": "kch.mis.prospective-study-index.v0.2.0",
                    "studies": [dict(row) for row in rows],
                    "study_count": len(rows),
                }
            study = connection.execute(
                "SELECT * FROM studies WHERE study_id=?", (study_id,)
            ).fetchone()
            ledger_row = connection.execute(
                "SELECT * FROM ledgers WHERE study_id=?", (study_id,)
            ).fetchone()
            rounds = connection.execute(
                "SELECT * FROM rounds WHERE study_id=? ORDER BY sequence", (study_id,)
            ).fetchall()
        if study is None or ledger_row is None:
            raise KeyError(study_id)
        ledger = self._backend("freeze").FutureOnlyLedger.from_payload(
            json.loads(str(ledger_row["ledger_json"]))
        )
        next_sequence = len(ledger.freezes) + 1
        return {
            "schema": "kch.mis.prospective-study-projection.v0.2.0",
            "study": dict(study),
            "rounds": [
                {
                    **dict(row),
                    "evidence_ids": json.loads(str(row["evidence_ids_json"])),
                }
                for row in rounds
            ],
            "freeze_count": len(ledger.freezes),
            "outcome_count": len(ledger.outcomes),
            "pending_outcome": len(ledger.freezes) > len(ledger.outcomes),
            "next_prior": ledger.prior_for(next_sequence).to_payload(),
            "ledger_sha256": str(ledger_row["ledger_sha256"]),
            "ledger_integrity": ledger.verify(),
            "claim_ceiling": study["claim_ceiling"],
            "authority_created": False,
        }

    def close_study(self, study_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            study, ledger = self._study_locked(connection, study_id)
            if len(ledger.freezes) != len(ledger.outcomes):
                raise ValueError("cannot close a MIS study with a pending outcome")
            closed_at = utc_now()
            connection.execute(
                "UPDATE studies SET state='CLOSED',closed_at=? WHERE study_id=?",
                (closed_at, study_id),
            )
            event = self._append(
                connection,
                "MIS_PROSPECTIVE_STUDY_CLOSED",
                {
                    "study_id": study_id,
                    "rounds": len(ledger.freezes),
                    "claim_ceiling": study["claim_ceiling"],
                },
            )
            connection.commit()
        return {
            "study_id": study_id,
            "state": "CLOSED",
            "closed_at": closed_at,
            "rounds": len(ledger.freezes),
            "event_hash": event["event_hash"],
            "claim_promotion_authorized": False,
        }

    def register_reviewable_decision(self, certificate: dict[str, Any]) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            stored = self._store_certificate(connection, certificate)
            digest = str(certificate["certificate_sha256"])
            existing = connection.execute(
                "SELECT * FROM reviewable_decisions WHERE certificate_sha256=?", (digest,)
            ).fetchone()
            if existing is not None:
                connection.commit()
                return {
                    "record": json.loads(str(existing["record_json"])),
                    "record_sha256": str(existing["record_sha256"]),
                    "phl_state": str(existing["phl_state"]),
                    "idempotent": True,
                    "certificate_registration": stored,
                }
            if certificate["schema"] != "kch.mis.v03.exact-decision-certificate.v0.1.0":
                raise ValueError(
                    "automatic reviewable conversion is defined for exact-decision certificates only"
                )
            decision = certificate["decision"]
            chosen = decision.get("chosen_action")
            ties = decision.get("minimizers", [])
            summary = (
                f"MIS exact decision for {certificate['purpose_id']}: "
                f"{chosen if chosen is not None else 'TIE_PRESERVED'}"
            )
            decision_id = f"mis-v03:exact:{digest[:24]}"
            record = {
                "schema": "kch.reviewable-decision.v0.2.0",
                "decision_id": decision_id,
                "emitted_at": stored["registered_at"],
                "component_id": "kch.mis.v03.federated-runtime",
                "decision_type": "MIS_EXACT_DECLARED_INPUT_DECISION",
                "initiator": "MIS_V0_3_1_EXACT_ENGINE",
                "trigger": "EXPLICIT_KCH_MIS_DECISION_REQUEST",
                "objective_contract_sha256": certificate["request_sha256"],
                "purpose_id": certificate["purpose_id"],
                "jurisdiction": certificate["jurisdiction"],
                "input_provenance_ids": list(certificate["evidence_ids"]),
                "source_event_ids": [stored["event_hash"]],
                "evidence_ids": [
                    *list(certificate["evidence_ids"]),
                    f"sha256:{digest}",
                ],
                "active_rule_ids": [
                    "CAPABILITY_DOES_NOT_IMPLY_AUTHORITY",
                    "PRESERVE_PURPOSE_AND_JURISDICTION",
                    "EXACT_CALCULATION_FOR_DECLARED_INPUTS_ONLY",
                ],
                "summary": summary,
                "rationale": (
                    "The sealed MIS v0.3.1 engine computed the exact posterior and loss "
                    "minimizers for the caller-declared prior, likelihood and loss table."
                ),
                "alternatives_considered": [str(item) for item in ties],
                "confidence_representation": {
                    "kind": "EXACT_RATIONAL_DECLARED_INPUT_CALCULATION",
                    "value": certificate["decision"],
                    "meaning": (
                        "Exactness applies to the supplied formal inputs; it does not validate "
                        "their empirical adequacy or authorize action."
                    ),
                },
                "risk_class": "BOUNDED_DECISION_SUPPORT",
                "authority_granted": [],
                "authority_exercised": [],
                "claim_ceiling": certificate["claim_ceiling"],
                "consequence": (
                    "The result becomes reviewable by KCH/PHL; execution, commit and claim "
                    "promotion remain separate governed decisions."
                ),
                "reversibility": (
                    "Registration is append-only and does not mutate the MIS certificate or "
                    "historical evidence."
                ),
                "stop_condition_ids": [
                    "CERTIFICATE_INTEGRITY_FAILURE",
                    "PURPOSE_OR_JURISDICTION_DRIFT",
                    "EMPIRICAL_INPUT_AUTHORITY_UNAVAILABLE",
                ],
                "source_uri": f"mis://v0.3.1/certificates/{digest}",
            }
            record_hash = sha256_json(record)
            connection.execute(
                "INSERT INTO reviewable_decisions VALUES(?,?,?,?,?,?)",
                (
                    decision_id,
                    digest,
                    canonical_json(record),
                    record_hash,
                    "READY_FOR_PHL_REGISTRATION",
                    None,
                ),
            )
            self._append(
                connection,
                "MIS_REVIEWABLE_DECISION_CREATED",
                {"decision_id": decision_id, "record_sha256": record_hash},
            )
            connection.commit()
        return {
            "record": record,
            "record_sha256": record_hash,
            "phl_state": "READY_FOR_PHL_REGISTRATION",
            "idempotent": False,
            "certificate_registration": stored,
            "authority_created": False,
        }

    def mark_phl_registration(self, decision_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM reviewable_decisions WHERE decision_id=?", (decision_id,)
            ).fetchone()
            if row is None:
                raise KeyError(decision_id)
            existing = (
                None
                if row["phl_receipt_json"] is None
                else json.loads(str(row["phl_receipt_json"]))
            )
            if existing is not None and existing != receipt:
                raise ValueError("PHL registration receipt differs from prior bridge receipt")
            connection.execute(
                "UPDATE reviewable_decisions SET phl_state='REGISTERED_REVIEWABLE_UNTRAINED',"
                "phl_receipt_json=? WHERE decision_id=?",
                (canonical_json(receipt), decision_id),
            )
            event = self._append(
                connection,
                "MIS_DECISION_REGISTERED_TO_PHL",
                {"decision_id": decision_id, "phl_receipt_sha256": sha256_json(receipt)},
            )
            connection.commit()
        return {
            "decision_id": decision_id,
            "phl_state": "REGISTERED_REVIEWABLE_UNTRAINED",
            "training_executed": False,
            "event_hash": event["event_hash"],
        }

    def lower_certificate_to_csi(self, certificate: dict[str, Any]) -> dict[str, Any]:
        verification = self.verify_certificate(certificate)
        digest = str(certificate["certificate_sha256"])
        program = [
            {
                "kind": "OPEN_SESSION",
                "session_id": f"csi:mis-v03:{digest[:24]}",
                "params": {"label": f"kch.preset.mis.v03.{digest[:16]}", "epoch": 0},
            },
            {
                "kind": "SEAL_IDENTITAS",
                "session_id": f"csi:mis-v03:{digest[:24]}",
                "params": {
                    "statements": [
                        "MIS supplies exact semantic and Bayesian calculation",
                        "KCH alone governs permission, authority, routing, commit and promotion",
                        "Certificate exactness does not validate empirical inputs",
                        "Purpose, jurisdiction, provenance and future-only chronology are preserved",
                    ],
                    "strata": [
                        ["MIS_V0_3_1", "EXACT_CALCULATION"],
                        ["KCH", "AUTHORITY_AND_COMMIT"],
                        ["CSI", "COMPOSITIONAL_ORCHESTRATION"],
                    ],
                    "explicitly_extensible": True,
                },
            },
            {
                "kind": "ADD_DATUM",
                "session_id": f"csi:mis-v03:{digest[:24]}",
                "params": {
                    "datum": {
                        "datum_id": f"mis-certificate-{digest[:16]}",
                        "role": "DECISION_SUPPORT_EVIDENCE",
                        "payload": certificate,
                        "priority": 2,
                        "source": f"mis://v0.3.1/certificates/{digest}",
                    }
                },
            },
            {
                "kind": "MODE_ON",
                "session_id": f"csi:mis-v03:{digest[:24]}",
                "params": {
                    "modus": {
                        "modus_id": "MIS_EXACT_DECISION_SUPPORT_NO_AUTHORITY",
                        "description": "Compose a verified MIS result without authority transfer",
                        "preserves_identitas": True,
                        "parameters": {
                            "calculation": "EXACT_RATIONAL",
                            "authority": "KCH_ONLY",
                            "automatic_execution": False,
                            "automatic_promotion": False,
                        },
                    }
                },
            },
        ]
        return {
            "schema": "kch.mis.v03.dynamic-csi-lowering.v0.2.0",
            "preset_id": f"kch.preset.mis.v03.{digest[:16]}",
            "topological_address": [
                "KCH",
                "FEDERATED_MATHEMATICAL_SERVICES",
                "MIS",
                "v0.3.1",
                digest,
            ],
            "source_certificate_sha256": digest,
            "certificate_verification": verification,
            "raw_csi_program": program,
            "raw_csi_program_sha256": sha256_json(program),
            "authority_created": False,
            "execution_authorized": False,
            "automatic_promotion": False,
        }

    def export_certificate(self, certificate: dict[str, Any]) -> dict[str, Any]:
        verification = self.verify_certificate(certificate)
        digest = str(certificate["certificate_sha256"])
        path = self.export_root / f"mis-certificate-{digest}.json"
        raw = (json.dumps(certificate, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        if path.is_file() and path.read_bytes() != raw:
            raise ValueError("MIS export path collision")
        if not path.is_file():
            path.write_bytes(raw)
        return {
            "path": str(path),
            "file_sha256": sha256_bytes(raw),
            "certificate_sha256": digest,
            "verification": verification,
            "original_certificate_unchanged": True,
        }

    def sco_work_order_template(
        self,
        *,
        certificate: dict[str, Any],
        sco_id: str,
        target_node_id: str,
        objective: str,
        required_outputs: list[str],
        depends_on: list[str],
        termination: str,
    ) -> dict[str, Any]:
        self.verify_certificate(certificate)
        digest = str(certificate["certificate_sha256"])
        core = {
            "sco_id": sco_id,
            "target_node_id": target_node_id,
            "objective": objective,
            "certificate_sha256": digest,
        }
        return {
            "schema": "kch.sco.work-order.v0.1.0",
            "sco_id": sco_id,
            "order_id": f"MIS-WO-{sha256_json(core)[:24]}",
            "target_node_id": target_node_id,
            "objective": objective,
            "input_refs": [f"mis://v0.3.1/certificates/{digest}"],
            "disclosed_fragments": [],
            "required_outputs": required_outputs,
            "authority_granted": [],
            "depends_on": depends_on,
            "termination": termination,
            "claim_ceiling": str(certificate["claim_ceiling"]),
        }

    def record_bridge(
        self, bridge_kind: str, source_ref: str, target_ref: str, receipt: dict[str, Any]
    ) -> dict[str, Any]:
        bridge_id = f"MIS-BRIDGE-{sha256_json([bridge_kind, source_ref, target_ref, receipt])[:24]}"
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT receipt_json FROM bridges WHERE bridge_id=?", (bridge_id,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO bridges VALUES(?,?,?,?,?,?)",
                    (
                        bridge_id,
                        bridge_kind,
                        source_ref,
                        target_ref,
                        canonical_json(receipt),
                        utc_now(),
                    ),
                )
                event = self._append(
                    connection,
                    "MIS_SYNERGISTIC_BRIDGE_RECORDED",
                    {"bridge_id": bridge_id, "bridge_kind": bridge_kind},
                )
                connection.commit()
                return {
                    "bridge_id": bridge_id,
                    "event_hash": event["event_hash"],
                    "idempotent": False,
                }
            if json.loads(str(existing["receipt_json"])) != receipt:
                raise ValueError("MIS bridge receipt collision")
            connection.rollback()
        return {"bridge_id": bridge_id, "idempotent": True}

    def verify_runtime(self) -> dict[str, Any]:
        defects: list[str] = []
        with closing(self.connect()) as connection:
            events = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
            certificates = connection.execute("SELECT * FROM certificates").fetchall()
            ledgers = connection.execute("SELECT * FROM ledgers").fetchall()
            decisions = connection.execute("SELECT * FROM reviewable_decisions").fetchall()
        parent: str | None = None
        for row in events:
            payload = json.loads(str(row["payload_json"]))
            body = {
                "event_id": row["event_id"],
                "emitted_at": row["emitted_at"],
                "kind": row["kind"],
                "payload": payload,
                "parent_hash": parent,
            }
            if row["parent_hash"] != parent or row["event_hash"] != sha256_json(body):
                defects.append(f"EVENT_CHAIN:{row['sequence']}")
            parent = str(row["event_hash"])
        for row in certificates:
            try:
                certificate = json.loads(str(row["certificate_json"]))
                self.verify_certificate(certificate)
                if certificate["certificate_sha256"] != row["certificate_sha256"]:
                    defects.append(f"CERTIFICATE_PROJECTION:{row['certificate_sha256']}")
            except Exception as exc:
                defects.append(f"CERTIFICATE:{row['certificate_sha256']}:{type(exc).__name__}")
        freeze_module = self._backend("freeze")
        for row in ledgers:
            try:
                payload = json.loads(str(row["ledger_json"]))
                ledger = freeze_module.FutureOnlyLedger.from_payload(payload)
                if not ledger.verify() or sha256_json(payload) != row["ledger_sha256"]:
                    defects.append(f"LEDGER:{row['study_id']}")
            except Exception as exc:
                defects.append(f"LEDGER:{row['study_id']}:{type(exc).__name__}")
        for row in decisions:
            record = json.loads(str(row["record_json"]))
            if sha256_json(record) != row["record_sha256"]:
                defects.append(f"REVIEWABLE_DECISION:{row['decision_id']}")
        return {
            "schema": "kch.mis.federation-integrity.v0.2.0",
            "gate": "PASS" if not defects else "FAIL",
            "defects": defects,
            "event_count": len(events),
            "certificate_count": len(certificates),
            "ledger_count": len(ledgers),
            "reviewable_decision_count": len(decisions),
            "head_hash": parent,
            "authority_created": False,
        }
