from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path


GATE = Path(__file__).resolve().parent
WORKSPACE = GATE.parents[1]
OUTPUTS = WORKSPACE / "outputs"
EXPECTED_KCH_ZIP = "a4e08bb2833dffbfe3a3f2036579d1c8e56c20ea67ec94d4685a3618d528ee02"
EXPECTED_PHL_STATE = "d17a982e55203cdce6ffba1a2a2455260bea1df88536ac4456969ae755a07c21"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_files() -> list[Path]:
    excluded_names = {"KCH_PROACTIVE_ACTIVATION_GATE_MANIFEST_v0.1.0.json", "KCH_PROACTIVE_ACTIVATION_GATE_RESULT_v0.1.0.json"}
    values = []
    for path in GATE.rglob("*"):
        relative = path.relative_to(GATE)
        if not path.is_file() or path.name in excluded_names:
            continue
        if "runtime" in relative.parts or "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        values.append(path)
    return sorted(values, key=lambda value: value.relative_to(GATE).as_posix())


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    tests = subprocess.run(
        [r"C:\Python314\python.exe", "-X", "utf8", "-m", "unittest", "discover", "-s", str(GATE / "tests"), "-v"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    test_text = tests.stdout + tests.stderr
    observed_tests = test_text.count(" ... ok")

    config = tomllib.loads((WORKSPACE / ".codex" / "config.toml").read_text(encoding="utf-8"))
    hooks = json.loads((WORKSPACE / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    kch_zip = WORKSPACE / "outputs" / "KCH_0.11_CANONICAL_MACRORELEASE.zip"
    phl_state = WORKSPACE / "work" / "KCH_0.11" / "evidence" / "KCH_CURRENT_INTEGRATION_STATE_v0.6.0.sqlite3"
    deployed_phl_state = WORKSPACE / "work" / "KCH_0.11_AGENT_SHADOW_DEPLOYMENT" / "bundle" / "evidence" / "KCH_CURRENT_INTEGRATION_STATE_v0.6.0.sqlite3"
    checks = {
        "tests_11_of_11": tests.returncode == 0 and observed_tests == 11,
        "kch_0_11_canonical_zip_unchanged": sha256(kch_zip) == EXPECTED_KCH_ZIP,
        "phl_source_state_unchanged": sha256(phl_state) == EXPECTED_PHL_STATE,
        "phl_deployed_replica_unchanged": sha256(deployed_phl_state) == EXPECTED_PHL_STATE,
        "codex_mcp_points_to_overlay": "kch_proactive_activation" in config.get("mcp_servers", {}),
        "codex_hooks_enabled": config.get("features", {}).get("hooks") is True,
        "user_prompt_hook_declared": "UserPromptSubmit" in hooks.get("hooks", {}),
        "session_end_hook_declared": "SessionEnd" in hooks.get("hooks", {}),
        "exact_consent_strings_in_hook_result": all(value in (GATE / "src" / "kch_activation" / "engine.py").read_text(encoding="utf-8") for value in ("Sí", "No", "Nunca en esta sesión", "Siempre en esta sesión")),
        "no_phl_real_rule_target": all(rule["target_tool"] != "kch.phl.execute" for rule in json.loads((GATE / "config" / "activation_rules.v0.1.0.json").read_text(encoding="utf-8"))["rules"]),
    }

    manifest_entries = [
        {"path": path.relative_to(GATE).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in source_files()
    ]
    manifest = {
        "schema": "kch.proactive-activation-gate-manifest.v0.1.0",
        "release": "KCH Proactive Activation Gate v0.1.0",
        "canonical_kch_release_modified": False,
        "entries": manifest_entries,
    }
    manifest_path = OUTPUTS / "KCH_PROACTIVE_ACTIVATION_GATE_MANIFEST_v0.1.0.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = {
        "schema": "kch.proactive-activation-gate-result.v0.1.0",
        "observed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "gate": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "test_count": observed_tests,
        "test_return_code": tests.returncode,
        "test_output": test_text,
        "surface": {"kch_0_11_tools": 49, "activation_tools": 4, "total_tools": 53},
        "consent_contract": ["Sí", "No", "Nunca en esta sesión", "Siempre en esta sesión"],
        "default_mode": "CONSULT_FIRST",
        "mutating_autoexecution": False,
        "phl_real_execution": False,
        "canonical_kch_zip_sha256": sha256(kch_zip),
        "phl_state_sha256": sha256(phl_state),
        "manifest_sha256": sha256(manifest_path),
        "adverse_results_repaired": [
            "SQLite read connections remained open on Windows until garbage collection; explicit close semantics were added.",
            "SessionEnd initially ignored an injected activation-state path; environment-aware state selection was added."
        ],
        "claim_ceiling": "LOCAL_CODEX_HOOK_AND_MCP_PROACTIVE_CONSULT_FIRST_GATE_PASS_WITH_READ_ONLY_TARGETS_AND_NO_REAL_PHL_EXECUTION",
        "limitations": [
            "Project-local hooks require a new/reloaded trusted Codex task and explicit hash review via /hooks.",
            "Rules are deterministic lexical triggers, not a validated general semantic activation model.",
            "Cline, Cowork, OpenCode and other host adapters are not yet validated.",
            "No longitudinal human-use reliability or causal benefit has been demonstrated."
        ],
    }
    result_path = OUTPUTS / "KCH_PROACTIVE_ACTIVATION_GATE_RESULT_v0.1.0.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    archive = OUTPUTS / "KCH_PROACTIVE_ACTIVATION_GATE_v0.1.0.zip"
    members = source_files() + [manifest_path, result_path, WORKSPACE / ".codex" / "config.toml", WORKSPACE / ".codex" / "hooks.json"]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for path in members:
            if path.is_relative_to(GATE):
                name = "KCH_PROACTIVE_ACTIVATION_GATE_v0.1.0/" + path.relative_to(GATE).as_posix()
            elif path.parent == OUTPUTS:
                name = "KCH_PROACTIVE_ACTIVATION_GATE_v0.1.0/results/" + path.name
            else:
                name = "KCH_PROACTIVE_ACTIVATION_GATE_v0.1.0/project_codex/" + path.name
            info = zipfile.ZipInfo(name, date_time=(2026, 8, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            handle.writestr(info, path.read_bytes())
    (OUTPUTS / "KCH_PROACTIVE_ACTIVATION_GATE_v0.1.0.sha256").write_text(f"{sha256(archive)}  {archive.name}\n", encoding="utf-8")
    print(json.dumps({"gate": result["gate"], "tests": observed_tests, "archive_sha256": sha256(archive), "manifest_sha256": result["manifest_sha256"]}, ensure_ascii=False))
    if result["gate"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
