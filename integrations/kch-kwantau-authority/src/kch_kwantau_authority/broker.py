from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping


ZERO_HASH = "0" * 64
CLAIM_STATUSES = {"PREPARED", "COMMITTED", "ABORTED", "IN_DOUBT", "EXPIRED"}


class AuthorityError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def default_database_path() -> Path:
    raw = os.environ.get("KCH_NATIVE_DATA")
    if raw:
        root = Path(raw)
    else:
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "KCH" / "NativeR21"
    return root / "kch_native_r21.sqlite"


def _required_string(params: Mapping[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AuthorityError("INVALID_REQUEST", f"{key} is required")
    return value.strip()


def _required_hash(params: Mapping[str, Any], key: str) -> str:
    value = _required_string(params, key).lower()
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise AuthorityError("INVALID_REQUEST", f"{key} must be lowercase SHA-256")
    return value


def _required_epoch(params: Mapping[str, Any]) -> int:
    value = params.get("epoch")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AuthorityError("INVALID_REQUEST", "epoch must be a non-negative integer")
    return value


def _ttl_seconds(params: Mapping[str, Any]) -> int:
    value = params.get("ttlSeconds", 5)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 30:
        raise AuthorityError("INVALID_REQUEST", "ttlSeconds must be an integer from 1 to 30")
    return value


@dataclass(frozen=True)
class PreparedInput:
    envelope_hash: str
    lease_id: str
    reservation_id: str
    decision_id: str
    intent_id: str
    policy_hash: str
    epoch: int
    session_id: str
    tool_name: str
    args_sha256: str
    ttl_seconds: int

    @classmethod
    def from_params(cls, params: Mapping[str, Any]) -> "PreparedInput":
        return cls(
            envelope_hash=_required_hash(params, "envelopeHash"),
            lease_id=_required_string(params, "leaseId"),
            reservation_id=_required_string(params, "reservationId"),
            decision_id=_required_string(params, "decisionId"),
            intent_id=_required_string(params, "intentId"),
            policy_hash=_required_hash(params, "policyHash"),
            epoch=_required_epoch(params),
            session_id=_required_string(params, "sessionId"),
            tool_name=_required_string(params, "toolName"),
            args_sha256=_required_hash(params, "argsSha256"),
            ttl_seconds=_ttl_seconds(params),
        )


class AuthorityBroker:
    """Bridge KwanTau envelopes to KCH Native one-shot user authorizations.

    KCH's predecessor authority remains the source of truth: the broker never
    manufactures an authorization. It only binds one existing unconsumed
    authorization to one envelope and records that binding in the same KCH
    event chain.
    """

    def __init__(self, database_path: str | os.PathLike[str] | None = None) -> None:
        self.database_path = Path(database_path) if database_path else default_database_path()

    def connect(self, *, readonly: bool = False) -> sqlite3.Connection:
        database_path = self.database_path.resolve()
        if not database_path.is_file():
            raise AuthorityError(
                "AUTHORITY_DB_MISSING",
                f"KCH Native database does not exist: {database_path}",
            )
        if readonly:
            db = sqlite3.connect(
                database_path.as_uri() + "?mode=ro",
                uri=True,
                timeout=10,
            )
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA busy_timeout=10000")
            self._require_predecessor_schema(db)
            return db
        db = sqlite3.connect(database_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        self._require_predecessor_schema(db)
        self._migrate(db)
        return db

    @staticmethod
    def _require_predecessor_schema(db: sqlite3.Connection) -> None:
        tables = {
            str(row[0])
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {"settings", "events", "proposals", "authorizations"}
        missing = required - tables
        if missing:
            raise AuthorityError(
                "AUTHORITY_SCHEMA_MISMATCH",
                f"KCH Native predecessor tables missing: {sorted(missing)}",
            )

    @staticmethod
    def _migrate(db: sqlite3.Connection) -> None:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS authority_claims(
              claim_id TEXT PRIMARY KEY,
              proposal_id TEXT NOT NULL UNIQUE REFERENCES proposals(id),
              envelope_hash TEXT NOT NULL UNIQUE,
              session_id TEXT NOT NULL,
              tool_name TEXT NOT NULL,
              args_sha256 TEXT NOT NULL,
              lease_id TEXT NOT NULL,
              reservation_id TEXT NOT NULL,
              decision_id TEXT NOT NULL,
              intent_id TEXT NOT NULL,
              policy_hash TEXT NOT NULL,
              epoch INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              status TEXT NOT NULL CHECK(
                status IN ('PREPARED','COMMITTED','ABORTED','IN_DOUBT','EXPIRED')
              ),
              dispatch_id TEXT,
              run_id TEXT,
              receipt_hash TEXT,
              completed_at TEXT,
              reason TEXT
            );
            CREATE INDEX IF NOT EXISTS authority_claim_status_idx
              ON authority_claims(status, expires_at);
            """
        )
        claim_columns = {row[1] for row in db.execute("PRAGMA table_info(authority_claims)")}
        if "dispatch_id" not in claim_columns:
            db.execute("ALTER TABLE authority_claims ADD COLUMN dispatch_id TEXT")
        db.commit()

    @staticmethod
    def _setting(db: sqlite3.Connection, key: str) -> str:
        row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str(row[0]) if row else ""

    @classmethod
    def verify_chain(cls, db: sqlite3.Connection) -> tuple[bool, int, str]:
        previous = ZERO_HASH
        count = 0
        for row in db.execute("SELECT * FROM events ORDER BY id"):
            material = canonical(
                {
                    "created_at": row["created_at"],
                    "event_name": row["event_name"],
                    "session_id": row["session_id"],
                    "turn_id": row["turn_id"],
                    "payload_sha256": row["payload_sha256"],
                    "previous_hash": previous,
                }
            )
            if row["previous_hash"] != previous:
                return False, count, previous
            if row["payload_json"] is not None:
                try:
                    stored_payload = canonical(json.loads(row["payload_json"]))
                except (TypeError, ValueError, json.JSONDecodeError):
                    return False, count, previous
                if sha256_text(stored_payload) != row["payload_sha256"]:
                    return False, count, previous
            expected = sha256_text(material)
            if row["event_hash"] != expected:
                return False, count, previous
            previous = expected
            count += 1
        return True, count, previous

    @classmethod
    def _append_event(
        cls,
        db: sqlite3.Connection,
        event_name: str,
        payload: Mapping[str, Any],
    ) -> str:
        exact = canonical(dict(payload))
        payload_sha = sha256_text(exact)
        previous_row = db.execute(
            "SELECT event_hash FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        previous_hash = str(previous_row[0]) if previous_row else ZERO_HASH
        created = utc_now()
        material = canonical(
            {
                "created_at": created,
                "event_name": event_name,
                "session_id": payload.get("session_id"),
                "turn_id": payload.get("turn_id"),
                "payload_sha256": payload_sha,
                "previous_hash": previous_hash,
            }
        )
        event_hash = sha256_text(material)
        stored = exact if cls._setting(db, "persist_exact_inputs") == "true" else None
        db.execute(
            "INSERT INTO events("
            "created_at,event_name,session_id,turn_id,payload_sha256,payload_json,"
            "previous_hash,event_hash"
            ") VALUES(?,?,?,?,?,?,?,?)",
            (
                created,
                event_name,
                payload.get("session_id"),
                payload.get("turn_id"),
                payload_sha,
                stored,
                previous_hash,
                event_hash,
            ),
        )
        return event_hash

    @staticmethod
    def _authorization_rows(
        db: sqlite3.Connection,
        prepared: PreparedInput,
    ) -> list[sqlite3.Row]:
        return list(
            db.execute(
                """
                SELECT p.*, a.authorized_at, a.consumed_at, a.consumed_tool_use_id
                FROM proposals p
                JOIN authorizations a ON a.proposal_id=p.id
                WHERE p.session_id=?
                  AND p.tool_name=?
                  AND p.args_sha256=?
                  AND p.status='AUTHORIZED'
                  AND a.consumed_at IS NULL
                ORDER BY a.authorized_at, p.id
                """,
                (prepared.session_id, prepared.tool_name, prepared.args_sha256),
            )
        )

    @classmethod
    def _exact_authorization(
        cls,
        db: sqlite3.Connection,
        prepared: PreparedInput,
    ) -> sqlite3.Row | None:
        rows = cls._authorization_rows(db, prepared)
        if len(rows) > 1:
            raise AuthorityError(
                "AUTHORITY_AMBIGUOUS",
                "Multiple unconsumed KCH authorizations match the exact attempt.",
            )
        return rows[0] if rows else None

    @staticmethod
    def _claim_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {key: row[key] for key in row.keys()}

    @staticmethod
    def _claim_response(
        claim: sqlite3.Row,
        *,
        generation: str,
        active: bool,
        attestation_level: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "active": active,
            "claimId": claim["claim_id"],
            "proposalId": claim["proposal_id"],
            "status": claim["status"],
            "envelopeHash": claim["envelope_hash"],
            "leaseId": claim["lease_id"],
            "reservationId": claim["reservation_id"],
            "decisionId": claim["decision_id"],
            "intentId": claim["intent_id"],
            "policyHash": claim["policy_hash"],
            "epoch": int(claim["epoch"]),
            "sessionId": claim["session_id"],
            "toolName": claim["tool_name"],
            "argsSha256": claim["args_sha256"],
            "generation": generation,
            "verifiedAtUnix": datetime.now(UTC).timestamp(),
            "attestationLevel": attestation_level,
            **({"reason": reason} if reason else {}),
        }

    @staticmethod
    def _claim_matches(row: sqlite3.Row, prepared: PreparedInput) -> bool:
        return all(
            (
                row["envelope_hash"] == prepared.envelope_hash,
                row["session_id"] == prepared.session_id,
                row["tool_name"] == prepared.tool_name,
                row["args_sha256"] == prepared.args_sha256,
                row["lease_id"] == prepared.lease_id,
                row["reservation_id"] == prepared.reservation_id,
                row["decision_id"] == prepared.decision_id,
                row["intent_id"] == prepared.intent_id,
                row["policy_hash"] == prepared.policy_hash,
                int(row["epoch"]) == prepared.epoch,
            )
        )

    @staticmethod
    def _is_expired(row: sqlite3.Row) -> bool:
        return parse_utc(str(row["expires_at"])) <= datetime.now(UTC)

    @classmethod
    def _expire_prepared_if_needed(
        cls,
        db: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> sqlite3.Row:
        if row["status"] != "PREPARED" or not cls._is_expired(row):
            return row
        completed = utc_now()
        db.execute(
            "UPDATE authority_claims "
            "SET status='EXPIRED',completed_at=?,reason='claim ttl expired' "
            "WHERE claim_id=? AND status='PREPARED'",
            (completed, row["claim_id"]),
        )
        db.execute(
            "UPDATE proposals SET status='EXPIRED' "
            "WHERE id=? AND status='AUTHORIZED'",
            (row["proposal_id"],),
        )
        cls._append_event(
            db,
            "KWANTAU_AUTHORITY_EXPIRED",
            {
                "session_id": row["session_id"],
                "claim_id": row["claim_id"],
                "proposal_id": row["proposal_id"],
                "envelope_hash": row["envelope_hash"],
            },
        )
        return db.execute(
            "SELECT * FROM authority_claims WHERE claim_id=?",
            (row["claim_id"],),
        ).fetchone()

    def verify(self, params: Mapping[str, Any]) -> dict[str, Any]:
        prepared = PreparedInput.from_params(params)
        db = self.connect(readonly=True)
        try:
            valid, _, generation = self.verify_chain(db)
            if not valid:
                raise AuthorityError("LEDGER_CHAIN_INVALID", "KCH event chain is invalid")
            has_claim_table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='authority_claims'"
            ).fetchone() is not None
            claim = (
                db.execute(
                    "SELECT * FROM authority_claims WHERE envelope_hash=?",
                    (prepared.envelope_hash,),
                ).fetchone()
                if has_claim_table
                else None
            )
            if claim:
                active = (
                    self._claim_matches(claim, prepared)
                    and claim["status"] == "PREPARED"
                    and not self._is_expired(claim)
                )
                return self._claim_response(
                    claim,
                    generation=generation,
                    active=active,
                    attestation_level="KCH_EXISTING_CLAIM_READ_ONLY",
                    reason=None if active else "claim is not active",
                )
            authorization = self._exact_authorization(db, prepared)
            prior_claim = (
                db.execute(
                    "SELECT * FROM authority_claims WHERE proposal_id=?",
                    (authorization["id"],),
                ).fetchone()
                if authorization and has_claim_table
                else None
            )
            available = authorization is not None and prior_claim is None
            return {
                "active": available,
                "claimId": prior_claim["claim_id"] if prior_claim else None,
                "proposalId": authorization["id"] if authorization else None,
                "status": "AUTHORIZED_AVAILABLE" if available else "DENIED",
                "envelopeHash": prepared.envelope_hash,
                "leaseId": prepared.lease_id,
                "reservationId": prepared.reservation_id,
                "decisionId": prepared.decision_id,
                "intentId": prepared.intent_id,
                "policyHash": prepared.policy_hash,
                "epoch": prepared.epoch,
                "sessionId": prepared.session_id,
                "toolName": prepared.tool_name,
                "argsSha256": prepared.args_sha256,
                "generation": generation,
                "verifiedAtUnix": datetime.now(UTC).timestamp(),
                "attestationLevel": "KCH_AUTHORIZATION_AVAILABLE_READ_ONLY",
                **(
                    {}
                    if available
                    else {
                        "reason": (
                            "authorization is already claimed"
                            if prior_claim
                            else "no exact unconsumed KCH authorization"
                        )
                    }
                ),
            }
        finally:
            db.close()

    def prepare(self, params: Mapping[str, Any]) -> dict[str, Any]:
        prepared = PreparedInput.from_params(params)
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            valid, _, _ = self.verify_chain(db)
            if not valid:
                raise AuthorityError("LEDGER_CHAIN_INVALID", "KCH event chain is invalid")

            existing = db.execute(
                "SELECT * FROM authority_claims WHERE envelope_hash=?",
                (prepared.envelope_hash,),
            ).fetchone()
            if existing:
                existing = self._expire_prepared_if_needed(db, existing)
                if not self._claim_matches(existing, prepared):
                    raise AuthorityError(
                        "AUTHORITY_CLAIM_CONFLICT",
                        "Envelope hash is already bound to different claim metadata.",
                    )
                generation = self._append_event(
                    db,
                    "KWANTAU_AUTHORITY_PREPARE_REPLAY",
                    {
                        "session_id": prepared.session_id,
                        "claim_id": existing["claim_id"],
                        "proposal_id": existing["proposal_id"],
                        "envelope_hash": prepared.envelope_hash,
                        "status": existing["status"],
                    },
                )
                db.commit()
                return self._claim_response(
                    existing,
                    generation=generation,
                    active=existing["status"] == "PREPARED",
                    attestation_level="KCH_AUTHORIZATION_PREPARED",
                    reason=None if existing["status"] == "PREPARED" else "claim is terminal",
                )

            authorization = self._exact_authorization(db, prepared)
            if authorization is None:
                raise AuthorityError(
                    "AUTHORITY_DENIED",
                    "No exact unconsumed KCH user authorization exists.",
                )
            prior_claim = db.execute(
                "SELECT * FROM authority_claims WHERE proposal_id=?",
                (authorization["id"],),
            ).fetchone()
            if prior_claim:
                raise AuthorityError(
                    "AUTHORITY_CLAIM_CONFLICT",
                    "The KCH authorization has already been claimed.",
                )

            claim_id = f"KCH-KWANTAU-CLAIM-{uuid.uuid4()}"
            created = datetime.now(UTC)
            expires = created + timedelta(seconds=prepared.ttl_seconds)
            db.execute(
                """
                INSERT INTO authority_claims(
                  claim_id,proposal_id,envelope_hash,session_id,tool_name,args_sha256,
                  lease_id,reservation_id,decision_id,intent_id,policy_hash,epoch,
                  created_at,expires_at,status
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'PREPARED')
                """,
                (
                    claim_id,
                    authorization["id"],
                    prepared.envelope_hash,
                    prepared.session_id,
                    prepared.tool_name,
                    prepared.args_sha256,
                    prepared.lease_id,
                    prepared.reservation_id,
                    prepared.decision_id,
                    prepared.intent_id,
                    prepared.policy_hash,
                    prepared.epoch,
                    created.isoformat().replace("+00:00", "Z"),
                    expires.isoformat().replace("+00:00", "Z"),
                ),
            )
            generation = self._append_event(
                db,
                "KWANTAU_AUTHORITY_PREPARED",
                {
                    "session_id": prepared.session_id,
                    "claim_id": claim_id,
                    "proposal_id": authorization["id"],
                    "envelope_hash": prepared.envelope_hash,
                    "tool_name": prepared.tool_name,
                    "args_sha256": prepared.args_sha256,
                    "lease_id": prepared.lease_id,
                    "reservation_id": prepared.reservation_id,
                    "decision_id": prepared.decision_id,
                    "intent_id": prepared.intent_id,
                    "policy_hash": prepared.policy_hash,
                    "epoch": prepared.epoch,
                    "expires_at": expires.isoformat().replace("+00:00", "Z"),
                },
            )
            db.commit()
            claim = db.execute(
                "SELECT * FROM authority_claims WHERE claim_id=?",
                (claim_id,),
            ).fetchone()
            return self._claim_response(
                claim,
                generation=generation,
                active=True,
                attestation_level="KCH_AUTHORIZATION_PREPARED",
            )
        except Exception:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def commit(self, params: Mapping[str, Any]) -> dict[str, Any]:
        """Consume KCH authority before KwanTau is allowed to dispatch."""
        claim_id = _required_string(params, "claimId")
        envelope_hash = _required_hash(params, "envelopeHash")
        dispatch_id = _required_string(params, "dispatchId")
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            valid, _, _ = self.verify_chain(db)
            if not valid:
                raise AuthorityError("LEDGER_CHAIN_INVALID", "KCH event chain is invalid")
            claim = db.execute(
                "SELECT * FROM authority_claims WHERE claim_id=?",
                (claim_id,),
            ).fetchone()
            if not claim:
                raise AuthorityError("AUTHORITY_CLAIM_UNKNOWN", "Unknown authority claim")
            if claim["envelope_hash"] != envelope_hash:
                raise AuthorityError("AUTHORITY_CLAIM_CONFLICT", "Envelope hash mismatch")
            if claim["status"] == "COMMITTED":
                if claim["dispatch_id"] != dispatch_id:
                    raise AuthorityError(
                        "AUTHORITY_CLAIM_CONFLICT",
                        "Committed dispatch identity differs",
                    )
                db.commit()
                return self._claim_response(
                    claim,
                    generation=self.verify_chain(db)[2],
                    active=False,
                    attestation_level="KCH_AUTHORIZATION_COMMITTED",
                )
            if claim["status"] != "PREPARED":
                raise AuthorityError(
                    "AUTHORITY_CLAIM_TERMINAL",
                    f"Cannot commit claim in state {claim['status']}",
                )
            if self._is_expired(claim):
                claim = self._expire_prepared_if_needed(db, claim)
                raise AuthorityError(
                    "AUTHORITY_CLAIM_TERMINAL",
                    f"Cannot commit claim in state {claim['status']}",
                )
            consumed = db.execute(
                "UPDATE authorizations SET consumed_at=?,consumed_tool_use_id=? "
                "WHERE proposal_id=? AND consumed_at IS NULL",
                (utc_now(), dispatch_id, claim["proposal_id"]),
            ).rowcount
            if consumed != 1:
                raise AuthorityError(
                    "AUTHORITY_CONSUMPTION_CONFLICT",
                    "Underlying KCH authorization is no longer consumable.",
                )
            committed_at = utc_now()
            db.execute(
                "UPDATE proposals SET status='CONSUMED' "
                "WHERE id=? AND status='AUTHORIZED'",
                (claim["proposal_id"],),
            )
            db.execute(
                "UPDATE authority_claims SET status='COMMITTED',dispatch_id=?,"
                "completed_at=?,reason=NULL WHERE claim_id=?",
                (dispatch_id, committed_at, claim_id),
            )
            generation = self._append_event(
                db,
                "KWANTAU_AUTHORITY_COMMITTED",
                {
                    "session_id": claim["session_id"],
                    "claim_id": claim_id,
                    "proposal_id": claim["proposal_id"],
                    "envelope_hash": envelope_hash,
                    "dispatch_id": dispatch_id,
                },
            )
            db.commit()
            committed = db.execute(
                "SELECT * FROM authority_claims WHERE claim_id=?",
                (claim_id,),
            ).fetchone()
            return self._claim_response(
                committed,
                generation=generation,
                active=False,
                attestation_level="KCH_AUTHORIZATION_COMMITTED",
            )
        except Exception:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def receipt(self, params: Mapping[str, Any]) -> dict[str, Any]:
        """Attach the remote run/receipt after authority was already consumed."""
        claim_id = _required_string(params, "claimId")
        envelope_hash = _required_hash(params, "envelopeHash")
        run_id = _required_string(params, "runId")
        receipt_hash = _required_hash(params, "receiptHash")
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            valid, _, _ = self.verify_chain(db)
            if not valid:
                raise AuthorityError("LEDGER_CHAIN_INVALID", "KCH event chain is invalid")
            claim = db.execute(
                "SELECT * FROM authority_claims WHERE claim_id=?",
                (claim_id,),
            ).fetchone()
            if not claim:
                raise AuthorityError("AUTHORITY_CLAIM_UNKNOWN", "Unknown authority claim")
            if claim["envelope_hash"] != envelope_hash:
                raise AuthorityError("AUTHORITY_CLAIM_CONFLICT", "Envelope hash mismatch")
            if claim["status"] not in {"COMMITTED", "IN_DOUBT"}:
                raise AuthorityError(
                    "AUTHORITY_CLAIM_TERMINAL",
                    f"Cannot attach receipt in state {claim['status']}",
                )
            if claim["run_id"] is not None:
                if claim["run_id"] != run_id or claim["receipt_hash"] != receipt_hash:
                    raise AuthorityError("AUTHORITY_CLAIM_CONFLICT", "Receipt differs")
                db.commit()
                return self._claim_response(
                    claim,
                    generation=self.verify_chain(db)[2],
                    active=False,
                    attestation_level="KCH_AUTHORIZATION_RECEIPTED",
                )
            db.execute(
                "UPDATE authority_claims SET status='COMMITTED',run_id=?,receipt_hash=?,"
                "reason=NULL WHERE claim_id=?",
                (run_id, receipt_hash, claim_id),
            )
            generation = self._append_event(
                db,
                "KWANTAU_AUTHORITY_RECEIPTED",
                {
                    "session_id": claim["session_id"],
                    "claim_id": claim_id,
                    "proposal_id": claim["proposal_id"],
                    "envelope_hash": envelope_hash,
                    "dispatch_id": claim["dispatch_id"],
                    "run_id": run_id,
                    "receipt_hash": receipt_hash,
                },
            )
            db.commit()
            receipted = db.execute(
                "SELECT * FROM authority_claims WHERE claim_id=?",
                (claim_id,),
            ).fetchone()
            return self._claim_response(
                receipted,
                generation=generation,
                active=False,
                attestation_level="KCH_AUTHORIZATION_RECEIPTED",
            )
        except Exception:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def _close_without_consuming(
        self,
        params: Mapping[str, Any],
        *,
        status: str,
        event_name: str,
    ) -> dict[str, Any]:
        if status not in {"ABORTED", "IN_DOUBT"}:
            raise ValueError(status)
        claim_id = _required_string(params, "claimId")
        envelope_hash = _required_hash(params, "envelopeHash")
        reason = _required_string(params, "reason")
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            valid, _, _ = self.verify_chain(db)
            if not valid:
                raise AuthorityError("LEDGER_CHAIN_INVALID", "KCH event chain is invalid")
            claim = db.execute(
                "SELECT * FROM authority_claims WHERE claim_id=?",
                (claim_id,),
            ).fetchone()
            if not claim:
                raise AuthorityError("AUTHORITY_CLAIM_UNKNOWN", "Unknown authority claim")
            if claim["envelope_hash"] != envelope_hash:
                raise AuthorityError("AUTHORITY_CLAIM_CONFLICT", "Envelope hash mismatch")
            if claim["status"] == status:
                db.commit()
                return self._claim_response(
                    claim,
                    generation=self.verify_chain(db)[2],
                    active=False,
                    attestation_level=f"KCH_AUTHORIZATION_{status}",
                )
            expected_source = "PREPARED" if status == "ABORTED" else "COMMITTED"
            if claim["status"] != expected_source:
                raise AuthorityError(
                    "AUTHORITY_CLAIM_TERMINAL",
                    f"Cannot enter {status} from {claim['status']}",
                )
            completed = utc_now()
            db.execute(
                "UPDATE authority_claims SET status=?,completed_at=?,reason=? WHERE claim_id=?",
                (status, completed, reason, claim_id),
            )
            if status == "ABORTED":
                db.execute(
                    "UPDATE proposals SET status='ABORTED' "
                    "WHERE id=? AND status='AUTHORIZED'",
                    (claim["proposal_id"],),
                )
            generation = self._append_event(
                db,
                event_name,
                {
                    "session_id": claim["session_id"],
                    "claim_id": claim_id,
                    "proposal_id": claim["proposal_id"],
                    "envelope_hash": envelope_hash,
                    "reason": reason,
                },
            )
            db.commit()
            closed = db.execute(
                "SELECT * FROM authority_claims WHERE claim_id=?",
                (claim_id,),
            ).fetchone()
            return self._claim_response(
                closed,
                generation=generation,
                active=False,
                attestation_level=f"KCH_AUTHORIZATION_{status}",
            )
        except Exception:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def abort(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return self._close_without_consuming(
            params,
            status="ABORTED",
            event_name="KWANTAU_AUTHORITY_ABORTED",
        )

    def indoubt(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return self._close_without_consuming(
            params,
            status="IN_DOUBT",
            event_name="KWANTAU_AUTHORITY_IN_DOUBT",
        )

    def status(self, params: Mapping[str, Any]) -> dict[str, Any]:
        claim_id = _required_string(params, "claimId")
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            valid, _, _ = self.verify_chain(db)
            if not valid:
                raise AuthorityError("LEDGER_CHAIN_INVALID", "KCH event chain is invalid")
            claim = db.execute(
                "SELECT * FROM authority_claims WHERE claim_id=?",
                (claim_id,),
            ).fetchone()
            if not claim:
                raise AuthorityError("AUTHORITY_CLAIM_UNKNOWN", "Unknown authority claim")
            claim = self._expire_prepared_if_needed(db, claim)
            generation = self.verify_chain(db)[2]
            db.commit()
            return self._claim_response(
                claim,
                generation=generation,
                active=claim["status"] == "PREPARED",
                attestation_level=f"KCH_AUTHORIZATION_{claim['status']}",
            )
        except Exception:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()
