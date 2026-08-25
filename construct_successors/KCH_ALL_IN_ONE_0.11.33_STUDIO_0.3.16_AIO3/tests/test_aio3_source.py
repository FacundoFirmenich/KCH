from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = load(ROOT / "scripts" / "build_aio3.py", "kch_aio3_builder_test")
controller = load(ROOT / "overlay" / "codex" / "scripts" / "kch_construct_persistence.py", "kch_construct_persistence_test")
closure = load(ROOT / "overlay" / "codex" / "scripts" / "kch_substantive_closure.py", "kch_substantive_closure_test")


class AIO3SourceTests(unittest.TestCase):
    def test_contracts_are_canonical_and_non_promoting(self):
        closure_contract = json.loads((ROOT / "contracts" / "substantive_closure.v1.json").read_text(encoding="utf-8"))
        persistence = json.loads((ROOT / "contracts" / "construct_persistence.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(closure_contract["closure"]["default_paragraphs"], {"minimum": 1, "maximum": 2})
        self.assertFalse(closure_contract["authority"]["automatic_promotion"])
        self.assertEqual(persistence["canonical_upstream"], "FacundoFirmenich/KCH")
        self.assertIn("generic_installed_package_write_to_FacundoFirmenich/KCH", persistence["hard_denials"])
        self.assertEqual(persistence["consultative_decisions"], ["Sí", "No", "Nunca en esta sesión", "Siempre en esta sesión"])

    def test_closure_context_contains_substantive_and_archival_boundaries(self):
        contract = closure.load_contract(ROOT / "contracts" / "substantive_closure.v1.json")
        text = closure.render_context(contract)
        self.assertIn("uno o dos parrafos", text)
        self.assertIn("no prueba de validez cientifica", text)
        self.assertIn("No firmes", text)
        self.assertLess(len(text), 2200)

    def test_hook_lowering_is_idempotent(self):
        with tempfile.TemporaryDirectory() as raw:
            plugin = Path(raw)
            hooks_path = plugin / "hooks" / "hooks.json"
            hooks_path.parent.mkdir()
            payload = {"hooks": {event: [{"hooks": []}] for event in builder.EXPECTED_EVENTS}} if hasattr(builder, "EXPECTED_EVENTS") else {
                "hooks": {event: [{"hooks": []}] for event in {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "SessionEnd"}}
            }
            hooks_path.write_text(json.dumps(payload), encoding="utf-8")
            builder.configure_hooks(plugin)
            first = hooks_path.read_bytes()
            builder.configure_hooks(plugin)
            self.assertEqual(first, hooks_path.read_bytes())
            hooks = json.loads(first)["hooks"]
            for event in ("SessionStart", "UserPromptSubmit"):
                self.assertEqual(sum(builder.CLOSURE_HOOK in item.get("command", "") for item in hooks[event][0]["hooks"]), 1)

    def test_cline_lowering_is_idempotent(self):
        with tempfile.TemporaryDirectory() as raw:
            package = Path(raw)
            rule = package / "adapters" / "cline-vscode" / "kch-all-in-one.md"
            rule.parent.mkdir(parents=True)
            rule.write_text("# stable predecessor\n", encoding="utf-8")
            builder.configure_cline(package)
            first = rule.read_bytes()
            builder.configure_cline(package)
            self.assertEqual(first, rule.read_bytes())
            self.assertEqual(rule.read_text(encoding="utf-8").count(builder.CLINE_BEGIN), 1)

    def test_local_all_registered_scope_is_exact(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            installations = []
            for name in ("one", "two"):
                plugin = root / name
                manifest = plugin / ".codex-plugin" / "plugin.json"
                manifest.parent.mkdir(parents=True)
                manifest.write_text(json.dumps({"name": controller.PLUGIN_NAME}), encoding="utf-8")
                installations.append({"path": str(plugin), "enabled": True})
            registry = root / "registry.json"
            registry.write_text(json.dumps({"installations": installations}), encoding="utf-8")
            args = argparse.Namespace(
                scope="LOCAL_ALL_REGISTERED_INSTALLATIONS", decision="Sí", session_id=None,
                plugin_root=None, registry=registry, repo=None, remote="origin", branch=None,
            )
            policy = controller.make_policy(args)
            self.assertEqual(len(policy.targets), 2)
            self.assertFalse(policy.upstream_write_allowed)

    def test_public_fork_accepts_only_verified_non_default_fork_branch(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            def fake(command, cwd=None):
                if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
                    return str(root)
                if command[:3] == ["git", "branch", "--show-current"]:
                    return "construct/live"
                if command[:3] == ["git", "remote", "get-url"]:
                    return "https://github.com/example-user/KCH.git"
                if command[:3] == ["gh", "repo", "view"]:
                    return json.dumps({
                        "nameWithOwner": "example-user/KCH",
                        "parent": {"nameWithOwner": controller.UPSTREAM},
                        "defaultBranchRef": {"name": "main"},
                    })
                raise AssertionError(command)
            original = controller.run
            controller.run = fake
            try:
                result = controller.public_fork(root, "origin", "construct/my-change")
                self.assertEqual(result["fork"], "example-user/KCH")
                with self.assertRaises(PermissionError):
                    controller.public_fork(root, "origin", "main")
            finally:
                controller.run = original

    def test_wrong_predecessor_digest_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            wrong = root / "wrong.zip"
            wrong.write_bytes(b"not the AIO2 release")
            with self.assertRaisesRegex(RuntimeError, "base digest mismatch"):
                builder.build(wrong, root / "out")


if __name__ == "__main__":
    unittest.main()