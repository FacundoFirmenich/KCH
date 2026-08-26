from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from storage_governor import build_archive, emit_part, inspect_disk, verify_archive


class StorageGovernorTests(unittest.TestCase):
    def test_archive_is_exact_and_excludes_caches(self) -> None:
        with TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / "source"
            root.mkdir()
            (root / "source.txt").write_text("dato exacto", encoding="utf-8")
            cache = root / "__pycache__"
            cache.mkdir()
            (cache / "derived.pyc").write_bytes(b"derived")
            archive = base / "bundle.zip"
            manifest = base / "manifest.json"
            result = build_archive(root, archive, manifest)
            self.assertEqual(result["archive"]["integrity_gate"], "PASS")
            self.assertEqual([item["path"] for item in result["included"]], ["source.txt"])
            self.assertEqual(verify_archive(archive, manifest)["status"], "PASS")

    def test_manifest_tamper_is_detected(self) -> None:
        with TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / "source"
            root.mkdir()
            (root / "x").write_bytes(b"x")
            archive = base / "bundle.zip"
            manifest = base / "manifest.json"
            build_archive(root, archive, manifest)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["archive"]["sha256"] = "0" * 64
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(verify_archive(archive, manifest)["status"], "FAIL")

    def test_disk_status_has_fail_closed_state(self) -> None:
        state = inspect_disk(Path.cwd())
        self.assertIn(state.state, {"GREEN", "WARNING", "CRITICAL", "EMERGENCY"})
        if state.state in {"CRITICAL", "EMERGENCY"}:
            self.assertFalse(state.nonessential_writes_allowed)

    def test_bounded_parts_reconstruct_original(self) -> None:
        with TemporaryDirectory() as folder:
            base = Path(folder)
            archive = base / "archive.bin"
            original = bytes(range(251)) * 11
            archive.write_bytes(original)
            parts = []
            for index in range(1, 5):
                part = base / f"part{index:03d}"
                receipt = emit_part(archive, part, index=index, part_bytes=1000)
                self.assertEqual(receipt["part_count"], 3)
                parts.append(part.read_bytes())
                if index == 3:
                    break
            self.assertEqual(b"".join(parts), original)


if __name__ == "__main__":
    unittest.main()
