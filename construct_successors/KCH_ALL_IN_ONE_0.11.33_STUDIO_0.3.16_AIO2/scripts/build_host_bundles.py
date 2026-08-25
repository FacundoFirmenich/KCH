from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


CODEX_INSTALLER = r'''param(
  [string]$RuntimeRoot = "D:\CodexRuntimes\kch-aio1",
  [string]$Marketplace = "$env:USERPROFILE\.agents\plugins\marketplace.json",
  [string]$ReceiptRoot = "D:\CodexRuntimes\kch-aio2-receipts"
)
$ErrorActionPreference = "Stop"
$package = Join-Path $PSScriptRoot "KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2"
py -3 (Join-Path $package "install_all_in_one.py") --package-root $package --runtime-root $RuntimeRoot --hosts codex --codex-marketplace $Marketplace --receipt-root $ReceiptRoot
'''

CLINE_INSTALLER = r'''param(
  [Parameter(Mandatory=$true)][string]$Workspace,
  [Parameter(Mandatory=$true)][string]$ClineSettings,
  [string]$RuntimeRoot = "D:\CodexRuntimes\kch-aio1",
  [string]$ReceiptRoot = "D:\CodexRuntimes\kch-aio2-receipts"
)
$ErrorActionPreference = "Stop"
$package = Join-Path $PSScriptRoot "KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2"
py -3 (Join-Path $package "install_all_in_one.py") --package-root $package --runtime-root $RuntimeRoot --hosts cline --cline-workspace $Workspace --cline-settings $ClineSettings --receipt-root $ReceiptRoot
'''


def bundle(package: Path, target: Path, installer_name: str, installer: str) -> None:
    fixed = (2026, 8, 25, 0, 0, 0)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            rel = Path(package.name) / path.relative_to(package)
            info = zipfile.ZipInfo(rel.as_posix(), fixed)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo(installer_name, fixed)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, installer.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build complete host-specific KCH AIO2 bundles")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--release-dir", type=Path, required=True)
    args = parser.parse_args()
    package = args.package_root.absolute()
    release = args.release_dir.absolute()
    if not (package / "install_all_in_one.py").is_file():
        raise FileNotFoundError(package)
    release.mkdir(parents=True, exist_ok=True)
    bundle(package, release / "KCH_AIO2_CODEX_COMPLETE.zip", "INSTALL_CODEX.ps1", CODEX_INSTALLER)
    bundle(package, release / "KCH_AIO2_CLINE_COMPLETE.zip", "INSTALL_CLINE.ps1", CLINE_INSTALLER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())