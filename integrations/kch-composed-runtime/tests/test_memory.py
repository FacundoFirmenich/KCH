"""Functional checks using repository files, not model/benchmark evaluation data.

Adversarial corruption and source substitution are explicit test operations on
temporary databases. They do not represent empirical LLM-quality measurements.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from kch_composed.memory import (MemoryIntegrityError, MemoryInvalidatedError,
                                MemoryStore, Scope)


REPO = Path(__file__).resolve().parents[3]
NATIVE = (REPO / "construct_successors/KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2"
          / "vendor/kch-native-r33-0.11.33/runtime/kch_mu_transmuter_scpp")
FILES = [NATIVE / "canonical.py", NATIVE / "temporal.py", REPO / "README.md"]


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "memory.sqlite3"
        self.store = MemoryStore(self.path)
        self.scope = Scope("repository-audit", "KCH", "memory-functional-validation")
        self.originals = [path.read_bytes() for path in FILES]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def ingest(self, count=3, *, store=None, scope=None):
        store = store or self.store
        scope = scope or self.scope
        return [store.ingest(scope, str(FILES[i].relative_to(REPO)), self.originals[i],
                             "text/plain", {"repository_path": str(FILES[i].relative_to(REPO)),
                                            "purpose": "real-repository-functional-test"})
                for i in range(count)]

    def test_originals_survive_reopen_and_idempotent_ingest(self):
        records = self.ingest()
        self.assertEqual(records, self.ingest())
        self.store.close()
        self.store = MemoryStore(self.path)
        for record, original in zip(records, self.originals):
            recalled = self.store.recall(self.scope, record["source_id"])
            self.assertEqual(recalled["content"], original)
            self.assertEqual(recalled["sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(recalled["byte_length"], len(original))

    def test_correction_requires_explicit_supersede(self):
        record = self.ingest(1)[0]
        with self.assertRaises(ValueError):
            self.store.ingest(self.scope, record["source_id"], self.originals[1])
        self.assertEqual(self.store.recall(self.scope, record["source_id"])["content"], self.originals[0])

    def test_contiguous_nested_fold_preserves_every_byte(self):
        records = self.ingest()
        fold = self.store.fold(self.scope, [r["source_id"] for r in records[:2]])
        nested = self.store.fold(self.scope, [fold["fold_id"], records[2]["source_id"]])
        actual = self.store.unfold(self.scope, nested["fold_id"])
        self.assertEqual([r["content"] for r in actual], self.originals)
        self.assertEqual(nested["manifest"]["byte_length"], sum(map(len, self.originals)))
        self.assertEqual(nested["manifest"]["members"][0]["kind"], "fold")

    def test_fold_rejects_omitted_reordered_duplicate_sources(self):
        records = self.ingest()
        ids = [r["source_id"] for r in records]
        for selection in ([ids[0], ids[2]], ids[::-1], [ids[0], ids[0]], []):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                self.store.fold(self.scope, selection)

    def test_exact_namespace_boundaries_for_recall_fold_search_and_view(self):
        records = self.ingest()
        fold = self.store.fold(self.scope, [r["source_id"] for r in records])
        view = self.store.view(self.scope)
        scopes = [Scope("different-principal", self.scope.workspace, self.scope.session),
                  Scope(self.scope.principal, "different-workspace", self.scope.session),
                  Scope(self.scope.principal, self.scope.workspace, "different-session")]
        for foreign in scopes:
            with self.subTest(scope=foreign):
                with self.assertRaises(KeyError):
                    self.store.recall(foreign, records[0]["source_id"], revision_id=records[0]["revision_id"])
                with self.assertRaises(KeyError):
                    self.store.unfold(foreign, fold["fold_id"])
                with self.assertRaises(KeyError):
                    self.store.read_view(foreign, view["view_id"])
                self.assertEqual(self.store.search(foreign, "canonical_json"), [])
                self.assertEqual(self.store.view(foreign)["references"], [])

    def test_correction_cascades_and_historical_bytes_remain_exact(self):
        records = self.ingest()
        fold = self.store.fold(self.scope, [r["source_id"] for r in records[:2]])
        nested = self.store.fold(self.scope, [fold["fold_id"], records[2]["source_id"]])
        view = self.store.view(self.scope, recent=0)
        old = records[0]
        corrected = self.store.supersede(self.scope, old["source_id"], self.originals[1],
            reason="explicit adversarial source substitution to test dependency invalidation",
            provenance={"actual_bytes_from": str(FILES[1].relative_to(REPO))})
        self.assertEqual(corrected["predecessor_revision_id"], old["revision_id"])
        self.assertEqual(corrected["version"], 2)
        self.assertTrue({old["revision_id"], fold["fold_id"], nested["fold_id"], view["view_id"]}
                        <= set(corrected["invalidated_ids"]))
        for fold_id in (fold["fold_id"], nested["fold_id"]):
            with self.assertRaises(MemoryInvalidatedError):
                self.store.unfold(self.scope, fold_id)
        with self.assertRaises(MemoryInvalidatedError):
            self.store.read_view(self.scope, view["view_id"])
        historical = self.store.recall(self.scope, old["source_id"],
                                      revision_id=old["revision_id"], allow_invalidated=True)
        self.assertEqual(historical["content"], self.originals[0])
        self.assertEqual(historical["status"], "INVALIDATED")
        self.assertEqual([r["content"] for r in self.store.unfold(
            self.scope, nested["fold_id"], allow_invalidated=True)], self.originals)
        self.assertEqual(self.store.recall(self.scope, old["source_id"])["content"], self.originals[1])
        self.assertNotIn(old["revision_id"], [r["revision_id"] for r in self.store.search(self.scope, "canonical_json")])

    def test_byte_and_character_budgets_never_truncate_sources(self):
        records = self.ingest()
        folded = self.store.fold(self.scope, [r["source_id"] for r in records[:2]])
        for byte_budget, char_budget in ((0, 0), (160, 120), (4096, 2048), (1000000, 1000000)):
            with self.subTest(byte_budget=byte_budget):
                view = self.store.view(self.scope, max_bytes=byte_budget, max_chars=char_budget, recent=1)
                self.assertLessEqual(len(view["text"].encode("utf-8")), byte_budget)
                self.assertLessEqual(len(view["text"]), char_budget)
                self.assertEqual(view["used_utf8_bytes"], len(view["text"].encode("utf-8")))
                self.assertEqual(len(view["references"]), 3)
                self.assertEqual(view["folds"][0]["fold_id"], folded["fold_id"])
                self.assertEqual(view["summarization"], "none")
                for ref in view["references"]:
                    if ref["included_verbatim"]:
                        original = self.store.recall(self.scope, ref["source_id"])["content"].decode("utf-8")
                        self.assertIn(original, view["text"])
                self.assertEqual(self.store.read_view(self.scope, view["view_id"])["text"], view["text"])

    def test_fts_rebuild_is_a_recoverable_projection(self):
        records = self.ingest()
        expected = {r["revision_id"] for r in self.store.search(self.scope, "canonical_json")}
        self.assertIn(records[0]["revision_id"], expected)
        if not self.store.fts_enabled:
            self.skipTest("SQLite FTS5 is unavailable; lexical fallback separately covered")
        with sqlite3.connect(self.path) as database:
            database.execute("DELETE FROM memory_fts")
        self.assertEqual(self.store.search(self.scope, "canonical_json"), [])
        rebuilt = self.store.rebuild_index()
        self.assertEqual(rebuilt["indexed"], 3)
        self.assertEqual({r["revision_id"] for r in self.store.search(self.scope, "canonical_json")}, expected)

    def test_lexical_fallback_uses_actual_source_text(self):
        self.store.close()
        self.store = MemoryStore(self.path, enable_fts=False)
        records = self.ingest()
        results = self.store.search(self.scope, "canonical_json")
        self.assertIn(records[0]["revision_id"], {r["revision_id"] for r in results})
        self.assertFalse(self.store.fts_enabled)

    def test_source_corruption_detected_on_recall_unfold_and_cached_view(self):
        records = self.ingest()
        fold = self.store.fold(self.scope, [r["source_id"] for r in records])
        view = self.store.view(self.scope)
        # Deliberate hostile modification of a temporary copy, not production data.
        with sqlite3.connect(self.path) as database:
            database.execute("UPDATE memory_revisions SET content=? WHERE revision_id=?",
                             (self.originals[0][::-1], records[0]["revision_id"]))
        for action in (lambda: self.store.recall(self.scope, records[0]["source_id"]),
                       lambda: self.store.unfold(self.scope, fold["fold_id"]),
                       lambda: self.store.read_view(self.scope, view["view_id"])):
            with self.assertRaises(MemoryIntegrityError):
                action()

    def test_manifest_corruption_detected(self):
        records = self.ingest()
        fold = self.store.fold(self.scope, [r["source_id"] for r in records])
        with sqlite3.connect(self.path) as database:
            database.execute("UPDATE memory_folds SET sha256=? WHERE fold_id=?",
                             ("deliberately-invalid-checksum", fold["fold_id"]))
        with self.assertRaises(MemoryIntegrityError):
            self.store.unfold(self.scope, fold["fold_id"])

    def test_head_deletion_cannot_silently_hide_an_immutable_source(self):
        records = self.ingest()
        with sqlite3.connect(self.path) as database:
            database.execute("DELETE FROM memory_heads WHERE revision_id=?", (records[0]["revision_id"],))
        for action in (lambda: self.store.view(self.scope),
                       lambda: self.store.search(self.scope, "canonical_json"),
                       lambda: self.store.recall(self.scope, records[0]["source_id"]),
                       lambda: self.ingest(1)):
            with self.assertRaises(MemoryIntegrityError):
                action()
        # Exact revision-based audit still retrieves preserved original bytes.
        record = self.store.recall(self.scope, records[0]["source_id"], revision_id=records[0]["revision_id"])
        self.assertEqual(record["content"], self.originals[0])

    def test_head_rollback_to_superseded_revision_is_detected(self):
        original = self.ingest(1)[0]
        self.store.supersede(self.scope, original["source_id"], self.originals[1],
                             reason="explicit repository-source replacement test")
        with sqlite3.connect(self.path) as database:
            database.execute("UPDATE memory_heads SET revision_id=? WHERE source_id=?",
                             (original["revision_id"], original["source_id"]))
        with self.assertRaises(MemoryIntegrityError):
            self.store.view(self.scope)

    def test_failed_successor_rolls_back_without_invalidating_original(self):
        original = self.ingest(1)[0]
        with self.assertRaises(ValueError):
            self.store.supersede(self.scope, original["source_id"], self.originals[1],
                                 reason="adversarial nonfinite provenance", provenance={"bad": float("nan")})
        recalled = self.store.recall(self.scope, original["source_id"])
        self.assertEqual(recalled["revision_id"], original["revision_id"])
        self.assertEqual(recalled["status"], "CURRENT")

    def test_concurrent_connections_idempotently_ingest_one_revision(self):
        other = MemoryStore(self.path)
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(self.ingest, 3, store=store) for store in (self.store, other)]
                results = [f.result() for f in futures]
            self.assertEqual(results[0], results[1])
            with sqlite3.connect(self.path) as database:
                self.assertEqual(database.execute("SELECT COUNT(*) FROM memory_revisions").fetchone()[0], 3)
        finally:
            other.close()

    def test_lexical_writer_keeps_existing_fts_reader_current(self):
        other = MemoryStore(self.path, enable_fts=False)
        try:
            original = self.ingest(1, store=other)[0]
            result = self.store.search(self.scope, "canonical_json")
            self.assertEqual([r["revision_id"] for r in result], [original["revision_id"]])
        finally:
            other.close()

    def test_invalidate_excludes_recall_search_and_view_but_preserves_audit(self):
        original = self.ingest(1)[0]
        self.store.invalidate(self.scope, original["source_id"], "explicit withdrawal test")
        with self.assertRaises(MemoryInvalidatedError):
            self.store.recall(self.scope, original["source_id"])
        self.assertEqual(self.store.search(self.scope, "canonical_json"), [])
        self.assertEqual(self.store.view(self.scope)["references"], [])
        self.assertEqual(self.store.recall(self.scope, original["source_id"], allow_invalidated=True)["content"], self.originals[0])

    def test_empty_or_incomplete_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            Scope("", "KCH", "test")
        with self.assertRaises(TypeError):
            self.store.ingest({"principal": "audit", "workspace": "KCH"}, "README.md", self.originals[0])
        record = self.store.ingest({"principal": "audit", "workspace": "KCH", "session": "test"},
                                   "README.md", self.originals[0])
        self.assertEqual(record["scope"]["principal"], "audit")


if __name__ == "__main__":
    unittest.main()
