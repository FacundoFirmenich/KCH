from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[3]
DEPLOYMENT = PROJECT / "work" / "KCH_0.11_AGENT_SHADOW_DEPLOYMENT"
STAGE = PROJECT / "work" / "KCH_0.11_AGENT_SHADOW_EVIDENCE_PACKAGE_v0.1.0"
OUTPUT = PROJECT / "outputs" / "KCH_0.11_AGENT_SHADOW_EVIDENCE_PACKAGE_v0.1.0.zip"
SEAL = PROJECT / "outputs" / "KCH_0.11_AGENT_SHADOW_EVIDENCE_PACKAGE_SEAL_v0.1.0.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if STAGE.exists() or OUTPUT.exists() or SEAL.exists():
        raise SystemExit("Evidence package target already exists; refusing to overwrite")

    fixed = {
        PROJECT / "outputs" / "KCH_0.11_CANONICAL_MACRORELEASE.zip": Path("canonical/KCH_0.11_CANONICAL_MACRORELEASE.zip"),
        PROJECT / "outputs" / "CHECKPOINT_07_KCH_0.11_DESPLIEGUE_REAL_AGENT_SHADOW_SIN_PHL_20260809.md": Path("checkpoint/CHECKPOINT_07_KCH_0.11_DESPLIEGUE_REAL_AGENT_SHADOW_SIN_PHL_20260809.md"),
        PROJECT / ".codex" / "config.toml": Path("deployment/project_config.toml"),
        DEPLOYMENT / "run_kch_011.py": Path("deployment/run_kch_011.py"),
        DEPLOYMENT / "OBJECTIVE_CONTRACT_KCH_0.11_REAL_SHADOW_DEPLOYMENT_v0.1.0.json": Path("deployment/OBJECTIVE_CONTRACT_KCH_0.11_REAL_SHADOW_DEPLOYMENT_v0.1.0.json"),
        DEPLOYMENT / "PHL_REAL_SESSION_FREEZE_v0.1.0.json": Path("deployment/PHL_REAL_SESSION_FREEZE_v0.1.0.json"),
        DEPLOYMENT / "scripts" / "run_real_shadow_gate.py": Path("deployment/run_real_shadow_gate.py"),
        DEPLOYMENT / "runtime" / "state" / "kch_011_agent_shadow.sqlite3": Path("deployment/kch_011_agent_shadow.sqlite3"),
    }
    for source in sorted((DEPLOYMENT / "results").iterdir()):
        if source.is_file():
            fixed[source] = Path("results") / source.name

    missing = [str(source) for source in fixed if not source.is_file()]
    if missing:
        raise SystemExit("Missing evidence inputs: " + ", ".join(missing))

    STAGE.mkdir(parents=True)
    rows = []
    for source, relative in sorted(fixed.items(), key=lambda item: item[1].as_posix()):
        target = STAGE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        rows.append(
            {
                "path": relative.as_posix(),
                "sha256": sha256(target),
                "size": target.stat().st_size,
                "source": str(source),
            }
        )

    manifest = {
        "schema": "kch.agent-shadow-evidence-package-manifest.v0.1.0",
        "release": "KCH 0.11",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "file_count_excluding_manifest": len(rows),
        "files": rows,
        "phl_real_session": "NOT_RUN_DEFERRED_BY_USER",
        "claim_ceiling": "REAL_LOCAL_PROJECT_SCOPED_MCP_DEPLOYMENT_AND_BOUNDED_AGENT_SHADOW_EXECUTION_WITHOUT_PHL_REAL_USE",
    }
    manifest_path = STAGE / "MANIFEST_SHA256_v0.1.0.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in STAGE.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(STAGE).as_posix())

    with tempfile.TemporaryDirectory() as directory:
        extracted = Path(directory)
        with zipfile.ZipFile(OUTPUT) as archive:
            archive.extractall(extracted)
        extracted_manifest = json.loads((extracted / "MANIFEST_SHA256_v0.1.0.json").read_text(encoding="utf-8"))
        failures = []
        for row in extracted_manifest["files"]:
            path = extracted / row["path"]
            if not path.is_file() or sha256(path) != row["sha256"] or path.stat().st_size != row["size"]:
                failures.append(row["path"])

    seal = {
        "schema": "kch.agent-shadow-evidence-package-seal.v0.1.0",
        "release": "KCH 0.11",
        "archive": OUTPUT.name,
        "archive_sha256": sha256(OUTPUT),
        "manifest_sha256": sha256(manifest_path),
        "verified_files": len(rows),
        "failures": failures,
        "reextraction_gate": "PASS" if not failures else "FAIL",
        "phl_real_session": "NOT_RUN_DEFERRED_BY_USER",
    }
    SEAL.write_text(json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTPUT.with_suffix(OUTPUT.suffix + ".sha256").write_text(f"{seal['archive_sha256']}  {OUTPUT.name}\n", encoding="ascii")
    print(json.dumps({"gate": seal["reextraction_gate"], "files": len(rows), "archive_sha256": seal["archive_sha256"]}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
