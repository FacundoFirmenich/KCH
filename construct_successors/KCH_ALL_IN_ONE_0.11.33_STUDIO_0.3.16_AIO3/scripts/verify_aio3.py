from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


NAME = "KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO3"
PLUGIN_NAME = "kch-all-in-one-0-11-33"
PLUGIN_VERSION = "0.11.33-aio.3"
EXPECTED_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "SessionEnd"}
CLOSURE_HOOK = "kch_substantive_closure.py"
CLINE_BEGIN = "<!-- KCH-SUBSTANTIVE-CLOSURE-V1:BEGIN -->"
CLINE_END = "<!-- KCH-SUBSTANTIVE-CLOSURE-V1:END -->"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_digest(root: Path) -> dict[str, Any]:
    rows = []
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel = path.relative_to(root).as_posix()
        item_hash = sha256(path)
        size = path.stat().st_size
        rows.append((rel, size, item_hash))
        digest.update(rel.encode() + b"\0" + item_hash.encode() + b"\0" + str(size).encode() + b"\n")
    return {"files": len(rows), "bytes": sum(row[1] for row in rows), "tree_sha256": digest.hexdigest()}


def check(condition: bool, label: str, rows: list[dict[str, Any]], detail: Any = None) -> None:
    rows.append({"check": label, "pass": bool(condition), "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: {detail}")


def verify_manifest(package: Path, rows: list[dict[str, Any]]) -> None:
    manifest = json.loads((package / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    check(manifest["package"] == NAME, "manifest_package", rows, manifest["package"])
    expected = set()
    for entry in manifest["files"]:
        rel = entry["path"]
        expected.add(rel)
        path = package / Path(rel)
        check(path.is_file(), f"manifest_file:{rel}", rows)
        check(path.stat().st_size == entry["bytes"], f"manifest_size:{rel}", rows)
        check(sha256(path) == entry["sha256"], f"manifest_hash:{rel}", rows)
    actual = {path.relative_to(package).as_posix() for path in package.rglob("*") if path.is_file() and path.name != "PACKAGE_MANIFEST.json"}
    check(actual == expected, "manifest_exact_file_set", rows, {"missing": sorted(expected - actual), "extra": sorted(actual - expected)})


def run_hook(plugin: Path, event: str) -> dict[str, Any]:
    script = plugin / "scripts" / CLOSURE_HOOK
    completed = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(script)],
        input=json.dumps({"hook_event_name": event}),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr or completed.stdout)
    return json.loads(completed.stdout)


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_construct_controller(plugin: Path, rows: list[dict[str, Any]]) -> None:
    module = load_module(plugin / "scripts" / "kch_construct_persistence.py", "kch_construct_persistence_verify")
    with tempfile.TemporaryDirectory(prefix="kch-aio3-policy-") as raw:
        root = Path(raw)
        policy_path = root / "policy.json"
        args = argparse.Namespace(
            scope="LOCAL_CURRENT_INSTALLATION",
            decision="Sí",
            session_id=None,
            plugin_root=plugin,
            registry=None,
            repo=None,
            remote="origin",
            branch=None,
        )
        policy = module.make_policy(args)
        check(policy.upstream_write_allowed is False, "construct_upstream_hard_denial", rows)
        check(policy.targets == (str(plugin.resolve()),), "construct_current_installation_target", rows, policy.targets)
        module.atomic_write(policy_path, module.asdict(policy))
        allowed, reason = module.policy_allows(json.loads(policy_path.read_text(encoding="utf-8")), plugin, None)
        check(allowed, "construct_current_installation_allowed", rows, reason)
        allowed, reason = module.policy_allows(json.loads(policy_path.read_text(encoding="utf-8")), root / "elsewhere", None)
        check(not allowed, "construct_out_of_scope_denied", rows, reason)

        args.decision = "Siempre en esta sesión"
        args.session_id = "session-A"
        policy = module.make_policy(args)
        allowed, reason = module.policy_allows(module.asdict(policy), plugin, "session-B")
        check(not allowed, "construct_session_authority_not_transferred", rows, reason)

        official = {
            "git rev-parse": str(root),
            "git branch": "construct/example",
            "git remote": "https://github.com/FacundoFirmenich/KCH.git",
            "gh repo": json.dumps({"nameWithOwner": "FacundoFirmenich/KCH", "parent": None, "defaultBranchRef": {"name": "main"}}),
        }

        def fake_official(command: list[str], cwd: Path | None = None) -> str:
            joined = " ".join(command)
            if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
                return official["git rev-parse"]
            if command[:3] == ["git", "branch", "--show-current"]:
                return official["git branch"]
            if command[:3] == ["git", "remote", "get-url"]:
                return official["git remote"]
            if command[:3] == ["gh", "repo", "view"]:
                return official["gh repo"]
            raise AssertionError(joined)

        original_run = module.run
        module.run = fake_official
        try:
            try:
                module.public_fork(root, "origin", "construct/example")
            except PermissionError as exc:
                denied = "official upstream" in str(exc)
            else:
                denied = False
            check(denied, "construct_official_upstream_rejected", rows)
        finally:
            module.run = original_run


def verify_package(package: Path, rows: list[dict[str, Any]]) -> None:
    check(package.name == NAME, "package_name", rows, package.name)
    verify_manifest(package, rows)
    provenance = json.loads((package / "AIO3_PROVENANCE.json").read_text(encoding="utf-8"))
    current_lineage = tree_digest(package / "lineage")
    check(provenance["lineage_before"] == provenance["lineage_after"] == current_lineage, "immutable_r21_r33_lineage", rows, current_lineage)
    check(provenance["official_upstream_write_enabled"] is False, "provenance_upstream_write_denied", rows)

    plugin = package / "adapters" / "codex" / "marketplace" / "plugins" / PLUGIN_NAME
    manifest = json.loads((plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    check(manifest["version"] == PLUGIN_VERSION, "plugin_version", rows, manifest["version"])
    contracts = package / "contracts"
    for name in ("substantive_closure.v1.json", "construct_persistence.v1.json"):
        check(sha256(contracts / name) == sha256(plugin / "config" / name), f"contract_projection_exact:{name}", rows)

    hooks = json.loads((plugin / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    check(set(hooks) == EXPECTED_EVENTS, "codex_event_compatibility", rows, sorted(hooks))
    for event in ("SessionStart", "UserPromptSubmit"):
        commands = hooks[event][0]["hooks"]
        count = sum(CLOSURE_HOOK in str(item.get("command", "")) for item in commands)
        check(count == 1, f"closure_hook_once:{event}", rows, commands)
        output = run_hook(plugin, event)
        context = output["hookSpecificOutput"]["additionalContext"]
        check("uno o dos parrafos" in context, f"closure_context_paragraphs:{event}", rows)
        check("no prueba de validez cientifica" in context, f"closure_context_hash_ceiling:{event}", rows)
        check("No firmes" in context, f"closure_context_no_signature:{event}", rows)

    skill = (plugin / "skills" / "kch-native-governance" / "SKILL.md").read_text(encoding="utf-8")
    check("Universal substantive-closure contract" in skill, "chatgpt_portable_closure_skill", rows)
    construct_skill = (plugin / "skills" / "kch-csi-construct" / "SKILL.md").read_text(encoding="utf-8")
    check("PUBLIC_FORK_BRANCH" in construct_skill and "official KCH repository" in construct_skill, "portable_construct_scope_skill", rows)

    cline = (package / "adapters" / "cline-vscode" / "kch-all-in-one.md").read_text(encoding="utf-8")
    check(cline.count(CLINE_BEGIN) == cline.count(CLINE_END) == 1, "cline_contract_once", rows)
    check("PUBLIC_FORK_BRANCH" in cline and "uno o dos párrafos" in cline, "cline_contract_content", rows)
    installer = (package / "install_all_in_one.py").read_text(encoding="utf-8")
    check(f'NAME = "{NAME}"' in installer, "installer_aio3_name", rows)
    check('source_plugin / "config", native_stage / "config"' in installer, "cline_contract_config_propagated", rows)
    check(".kch-aio3-custody" in installer and ".kch-aio2-custody" in installer, "aio3_recovery_inherits_aio2", rows)
    rollback = (package / "rollback_all_in_one.py").read_text(encoding="utf-8")
    check('ACK = "KCH-AIO3-ROLLBACK"' in rollback, "aio3_rollback_ack", rows)
    verify_construct_controller(plugin, rows)


def verify_zip(path: Path, rows: list[dict[str, Any]]) -> None:
    check(path.is_file(), "zip_exists", rows, str(path))
    with zipfile.ZipFile(path) as archive:
        check(archive.testzip() is None, "zip_crc", rows)
        roots = {Path(name).parts[0] for name in archive.namelist() if Path(name).parts}
        check(roots == {NAME}, "zip_single_root", rows, sorted(roots))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify KCH AIO3 substantive closure and CONSTRUCT persistence")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows: list[dict[str, Any]] = []
    error: str | None = None
    try:
        verify_package(args.package_root.resolve(), rows)
        if args.zip:
            verify_zip(args.zip.resolve(), rows)
        status = "PASS"
    except Exception as exc:
        status = "FAIL"
        error = f"{type(exc).__name__}: {exc}"
    report = {
        "schema": "kch.aio3.validation.v1",
        "package": NAME,
        "status": status,
        "checks_passed": sum(1 for row in rows if row["pass"]),
        "checks_total": len(rows),
        "checks": rows,
        "error": error,
        "live_installation_performed": False,
        "host_activation_observed": False,
        "official_upstream_write_enabled": False,
        "automatic_promotion": False,
        "phl_training_executed": False,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temp = args.output.with_name(args.output.name + ".tmp")
        temp.write_text(rendered, encoding="utf-8", newline="\n")
        os.replace(temp, args.output)
    print(rendered, end="")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())