from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from .canonical import attach_hash, sha256_json, verify_attached_hash


TemporalStatus = Literal["CURRENT", "OBSOLETE", "RESIDUAL", "RECURRENT", "PENDING_READMISSION"]


@dataclass(frozen=True, slots=True)
class TemporalEntry:
    sequence: int
    subject: str
    status: TemporalStatus
    payload: dict[str, Any]
    payload_sha256: str
    source_receipts: tuple[str, ...]
    predecessor_receipt_sha256: str | None
    valid_from: str
    observed_at: str
    authority: str
    reason: str
    receipt_sha256: str

    def core(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("receipt_sha256")
        return value

    def verify(self) -> bool:
        return self.payload_sha256 == sha256_json(self.payload) and verify_attached_hash(asdict(self))


class TemporalMemory:
    """Append-only temporal memory; transitions create successors and never rewrite history."""

    def __init__(self) -> None:
        self._entries: list[TemporalEntry] = []

    @property
    def entries(self) -> tuple[TemporalEntry, ...]:
        return tuple(self._entries)

    def latest(self, subject: str) -> TemporalEntry | None:
        return next((item for item in reversed(self._entries) if item.subject == subject), None)

    def append(
        self,
        subject: str,
        payload: dict[str, Any],
        *,
        status: TemporalStatus,
        valid_from: str,
        observed_at: str,
        authority: str,
        reason: str,
        source_receipts: tuple[str, ...] = (),
    ) -> TemporalEntry:
        if status not in {"CURRENT", "OBSOLETE", "RESIDUAL", "RECURRENT", "PENDING_READMISSION"}:
            raise ValueError("invalid temporal status")
        if not subject.strip() or not reason.strip() or not authority.strip():
            raise ValueError("subject, authority and reason must be explicit")
        predecessor = self.latest(subject)
        core = {
            "sequence": len(self._entries) + 1,
            "subject": subject,
            "status": status,
            "payload": payload,
            "payload_sha256": sha256_json(payload),
            "source_receipts": source_receipts,
            "predecessor_receipt_sha256": None if predecessor is None else predecessor.receipt_sha256,
            "valid_from": valid_from,
            "observed_at": observed_at,
            "authority": authority,
            "reason": reason,
        }
        sealed = attach_hash(core)
        entry = TemporalEntry(
            sequence=sealed["sequence"], subject=sealed["subject"], status=sealed["status"],
            payload=sealed["payload"], payload_sha256=sealed["payload_sha256"],
            source_receipts=tuple(sealed["source_receipts"]),
            predecessor_receipt_sha256=sealed["predecessor_receipt_sha256"],
            valid_from=sealed["valid_from"], observed_at=sealed["observed_at"],
            authority=sealed["authority"], reason=sealed["reason"], receipt_sha256=sealed["receipt_sha256"],
        )
        if not entry.verify():
            raise RuntimeError("temporal receipt failed self-verification")
        self._entries.append(entry)
        return entry

    def mark_obsolete(self, subject: str, *, observed_at: str, reason: str) -> TemporalEntry:
        current = self.latest(subject)
        if current is None:
            raise KeyError(subject)
        return self.append(subject, current.payload, status="OBSOLETE", valid_from=current.valid_from,
                           observed_at=observed_at, authority=current.authority, reason=reason,
                           source_receipts=(current.receipt_sha256,))

    def resurface(self, subject: str, *, observed_at: str, reason: str) -> TemporalEntry:
        previous = self.latest(subject)
        if previous is None:
            raise KeyError(subject)
        return self.append(subject, previous.payload, status="PENDING_READMISSION", valid_from=previous.valid_from,
                           observed_at=observed_at, authority="NONE", reason=reason,
                           source_receipts=(previous.receipt_sha256,))

    def readmit(self, subject: str, *, observed_at: str, valid_from: str, reason: str, user_authorized: bool) -> TemporalEntry:
        pending = self.latest(subject)
        if pending is None or pending.status != "PENDING_READMISSION":
            raise ValueError("readmission requires the latest state to be PENDING_READMISSION")
        if user_authorized is not True:
            raise PermissionError("exact user authority is required for temporal readmission")
        return self.append(subject, pending.payload, status="CURRENT", valid_from=valid_from,
                           observed_at=observed_at, authority="USER", reason=reason,
                           source_receipts=(pending.receipt_sha256,))

    def verify(self) -> bool:
        for index, entry in enumerate(self._entries):
            if entry.sequence != index + 1 or not entry.verify():
                return False
            previous = next((item for item in reversed(self._entries[:index]) if item.subject == entry.subject), None)
            if entry.predecessor_receipt_sha256 != (None if previous is None else previous.receipt_sha256):
                return False
        return True
