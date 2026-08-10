from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import GovernanceNode


ROOT_FILES = ("HARNESS.md", "AGENTS.md", "RULES.md")


@dataclass(frozen=True, slots=True)
class GovernanceGraph:
    root: Path
    nodes: dict[str, GovernanceNode]

    @classmethod
    def load(cls, root: str | Path) -> "GovernanceGraph":
        source = Path(root).resolve()
        paths = [source / name for name in ROOT_FILES]
        paths.extend(sorted((source / "agents").glob("*.md")))
        paths.extend(sorted((source / "rules").glob("*.md")))
        missing = [str(path) for path in paths[:3] if not path.is_file()]
        if missing:
            raise ValueError(f"required governance files missing: {missing}")
        nodes: dict[str, GovernanceNode] = {}
        for path in paths:
            node = GovernanceNode.load(path)
            if node.node_id in nodes:
                raise ValueError(f"duplicate governance id: {node.node_id}")
            nodes[node.node_id] = node
        graph = cls(source, nodes)
        graph.validate()
        return graph

    def validate(self) -> None:
        required = {"KCH-HARNESS": "HARNESS", "KCH-AGENTS": "AGENTS", "KCH-RULES": "RULES"}
        for node_id, kind in required.items():
            if node_id not in self.nodes or self.nodes[node_id].kind != kind:
                raise ValueError(f"required {kind} node missing: {node_id}")
        expected_parent_kind = {
            "HARNESS": {""},
            "AGENTS": {"HARNESS"},
            "AGENT": {"AGENTS", "AGENT"},
            "RULES": {"AGENTS"},
            "RULE": {"RULES"},
        }
        actual_children: dict[str, set[str]] = {node_id: set() for node_id in self.nodes}
        for node in self.nodes.values():
            if node.parent:
                if node.parent not in self.nodes:
                    raise ValueError(f"unknown parent {node.parent} for {node.node_id}")
                parent = self.nodes[node.parent]
                if parent.kind not in expected_parent_kind[node.kind]:
                    raise ValueError(f"invalid parent kind {parent.kind} for {node.kind} {node.node_id}")
                if not node.authority_ceiling.issubset(parent.authority_ceiling):
                    escalation = sorted(node.authority_ceiling - parent.authority_ceiling)
                    raise ValueError(f"authority escalation at {node.node_id}: {escalation}")
                actual_children[node.parent].add(node.node_id)
            elif node.kind != "HARNESS":
                raise ValueError(f"only HARNESS may have no parent: {node.node_id}")
        for node_id, node in self.nodes.items():
            if set(node.children) != actual_children[node_id]:
                raise ValueError(
                    f"declared children mismatch at {node_id}: declared={sorted(node.children)}, actual={sorted(actual_children[node_id])}"
                )
        for start in self.nodes:
            seen: set[str] = set()
            cursor = start
            while cursor:
                if cursor in seen:
                    raise ValueError(f"governance cycle detected from {start}")
                seen.add(cursor)
                cursor = self.nodes[cursor].parent
        if any("INSTALL" in node.authority_ceiling or "PUBLISH" in node.authority_ceiling for node in self.nodes.values()):
            raise ValueError("preinstallation governance cannot contain INSTALL or PUBLISH authority")

    def ordered(self) -> list[GovernanceNode]:
        order: list[GovernanceNode] = []

        def visit(node_id: str) -> None:
            node = self.nodes[node_id]
            order.append(node)
            for child in sorted(node.children):
                visit(child)

        visit("KCH-HARNESS")
        if len(order) != len(self.nodes):
            raise ValueError("orphan governance nodes detected")
        return order

    def csi_projection(self) -> dict[str, Any]:
        edges: list[dict[str, str]] = []
        for node in self.ordered():
            if node.parent:
                relation = {
                    "AGENTS": "GOVERNS_AGENT_PLANE",
                    "AGENT": "DELEGATES" if self.nodes[node.parent].kind == "AGENTS" else "SUPERVISES",
                    "RULES": "GOVERNS_RULE_PLANE",
                    "RULE": "DEFINES_RULE",
                }[node.kind]
                edges.append({"source": node.parent, "target": node.node_id, "relation": relation})
        for rule in sorted((node for node in self.nodes.values() if node.kind == "RULE"), key=lambda value: value.node_id):
            for agent in sorted((node for node in self.nodes.values() if node.kind == "AGENT"), key=lambda value: value.node_id):
                edges.append({"source": rule.node_id, "target": agent.node_id, "relation": "CONSTRAINS"})
        return {
            "schema": "kch.csi-self-governance-graph.v0.1.0",
            "root": "KCH-HARNESS",
            "hierarchy": ["HARNESS", "AGENTS", "RULES"],
            "resolution": "MOST_RESTRICTIVE_AUTHORITY_THEN_NARROWEST_VALID_SCOPE",
            "nodes": [node.describe(self.root) for node in self.ordered()],
            "edges": edges,
            "node_count": len(self.nodes),
            "agent_count": sum(node.kind == "AGENT" for node in self.nodes.values()),
            "rule_count": sum(node.kind == "RULE" for node in self.nodes.values()),
            "install_authority": False,
        }
