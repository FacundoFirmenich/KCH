"""Check diagnostic admission without installing optional transport dependencies."""
import json
from pathlib import Path
import tempfile
import unittest

from doctor import load_profile
from generate import profiles


class DoctorAdmissionTests(unittest.TestCase):
    def test_only_exact_generated_read_only_launch_is_admitted(self):
        repository = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            documents = profiles(repository=repository, workspace=repository, state=root / "state",
                                 principal="owner", session_prefix="diagnostic")
            for filename, document in documents.items():
                path = root / filename
                path.write_text(json.dumps(document))
                host, config, values = load_profile(path)
                self.assertIn(host, {"qwenpaw", "openclaw"})
                self.assertEqual(values["--workspace"], str(repository))
                source = (document["mcpServers"] if host == "qwenpaw" else
                          document["mcp"]["servers"])["kch_composed"]
                source["args"].insert(-1, "--enable-write")
                path.write_text(json.dumps(document))
                with self.assertRaises(ValueError):
                    load_profile(path)
            self.assertFalse((root / "state").exists())

    def test_extra_environment_is_not_silently_ignored(self):
        repository = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = profiles(repository=repository, workspace=repository, state=root / "state",
                                principal="owner", session_prefix="diagnostic")["qwenpaw.local.json"]
            document["mcpServers"]["kch_composed"]["env"] = {"PYTHONPATH": "different-source"}
            path = root / "profile.json"
            path.write_text(json.dumps(document))
            with self.assertRaises(ValueError):
                load_profile(path)


if __name__ == "__main__":
    unittest.main()
