from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "overlay" / "codex" / "runtime" / "kwandisk" / "general_cleanup.py"
SPEC = importlib.util.spec_from_file_location("kwandisk_general_cleanup", MODULE)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)
GeneralCleanup = MOD.GeneralCleanup
GeneralCleanupError = MOD.GeneralCleanupError


class GeneralCleanupTests(unittest.TestCase):
    def old(self, path: Path) -> None:
        old = 946684800
        os.utime(path, (old, old))

    def test_discovery_covers_all_declared_jurisdictions(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "Documents" / "Codex").mkdir(parents=True)
            (home / ".codex").mkdir()
            (home / ".agents").mkdir()
            adhoc = home / "adhoc"
            temp = home / "temp"
            adhoc.mkdir()
            temp.mkdir()
            result = GeneralCleanup.discover(home=home, adhoc_roots=[adhoc], temp_roots=[temp])
            kinds = {item["kind"] for item in result["roots"] if item["exists"]}
            self.assertEqual({"ADHOC", "CODEX_PROJECTS", "AGENT_STATE", "TEMP"}, kinds)
            self.assertEqual("GOOGLE_DRIVE", result["storage_priority"][0])
            self.assertEqual("GITHUB_WITHIN_PROVIDER_LIMITS", result["storage_priority"][1])
            self.assertFalse(result["automatic_deletion"])

    def test_plan_only_known_regenerable_and_transient(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            cache = root / "__pycache__"
            cache.mkdir()
            cached = cache / "x.pyc"
            cached.write_bytes(b"cache")
            partial = root / "download.partial"
            partial.write_bytes(b"partial")
            unknown = root / "evidence.txt"
            unknown.write_text("retain", encoding="utf-8")
            self.old(cached)
            self.old(cache)
            self.old(partial)
            discovery = {"roots": [{"kind": "ADHOC", "path": str(root), "exists": True}], "storage_priority": []}
            plan = GeneralCleanup.plan(discovery, older_than_hours=1)
            paths = {item["path"]: item["classification"] for item in plan["candidates"]}
            self.assertEqual("REGENERABLE", paths["__pycache__"])
            self.assertEqual("TRANSIENT", paths["download.partial"])
            self.assertNotIn("evidence.txt", paths)

    def test_active_and_agent_protected_paths_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            sessions = root / "sessions"
            cache = sessions / "__pycache__"
            cache.mkdir(parents=True)
            cached = cache / "x.pyc"
            cached.write_bytes(b"x")
            self.old(cached)
            self.old(cache)
            discovery = {"roots": [{"kind": "AGENT_STATE", "path": str(root), "exists": True}], "storage_priority": []}
            plan = GeneralCleanup.plan(discovery, older_than_hours=0, active_paths=[cache])
            self.assertEqual([], plan["candidates"])
            self.assertTrue(any(item["reason"] == "PROTECTED_OR_ACTIVE" for item in plan["blocked"]))

    def test_execute_requires_exact_identity_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            partial = root / "x.partial"
            partial.write_bytes(b"x")
            self.old(partial)
            discovery = {"roots": [{"kind": "TEMP", "path": str(root), "exists": True}], "storage_priority": []}
            plan = GeneralCleanup.plan(discovery, older_than_hours=0)
            with self.assertRaises(PermissionError):
                GeneralCleanup.execute(plan, actor="AGENT", exact_authorization_id="A", expected_plan_sha256=plan["plan_sha256"])
            with self.assertRaises(GeneralCleanupError):
                GeneralCleanup.execute(plan, actor="USER", exact_authorization_id="A", expected_plan_sha256="wrong")
            first = GeneralCleanup.execute(plan, actor="USER", exact_authorization_id="A", expected_plan_sha256=plan["plan_sha256"])
            second = GeneralCleanup.execute(plan, actor="USER", exact_authorization_id="A", expected_plan_sha256=plan["plan_sha256"])
            self.assertEqual(1, len(first["removed"]))
            self.assertEqual(1, len(second["already_absent"]))
            self.assertFalse(partial.exists())

    def test_replicated_cleanup_requires_full_chain_and_unchanged_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            material = root / "closed-task"
            material.mkdir()
            (material / "a.txt").write_text("data", encoding="utf-8")
            signature = MOD._path_fingerprint(material)["signature"]
            discovery = {"roots": [{"kind": "ADHOC", "path": str(root), "exists": True}], "storage_priority": []}
            receipt = {"entries": [{
                "root": str(root), "path": "closed-task", "local_signature": signature,
                "drive_verified": True, "github_verified": True, "recovery_verified": False,
            }]}
            blocked = GeneralCleanup.plan(discovery, older_than_hours=0, replicated_receipt=receipt)
            self.assertFalse(any(item["classification"] == "REPLICATED_CUSTODY" for item in blocked["candidates"]))
            receipt["entries"][0]["recovery_verified"] = True
            allowed = GeneralCleanup.plan(discovery, older_than_hours=0, replicated_receipt=receipt)
            self.assertTrue(any(item["classification"] == "REPLICATED_CUSTODY" for item in allowed["candidates"]))


if __name__ == "__main__":
    unittest.main()
