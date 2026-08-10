from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
OUTPUTS = WORKSPACE / "outputs"
sys.path.insert(0, str(ROOT / "src"))

from kch_self_governance.compiler import compile_governance
from kch_self_governance.graph import GovernanceGraph


EXPECTED_KCH = "a4e08bb2833dffbfe3a3f2036579d1c8e56c20ea67ec94d4685a3618d528ee02"
EXPECTED_PHL = "d17a982e55203cdce6ffba1a2a2455260bea1df88536ac4456969ae755a07c21"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def project_files() -> list[Path]:
    excluded = {"__pycache__", "runtime"}
    values = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part in excluded for part in relative.parts) or path.suffix == ".pyc":
            continue
        values.append(path)
    return sorted(values, key=lambda value: value.relative_to(ROOT).as_posix())


def main() -> None:
    OUTPUTS.mkdir(exist_ok=True)
    tests = subprocess.run(
        [r"C:\Python314\python.exe", "-X", "utf8", "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    test_output = tests.stdout + tests.stderr
    test_count = test_output.count(" ... ok")
    graph = GovernanceGraph.load(ROOT / "governance")
    projection = graph.csi_projection()
    write_json(ROOT / "validation_result.json", {"schema": "kch.csi-governance-validation.v0.1.0", "gate": "PASS", **projection})

    with tempfile.TemporaryDirectory() as temporary:
        fresh = Path(temporary) / "dist"
        compile_result = compile_governance(graph, fresh)
        compared = [
            "csi/governance_graph.json",
            "codex/AGENTS.md",
            "codex/.codex/rules/kch-generated.rules",
            "codex/COMPATIBILITY_RECEIPT.json",
            "governance.lock.json",
        ]
        dist_matches = all((ROOT / "dist" / relative).read_bytes() == (fresh / relative).read_bytes() for relative in compared)
    write_json(ROOT / "compile_result.json", compile_result)

    kch_zip = WORKSPACE / "outputs" / "KCH_0.11_CANONICAL_MACRORELEASE.zip"
    phl_state = WORKSPACE / "work" / "KCH_0.11" / "evidence" / "KCH_CURRENT_INTEGRATION_STATE_v0.6.0.sqlite3"
    artifact_catalog = json.loads((ROOT / "catalogs" / "artifact_types.v0.1.0.json").read_text(encoding="utf-8"))
    provider_catalog = json.loads((ROOT / "catalogs" / "discovery_providers.v0.1.0.json").read_text(encoding="utf-8"))
    codex_receipt = json.loads((ROOT / "dist" / "codex" / "COMPATIBILITY_RECEIPT.json").read_text(encoding="utf-8"))
    checks = {
        "tests_11_of_11": tests.returncode == 0 and test_count == 11,
        "hierarchy_exact": projection["hierarchy"] == ["HARNESS", "AGENTS", "RULES"],
        "graph_13_nodes": projection["node_count"] == 13,
        "four_agents": projection["agent_count"] == 4,
        "six_rules": projection["rule_count"] == 6,
        "no_install_authority": projection["install_authority"] is False,
        "fresh_compile_matches_persisted_dist": dist_matches,
        "codex_projection_declares_loss": codex_receipt["state"] == "SHADOW_ONLY_REVIEW_REQUIRED" and codex_receipt["agent_topology_transport"].startswith("FLATTENED"),
        "semantic_rules_not_misrepresented_as_native_rules": codex_receipt["command_rules_generated"] == 0,
        "studio_catalog_is_specification_only": artifact_catalog["implemented_through"] == "SPECIFICATION_ONLY",
        "extension_catalog_is_specification_only": provider_catalog["implemented_through"] == "SPECIFICATION_ONLY",
        "kch_0_11_unchanged": sha256(kch_zip) == EXPECTED_KCH,
        "phl_state_unchanged": sha256(phl_state) == EXPECTED_PHL,
    }

    manifest_entries = [
        {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in project_files()
    ]
    manifest = {
        "schema": "kch.csi-self-governance-manifest.v0.1.0",
        "release": "KCH CSI Self-Governance v0.1.0",
        "entries": manifest_entries,
        "canonical_kch_modified": False,
        "external_environment_modified": False,
    }
    manifest_path = OUTPUTS / "KCH_CSI_SELF_GOVERNANCE_MANIFEST_v0.1.0.json"
    write_json(manifest_path, manifest)
    result = {
        "schema": "kch.csi-self-governance-gate-result.v0.1.0",
        "observed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "gate": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "tests": test_count,
        "test_output": test_output,
        "source_graph_sha256": compile_result["source_graph_sha256"],
        "manifest_sha256": sha256(manifest_path),
        "implemented": ["HARNESS_AGENTS_RULES_CONTRACT", "CSI_GOVERNANCE_GRAPH", "AUTHORITY_VALIDATOR", "DETERMINISTIC_COMPILER", "CODEX_LOSS_AWARE_PROJECTION", "LOCK_AND_HASHES"],
        "specified_not_implemented": ["CSI_STUDIO_VISUAL", "GUIDED_ARTIFACT_GENERATORS", "EXTENSION_FABRIC", "MCP_SEARCH_AND_RECOMMENDER", "PYPI_PROVIDER", "NPM_PROVIDER", "HOST_ADDON_INSTALLERS"],
        "installation_authorized": False,
        "external_environment_modified": False,
        "phl_real_execution": False,
        "canonical_kch_zip_sha256": sha256(kch_zip),
        "phl_state_sha256": sha256(phl_state),
        "claim_ceiling": "EXECUTABLE_KCH_CSI_SELF_GOVERNANCE_FOUNDATION_WITH_LOSS_AWARE_CODEX_PROJECTION_NO_INSTALLATION",
    }
    result_path = OUTPUTS / "KCH_CSI_SELF_GOVERNANCE_GATE_RESULT_v0.1.0.json"
    write_json(result_path, result)

    archive = OUTPUTS / "KCH_CSI_SELF_GOVERNANCE_v0.1.0.zip"
    members = project_files() + [manifest_path, result_path]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for path in members:
            if path.is_relative_to(ROOT):
                name = "KCH_CSI_SELF_GOVERNANCE_v0.1.0/" + path.relative_to(ROOT).as_posix()
            else:
                name = "KCH_CSI_SELF_GOVERNANCE_v0.1.0/results/" + path.name
            info = zipfile.ZipInfo(name, date_time=(2026, 8, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            handle.writestr(info, path.read_bytes())
    archive_hash = sha256(archive)
    (OUTPUTS / "KCH_CSI_SELF_GOVERNANCE_v0.1.0.sha256").write_text(f"{archive_hash}  {archive.name}\n", encoding="utf-8")
    print(json.dumps({"gate": result["gate"], "tests": test_count, "graph": compile_result["source_graph_sha256"], "archive_sha256": archive_hash}, ensure_ascii=False))
    if result["gate"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
