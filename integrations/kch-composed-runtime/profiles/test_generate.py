"""Validate generated files against the real checkout; no host is launched."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from generate import profiles


REPOSITORY = Path(__file__).resolve().parents[3]
GENERATOR = Path(__file__).with_name("generate.py")


class ProfileGenerationTests(unittest.TestCase):
    def test_real_checkout_profiles_have_exact_host_shapes_and_separate_sessions(self):
        docs = profiles(repository=REPOSITORY, state=REPOSITORY / ".kch-composed-state",
                        workspace=REPOSITORY, principal="local-owner",
                        session_prefix="profile-verification")
        qwen = docs["qwenpaw.local.json"]["mcpServers"]["kch_composed"]
        claw = docs["openclaw.local.json"]["mcp"]["servers"]["kch_composed"]
        for host, client in (("qwenpaw", qwen), ("openclaw", claw)):
            self.assertTrue(Path(client["command"]).is_file())
            self.assertTrue((Path(client["cwd"]) / "kch_composed" / "__main__.py").is_file())
            self.assertEqual(client["transport"], "stdio")
            self.assertEqual(client["args"][-1], "mcp")
            self.assertEqual(client["args"][client["args"].index("--session") + 1],
                             host + "-profile-verification")
            self.assertNotIn("--enable-write", client["args"])
            self.assertNotIn("env", client)
            self.assertEqual(json.loads(json.dumps(client)), client)
        self.assertEqual(qwen["name"], "kch_composed")

    def test_cli_creates_only_json_output_without_starting_runtime_or_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, output = root / "state", root / "profiles"
            result = subprocess.run([sys.executable, str(GENERATOR),
                                     "--repository", str(REPOSITORY), "--state", str(state),
                                     "--workspace", str(REPOSITORY), "--principal", "local-owner",
                                     "--session-prefix", "generator-verification", "--output", str(output)],
                                    capture_output=True, text=True, check=True)
            receipt = json.loads(result.stdout)
            self.assertFalse(receipt["host_activated"])
            self.assertFalse(receipt["host_configuration_modified"])
            self.assertFalse(state.exists())
            self.assertEqual(sorted(path.name for path in output.iterdir()),
                             ["openclaw.local.json", "qwenpaw.local.json"])
            for filename in receipt["generated"]:
                self.assertIsInstance(json.loads(Path(filename).read_text()), dict)
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            repeated = subprocess.run([sys.executable, str(GENERATOR),
                                       "--repository", str(REPOSITORY), "--state", str(state),
                                       "--workspace", str(REPOSITORY), "--principal", "local-owner",
                                       "--session-prefix", "generator-verification", "--output", str(output)],
                                      capture_output=True, text=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir()})

    def test_invalid_bindings_or_checkout_rejected(self):
        parameters = dict(repository=REPOSITORY, state=REPOSITORY / ".kch-composed-state",
                          workspace=REPOSITORY, principal="local-owner", session_prefix="verification")
        for key, value in (("principal", ""), ("principal", "owner\nadmin"),
                           ("session_prefix", ""), ("session_prefix", "../other-session"),
                           ("repository", REPOSITORY / "integrations")):
            with self.subTest(key=key, value=str(value)), self.assertRaises(ValueError):
                profiles(**{**parameters, key: value})

    def test_either_composition_can_be_selected_without_the_other(self):
        parameters = dict(repository=REPOSITORY, state=REPOSITORY / ".kch-composed-state",
                          workspace=REPOSITORY, principal="local-owner", session_prefix="choice")
        for host in ("qwenpaw", "openclaw"):
            with self.subTest(host=host):
                docs = profiles(**parameters, host=host)
                self.assertEqual(list(docs), [host + ".local.json"])
        with self.assertRaises(ValueError):
            profiles(**parameters, host="unsupported")


if __name__ == "__main__":
    unittest.main()
