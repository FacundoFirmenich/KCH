from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


NAME = "KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2"
PLUGIN_NAME = "kch-all-in-one-0-11-33"
CLINE_HOOKS = {
    "TaskStart",
    "TaskResume",
    "TaskCancel",
    "TaskComplete",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PreCompact",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check(condition: bool, label: str, rows: list[dict[str, Any]], detail: Any = None) -> None:
    rows.append({"check": label, "pass": bool(condition), "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: {detail}")


def verify_manifest(package: Path, rows: list[dict[str, Any]]) -> None:
    manifest_path = package / "PACKAGE_MANIFEST.json"
    check(manifest_path.is_file(), "manifest_exists", rows, str(manifest_path))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("files", [])
    check(isinstance(entries, list) and entries, "manifest_entries_nonempty", rows, len(entries))
    expected = set()
    for entry in entries:
        rel = entry["path"]
        expected.add(rel)
        path = package / Path(rel)
        check(path.is_file(), f"manifest_file:{rel}", rows)
        check(path.stat().st_size == entry["bytes"], f"manifest_size:{rel}", rows)
        check(sha256(path) == entry["sha256"], f"manifest_hash:{rel}", rows)
    actual = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file() and path.name != "PACKAGE_MANIFEST.json"
    }
    check(actual == expected, "manifest_exact_file_set", rows, {"missing": sorted(expected - actual), "extra": sorted(actual - expected)})


def verify_structure(package: Path, rows: list[dict[str, Any]]) -> None:
    for lineage in ("kch-native-r21-0.11.33", "kch-native-r33-0.11.33"):
        check((package / "lineage" / lineage / ".codex-plugin" / "plugin.json").is_file(), f"lineage:{lineage}", rows)
    plugin = package / "adapters" / "codex" / "marketplace" / "plugins" / PLUGIN_NAME
    manifest = json.loads((plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    check(manifest["name"] == PLUGIN_NAME, "codex_plugin_name", rows, manifest["name"])
    check(manifest["version"] == "0.11.33-aio.2", "codex_plugin_version", rows, manifest["version"])
    hooks = json.loads((plugin / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    events = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "SessionEnd"}
    check(set(hooks) == events, "single_codex_hook_lifecycle", rows, sorted(hooks))
    skills = [path for path in (plugin / "skills").iterdir() if path.is_dir() and (path / "SKILL.md").is_file()]
    check(len(skills) == 20, "r33_skills_19_plus_rigor_fader", rows, sorted(path.name for path in skills))
    runtime = plugin / "runtime"
    modules = {
        "kwandisk": runtime / "kwandisk",
        "tokenmaster": runtime / "tokenmaster",
        "mis031_full_csi": runtime / "kch_mis031_full_csi",
        "mu_transmuter_scpp": runtime / "kch_mu_transmuter_scpp",
        "virtuous_handoff": runtime / "kch_virtuous_handoff",
    }
    for name, path in modules.items():
        check(path.is_dir(), f"runtime:{name}", rows, str(path))
    mcp = json.loads((plugin / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    check(set(mcp) == {"kch-codex-preflight", "kch-codex-bootstrap"}, "codex_mcp_two_stage", rows, sorted(mcp))
    cline = package / "adapters" / "cline-vscode"
    check((cline / "kch-all-in-one.md").is_file(), "cline_rule", rows)
    check((cline / "README_CLINE_ES.md").is_file(), "cline_readme_es", rows)
    check((cline / "hooks" / "kch_cline_hook_bridge.py").is_file(), "cline_hook_bridge", rows)
    check((cline / "hooks" / "kch-cline-hook.ps1.template").is_file(), "cline_hook_ps1_template", rows)
    installer_text = (package / "install_all_in_one.py").read_text(encoding="utf-8")
    check("DEFERRED_HOST_UNSUPPORTED_ON_WINDOWS" not in installer_text, "cline_no_obsolete_windows_defer", rows)
    check(all(f'"{event}"' in installer_text for event in CLINE_HOOKS), "cline_eight_hook_events", rows, sorted(CLINE_HOOKS))
    check(
        'plugin_target = marketplace_path.parent / "plugins" / PLUGIN_NAME' in installer_text,
        "codex_marketplace_target_is_relative_to_manifest",
        rows,
    )
    check(
        "marketplace_path.parent.parent.parent" not in installer_text,
        "codex_marketplace_no_legacy_parent_escape",
        rows,
    )
    check(
        (package / "validation" / "verify_marketplace_projection.py").is_file(),
        "codex_marketplace_projection_gate_packaged",
        rows,
    )
    check(
        (plugin / "skills" / "kch-contractual-rigor-fader" / "SKILL.md").is_file(),
        "contractual_rigor_fader_skill",
        rows,
    )
    check(
        (plugin / "scripts" / "kch_contractual_rigor.py").is_file(),
        "contractual_rigor_fader_runtime",
        rows,
    )
    for event in ("SessionStart", "UserPromptSubmit"):
        commands = hooks[event][0]["hooks"]
        check(
            sum("kch_contractual_rigor.py" in str(item.get("command", "")) for item in commands) == 1,
            f"contractual_rigor_fader_hook:{event}",
            rows,
            commands,
        )
    wheel_names = {path.name.lower() for path in (package / "wheelhouse").glob("*.whl")}
    for prefix in (
        "kwancode_harness-0.11.0",
        "kch_csi_studio_extension_fabric-0.3.16",
        "kch_virtuous_handoff-0.2.2",
        "kch_mis_v03_integration-0.1.0",
        "mis_qualitative_bayes-0.3.1",
    ):
        check(any(name.startswith(prefix) for name in wheel_names), f"wheel:{prefix}", rows, sorted(wheel_names))
    bad_paths = [path.relative_to(package).as_posix() for path in package.rglob("*") if "r34" in path.name.lower()]
    check(not bad_paths, "no_r34_path", rows, bad_paths)


def verify_zip(path: Path, rows: list[dict[str, Any]]) -> None:
    check(path.is_file(), "zip_exists", rows, str(path))
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        check(bad is None, "zip_crc", rows, bad)
def verify_fader(plugin: Path, rows: list[dict[str, Any]]) -> None:
    scripts = plugin / "scripts"
    code = (
        "import json,sys;"
        "sys.path.insert(0,sys.argv[1]);"
        "import kch_contractual_rigor as rigor;"
        "from kch_native_state import connect;"
        "db=connect();"
        "print(json.dumps(rigor.resolve(db,sys.argv[2]),sort_keys=True));"
        "db.close()"
    )
    with tempfile.TemporaryDirectory(prefix="kch-aio2-rigor-") as raw:
        env = dict(os.environ)
        env["KCH_NATIVE_DATA"] = raw
        env["PYTHONPATH"] = str(scripts)

        def resolve(prompt: str) -> dict[str, Any]:
            run = subprocess.run(
                [sys.executable, "-B", "-X", "utf8", "-c", code, str(scripts), prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            check(run.returncode == 0, f"rigor_resolve:{prompt[:12]}", rows, run.stderr or run.stdout)
            return json.loads(run.stdout)

        exploratory = resolve("brainstorm audaz para construct")
        strict = resolve("audita evidencia y congela release de produccion")
        check(exploratory["intensity"] < strict["intensity"], "rigor_adaptive_order", rows, [exploratory["intensity"], strict["intensity"]])
        check(
            all(exploratory["fields"][name]["effective"] == 100 for name in exploratory["non_relaxable"]),
            "rigor_non_relaxable_floors",
            rows,
            exploratory["non_relaxable"],
        )

        admin = scripts / "kch_rigor_admin.py"
        changed = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(admin), "set-field", "evidence_truth", "0"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        check(changed.returncode == 0, "rigor_admin_set_field", rows, changed.stderr or changed.stdout)
        profile = json.loads(changed.stdout)
        check(profile["fields"]["evidence_truth"]["requested"] == 0, "rigor_requested_relaxation_recorded", rows)
        check(profile["fields"]["evidence_truth"]["effective"] == 100, "rigor_hard_floor_enforced", rows)




def verify_runtime(runtime_root: Path, rows: list[dict[str, Any]]) -> None:
    py = runtime_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    check(py.is_file(), "runtime_python", rows, str(py))
    code = (
        "import importlib,json;"
        "mods=['kwancode_harness','kch_studio','kch_virtuous_handoff','kch_mis_v03_integration',"
        "'kch_phl_integration','kch_learning','kch_sco',"
        "'kch_rigor_governor','kwanprompts','mis_v03'];"
        "print(json.dumps({m:bool(importlib.import_module(m)) for m in mods},sort_keys=True))"
    )
    env = dict(os.environ)
    check(run.returncode == 0, "runtime_imports", rows, run.stderr or run.stdout)
    expected = ["kch-codex-preflight-mcp", "kch-codex-bootstrap-mcp", "kch-super-mcp-studio"]
    bindir = runtime_root / ("Scripts" if os.name == "nt" else "bin")
    for name in expected:
        found = any((bindir / candidate).is_file() for candidate in (name, f"{name}.exe", f"{name}.cmd"))
        check(found, f"runtime_command:{name}", rows, str(bindir))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=Path(__file__).absolute().parent)
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    package = args.package_root.absolute()
    rows: list[dict[str, Any]] = []
    try:
        check(package.name == NAME, "package_name", rows, package.name)
        verify_manifest(package, rows)
        verify_fader(package / "adapters" / "codex" / "marketplace" / "plugins" / PLUGIN_NAME, rows)
        verify_structure(package, rows)
        if args.zip:
            verify_zip(args.zip.absolute(), rows)
        if args.runtime_root:
            verify_runtime(args.runtime_root.absolute(), rows)
        status = "PASS"
        error = None
    except Exception as exc:
        status = "FAIL"
        error = f"{type(exc).__name__}: {exc}"
    report = {
        "schema": "kch.aio.validation.v1",
        "package": NAME,
        "status": status,
        "checks_passed": sum(1 for row in rows if row["pass"]),
        "checks_total": len(rows),
        "checks": rows,
        "error": error,
        "authority_created": False,
        "phl_training_executed": False,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temp = args.output.with_name(args.output.name + ".tmp")
        temp.write_text(rendered, encoding="utf-8")
        os.replace(temp, args.output)
    print(rendered, end="")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
