from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .graph import GovernanceGraph


MARKER = ".kch-csi-generated-v0.1.0"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def codex_agents_projection(graph: GovernanceGraph) -> str:
    sections = [
        "# KCH CSI governance projection for Codex",
        "",
        "> Generated from HARNESS.md > AGENTS.md > RULES.md. The CSI graph and lock are canonical; this file is a host projection.",
        "> Multiple sovereign agents are flattened into instructions because native AGENTS.md discovery is directory-layered, not a simultaneous agent graph.",
    ]
    for node in graph.ordered():
        sections.extend(
            [
                "",
                f"## [{node.kind}] {node.node_id} — {node.title}",
                "",
                f"Authority ceiling: {', '.join(sorted(node.authority_ceiling)) or 'NONE'}.",
                "",
                node.body,
            ]
        )
    return "\n".join(sections).rstrip() + "\n"


def codex_exec_rules_projection(graph: GovernanceGraph) -> str:
    entries: list[str] = []
    for node in graph.nodes.values():
        if node.kind == "RULE":
            entries.extend(node.metadata["native_exec_rules"])
    header = [
        "# Generated KCH Codex execution-policy projection.",
        "# RULES.md is semantic governance; only exact native_exec_rules mappings may appear here.",
    ]
    if not entries:
        header.append("# No command-prefix permissions are granted by this governance version.")
    return "\n".join([*header, *entries]) + "\n"


def compile_governance(graph: GovernanceGraph, target: str | Path, *, replace: bool = False) -> dict[str, Any]:
    destination = Path(target).resolve()
    if destination.exists():
        if not replace or not (destination / MARKER).is_file():
            raise ValueError("refusing to replace a non-generated or unapproved target directory")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    (destination / MARKER).write_text("KCH CSI generated output v0.1.0\n", encoding="utf-8")

    csi = graph.csi_projection()
    write_json(destination / "csi" / "governance_graph.json", csi)
    codex_agents = codex_agents_projection(graph)
    (destination / "codex").mkdir(parents=True)
    (destination / "codex" / "AGENTS.md").write_text(codex_agents, encoding="utf-8")
    rules_path = destination / "codex" / ".codex" / "rules" / "kch-generated.rules"
    rules_path.parent.mkdir(parents=True)
    rules_path.write_text(codex_exec_rules_projection(graph), encoding="utf-8")

    generic = destination / "generic"
    generic.mkdir()
    for name in ("HARNESS.md", "AGENTS.md", "RULES.md"):
        shutil.copy2(graph.root / name, generic / name)

    receipt = {
        "schema": "kch.host-projection-receipt.v0.1.0",
        "host": "CODEX",
        "state": "SHADOW_ONLY_REVIEW_REQUIRED",
        "source_hierarchy": ["HARNESS.md", "AGENTS.md", "RULES.md"],
        "native_support": {
            "HARNESS.md": False,
            "AGENTS.md": True,
            "RULES.md": False,
            ".rules": "COMMAND_PERMISSION_SUBSET_ONLY",
        },
        "agent_topology_transport": "FLATTENED_IN_AGENTS_MD_GRAPH_PRESERVED_SEPARATELY",
        "semantic_rules_transport": "INCLUDED_IN_AGENTS_PROJECTION",
        "command_rules_generated": sum(len(node.metadata["native_exec_rules"]) for node in graph.nodes.values() if node.kind == "RULE"),
        "authority_inherited": False,
        "activation_authorized": False,
        "installation_authorized": False,
    }
    write_json(destination / "codex" / "COMPATIBILITY_RECEIPT.json", receipt)

    artifacts = []
    for path in sorted((value for value in destination.rglob("*") if value.is_file()), key=lambda value: value.relative_to(destination).as_posix()):
        raw = path.read_bytes()
        artifacts.append({"path": path.relative_to(destination).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    lock = {
        "schema": "kch.csi-self-governance-lock.v0.1.0",
        "source_graph_sha256": sha256_json(csi),
        "source_nodes": [node.describe(graph.root) for node in graph.ordered()],
        "artifacts": artifacts,
        "authority_inherited": False,
        "installation_authorized": False,
    }
    write_json(destination / "governance.lock.json", lock)
    return {
        "schema": "kch.csi-self-governance-compile-result.v0.1.0",
        "gate": "PASS",
        "target": str(destination),
        "node_count": csi["node_count"],
        "agent_count": csi["agent_count"],
        "rule_count": csi["rule_count"],
        "source_graph_sha256": lock["source_graph_sha256"],
        "installation_authorized": False,
    }
