"""Actual CLI subprocess protocol checks, not OpenClaw/QwenPaw host activation.

Generate concrete profiles with the tracked generator into isolated test scopes,
then execute their command/cwd unchanged. No ignored local file or LLM is needed.
"""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
REPOSITORY = PACKAGE.parents[1]


def request(ident, method, params=None):
    return {"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}}


class MCPSubprocessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kch-mcp-contract-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        shutil.copyfile(REPOSITORY / "README.md", self.workspace / "README.md")
        self.original = (REPOSITORY / "README.md").read_bytes()
        self.generated = self.root / "profiles"
        generator = subprocess.run([sys.executable, str(PACKAGE / "profiles/generate.py"),
            "--repository", str(REPOSITORY), "--state", str(self.root / "state"),
            "--workspace", str(self.workspace), "--principal", "mcp-contract-owner",
            "--session-prefix", "protocol-contract", "--output", str(self.generated)],
            capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(generator.returncode, 0, generator.stderr)
        receipt = json.loads(generator.stdout)
        self.assertFalse(receipt["host_activated"])
        self.assertFalse(receipt["host_configuration_modified"])

    def profile(self, name):
        config = json.loads((self.generated / f"{name}.local.json").read_text())
        server = (config["mcp"]["servers"] if name == "openclaw" else config["mcpServers"])["kch_composed"]
        return [server["command"], *server["args"]], server["cwd"]

    def exchange(self, name, messages):
        command, cwd = self.profile(name)
        process = subprocess.run(command, cwd=cwd,
            input="".join(json.dumps(m) + "\n" for m in messages),
            capture_output=True, text=True, timeout=25, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, "")
        return [json.loads(line) for line in process.stdout.splitlines()]

    @staticmethod
    def initialize():
        return request(1, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                         "clientInfo": {"name": "explicit-contract-test", "version": "1"}})

    def test_both_profile_commands_initialize_list_and_call_real_tools(self):
        for name in ("openclaw", "qwenpaw"):
            with self.subTest(profile=name):
                responses = self.exchange(name, [self.initialize(),
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    request(2, "tools/list"),
                    request(3, "tools/call", {"name": "read_file", "arguments": {"path": "README.md", "max_bytes": 65536}}),
                    request(4, "tools/call", {"name": "memory_ingest", "arguments": {"path": "README.md", "source_id": "actual-readme"}}),
                    request(5, "tools/call", {"name": "memory_recall", "arguments": {"source_id": "actual-readme"}})])
                self.assertEqual([r["id"] for r in responses], [1, 2, 3, 4, 5])
                self.assertEqual(responses[0]["result"]["protocolVersion"], "2025-11-25")
                names = {t["name"] for t in responses[1]["result"]["tools"]}
                self.assertIn("memory_fold", names)
                self.assertNotIn("write_file", names)
                self.assertNotIn("sensor_observe", names)
                read = json.loads(responses[2]["result"]["content"][0]["text"])
                recalled = json.loads(responses[4]["result"]["content"][0]["text"])
                self.assertEqual(base64.b64decode(read["value"]["content"]["data"]), self.original[:65536])
                self.assertEqual(base64.b64decode(recalled["value"]["content"]["data"]), self.original)
                self.assertEqual(recalled["value"]["sha256"], hashlib.sha256(self.original).hexdigest())
                self.assertFalse(responses[4]["result"]["isError"])

    def test_duplicate_id_unknown_method_and_disabled_effect_are_explicit(self):
        responses = self.exchange("openclaw", [self.initialize(), request(2, "tools/list"),
            request(2, "tools/call", {"name": "read_file", "arguments": {"path": "README.md"}}),
            request(3, "not-a-supported-method"),
            request(4, "tools/call", {"name": "write_file", "arguments": {"path": "must-not-exist.md", "content": self.original.decode("utf-8")}})])
        self.assertEqual(responses[2]["error"]["code"], -32600)
        self.assertEqual(responses[3]["error"]["code"], -32601)
        self.assertTrue(responses[4]["result"]["isError"])
        self.assertFalse((self.workspace / "must-not-exist.md").exists())

    def test_request_ids_are_connection_local_without_cross_replay(self):
        batch = [self.initialize(), request(2, "tools/call", {"name": "read_file", "arguments": {"path": "README.md", "max_bytes": 65536}})]
        first = self.exchange("qwenpaw", batch)
        second_actual = (PACKAGE / "src/kch_composed/model.py").read_bytes()
        shutil.copyfile(PACKAGE / "src/kch_composed/model.py", self.workspace / "README.md")
        second = self.exchange("qwenpaw", batch)
        original_read = json.loads(first[1]["result"]["content"][0]["text"])
        current_read = json.loads(second[1]["result"]["content"][0]["text"])
        self.assertEqual(base64.b64decode(original_read["value"]["content"]["data"]), self.original[:65536])
        self.assertEqual(base64.b64decode(current_read["value"]["content"]["data"]), second_actual[:65536])


if __name__ == "__main__":
    unittest.main()
