"""Portable evidence contracts over actual repository files; no model inference."""
from dataclasses import asdict
import hashlib
import json
import os
import stat
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from kch_composed.checkpoint import CheckpointError, export_checkpoint, import_checkpoint_evidence
from kch_composed.memory import MemoryInvalidatedError, _canonical_json, _seal
from kch_composed.runtime import Runtime, SessionBusy

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="kch-portable-checkpoint-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.first = (REPO / "README.md").read_bytes()
        self.second = (PACKAGE / "src/kch_composed/model.py").read_bytes()
        shutil.copyfile(REPO / "README.md", self.workspace / "README.md")
        self.source = self.open("source")
        self.destination = self.open("destination")
        self.archive = self.root / "checkpoint.zip"

    def open(self, session, state=None):
        runtime = Runtime(repository=REPO, state=state or self.root / "state", workspace=self.workspace,
                          principal="checkpoint-contract-owner", session=session)
        self.addCleanup(runtime.memory.close)
        self.addCleanup(runtime.journal.close)
        return runtime

    def prepare(self):
        mem, scope = self.source.memory, self.source.scope
        self.old = mem.ingest(scope, "readme", self.first, provenance={"path": "README.md"})
        mem.ingest(scope, "model", self.second)
        self.fold = mem.fold(scope, ["readme", "model"])
        self.view = mem.view(scope)
        self.new = mem.supersede(scope, "readme", self.second, reason="contract correction from another real repository file")
        self.source.execute("actual-read", "read_file", {"path": "README.md", "max_bytes": 1024})
        self.source.journal.append("message", {"role": "user", "content": "Repository file checkpoint contract"})
        # Provider-native bytes are authored protocol evidence, not claimed inference.
        self.source.journal.append("protocol.contract", {"reasoning_content": "explicit transport-contract value", "provider": "not-live"})
        return export_checkpoint(self.source, self.archive)

    def test_exact_revisions_folds_views_and_session_preserved_scope_only(self):
        self.destination.memory.ingest(self.destination.scope, "destination-only", self.second)
        result = self.prepare()
        with zipfile.ZipFile(self.archive) as z:
            snapshot = json.loads(z.read("snapshot.json"))
            self.assertEqual(snapshot["scope"], asdict(self.source.scope))
            rows = snapshot["memory"]["memory_revisions"]
            self.assertEqual(len(rows), 3)
            self.assertEqual(z.read(next(r["content_entry"] for r in rows if r["revision_id"] == self.old["revision_id"])), self.first)
            self.assertEqual(len(snapshot["memory"]["memory_folds"]), 1)
            self.assertEqual(len(snapshot["memory"]["memory_views"]), 1)
            self.assertEqual(len(snapshot["session"]["session_calls"]), 1)
            self.assertTrue(all("native" not in name for name in z.namelist()))
        self.assertEqual(result["archive_sha256"], hashlib.sha256(self.archive.read_bytes()).hexdigest())

    def test_import_is_evidence_only_preserves_old_invalidations(self):
        self.prepare()
        receipt = import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        self.assertEqual(receipt["audit_delivery"], "DELIVERED")
        self.assertEqual(self.destination.journal.messages(), [])
        self.assertEqual(self.destination.journal.calls(), [])
        target = receipt["selected_sources"]["readme"]
        self.assertEqual(self.destination.memory.recall(self.destination.scope, target)["content"], self.second)
        old_id = receipt["revision_mapping"][self.old["revision_id"]]
        with self.assertRaises(MemoryInvalidatedError):
            self.destination.memory.recall(self.destination.scope, target, revision_id=old_id)
        old = self.destination.memory.recall(self.destination.scope, target, revision_id=old_id, allow_invalidated=True)
        self.assertEqual(old["content"], self.first)
        self.assertEqual(old["provenance"]["source_manifest"]["scope"], asdict(self.source.scope))
        saved = self.destination.memory.recall(self.destination.scope, receipt["archive_source_id"])
        self.assertEqual(saved["content"], self.archive.read_bytes())
        self.assertEqual(self.destination.recover_tools(), [])

    def test_default_import_materializes_only_archive_and_is_idempotent(self):
        self.prepare()
        a = import_checkpoint_evidence(self.destination, self.archive)
        b = import_checkpoint_evidence(self.destination, self.archive)
        self.assertEqual(a, b)
        self.assertEqual(a["selected_sources"], {})
        self.assertEqual(len(self.destination.journal.events()), 1)
        count = self.destination.memory._db.execute("SELECT COUNT(*) FROM memory_revisions WHERE scope_key=?",
            (self.destination.memory._key(self.destination.scope),)).fetchone()[0]
        self.assertEqual(count, 1)

    def test_invalidated_latest_does_not_become_current_on_import(self):
        self.source.memory.ingest(self.source.scope, "withdrawn", self.first)
        self.source.memory.invalidate(self.source.scope, "withdrawn", "explicit evidence withdrawal")
        export_checkpoint(self.source, self.archive)
        receipt = import_checkpoint_evidence(self.destination, self.archive, ["withdrawn"])
        with self.assertRaises(MemoryInvalidatedError):
            self.destination.memory.recall(self.destination.scope, receipt["selected_sources"]["withdrawn"])

    def rewrite(self, changed=None, extra=None):
        target = self.root / "altered.zip"
        with zipfile.ZipFile(self.archive) as src, zipfile.ZipFile(target, "w") as dst:
            for name in src.namelist():
                raw = src.read(name)
                dst.writestr(name, changed(name, raw) if changed else raw)
            if extra:
                dst.writestr(*extra)
        return target

    def test_hash_corruption_rejected_before_any_mutation(self):
        self.prepare()
        target = self.rewrite(lambda name, raw: raw + b"corruption" if name.startswith("blobs/") else raw)
        with self.assertRaises(CheckpointError):
            import_checkpoint_evidence(self.destination, target, ["readme"])
        self.assertEqual(self.destination.journal.events(), [])
        self.assertEqual(self.destination.memory._db.execute("SELECT COUNT(*) FROM memory_revisions WHERE scope_key=?",
            (self.destination.memory._key(self.destination.scope),)).fetchone()[0], 0)

    def test_traversal_and_duplicate_archive_members_rejected(self):
        self.prepare()
        for extra in [("../escaped", self.first), ("snapshot.json", b"{}")]:
            with self.subTest(name=extra[0]):
                with self.assertRaises(CheckpointError):
                    import_checkpoint_evidence(self.destination, self.rewrite(extra=extra))
        self.assertFalse((self.root / "escaped").exists())

    def test_unknown_selection_rejected_before_mutation(self):
        self.prepare()
        with self.assertRaises(CheckpointError):
            import_checkpoint_evidence(self.destination, self.archive, ["not-present"])
        self.assertEqual(self.destination.journal.events(), [])

    def test_failed_audit_is_durable_outbox_and_retry_does_not_duplicate_sources(self):
        self.prepare()
        with patch.object(self.destination.journal, "append", side_effect=OSError("audit write contract interruption")):
            queued = import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        self.assertEqual(queued["audit_delivery"], "PENDING_RETRY_IMPORT")
        count = self.destination.memory._db.execute("SELECT COUNT(*) FROM memory_revisions").fetchone()[0]
        done = import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        self.assertEqual(done["audit_delivery"], "DELIVERED")
        self.assertEqual(self.destination.memory._db.execute("SELECT COUNT(*) FROM memory_revisions").fetchone()[0], count)
        self.assertEqual(len(self.destination.journal.events()), 1)

    def test_queued_audit_is_preserved_by_successor_export_without_becoming_active(self):
        self.prepare()
        with patch.object(self.destination.journal, "append", side_effect=OSError("audit contract interruption")):
            original_receipt = import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        successor = self.root / "successor.zip"
        export_checkpoint(self.destination, successor)
        with zipfile.ZipFile(successor) as archive:
            snapshot = json.loads(archive.read("snapshot.json"))
            self.assertEqual(snapshot["import_audit"][0]["delivered"], 0)
            self.assertEqual(json.loads(snapshot["import_audit"][0]["receipt"])["receipt_id"], original_receipt["receipt_id"])
        third = self.open("third")
        imported = import_checkpoint_evidence(third, successor)
        self.assertEqual(imported["mode"], "EVIDENCE_ONLY")
        self.assertEqual(len(third.journal.events()), 1)
        self.assertEqual(third.journal.messages(), [])

    def test_outbox_receipt_corruption_rejected_without_repair_or_new_audit(self):
        self.prepare()
        receipt = import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        events = self.destination.journal.events()
        row = self.destination.memory._db.execute("SELECT receipt FROM checkpoint_import_outbox WHERE receipt_id=?",
                                                  (receipt["receipt_id"],)).fetchone()
        changed = json.loads(row["receipt"])
        changed["authority_transferred"] = True
        changed["selected_sources"] = {"readme": "unrelated-source"}
        altered = _canonical_json(changed)
        self.destination.memory._db.execute("UPDATE checkpoint_import_outbox SET receipt=? WHERE receipt_id=?",
                                            (altered, receipt["receipt_id"]))
        with self.assertRaisesRegex(CheckpointError, "outbox receipt integrity"):
            import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        self.assertEqual(self.destination.journal.events(), events)
        self.assertTrue(self.destination.journal.verify())
        self.assertEqual(self.destination.memory._db.execute("SELECT receipt FROM checkpoint_import_outbox WHERE receipt_id=?",
            (receipt["receipt_id"],)).fetchone()[0], altered)
        # Rehashing the corrupted outbox cannot make a changed contract legitimate.
        self.destination.memory._db.execute("UPDATE checkpoint_import_outbox SET receipt_sha256=? WHERE receipt_id=?",
                                            (_seal(changed), receipt["receipt_id"]))
        with self.assertRaisesRegex(CheckpointError, "differs from input contract"):
            import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        self.assertEqual(self.destination.journal.events(), events)

    def test_resealed_timestamp_receipt_must_match_complete_journal_event(self):
        self.prepare()
        receipt = import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        row = self.destination.memory._db.execute("SELECT receipt FROM checkpoint_import_outbox WHERE receipt_id=?",
                                                  (receipt["receipt_id"],)).fetchone()
        changed = json.loads(row["receipt"])
        changed["imported_at"] = "2000-01-01T00:00:00+00:00"
        self.destination.memory._db.execute("UPDATE checkpoint_import_outbox SET receipt=?,receipt_sha256=? WHERE receipt_id=?",
                                            (_canonical_json(changed), _seal(changed), receipt["receipt_id"]))
        with self.assertRaisesRegex(CheckpointError, "journal import receipt differs"):
            import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        self.assertEqual(len(self.destination.journal.events()), 1)

    def test_reimport_rejects_changed_destination_source_without_overwriting(self):
        self.prepare()
        receipt = import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        source_id = receipt["selected_sources"]["readme"]
        self.destination.memory.supersede(self.destination.scope, source_id, self.first,
                                          reason="explicit destination evidence correction")
        events = self.destination.journal.events()
        with self.assertRaisesRegex(CheckpointError, "revision count differs"):
            import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        self.assertEqual(self.destination.memory.recall(self.destination.scope, source_id)["content"], self.first)
        self.assertEqual(self.destination.journal.events(), events)

    def test_overlapping_source_selections_retain_complete_revision_mapping(self):
        self.prepare()
        first = import_checkpoint_evidence(self.destination, self.archive, ["readme"])
        second = import_checkpoint_evidence(self.destination, self.archive, ["readme", "model"])
        self.assertEqual(len(second["revision_mapping"]), 3)
        for original, destination in first["revision_mapping"].items():
            self.assertEqual(second["revision_mapping"][original], destination)
        self.assertEqual(import_checkpoint_evidence(self.destination, self.archive, ["model", "readme"]), second)

    def test_directory_fsync_failure_retains_archive_without_success_receipt(self):
        real_fsync = os.fsync
        calls = []
        def fail_directory(fd):
            mode = os.fstat(fd).st_mode
            calls.append("directory" if stat.S_ISDIR(mode) else "file")
            if stat.S_ISDIR(mode):
                raise OSError("directory fsync interruption contract")
            return real_fsync(fd)
        with patch("kch_composed.checkpoint.os.fsync", side_effect=fail_directory):
            with self.assertRaisesRegex(OSError, "directory fsync interruption contract"):
                export_checkpoint(self.source, self.archive)
        self.assertEqual(calls, ["file", "directory"])
        self.assertTrue(self.archive.is_file())
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(json.loads(archive.read("manifest.json"))["mode"], "EVIDENCE_ONLY")
        self.assertEqual(list(self.archive.parent.glob(".kch-checkpoint-*")), [])
        with self.assertRaises(FileExistsError):
            export_checkpoint(self.source, self.archive)

    def test_export_refuses_busy_session_and_existing_output(self):
        with self.source.lock():
            with self.assertRaises(SessionBusy):
                export_checkpoint(self.source, self.archive)
        export_checkpoint(self.source, self.archive)
        with self.assertRaises(FileExistsError):
            export_checkpoint(self.source, self.archive)


if __name__ == "__main__":
    unittest.main()
