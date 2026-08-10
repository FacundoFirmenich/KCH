import json
import tempfile
import unittest
from pathlib import Path

from transport_guard import TransportError, TransportGuard


def envelope():
    return json.loads((Path(__file__).parent / "dispatch_envelope.json").read_text(encoding="utf-8"))


def receipt():
    value = envelope()
    return {
        "schema": value["expected_receipt_schema"],
        "dispatch_id": value["dispatch_id"],
        "order_id": value["order_id"],
        "node_state": "COMPLETED_NO_SIDE_EFFECTS",
        "nonce": value["nonce"],
        "authority_exercised": ["RETURN_BOUNDED_TEXT_RECEIPT"],
        "forbidden_actions_observed": value["forbidden_actions"],
        "result": "SCO_LIVE_TRANSPORT_OK",
        "limitations": ["TEXTUAL_RECEIPT_ONLY", "NO_FILESYSTEM_OR_NETWORK_ACTION"],
    }


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.guard = TransportGuard(Path(self.temp.name) / "guard.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_prepare_and_retry(self):
        self.assertTrue(self.guard.prepare(envelope())["should_send"])
        self.guard.mark_sent(envelope()["dispatch_id"], "turn-request")
        replay = self.guard.prepare(envelope())
        self.assertFalse(replay["should_send"])
        self.assertTrue(replay["idempotent_replay"])

    def test_dispatch_id_collision(self):
        self.guard.prepare(envelope())
        changed = envelope()
        changed["nonce"] = "different"
        with self.assertRaises(TransportError):
            self.guard.prepare(changed)

    def test_receipt_binding_and_replay(self):
        self.guard.prepare(envelope())
        self.guard.mark_sent(envelope()["dispatch_id"], "turn-request")
        text = json.dumps(receipt(), separators=(",", ":"))
        first = self.guard.ingest(envelope()["dispatch_id"], "turn-response", text)
        replay = self.guard.ingest(envelope()["dispatch_id"], "turn-response", text)
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(self.guard.verify()["gate"], "PASS")

    def test_wrong_nonce_rejected(self):
        self.guard.prepare(envelope())
        self.guard.mark_sent(envelope()["dispatch_id"], "turn-request")
        value = receipt()
        value["nonce"] = "wrong"
        with self.assertRaises(TransportError):
            self.guard.ingest(envelope()["dispatch_id"], "turn-response", json.dumps(value))

    def test_authority_escalation_rejected(self):
        self.guard.prepare(envelope())
        self.guard.mark_sent(envelope()["dispatch_id"], "turn-request")
        value = receipt()
        value["authority_exercised"] = ["FILESYSTEM_MUTATION"]
        with self.assertRaises(TransportError):
            self.guard.ingest(envelope()["dispatch_id"], "turn-response", json.dumps(value))


if __name__ == "__main__":
    unittest.main()
