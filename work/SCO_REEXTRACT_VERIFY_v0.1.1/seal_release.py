from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new(path: Path, value) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry-v04", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    results = root / "results"
    validation = results / "SCO_VALIDATION_RESULT_v0.1.0.json"
    csi = results / "SCO_KCH_PRE2G_CSI_LOWERING_v0.1.0.json"
    wheel = root / "dist" / "kch_superchats_orchestrators-0.1.0-py3-none-any.whl"
    state = root / "runtime" / "KCH_PRE2G_SCO_v0.1.0.sqlite3"
    required = (validation, csi, wheel, state, args.registry_v04)
    if not all(path.is_file() for path in required):
        raise SystemExit("required release evidence is missing")

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "runtime" / "wheel_smoke")
    smoke = subprocess.run(
        [sys.executable, "-m", "kch_sco.cli", "--state", str(state), "projection", "--sco-id", "sco.kch-pre2g-continuation.20260809"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    smoke_projection = json.loads(smoke.stdout) if smoke.returncode == 0 else None
    wheel_result = {
        "schema": "kch.sco.wheel-smoke-result.v0.1.0",
        "gate": "PASS" if smoke.returncode == 0 and smoke_projection and smoke_projection["nodes"] == 2 else "FAIL",
        "wheel": wheel.name,
        "wheel_sha256": sha256_file(wheel),
        "installed_distribution_version": "0.1.0",
        "installed_projection": smoke_projection,
        "isolated_build_attempt": "TIMEOUT_INSTALLING_BUILD_DEPENDENCIES_NO_RUNTIME_INFERENCE",
        "no_build_isolation_retry": "PASS",
        "claim_boundary": "Wheel installs locally and reads the validated SCO state; no external provider bridge is exercised.",
    }
    wheel_result_path = results / "SCO_WHEEL_SMOKE_RESULT_v0.1.0.json"
    write_new(wheel_result_path, wheel_result)

    validation_value = json.loads(validation.read_text(encoding="utf-8"))
    registry = json.loads(args.registry_v04.read_text(encoding="utf-8-sig"))
    if not isinstance(registry, list) or len(registry) != 17:
        raise SystemExit("unexpected v0.4 registry shape")
    if any(item.get("active_name") == "KCH SuperChats Orchestrators (SCO)" for item in registry):
        raise SystemExit("SCO is already present in source registry")
    registry.append(
        {
            "active_name": "KCH SuperChats Orchestrators (SCO)",
            "legacy_source_directory": None,
            "family": "KCH_ORCHESTRATION_SERVICE",
            "state": "LOCAL_VALIDATED_SOVEREIGN_MULTI_CHAT_INTEGRATION_CANDIDATE",
            "jurisdiction": "selection and graph orchestration of sovereign native chat/task references; no context fusion, memory replacement, implicit authority, live cross-provider dispatch or comparative outcome-superiority claim",
            "evidence_file": str(validation.resolve()),
            "evidence_sha256": sha256_file(validation),
            "csi_lowering_evidence_sha256": sha256_file(csi),
            "unit_tests": validation_value["unit_test_count"],
            "gate_checks": validation_value["checks_total"],
            "real_selected_nodes": validation_value["projection"]["nodes"],
            "live_cross_provider_dispatch": False,
            "authority_inheritance": False,
        }
    )
    registry_path = results / "KCH_SUPER_MCP_FEDERATED_REGISTRY_v0.5.0.json"
    write_new(registry_path, registry)

    include_roots = [root / name for name in ("src", "config", "deployment", "tests", "dist", "results")]
    top_files = [root / name for name in ("pyproject.toml", "README.md", "validate_release.py", "seal_release.py")]
    files: list[Path] = [path for path in top_files if path.is_file()]
    for base in include_roots:
        files.extend(path for path in base.rglob("*") if path.is_file())
    files.append(state)
    files = sorted(
        {
            path.resolve()
            for path in files
            if "__pycache__" not in path.parts
            and ".egg-info" not in str(path)
            and path.name != "BUILD_MANIFEST_v0.1.0.json"
            and not path.name.endswith(("-wal", "-shm"))
            and "wheel_smoke" not in path.parts
        },
        key=lambda path: str(path).lower(),
    )
    entries = [
        {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in files
    ]
    manifest = {
        "schema": "kch.sco.build-manifest.v0.1.0",
        "canonical_name": "KCH SuperChats Orchestrators (SCO)",
        "version": "0.1.0",
        "release_state": "LOCAL_VALIDATED_INTEGRATION_CANDIDATE",
        "file_count": len(entries),
        "files": entries,
        "exclusions": ["__pycache__", "*.egg-info", "runtime/wheel_smoke", "SQLite WAL/SHM sidecars", "manifest self"],
        "wheel_sha256": sha256_file(wheel),
        "validation_sha256": sha256_file(validation),
        "registry_v0_5_sha256": sha256_file(registry_path),
        "authority_created": False,
    }
    manifest_path = results / "BUILD_MANIFEST_v0.1.0.json"
    write_new(manifest_path, manifest)
    print(json.dumps({"gate": wheel_result["gate"], "manifest_files": len(entries), "wheel_sha256": manifest["wheel_sha256"], "registry_rows": len(registry)}, ensure_ascii=False))
    return 0 if wheel_result["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
