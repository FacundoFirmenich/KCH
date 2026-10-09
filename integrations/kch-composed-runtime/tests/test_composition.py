"""Connected Runtime/SuperMCP and CLI checkpoint operations on real source files."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from kch_composed.runtime import Runtime
from kch_composed.tools import ToolDenied

PACKAGE = Path(__file__).resolve().parents[1]
REPOSITORY = PACKAGE.parents[1]
FEDERATION_READY = all(importlib.util.find_spec(n) for n in ("jsonschema", "numpy", "scipy"))


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"

    def runtime(self, session="source", **kwargs):
        return Runtime(repository=REPOSITORY, workspace=REPOSITORY, state=self.state,
                       principal="composition-contract", session=session, **kwargs)

    def cli(self, session, *command):
        process = subprocess.run([sys.executable, "-m", "kch_composed",
            "--repository", str(REPOSITORY), "--workspace", str(REPOSITORY),
            "--state", str(self.state), "--principal", "composition-contract",
            "--session", session, *map(str, command)], cwd=PACKAGE / "src",
            text=True, capture_output=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def test_cli_checkpoint_transports_exact_evidence_without_messages_or_calls(self):
        with self.runtime() as runtime:
            result = runtime.execute("ingest-original", "memory_ingest",
                                     {"path": "README.md", "source_id": "actual-source"})
            self.assertTrue(result["ok"])
        archive = self.root / "source.zip"
        exported = self.cli("source", "checkpoint-export", "--output", archive)
        self.assertEqual(exported["archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
        imported = self.cli("destination", "checkpoint-import", "--input", archive,
                            "--source-id", "actual-source")
        self.assertEqual(imported["audit_delivery"], "DELIVERED")
        with self.runtime("destination") as destination:
            self.assertEqual(destination.journal.messages(), [])
            self.assertEqual(destination.journal.calls(), [])
            source_id = imported["selected_sources"]["actual-source"]
            self.assertEqual(destination.memory.recall(destination.scope, source_id)["content"],
                             (REPOSITORY / "README.md").read_bytes())
        self.assertEqual(self.cli("destination", "checkpoint-import", "--input", archive,
                                 "--source-id", "actual-source"), imported)

    @unittest.skipUnless(FEDERATION_READY, "Federation optional dependencies required")
    def test_original_supermcp_is_invoked_by_runtime_with_two_durable_receipts(self):
        from kch_composed.federation import FederationBridge, kch_config
        config = kch_config(REPOSITORY, REPOSITORY, self.root / "full-kch",
                            "composition-contract", "source",
                            {"kch.super.status": {"read_only": True}})
        bridge = FederationBridge(config, self.state / "federation.sqlite")
        with self.runtime(federation=bridge) as runtime:
            names = {s["function"]["name"] for s in runtime.tools.schemas()}
            alias = "kch_" + hashlib.sha256(b"kch.super.status").hexdigest()[:32]
            self.assertIn(alias, names)
            result = runtime.execute("actual-supermcp", alias, {})
            self.assertTrue(result["ok"])
            native = json.loads(result["value"]["result"]["content"][0]["text"])
            self.assertEqual(native["package_version"], "0.11.0")
            self.assertFalse(native["mutating_execution_authorized"])
            self.assertEqual(runtime.execute("actual-supermcp", alias, {}), result)
            self.assertEqual(bridge.audit()["calls_by_status"], {"COMPLETED": 1})
            self.assertEqual(len(runtime.journal.calls()), 1)
            rejected = runtime.execute("disabled-native", "studio_create_session", {})
            self.assertFalse(rejected["ok"])
            self.assertEqual(bridge.audit()["calls_by_status"], {"COMPLETED": 1})

    @unittest.skipUnless(FEDERATION_READY, "Federation optional dependencies required")
    def test_federation_scope_cannot_substitute_runtime_principal(self):
        from kch_composed.federation import FederationBridge, kch_config
        bridge = FederationBridge(kch_config(REPOSITORY, REPOSITORY, self.root / "other-full-kch",
            "another-principal", "source", {"kch.super.status": {"read_only": True}}),
            self.state / "federation.sqlite")
        self.addCleanup(bridge.close)
        with self.assertRaises(ToolDenied):
            self.runtime(federation=bridge)
        self.assertEqual(bridge.audit()["calls_by_status"], {})


if __name__ == "__main__":
    unittest.main()
