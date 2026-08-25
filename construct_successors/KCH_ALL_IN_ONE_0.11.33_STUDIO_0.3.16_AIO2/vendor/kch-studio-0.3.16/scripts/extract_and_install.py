from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_member(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ValueError(f"unsafe ZIP member: {name}")
    target = root.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"ZIP member escapes extraction root: {name}") from exc
    return target


def extract_exact(archive: Path, target: Path) -> dict[str, Any]:
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"extraction target must be new or empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    roots: set[str] = set()
    with zipfile.ZipFile(archive) as stream:
        bad_crc = stream.testzip()
        if bad_crc is not None:
            raise ValueError(f"ZIP CRC failure before extraction: {bad_crc}")
        for info in stream.infolist():
            relative = PurePosixPath(info.filename)
            roots.add(relative.parts[0])
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(
                    f"symbolic links are not accepted in portable package: {info.filename}"
                )
            destination = safe_member(target, info.filename)
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary_name = tempfile.mkstemp(
                prefix=".kch-part-", suffix=".part", dir=destination.parent
            )
            try:
                with os.fdopen(fd, "wb") as output, stream.open(info, "r") as source:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary_name, destination)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
            files.append(
                {
                    "path": info.filename,
                    "bytes": destination.stat().st_size,
                    "sha256": sha256(destination),
                }
            )
    if len(roots) != 1:
        raise ValueError(
            f"portable ZIP must have exactly one package root, observed: {sorted(roots)}"
        )
    package = target / next(iter(roots))
    return {
        "package": str(package),
        "file_count": len(files),
        "files_hash": hashlib.sha256(
            json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }


def main() -> None:
    script_root = Path(__file__).resolve().parent
    archive = (
        Path(sys.argv[1]).resolve()
        if len(sys.argv) > 1
        else next(iter(sorted(script_root.glob("KCH_0.11_PRE2G_*.zip"))), None)
    )
    if archive is None or not archive.is_file():
        raise FileNotFoundError("pass the KCH portable ZIP path")
    local = os.environ.get("LOCALAPPDATA")
    default_base = Path(local) / "KCH" / "packages" if local else script_root / "extracted"
    release_match = re.search(r"_R(\d+)\.zip$", archive.name, flags=re.IGNORECASE)
    release_tag = "unversioned" if release_match is None else f"r{release_match.group(1)}"
    target = (
        Path(sys.argv[2]).resolve()
        if len(sys.argv) > 2
        else (default_base / f"pre2g-{release_tag}").resolve()
    )
    extraction = extract_exact(archive, target)
    package = Path(extraction["package"])
    installer = package / "INSTALL_KCH.cmd"
    if os.name != "nt" or not installer.is_file():
        install = {"state": "NOT_RUN_PLATFORM_OR_INSTALLER_UNAVAILABLE"}
    else:
        completed = subprocess.run(
            [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(installer)],
            cwd=package,
            text=True,
            capture_output=True,
            shell=False,
        )
        install = {
            "state": "INSTALL_COMPLETED"
            if completed.returncode == 0
            else "INSTALL_FAILED_PRESERVED",
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    receipt = {
        "schema": "kch.safe-short-extract-install-receipt.v0.2.0",
        "archive": str(archive),
        "archive_sha256": sha256(archive),
        "target": str(target),
        "target_characters": len(str(target)),
        "path_strategy": "SHORT_LOCALAPPDATA_NEW_ROOT_NO_OVERWRITE",
        "release_tag": release_tag,
        "extraction": extraction,
        "install": install,
        "external_host_configuration_modified": False,
    }
    receipt_path = package / "EXTRACT_INSTALL_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if install.get("state") == "INSTALL_FAILED_PRESERVED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
