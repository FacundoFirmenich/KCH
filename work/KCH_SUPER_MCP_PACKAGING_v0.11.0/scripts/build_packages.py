from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any


PACKAGING = Path(__file__).resolve().parents[1]
PROJECT = Path(__file__).resolve().parents[3]
OUTPUTS = PROJECT / "outputs"
BUILD_ROOT = PROJECT.parents[1]
BUILD = BUILD_ROOT / "_kchsmcp011b"
CANONICAL_ZIP = OUTPUTS / "KCH_0.11_CANONICAL_MACRORELEASE.zip"
CANONICAL_SHA256 = "a4e08bb2833dffbfe3a3f2036579d1c8e56c20ea67ec94d4685a3618d528ee02"
DOC_NAME = "KCH_SUPER_MCP_DOCUMENTACION_Y_USO_v0.11.0"
RUNTIME_NAME = "KCH_SUPER_MCP_COMPLETO_PORTABLE_v0.11.0"
FIXED_ZIP_TIME = (2026, 8, 10, 0, 0, 0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_under(path: Path, parent: Path) -> None:
    path.resolve().relative_to(parent.resolve())


def reset_build() -> None:
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    ensure_under(BUILD, BUILD_ROOT)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)


def copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def payload_files(root: Path) -> list[Path]:
    excluded = {"MANIFEST_SHA256.json", "PACKAGE_SEAL.json"}
    return [
        path for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in excluded and "__pycache__" not in path.parts
    ]


def write_manifest(root: Path, package_type: str) -> dict[str, Any]:
    rows = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in payload_files(root)
    ]
    manifest = {
        "schema": "kch.super-mcp-package-manifest.v0.11.0",
        "release": "KCH 0.11",
        "package_type": package_type,
        "hash_algorithm": "SHA-256",
        "exclusions": ["MANIFEST_SHA256.json", "PACKAGE_SEAL.json"],
        "file_count": len(rows),
        "files": rows,
    }
    path = root / "MANIFEST_SHA256.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    seal = {
        "schema": "kch.super-mcp-package-seal.v0.11.0",
        "release": "KCH 0.11",
        "package_type": package_type,
        "manifest_sha256": sha256_file(path),
        "payload_file_count": len(rows),
        "canonical_kch_0_11_zip_sha256": CANONICAL_SHA256,
        "phl_real_session": "NOT_RUN",
    }
    (root / "PACKAGE_SEAL.json").write_text(json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return seal


def zip_deterministic(root: Path, destination: Path) -> None:
    if destination.exists():
        destination.unlink()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            arcname = (Path(root.name) / path.relative_to(root)).as_posix()
            info = zipfile.ZipInfo(arcname, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.suffix in {".sh", ".py"} else 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def verify_extracted_manifest(root: Path) -> dict[str, Any]:
    manifest = json.loads((root / "MANIFEST_SHA256.json").read_text(encoding="utf-8"))
    failures = []
    for row in manifest["files"]:
        path = root / row["path"]
        if not path.is_file():
            failures.append({"path": row["path"], "reason": "MISSING"})
        elif path.stat().st_size != row["bytes"]:
            failures.append({"path": row["path"], "reason": "SIZE"})
        elif sha256_file(path) != row["sha256"]:
            failures.append({"path": row["path"], "reason": "SHA256"})
    return {"gate": "PASS" if not failures else "FAIL", "checked": len(manifest["files"]), "failures": failures}


def reextract_and_verify(zip_path: Path, expected_root: str) -> dict[str, Any]:
    target = BUILD / ("xr" if "COMPLETO" in expected_root else "xd")
    target.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(target)
    root = target / expected_root
    result = verify_extracted_manifest(root)
    result["root"] = str(root)
    return result


def main() -> int:
    if sha256_file(CANONICAL_ZIP) != CANONICAL_SHA256:
        raise SystemExit("canonical KCH 0.11 ZIP hash mismatch")
    reset_build()
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    docs = BUILD / DOC_NAME
    runtime = BUILD / RUNTIME_NAME
    copy_tree(PACKAGING / "docs_source", docs)
    copy_tree(PACKAGING / "runtime_source" / "config_templates", docs / "templates")

    copy_tree(PACKAGING / "runtime_source", runtime)
    copy_tree(PACKAGING / "docs_source", runtime / "docs" / "full")
    copy_tree(PACKAGING / "runtime_source" / "config_templates", runtime / "docs" / "full" / "templates")

    bundle = runtime / "bundle"
    bundle.mkdir(parents=True)
    with zipfile.ZipFile(CANONICAL_ZIP) as archive:
        archive.extractall(bundle)
    (runtime / "canonical").mkdir(parents=True)
    shutil.copy2(CANONICAL_ZIP, runtime / "canonical" / CANONICAL_ZIP.name)
    shutil.copy2(OUTPUTS / "KCH_0.11_CANONICAL_MACRORELEASE.sha256", runtime / "canonical" / "KCH_0.11_CANONICAL_MACRORELEASE.sha256")

    validation = runtime / "validation_evidence"
    validation.mkdir(parents=True)
    validation_sources = [
        OUTPUTS / "CHECKPOINT_06_KCH_0.11_MACRORELEASE_CANONICA_20260809.md",
        OUTPUTS / "CHECKPOINT_07_KCH_0.11_DESPLIEGUE_REAL_AGENT_SHADOW_SIN_PHL_20260809.md",
        PROJECT / "work" / "KCH_0.11_AGENT_SHADOW_DEPLOYMENT" / "results" / "KCH_0.11_REAL_SHADOW_DEPLOYMENT_GATE_RESULT.json",
        PROJECT / "work" / "KCH_0.11_AGENT_SHADOW_DEPLOYMENT" / "results" / "CODEX_HOST_TRANSPORT_RECEIPT_v0.3.0.json",
        PROJECT / "work" / "KCH_0.11_AGENT_SHADOW_DEPLOYMENT" / "results" / "KCH_0.11_INSTALLED_POST_DEPLOYMENT_VALIDATION.json",
    ]
    for source in validation_sources:
        if not source.is_file():
            raise SystemExit(f"required validation evidence unavailable: {source}")
        shutil.copy2(source, validation / source.name)

    doc_seal = write_manifest(docs, "EXPLANATORY_AND_INSTRUCTIONAL")
    runtime_seal = write_manifest(runtime, "COMPLETE_PORTABLE_RUNTIME")
    doc_zip = OUTPUTS / f"{DOC_NAME}.zip"
    runtime_zip = OUTPUTS / f"{RUNTIME_NAME}.zip"
    zip_deterministic(docs, doc_zip)
    zip_deterministic(runtime, runtime_zip)

    verifications = {
        "documentation": reextract_and_verify(doc_zip, DOC_NAME),
        "runtime": reextract_and_verify(runtime_zip, RUNTIME_NAME),
    }
    gate = "PASS" if all(row["gate"] == "PASS" for row in verifications.values()) else "FAIL"
    package_rows = []
    for package_type, path, seal in (
        ("documentation", doc_zip, doc_seal),
        ("runtime", runtime_zip, runtime_seal),
    ):
        digest = sha256_file(path)
        (OUTPUTS / f"{path.name}.sha256").write_text(f"{digest}  {path.name}\n", encoding="ascii")
        external_seal = {
            **seal,
            "archive_name": path.name,
            "archive_bytes": path.stat().st_size,
            "archive_sha256": digest,
            "reextracted_manifest_gate": verifications[package_type]["gate"],
        }
        seal_path = OUTPUTS / f"{path.stem}_SEAL_v0.11.0.json"
        seal_path.write_text(json.dumps(external_seal, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        package_rows.append({"type": package_type, "path": str(path), "bytes": path.stat().st_size, "sha256": digest, "seal": str(seal_path)})

    result = {
        "schema": "kch.super-mcp-two-package-build-result.v0.11.0",
        "release": "KCH 0.11",
        "gate": gate,
        "canonical_zip_sha256": CANONICAL_SHA256,
        "packages": package_rows,
        "reextraction": verifications,
        "phl_real_session": "NOT_RUN",
    }
    result_path = OUTPUTS / "KCH_SUPER_MCP_TWO_PACKAGE_BUILD_RESULT_v0.11.0.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate": gate, "packages": package_rows, "result": str(result_path)}, ensure_ascii=False))
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
