from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = "kch.csi-governance-node.v0.1.0"
KINDS = {"HARNESS", "AGENTS", "AGENT", "RULES", "RULE"}
AUTHORITIES = {"INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND", "REQUEST_INSTALL"}
COMMON_FIELDS = {"schema", "id", "kind", "version", "title", "parent", "children", "authority_ceiling", "supersedes"}
KIND_FIELDS = {
    "HARNESS": {"conflict_policy"},
    "AGENTS": {"topology", "conflict_policy"},
    "AGENT": {"categories", "reads", "writes", "parallel_group"},
    "RULES": {"conflict_policy"},
    "RULE": {"routines", "subroutines", "native_exec_rules"},
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_governance_markdown(path: Path) -> tuple[dict[str, Any], str, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "+++":
        raise ValueError(f"missing TOML frontmatter opener: {path}")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "+++")
    except StopIteration as exc:
        raise ValueError(f"missing TOML frontmatter closer: {path}") from exc
    metadata = tomllib.loads("\n".join(lines[1:end]))
    body = "\n".join(lines[end + 1 :]).strip()
    if not body:
        raise ValueError(f"empty governance body: {path}")
    return metadata, body, sha256_bytes(raw)


def string_list(value: Any, field: str, path: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{field} must be a string array: {path}")
    if len(value) != len(set(value)):
        raise ValueError(f"{field} contains duplicates: {path}")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class GovernanceNode:
    node_id: str
    kind: str
    version: str
    title: str
    parent: str
    children: tuple[str, ...]
    authority_ceiling: frozenset[str]
    supersedes: tuple[str, ...]
    metadata: dict[str, Any]
    body: str
    path: Path
    sha256: str

    @classmethod
    def load(cls, path: Path) -> "GovernanceNode":
        metadata, body, digest = parse_governance_markdown(path)
        kind = str(metadata.get("kind", ""))
        if metadata.get("schema") != SCHEMA or kind not in KINDS:
            raise ValueError(f"invalid governance schema/kind: {path}")
        expected = COMMON_FIELDS | KIND_FIELDS[kind]
        if set(metadata) != expected:
            missing = sorted(expected - set(metadata))
            extra = sorted(set(metadata) - expected)
            raise ValueError(f"frontmatter fields mismatch in {path}: missing={missing}, extra={extra}")
        node_id = str(metadata["id"])
        if not re.fullmatch(r"[A-Z][A-Z0-9-]{2,95}", node_id):
            raise ValueError(f"invalid governance id: {node_id}")
        authorities = frozenset(string_list(metadata["authority_ceiling"], "authority_ceiling", path))
        unknown = authorities - AUTHORITIES
        if unknown:
            raise ValueError(f"unknown authority in {path}: {sorted(unknown)}")
        return cls(
            node_id=node_id,
            kind=kind,
            version=str(metadata["version"]),
            title=str(metadata["title"]),
            parent=str(metadata["parent"]),
            children=string_list(metadata["children"], "children", path),
            authority_ceiling=authorities,
            supersedes=string_list(metadata["supersedes"], "supersedes", path),
            metadata=metadata,
            body=body,
            path=path.resolve(),
            sha256=digest,
        )

    def describe(self, root: Path) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "kind": self.kind,
            "version": self.version,
            "title": self.title,
            "parent": self.parent,
            "children": list(self.children),
            "authority_ceiling": sorted(self.authority_ceiling),
            "path": self.path.relative_to(root.resolve()).as_posix(),
            "sha256": self.sha256,
        }
