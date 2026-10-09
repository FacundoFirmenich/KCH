"""Durability tests; read real repository text, never simulate model responses."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from kch_composed.journal import (JournalIntegrityError, SessionConfigurationError,
                                 SessionJournal, UncertainEffectError)


REPO = Path(__file__).resolve().parents[3]


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "journal.sqlite3"
        self.configuration = {"purpose": "repository-functional-verification", "side_effects": "none"}
        self.journal = self.open()
        self.source = REPO / "README.md"
        self.actual = self.source.read_bytes()
        self.request = {"path": str(self.source)}
        self.result = {"sha256": hashlib.sha256(self.actual).hexdigest(), "bytes": len(self.actual)}

    def open(self, **changes):
        fields = {"principal": "repository-audit", "workspace": "KCH", "session": "journal-validation",
                  "configuration": self.configuration}
        fields.update(changes)
        return SessionJournal(self.path, **fields)

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def test_events_messages_and_chain_survive_reopen(self):
        message = {"role": "user", "content": self.actual.decode("utf-8")}
        first = self.journal.append("message", message)
        second = self.journal.append("source.observed", self.result)
        self.assertEqual(second["previous_sha256"], first["sha256"])
        self.journal.close()
        self.journal = self.open()
        self.assertEqual(self.journal.messages(), [message])
        self.assertEqual(self.journal.events(), [first, second])
        self.assertTrue(self.journal.verify())

    def test_profile_immutable(self):
        self.journal.append("source.observed", self.result)
        with self.assertRaises(SessionConfigurationError):
            self.open(configuration={"purpose": "changed-profile"})
        self.assertTrue(self.journal.verify())

    def test_terminal_call_is_idempotent_and_recoverable(self):
        started = self.journal.call_begin("source-read", "repository.read", self.request)
        self.assertEqual(started["status"], "STARTED")
        finished = self.journal.call_finish("source-read", self.result)
        self.assertEqual(finished["status"], "DONE")
        self.journal.close()
        self.journal = self.open()
        self.assertEqual(self.journal.call_begin("source-read", "repository.read", self.request), finished)
        self.assertEqual(self.journal.call_finish("source-read", self.result), finished)
        self.assertEqual(len(self.journal.events()), 2)

    def test_uncertain_call_is_not_replayed_after_reopen(self):
        self.journal.call_begin("source-read", "repository.read", self.request)
        self.journal.close()
        self.journal = self.open()
        with self.assertRaises(UncertainEffectError):
            self.journal.call_begin("source-read", "repository.read", self.request)
        self.assertEqual(len(self.journal.events()), 1)

    def test_mismatched_request_rejected(self):
        self.journal.call_begin("source-read", "repository.read", self.request)
        with self.assertRaises(ValueError):
            self.journal.call_begin("source-read", "different-operation", self.request)
        self.journal.call_finish("source-read", self.result)
        with self.assertRaises(ValueError):
            self.journal.call_begin("source-read", "repository.read", {"path": str(REPO / "CHANGELOG.md")})
        with self.assertRaises(ValueError):
            self.journal.call_finish("source-read", self.result, "FAILED")

    def test_failed_result_terminal_and_receipt_explicit(self):
        self.journal.call_begin("source-read", "repository.read", self.request)
        # Failure result is the actual rejection observed here, not fake service data.
        try:
            self.journal.call_begin("source-read", "repository.read", self.request)
        except UncertainEffectError as error:
            receipt = {"error_type": type(error).__name__, "detail": str(error)}
        finished = self.journal.call_finish("source-read", receipt, "FAILED")
        self.assertEqual(self.journal.call_begin("source-read", "repository.read", self.request), finished)

    def test_scope_separation(self):
        self.journal.append("message", {"role": "user", "content": self.actual.decode("utf-8")})
        self.journal.call_begin("source-read", "repository.read", self.request)
        for field in ("principal", "workspace", "session"):
            with self.open(**{field: "separate-namespace"}) as other:
                self.assertEqual(other.messages(), [])
                self.assertEqual(other.calls(), [])
                with self.assertRaises(KeyError):
                    other.call_finish("source-read", self.result)

    def test_event_tampering_detected_before_append(self):
        self.journal.append("source.observed", self.result)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE session_events SET kind='deliberately-tampered'")
        with self.assertRaises(JournalIntegrityError):
            self.journal.verify()
        with self.assertRaises(JournalIntegrityError):
            self.journal.append("message", {})

    def test_call_projection_tampering_detected(self):
        self.journal.call_begin("source-read", "repository.read", self.request)
        self.journal.call_finish("source-read", self.result)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE session_calls SET status='STARTED'")
        with self.assertRaises(JournalIntegrityError):
            self.journal.calls()

    def test_final_event_truncation_detected(self):
        self.journal.append("source.observed", self.result)
        self.journal.append("source.observed", self.result)
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM session_events WHERE seq=2")
        with self.assertRaises(JournalIntegrityError):
            self.journal.verify()

    def test_failed_finish_serialization_keeps_started_receipt(self):
        self.journal.call_begin("source-read", "repository.read", self.request)
        with self.assertRaises(ValueError):
            self.journal.call_finish("source-read", {"invalid": float("nan")})
        self.assertEqual(self.journal.calls()[0]["status"], "STARTED")
        self.assertEqual(len(self.journal.events()), 1)

    def test_concurrent_writers_have_contiguous_chain(self):
        other = self.open()
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(j.append, "source.observed", self.result)
                           for j in (self.journal, other)]
                for future in futures:
                    future.result()
            self.assertEqual([e["seq"] for e in self.journal.events()], [1, 2])
            self.assertTrue(self.journal.verify())
        finally:
            other.close()

    def test_reserved_receipts_cannot_bypass_call_state_machine(self):
        for kind in ("call.started", "call.finished"):
            with self.assertRaises(ValueError):
                self.journal.append(kind, {})
        with self.assertRaises(ValueError):
            self.journal.call_finish("missing", {}, "STARTED")

    def test_append_many_is_atomic_on_database_failure(self):
        # A real SQLite constraint failure in the second insert must roll back
        # the first insert and head update, including after a fresh connection.
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TRIGGER contract_insert_failure BEFORE INSERT ON session_events
                          WHEN NEW.kind='contract.reject'
                          BEGIN SELECT RAISE(ABORT, 'explicit transaction failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.journal.append_many([("source.observed", self.result), ("contract.reject", {})])
        self.assertEqual(self.journal.events(), [])
        with self.open() as reopened:
            self.assertEqual(reopened.events(), [])
            self.assertTrue(reopened.verify())

    def test_append_many_preserves_order_chain_and_reserved_events(self):
        values = [("source.observed", self.result), ("source.verified", self.result)]
        events = self.journal.append_many(values)
        self.assertEqual([e["kind"] for e in events], [x[0] for x in values])
        self.assertEqual(events[1]["previous_sha256"], events[0]["sha256"])
        for invalid in ([], [("source.observed", self.result), ("call.finished", {})],
                        [("source.observed", self.result), ("bad", {"x": float("nan")})]):
            with self.assertRaises(ValueError):
                self.journal.append_many(invalid)
            self.assertEqual(self.journal.events(), events)


if __name__ == "__main__":
    unittest.main()
