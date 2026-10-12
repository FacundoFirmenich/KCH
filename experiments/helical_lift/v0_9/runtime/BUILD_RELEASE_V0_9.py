from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import zipfile
from typing import Any

from common_v09 import canonical_json_bytes, content_id, sha256_file, write_json_atomic


def included_files(root: Path, *, include_manifest: bool) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if "__pycache__" in rel.parts or path.suffix == ".pyc":
            continue
        if not include_manifest and rel.parts and rel.parts[0] == "manifest":
            continue
        files.append(path)
    return files


def entry(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def deterministic_zip(root: Path, destination: Path) -> list[dict[str, Any]]:
    files = included_files(root, include_manifest=True)
    members: list[dict[str, Any]] = []
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            rel = f"{root.name}/{path.relative_to(root).as_posix()}"
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            executable = path.suffix == ".sh"
            mode = 0o755 if executable else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits |= 0x800
            with path.open("rb") as source, archive.open(info, "w", force_zip64=True) as target:
                for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    target.write(block)
            members.append({"name": rel, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return members


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--zip", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    destination = args.zip.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    (root / "manifest").mkdir(parents=True, exist_ok=True)

    for cache in root.rglob("__pycache__"):
        if cache.is_dir():
            import shutil
            shutil.rmtree(cache)
    for artifact in (root / "manifest").glob("*"):
        if artifact.is_file():
            artifact.unlink()

    validation = json.loads((root / "receipts/VALIDATION_REPORT_V0_9.json").read_text())
    status = json.loads((root / "STATUS.json").read_text())
    ledger = json.loads((root / "receipts/LEDGER_RECONCILIATION_RECEIPT_V0_9.json").read_text())
    payload_entries = [entry(root, path) for path in included_files(root, include_manifest=False)]
    payload_lines = "".join(f"{row['sha256']}  {row['path']}\n" for row in payload_entries)
    payload_tree_sha = hashlib.sha256(payload_lines.encode("utf-8")).hexdigest()
    (root / "manifest/PAYLOAD_SHA256SUMS.txt").write_text(payload_lines, encoding="utf-8")
    (root / "manifest/TREE_SHA256.txt").write_text(payload_tree_sha + "\n", encoding="utf-8")

    manifest = {
        "format": "KCH_HELICAL_V0_9_RELEASE_MANIFEST",
        "release_name": root.name,
        "version": "0.9.0",
        "scientific_protocol_version": "0.8.0_UNCHANGED",
        "protocol_id": status["protocol_id"],
        "payload_tree_sha256": payload_tree_sha,
        "payload_file_count": len(payload_entries),
        "payload_bytes": sum(row["bytes"] for row in payload_entries),
        "entries": payload_entries,
        "validation_id": validation["validation_id"],
        "validation": f"{validation['passed']}/{validation['total']}_PASS",
        "kwanblock_id": status["kwanblock_id"],
        "graph_id": status["graph_id"],
        "event_id": status["event_id"],
        "ledger_receipt_id": ledger["receipt_id"],
        "scientific_execution_performed": False,
        "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
    }
    manifest["manifest_id"] = content_id("h9manifest", manifest)
    write_json_atomic(root / "manifest/MANIFEST.json", manifest)
    manifest_sha = sha256_file(root / "manifest/MANIFEST.json")

    release_receipt = {
        "format": "KCH_HELICAL_V0_9_RELEASE_RECEIPT",
        "release_name": root.name,
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": manifest_sha,
        "payload_tree_sha256": payload_tree_sha,
        "payload_file_count": len(payload_entries),
        "payload_bytes": manifest["payload_bytes"],
        "validation_id": validation["validation_id"],
        "validation_status": validation["status"],
        "kwanblock_id": status["kwanblock_id"],
        "ledger_receipt_id": ledger["receipt_id"],
        "scientific_execution_performed": False,
        "authority_ceiling": "NONE",
    }
    release_receipt["release_receipt_id"] = content_id("h9release", release_receipt)
    write_json_atomic(root / "manifest/RELEASE_RECEIPT.json", release_receipt)

    full_files = [path for path in included_files(root, include_manifest=True) if path.name != "FULL_SHA256SUMS.txt"]
    full_lines = "".join(
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}\n" for path in full_files
    )
    (root / "manifest/FULL_SHA256SUMS.txt").write_text(full_lines, encoding="utf-8")

    destination.unlink(missing_ok=True)
    members = deterministic_zip(root, destination)
    zip_sha = sha256_file(destination)
    (destination.parent / f"{destination.name}.sha256").write_text(f"{zip_sha}  {destination.name}\n", encoding="utf-8")

    with zipfile.ZipFile(destination, "r") as archive:
        bad = archive.testzip()
        names = archive.namelist()
        source_by_name = {f"{root.name}/{path.relative_to(root).as_posix()}": path for path in included_files(root, include_manifest=True)}
        mismatches = []
        for name, path in source_by_name.items():
            h = hashlib.sha256()
            with archive.open(name) as handle:
                for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                    h.update(block)
            if h.hexdigest() != sha256_file(path):
                mismatches.append(name)
    verification = {
        "format": "KCH_HELICAL_V0_9_ZIP_VERIFICATION",
        "status": "PASS" if bad is None and not mismatches and set(names) == set(source_by_name) else "FAIL",
        "zip": destination.name,
        "zip_bytes": destination.stat().st_size,
        "zip_sha256": zip_sha,
        "member_count": len(names),
        "source_file_count": len(source_by_name),
        "crc_failure": bad,
        "hash_mismatches": mismatches,
        "member_set_exact": set(names) == set(source_by_name),
        "manifest_id": manifest["manifest_id"],
        "release_receipt_id": release_receipt["release_receipt_id"],
    }
    verification["verification_id"] = content_id("h9zipverify", verification)
    write_json_atomic(destination.parent / f"{destination.name}.validation.json", verification)
    print(json.dumps({
        "status": verification["status"],
        "zip": str(destination),
        "zip_bytes": destination.stat().st_size,
        "zip_sha256": zip_sha,
        "members": len(names),
        "payload_files": len(payload_entries),
        "payload_bytes": manifest["payload_bytes"],
        "payload_tree_sha256": payload_tree_sha,
        "manifest_id": manifest["manifest_id"],
        "release_receipt_id": release_receipt["release_receipt_id"],
        "verification_id": verification["verification_id"],
    }, sort_keys=True, indent=2))
    return 0 if verification["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
