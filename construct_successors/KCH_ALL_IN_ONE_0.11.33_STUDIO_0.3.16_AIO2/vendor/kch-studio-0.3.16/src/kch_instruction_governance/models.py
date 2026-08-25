from __future__ import annotations

import fnmatch
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.astimezone(UTC)


class GovernanceLayer(IntEnum):
    """Hard precedence supplied by an attested host/KCH authority compiler.

    Lower values have stronger precedence.  Credal inference is forbidden from
    changing this value.  An explicit stop policy may be compiled into HARNESS;
    this enum is not an attempt to replace the host's own instruction hierarchy.
    """

    EXTERNAL_PLATFORM = 0
    HARNESS = 100
    AGENTS = 200
    RULES = 300
    SESSION_POLICY = 400
    MODEL_PROPOSAL = 500


class InstructionEffect(StrEnum):
    REQUIRE = "REQUIRE"
    FORBID = "FORBID"
    ALLOW = "ALLOW"
    PREFER = "PREFER"
    INFORM = "INFORM"


class LifecycleState(StrEnum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    ENACTED = "ENACTED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class DecisionState(StrEnum):
    APPLY = "APPLY"
    BLOCK = "BLOCK"
    ASK_USER = "ASK_USER"
    ABSTAIN = "ABSTAIN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_ESTIMABLE = "NOT_ESTIMABLE"
    CONFLICT_SET = "CONFLICT_SET"


@dataclass(frozen=True, slots=True)
class GovernanceContext:
    jurisdiction: str
    scope_tags: tuple[str, ...] = ()
    resource: str = "resource://unspecified"
    operation: str = "*"
    exception_tags: tuple[str, ...] = ()
    at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction cannot be empty")
        if "://" not in self.resource:
            raise ValueError("resource must be a scheme:// identifier")
        parse_time(self.at)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["scope_tags"] = list(self.scope_tags)
        value["exception_tags"] = list(self.exception_tags)
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> GovernanceContext:
        return cls(
            jurisdiction=str(value["jurisdiction"]),
            scope_tags=tuple(str(item) for item in value.get("scope_tags", ())),
            resource=str(value.get("resource", "resource://unspecified")),
            operation=str(value.get("operation", "*")),
            exception_tags=tuple(str(item) for item in value.get("exception_tags", ())),
            at=str(value.get("at", utc_now())),
        )


@dataclass(frozen=True, slots=True)
class Instruction:
    instruction_id: str
    revision: int
    raw_text: str
    canonical_text: str
    layer: GovernanceLayer
    authority_source: str
    authority_attested: bool
    authority_receipt_sha256: str | None
    effect: InstructionEffect
    lifecycle: LifecycleState
    jurisdictions: tuple[str, ...]
    scopes: tuple[str, ...]
    resources: tuple[str, ...]
    operations: tuple[str, ...]
    exception_tags: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    credal_profile_id: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.instruction_id.strip() or not self.raw_text.strip():
            raise ValueError("instruction_id and raw_text cannot be empty")
        if not self.canonical_text.strip() or not self.authority_source.strip():
            raise ValueError("canonical_text and authority_source cannot be empty")
        if self.revision < 1:
            raise ValueError("revision must be positive")
        if self.authority_attested:
            digest = self.authority_receipt_sha256 or ""
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("attested authority requires a lowercase SHA-256 receipt")
        elif self.authority_receipt_sha256 is not None:
            raise ValueError("unattested authority cannot carry an authority receipt")
        for label, values in {
            "jurisdictions": self.jurisdictions,
            "scopes": self.scopes,
            "resources": self.resources,
            "operations": self.operations,
            "exception_tags": self.exception_tags,
            "depends_on": self.depends_on,
            "supersedes": self.supersedes,
            "evidence_refs": self.evidence_refs,
        }.items():
            if len(values) != len(set(values)) or any(not item.strip() for item in values):
                raise ValueError(f"{label} must contain unique non-empty strings")
        if not self.jurisdictions or not self.resources or not self.operations:
            raise ValueError("jurisdictions, resources and operations cannot be empty")
        if self.instruction_id in self.depends_on or self.instruction_id in self.supersedes:
            raise ValueError("an instruction cannot depend on or supersede itself")
        start, end = parse_time(self.valid_from), parse_time(self.valid_until)
        if start is not None and end is not None and end <= start:
            raise ValueError("valid_until must be later than valid_from")
        parse_time(self.created_at)

    @property
    def active(self) -> bool:
        return self.lifecycle is LifecycleState.ENACTED

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["layer"] = self.layer.name
        value["effect"] = self.effect.value
        value["lifecycle"] = self.lifecycle.value
        for key in (
            "jurisdictions",
            "scopes",
            "resources",
            "operations",
            "exception_tags",
            "depends_on",
            "supersedes",
            "evidence_refs",
        ):
            value[key] = list(value[key])
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Instruction:
        return cls(
            instruction_id=str(value["instruction_id"]),
            revision=int(value["revision"]),
            raw_text=str(value["raw_text"]),
            canonical_text=str(value["canonical_text"]),
            layer=GovernanceLayer[str(value["layer"])],
            authority_source=str(value["authority_source"]),
            authority_attested=value.get("authority_attested") is True,
            authority_receipt_sha256=value.get("authority_receipt_sha256"),
            effect=InstructionEffect(str(value["effect"])),
            lifecycle=LifecycleState(str(value["lifecycle"])),
            jurisdictions=tuple(str(item) for item in value["jurisdictions"]),
            scopes=tuple(str(item) for item in value.get("scopes", ())),
            resources=tuple(str(item) for item in value["resources"]),
            operations=tuple(str(item) for item in value["operations"]),
            exception_tags=tuple(str(item) for item in value.get("exception_tags", ())),
            depends_on=tuple(str(item) for item in value.get("depends_on", ())),
            supersedes=tuple(str(item) for item in value.get("supersedes", ())),
            evidence_refs=tuple(str(item) for item in value.get("evidence_refs", ())),
            credal_profile_id=value.get("credal_profile_id"),
            valid_from=value.get("valid_from"),
            valid_until=value.get("valid_until"),
            provenance=dict(value.get("provenance", {})),
            created_at=str(value.get("created_at", utc_now())),
        )

    def applies_to(self, context: GovernanceContext) -> bool:
        if not self.active or not self.authority_attested:
            return False
        now = parse_time(context.at)
        start, end = parse_time(self.valid_from), parse_time(self.valid_until)
        if start is not None and now is not None and now < start:
            return False
        if end is not None and now is not None and now >= end:
            return False
        if "*" not in self.jurisdictions and context.jurisdiction not in self.jurisdictions:
            return False
        if self.scopes and "*" not in self.scopes and not set(self.scopes) & set(context.scope_tags):
            return False
        if not any(fnmatch.fnmatchcase(context.resource, pattern) for pattern in self.resources):
            return False
        operation = context.operation.upper()
        if "*" not in self.operations and operation not in {item.upper() for item in self.operations}:
            return False
        if set(self.exception_tags) & set(context.exception_tags):
            return False
        return True


def effects_conflict(left: InstructionEffect, right: InstructionEffect) -> bool:
    pair = {left, right}
    return InstructionEffect.FORBID in pair and bool(
        pair & {InstructionEffect.REQUIRE, InstructionEffect.ALLOW}
    )
