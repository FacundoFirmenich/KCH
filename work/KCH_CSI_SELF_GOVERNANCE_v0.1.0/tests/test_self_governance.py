from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kch_self_governance.compiler import compile_governance
from kch_self_governance.graph import GovernanceGraph


class SelfGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def copy_governance(self) -> Path:
        target = self.root / "governance"
        shutil.copytree(ROOT / "governance", target)
        return target

    def test_canonical_hierarchy_and_counts(self) -> None:
        graph = GovernanceGraph.load(ROOT / "governance")
        projection = graph.csi_projection()
        self.assertEqual(projection["hierarchy"], ["HARNESS", "AGENTS", "RULES"])
        self.assertEqual(projection["node_count"], 13)
        self.assertEqual(projection["agent_count"], 4)
        self.assertEqual(projection["rule_count"], 6)
        self.assertFalse(projection["install_authority"])

    def test_horizontal_and_subhierarchical_agents_are_preserved(self) -> None:
        graph = GovernanceGraph.load(ROOT / "governance")
        self.assertEqual(graph.nodes["AGENT-GOVERNANCE-COMPILER"].parent, "KCH-AGENTS")
        self.assertEqual(graph.nodes["AGENT-EXTENSION-CURATOR"].parent, "KCH-AGENTS")
        self.assertEqual(graph.nodes["AGENT-ARTIFACT-BUILDER"].parent, "AGENT-CSI-STUDIO-ORCHESTRATOR")
        edges = graph.csi_projection()["edges"]
        self.assertIn(
            {"source": "AGENT-CSI-STUDIO-ORCHESTRATOR", "target": "AGENT-ARTIFACT-BUILDER", "relation": "SUPERVISES"},
            edges,
        )

    def test_rule_routines_and_subroutines_are_material(self) -> None:
        graph = GovernanceGraph.load(ROOT / "governance")
        for node in graph.nodes.values():
            if node.kind == "RULE":
                self.assertGreater(len(node.metadata["routines"]), 0)
                self.assertGreater(len(node.metadata["subroutines"]), 0)

    def test_authority_escalation_fails_closed(self) -> None:
        governance = self.copy_governance()
        agents = governance / "AGENTS.md"
        text = agents.read_text(encoding="utf-8").replace(', "REQUEST_INSTALL"]', "]", 1)
        agents.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "authority escalation"):
            GovernanceGraph.load(governance)

    def test_undeclared_child_fails_closed(self) -> None:
        governance = self.copy_governance()
        rules = governance / "RULES.md"
        text = rules.read_text(encoding="utf-8").replace(', "RULE-HOST-PROJECTION"]', "]", 1)
        rules.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "declared children mismatch"):
            GovernanceGraph.load(governance)

    def test_compile_emits_loss_aware_codex_projection(self) -> None:
        graph = GovernanceGraph.load(ROOT / "governance")
        target = self.root / "dist"
        result = compile_governance(graph, target)
        self.assertEqual(result["gate"], "PASS")
        receipt = json.loads((target / "codex" / "COMPATIBILITY_RECEIPT.json").read_text(encoding="utf-8"))
        self.assertFalse(receipt["native_support"]["HARNESS.md"])
        self.assertTrue(receipt["native_support"]["AGENTS.md"])
        self.assertFalse(receipt["native_support"]["RULES.md"])
        self.assertEqual(receipt["native_support"][".rules"], "COMMAND_PERMISSION_SUBSET_ONLY")
        self.assertEqual(receipt["command_rules_generated"], 0)
        self.assertFalse(receipt["installation_authorized"])
        agents = (target / "codex" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertLess(agents.index("[HARNESS]"), agents.index("[AGENTS]"))
        self.assertLess(agents.index("[AGENTS]"), agents.index("[RULES]"))

    def test_semantic_rules_do_not_grant_native_command_permissions(self) -> None:
        graph = GovernanceGraph.load(ROOT / "governance")
        target = self.root / "dist"
        compile_governance(graph, target)
        native = (target / "codex" / ".codex" / "rules" / "kch-generated.rules").read_text(encoding="utf-8")
        self.assertNotIn("prefix_rule(", native)
        self.assertIn("No command-prefix permissions are granted", native)

    def test_lock_contains_source_and_artifact_hashes(self) -> None:
        graph = GovernanceGraph.load(ROOT / "governance")
        target = self.root / "dist"
        compile_governance(graph, target)
        lock = json.loads((target / "governance.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(len(lock["source_nodes"]), 13)
        self.assertGreaterEqual(len(lock["artifacts"]), 8)
        self.assertTrue(all(len(row["sha256"]) == 64 for row in lock["source_nodes"]))
        self.assertTrue(all(len(row["sha256"]) == 64 for row in lock["artifacts"]))

    def test_compilation_is_deterministic(self) -> None:
        graph = GovernanceGraph.load(ROOT / "governance")
        first = self.root / "first"
        second = self.root / "second"
        compile_governance(graph, first)
        compile_governance(graph, second)
        files = [
            "csi/governance_graph.json",
            "codex/AGENTS.md",
            "codex/.codex/rules/kch-generated.rules",
            "codex/COMPATIBILITY_RECEIPT.json",
            "governance.lock.json",
        ]
        for relative in files:
            self.assertEqual((first / relative).read_bytes(), (second / relative).read_bytes(), relative)

    def test_replace_requires_generated_marker_and_explicit_flag(self) -> None:
        graph = GovernanceGraph.load(ROOT / "governance")
        target = self.root / "occupied"
        target.mkdir()
        (target / "foreign.txt").write_text("user data", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "refusing to replace"):
            compile_governance(graph, target, replace=True)

    def test_future_catalogs_are_explicit_and_do_not_claim_implementation(self) -> None:
        artifacts = json.loads((ROOT / "catalogs" / "artifact_types.v0.1.0.json").read_text(encoding="utf-8"))
        providers = json.loads((ROOT / "catalogs" / "discovery_providers.v0.1.0.json").read_text(encoding="utf-8"))
        self.assertEqual(artifacts["implemented_through"], "SPECIFICATION_ONLY")
        self.assertEqual(providers["implemented_through"], "SPECIFICATION_ONLY")
        artifact_ids = [row["id"] for row in artifacts["artifact_types"]]
        provider_ids = [row["id"] for row in providers["providers"]]
        self.assertEqual(len(artifact_ids), len(set(artifact_ids)))
        self.assertEqual(len(provider_ids), len(set(provider_ids)))
        self.assertTrue(all("IMPLEMENTED" not in row["state"] or row["state"] == "NOT_IMPLEMENTED" for row in providers["providers"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
