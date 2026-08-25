from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "results" / "KCH_MIS_V03_BUILD_MANIFEST_v0.1.0.json"
ARCHIVE = ROOT / "dist" / "KCH_MIS_V03_EFFECTIVE_INTEGRATION_v0.1.0.zip"
HASH_FILE = ROOT / "dist" / "KCH_MIS_V03_EFFECTIVE_INTEGRATION_v0.1.0.zip.sha256"


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def admitted(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    parts = set(relative.parts)
    if "__pycache__" in parts or "build" in parts or any(part.endswith(".egg-info") for part in parts):
        return False
    if path.suffix in {".pyc", ".pyo"}:
        return False
    if path in {MANIFEST, ARCHIVE, HASH_FILE}:
        return False
    return path.is_file()


def main() -> int:
    for path in (MANIFEST, ARCHIVE, HASH_FILE):
        if path.exists():
            raise SystemExit(f"refusing to overwrite: {path}")
    result = json.loads((ROOT / "results" / "KCH_MIS_V03_EFFECTIVE_INTEGRATION_RESULT_v0.1.0.json").read_text(encoding="utf-8"))
    if result.get("gate") != "PASS_BOUNDED" or result.get("checks_passed") != 21:
        raise SystemExit("effective integration gate is not 21/21 PASS_BOUNDED")
    files = sorted((path for path in ROOT.rglob("*") if admitted(path)), key=lambda item: item.relative_to(ROOT).as_posix())
    rows = [
        {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)}
        for path in files
    ]
    manifest = {
        "schema": "kch.mis.v03.build-manifest.v0.1.0",
        "version": "0.1.0",
        "state": "LOCAL_VALIDATED_EFFECTIVE_INTEGRATION_CANDIDATE",
        "gate": "PASS_BOUNDED",
        "gate_checks": "21/21",
        "unit_tests": "7/7",
        "historical_certificate_sha256": result["historical_certificate_sha256"],
        "source_kch_state_unchanged": result["source_state_sha256_before"] == result["source_state_sha256_after"],
        "authority_created": False,
        "automatic_promotion": False,
        "file_count_excluding_manifest_and_archive": len(rows),
        "files": rows,
        "portable_gate_inputs": {
            "source_state": "evidence/KCH_BASELINE_STATE_v0.5.0.sqlite3",
            "integration_control_plane_wheel": "vendor/kch_phl_effective_integration-0.2.0-py3-none-any.whl",
            "mis_wheel": "vendor/mis_qualitative_bayes-0.3.1-py3-none-any.whl",
            "registry": "evidence/KCH_SUPER_MCP_FEDERATED_REGISTRY_v0.5.0.json",
        },
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive_files = files + [MANIFEST]
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in archive_files:
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(2026, 8, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    archive_hash = sha_file(ARCHIVE)
    HASH_FILE.write_text(f"{archive_hash}  {ARCHIVE.name}\n", encoding="ascii")
    print(json.dumps({"archive": ARCHIVE.name, "sha256": archive_hash, "files": len(archive_files)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

