from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable


SCHEMA = "kch.storage-migration-manifest.v0.1.0"
DEFAULT_EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    ".venv",
    "venv",
}


def _sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _normalized_relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


@dataclass(frozen=True)
class DiskPressure:
    root: str
    total_bytes: int
    free_bytes: int
    free_ratio: float
    state: str
    nonessential_writes_allowed: bool


def inspect_disk(path: Path) -> DiskPressure:
    usage = shutil.disk_usage(path)
    ratio = usage.free / usage.total if usage.total else 0.0
    if usage.free < 512 * 1024 * 1024 or ratio < 0.005:
        state = "EMERGENCY"
        allowed = False
    elif usage.free < 2 * 1024**3 or ratio < 0.02:
        state = "CRITICAL"
        allowed = False
    elif usage.free < 10 * 1024**3 or ratio < 0.10:
        state = "WARNING"
        allowed = True
    else:
        state = "GREEN"
        allowed = True
    return DiskPressure(
        root=str(path.resolve().anchor),
        total_bytes=usage.total,
        free_bytes=usage.free,
        free_ratio=ratio,
        state=state,
        nonessential_writes_allowed=allowed,
    )


def iter_files(
    root: Path,
    *,
    excluded_prefixes: Iterable[str] = (),
    excluded_dir_names: Iterable[str] = DEFAULT_EXCLUDED_DIR_NAMES,
) -> tuple[list[Path], list[dict[str, str]]]:
    root = root.resolve(strict=True)
    prefix_parts = [PurePosixPath(item).parts for item in excluded_prefixes]
    excluded_names = set(excluded_dir_names)
    included: list[Path] = []
    excluded: list[dict[str, str]] = []

    def is_prefix(parts: tuple[str, ...]) -> bool:
        return any(parts[: len(prefix)] == prefix for prefix in prefix_parts)

    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        relative_current = current_path.relative_to(root)
        kept_dirs: list[str] = []
        for name in sorted(dirs):
            candidate = relative_current / name
            parts = PurePosixPath(candidate.as_posix()).parts
            if name in excluded_names:
                excluded.append({"path": candidate.as_posix(), "reason": "DERIVED_CACHE_DIRECTORY"})
            elif is_prefix(parts):
                excluded.append({"path": candidate.as_posix(), "reason": "EXPLICIT_PREFIX"})
            else:
                kept_dirs.append(name)
        dirs[:] = kept_dirs
        for name in sorted(files):
            path = current_path / name
            relative = path.relative_to(root)
            parts = PurePosixPath(relative.as_posix()).parts
            if is_prefix(parts):
                excluded.append({"path": relative.as_posix(), "reason": "EXPLICIT_PREFIX"})
                continue
            if path.is_symlink():
                excluded.append({"path": relative.as_posix(), "reason": "SYMLINK_NOT_FOLLOWED"})
                continue
            included.append(path)
    included.sort(key=lambda path: _normalized_relative(root, path))
    excluded.sort(key=lambda item: item["path"])
    return included, excluded


def build_archive(
    root: Path,
    archive: Path,
    manifest_path: Path,
    *,
    excluded_prefixes: Iterable[str] = (),
) -> dict[str, object]:
    root = root.resolve(strict=True)
    archive = archive.resolve()
    manifest_path = manifest_path.resolve()
    if archive == manifest_path:
        raise ValueError("archive and manifest paths must differ")
    for output in (archive, manifest_path):
        if output == root or root in output.parents:
            raise ValueError("outputs must be outside the archived root")
        output.parent.mkdir(parents=True, exist_ok=True)

    before = inspect_disk(root)
    files, excluded = iter_files(root, excluded_prefixes=excluded_prefixes)
    entries: list[dict[str, object]] = []
    archive_tmp = archive.with_suffix(archive.suffix + ".partial")
    if archive_tmp.exists():
        archive_tmp.unlink()

    try:
        with zipfile.ZipFile(
            archive_tmp,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as bundle:
            for path in files:
                relative = _normalized_relative(root, path)
                size = path.stat().st_size
                digest = _sha256_file(path)
                bundle.write(path, arcname=relative)
                entries.append({"path": relative, "bytes": size, "sha256": digest})
        os.replace(archive_tmp, archive)
    finally:
        if archive_tmp.exists():
            archive_tmp.unlink()

    archive_sha256 = _sha256_file(archive)
    with zipfile.ZipFile(archive) as bundle:
        bad_member = bundle.testzip()
        zip_entries = [item for item in bundle.infolist() if not item.is_dir()]
        zip_sizes = {item.filename: item.file_size for item in zip_entries}
    expected_sizes = {str(item["path"]): int(item["bytes"]) for item in entries}
    manifest_core: dict[str, object] = {
        "schema": SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(root),
        "archive": {
            "path": str(archive),
            "bytes": archive.stat().st_size,
            "sha256": archive_sha256,
            "member_count": len(zip_entries),
            "expanded_bytes": sum(expected_sizes.values()),
            "integrity_gate": "PASS"
            if bad_member is None and zip_sizes == expected_sizes
            else "FAIL",
            "bad_member": bad_member,
        },
        "disk_before": asdict(before),
        "included": entries,
        "excluded": excluded,
        "authority": {
            "remote_upload_performed": False,
            "deletion_authorized_by_manifest": False,
            "automatic_deletion": False,
        },
    }
    manifest_core["manifest_sha256"] = hashlib.sha256(_canonical_bytes(manifest_core)).hexdigest()
    manifest_path.write_bytes(json.dumps(manifest_core, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    if manifest_core["archive"]["integrity_gate"] != "PASS":  # type: ignore[index]
        raise RuntimeError("archive integrity gate failed")
    return manifest_core


def verify_archive(archive: Path, manifest_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {item["path"]: item for item in manifest["included"]}
    actual_sha = _sha256_file(archive)
    with zipfile.ZipFile(archive) as bundle:
        bad = bundle.testzip()
        actual = {
            item.filename: item.file_size
            for item in bundle.infolist()
            if not item.is_dir()
        }
    size_gate = actual == {path: item["bytes"] for path, item in expected.items()}
    hash_gate = actual_sha == manifest["archive"]["sha256"]
    return {
        "schema": "kch.storage-archive-verification.v0.1.0",
        "archive_sha256": actual_sha,
        "archive_hash_gate": hash_gate,
        "member_size_gate": size_gate,
        "zip_integrity_gate": bad is None,
        "bad_member": bad,
        "status": "PASS" if hash_gate and size_gate and bad is None else "FAIL",
    }


def emit_part(
    archive: Path,
    destination: Path,
    *,
    index: int,
    part_bytes: int = 95_000_000,
) -> dict[str, object]:
    """Emit one bounded transport part without retaining a second full copy."""
    if index < 1:
        raise ValueError("part index is one-based")
    if part_bytes < 1:
        raise ValueError("part_bytes must be positive")
    archive = archive.resolve(strict=True)
    offset = (index - 1) * part_bytes
    total = archive.stat().st_size
    if offset >= total:
        raise ValueError("part index starts beyond end of archive")
    expected_size = min(part_bytes, total - offset)
    part_count = (total + part_bytes - 1) // part_bytes
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    if temporary.exists():
        temporary.unlink()
    digest = hashlib.sha256()
    remaining = expected_size
    try:
        with archive.open("rb") as source, temporary.open("wb") as target:
            source.seek(offset)
            while remaining:
                chunk = source.read(min(8 * 1024 * 1024, remaining))
                if not chunk:
                    raise IOError("archive ended before the declared part boundary")
                target.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    if destination.stat().st_size != expected_size:
        raise IOError("emitted part size mismatch")
    return {
        "schema": "kch.storage-transport-part.v0.1.0",
        "source_archive": str(archive),
        "source_archive_bytes": total,
        "index": index,
        "part_count": part_count,
        "offset": offset,
        "bytes": expected_size,
        "sha256": digest.hexdigest(),
        "path": str(destination),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("path", type=Path)
    archive = subparsers.add_parser("archive")
    archive.add_argument("root", type=Path)
    archive.add_argument("archive", type=Path)
    archive.add_argument("manifest", type=Path)
    archive.add_argument("--exclude-prefix", action="append", default=[])
    verify = subparsers.add_parser("verify")
    verify.add_argument("archive", type=Path)
    verify.add_argument("manifest", type=Path)
    part = subparsers.add_parser("emit-part")
    part.add_argument("archive", type=Path)
    part.add_argument("destination", type=Path)
    part.add_argument("index", type=int)
    part.add_argument("--part-bytes", type=int, default=95_000_000)
    args = parser.parse_args()
    if args.command == "status":
        payload = asdict(inspect_disk(args.path))
    elif args.command == "archive":
        payload = build_archive(
            args.root,
            args.archive,
            args.manifest,
            excluded_prefixes=args.exclude_prefix,
        )
    elif args.command == "verify":
        payload = verify_archive(args.archive, args.manifest)
    else:
        payload = emit_part(
            args.archive,
            args.destination,
            index=args.index,
            part_bytes=args.part_bytes,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status", "PASS") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
