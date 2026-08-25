from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ClosingSQLiteConnection(sqlite3.Connection):
    """SQLite connection whose context manager also closes the OS handle.

    The stdlib context manager commits or rolls back but deliberately does not
    close.  KCH runtimes need deterministic closure for Windows rollback,
    replacement, checkpointing and disposable-workspace cleanup.
    """

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool | None:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def sqlite_connection(*args: Any, **kwargs: Any) -> sqlite3.Connection:
    if "factory" in kwargs and kwargs["factory"] is not ClosingSQLiteConnection:
        raise ValueError("KCH sqlite_connection owns the deterministic closing factory")
    kwargs["factory"] = ClosingSQLiteConnection
    return sqlite3.connect(*args, **kwargs)


SCHEMA_VERSION = "kch.csi-studio.v0.1.0"
ALLOWED_AUTHORITIES = frozenset(
    {"INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND", "REQUEST_INSTALL"}
)


class ArtifactKind(StrEnum):
    SKILL = "SKILL"
    TOOL = "TOOL"
    MCP = "MCP"
    OPERATOR = "OPERATOR"
    AGENT = "AGENT"
    RULE = "RULE"
    KWANFORK = "KWANFORK"
    MOD = "MOD"
    PLUGIN = "PLUGIN"
    HOST_ADAPTER = "HOST_ADAPTER"
    PRESET = "PRESET"


class LifecycleState(StrEnum):
    DRAFT = "DRAFT"
    SPECIFIED = "SPECIFIED"
    GENERATED_STAGED = "GENERATED_STAGED"
    VALIDATED = "VALIDATED"
    SEALED_CANDIDATE = "SEALED_CANDIDATE"
    INSTALL_REQUESTED = "INSTALL_REQUESTED"
    INSTALLED = "INSTALLED"
    ENABLED = "ENABLED"


TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.DRAFT: frozenset({LifecycleState.SPECIFIED}),
    LifecycleState.SPECIFIED: frozenset({LifecycleState.GENERATED_STAGED}),
    LifecycleState.GENERATED_STAGED: frozenset({LifecycleState.VALIDATED}),
    LifecycleState.VALIDATED: frozenset({LifecycleState.SEALED_CANDIDATE}),
    LifecycleState.SEALED_CANDIDATE: frozenset({LifecycleState.INSTALL_REQUESTED}),
    LifecycleState.INSTALL_REQUESTED: frozenset({LifecycleState.INSTALLED}),
    LifecycleState.INSTALLED: frozenset({LifecycleState.ENABLED}),
    LifecycleState.ENABLED: frozenset(),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    value = re.sub(r"-{2,}", "-", value)
    if not value or len(value) > 63:
        raise ValueError("name must normalize to 1-63 lowercase letters, digits, or hyphens")
    return value


def safe_child(root: Path, relative: str | Path) -> Path:
    base = root.resolve()
    candidate = (base / relative).resolve()
    if candidate == base or not candidate.is_relative_to(base):
        raise ValueError(f"path escapes governed root: {relative}")
    return candidate


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    name: str
    kind: ArtifactKind
    objective: str
    jurisdiction: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    authority_ceiling: frozenset[str]
    host_targets: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        slugify(self.name)
        if self.schema != SCHEMA_VERSION:
            raise ValueError(f"unsupported spec schema: {self.schema}")
        for field_name in ("objective", "jurisdiction"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be empty")
        for field_name in ("inputs", "outputs", "host_targets"):
            values = getattr(self, field_name)
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValueError(f"{field_name} must contain non-empty strings")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} contains duplicates")
        unknown = self.authority_ceiling - ALLOWED_AUTHORITIES
        if unknown:
            raise ValueError(f"unknown authority values: {sorted(unknown)}")
        if "BUILD_STAGED" not in self.authority_ceiling:
            raise ValueError("artifact generation requires BUILD_STAGED authority")
        if {"INSTALL", "PUBLISH", "ENABLE"} & self.authority_ceiling:
            raise ValueError(
                "preinstallation specs cannot grant install, publish, or enable authority"
            )

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["kind"] = self.kind.value
        value["authority_ceiling"] = sorted(self.authority_ceiling)
        value["inputs"] = list(self.inputs)
        value["outputs"] = list(self.outputs)
        value["host_targets"] = list(self.host_targets)
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ArtifactSpec":
        return cls(
            name=str(value["name"]),
            kind=ArtifactKind(str(value["kind"])),
            objective=str(value["objective"]),
            jurisdiction=str(value["jurisdiction"]),
            inputs=tuple(value.get("inputs", ())),
            outputs=tuple(value.get("outputs", ())),
            authority_ceiling=frozenset(value.get("authority_ceiling", ())),
            host_targets=tuple(value.get("host_targets", ())),
            metadata=dict(value.get("metadata", {})),
            schema=str(value.get("schema", SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    check_id: str
    passed: bool
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def file_manifest(root: Path) -> list[dict[str, Any]]:
    base = root.resolve()
    entries: list[dict[str, Any]] = []
    for path in sorted(
        (p for p in base.rglob("*") if p.is_file()), key=lambda p: p.relative_to(base).as_posix()
    ):
        raw = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(base).as_posix(),
                "bytes": len(raw),
                "sha256": sha256_bytes(raw),
            }
        )
    return entries
