"""Authority rejection tests; no model response is fabricated or requested."""
from pathlib import Path
import tempfile
import unittest
from kch_composed.bindings import make_model_handler


class BindingTests(unittest.TestCase):
    def test_missing_grants_block_before_client_creation(self):
        with tempfile.TemporaryDirectory() as state:
            def forbidden_factory():
                raise AssertionError("Model client must not be created")
            handler = make_model_handler(repository=Path(__file__).resolve().parents[3],
                state=state, workspace=Path(__file__).resolve().parents[3], principal="local-contract",
                client_factory=forbidden_factory, model_binding={"model": "not-invoked"},
                enabled_tools={"read_file"})
            for grants in ([], ["MODEL_INFERENCE"], ["tool:read_file"], ["*"], ["authority_choice"]):
                result = handler({"work_order": {"authority_granted": grants}})
                self.assertEqual("BLOCKED", result["outcome"])
                self.assertEqual([], result["authority_exercised"])


if __name__ == "__main__":
    unittest.main()
