from __future__ import annotations

import email.parser
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
DIST = ROOT / "dist"
VENDOR = ROOT / "vendor"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def wheel_metadata(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = email.parser.BytesParser().parsebytes(archive.read(metadata_name))
    declared = metadata.get("License") or "NOASSERTION"
    classifiers = metadata.get_all("Classifier") or []
    license_classifiers = [item for item in classifiers if item.startswith("License ::")]
    return {
        "filename": path.name,
        "name": metadata.get("Name"),
        "version": metadata.get("Version"),
        "sha256": sha256_file(path),
        "license_declared": declared,
        "license_classifiers": license_classifiers,
        "license_concluded": "NOASSERTION",
        "authority_inherited": False,
    }


def network_scan(path: Path) -> dict[str, Any]:
    patterns = {
        "http_server": re.compile(rb"\bHTTPServer\b|\bThreadingHTTPServer\b"),
        "socket": re.compile(rb"\bimport socket\b|\bfrom socket\b"),
        "requests": re.compile(rb"\bimport requests\b|\bfrom requests\b"),
        "urllib": re.compile(rb"\burllib\b"),
        "subprocess": re.compile(rb"\bsubprocess\b"),
    }
    hits: dict[str, list[str]] = {key: [] for key in patterns}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.endswith(".py"):
                continue
            data = archive.read(name)
            for label, pattern in patterns.items():
                if pattern.search(data):
                    hits[label].append(name)
    return {"wheel": path.name, "hits": {key: value for key, value in hits.items() if value}}


def included_files() -> list[Path]:
    allowed_roots = ["README.md", "KCH_0.11_RELEASE_CONTRACT.md", "pyproject.toml", "src", "tests", "scripts", "config", "vendor", "evidence", "dist", "results", "SBOM_SPDX_v0.11.0.json", "LICENSE_INVENTORY_v0.11.0.json", "NETWORK_SURFACE_AUDIT_v0.11.0.json", "RELEASE_SEAL_v0.11.0.json"]
    files: list[Path] = []
    for name in allowed_roots:
        path = ROOT / name
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file())
    excluded_parts = {"__pycache__", "build", "runtime", "vendor_build"}
    return sorted(
        [path for path in files if not excluded_parts.intersection(path.parts) and path.suffix not in {".pyc", ".pyo"} and ".egg-info" not in path.as_posix()],
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )


def main() -> int:
    gate = json.loads((RESULTS / "KCH_0.11_GATE_RESULT.json").read_text(encoding="utf-8"))
    extracted_gate = json.loads((RESULTS / "KCH_0.11_EXTRACTED_WHEELS_GATE_RESULT.json").read_text(encoding="utf-8"))
    suites = json.loads((RESULTS / "KCH_0.11_COMPONENT_SUITES.json").read_text(encoding="utf-8"))
    if gate["gate"] != "PASS_KCH_0.11_LOCAL_BOUNDED" or extracted_gate["gate"] != "PASS_KCH_0.11_LOCAL_BOUNDED" or suites["gate"] != "PASS":
        raise SystemExit("release gates are not green")

    wheel_paths = sorted([*DIST.glob("*.whl"), *VENDOR.glob("*.whl")], key=lambda path: path.name)
    packages = [wheel_metadata(path) for path in wheel_paths]
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "KCH-0.11-offline-bundle",
        "documentNamespace": "https://kwancode.local/spdx/KCH-0.11/" + hashlib.sha256(canonical_json(packages).encode()).hexdigest(),
        "creationInfo": {"created": "2026-08-09T00:00:00Z", "creators": ["Tool: KCH-0.11-sealer"]},
        "packages": [
            {
                "name": item["name"],
                "SPDXID": "SPDXRef-Package-" + re.sub(r"[^A-Za-z0-9.-]", "-", str(item["name"])),
                "versionInfo": item["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": item["license_declared"],
                "checksums": [{"algorithm": "SHA256", "checksumValue": item["sha256"]}],
                "externalRefs": [{"referenceCategory": "PACKAGE-MANAGER", "referenceType": "purl", "referenceLocator": f"pkg:pypi/{str(item['name']).lower()}@{item['version']}"}],
            }
            for item in packages
        ],
    }
    write_json(ROOT / "SBOM_SPDX_v0.11.0.json", sbom)
    license_inventory = {
        "schema": "kch.license-inventory.v0.11.0",
        "release": "KCH 0.11",
        "adjudication": "NOASSERTION is preserved where wheel metadata does not declare a license; bundle inclusion is not a relicensing claim.",
        "packages": packages,
    }
    write_json(ROOT / "LICENSE_INVENTORY_v0.11.0.json", license_inventory)
    scans = [network_scan(path) for path in wheel_paths]
    network_audit = {
        "schema": "kch.network-surface-audit.v0.11.0",
        "release": "KCH 0.11",
        "method": "Static token scan of Python sources inside bundled wheels; not a dynamic penetration test.",
        "kch_super_mcp_transport": "STDIO",
        "remote_listener_enabled_by_default": False,
        "findings": scans,
    }
    write_json(ROOT / "NETWORK_SURFACE_AUDIT_v0.11.0.json", network_audit)

    core_wheel = DIST / "kwancode_harness-0.11.0-py3-none-any.whl"
    seal = {
        "schema": "kch.release-seal.v0.11.0",
        "release": "KCH 0.11",
        "package_version": "0.11.0",
        "state": "SEALED_CANONICAL_PRE2G_MACRORELEASE_LOCAL_BOUNDED",
        "core_wheel_sha256": sha256_file(core_wheel),
        "local_gate_sha256": sha256_file(RESULTS / "KCH_0.11_GATE_RESULT.json"),
        "extracted_wheels_gate_sha256": sha256_file(RESULTS / "KCH_0.11_EXTRACTED_WHEELS_GATE_RESULT.json"),
        "component_suites_sha256": sha256_file(RESULTS / "KCH_0.11_COMPONENT_SUITES.json"),
        "component_suite_tests": suites["test_total"],
        "component_suites": suites["suite_count"],
        "profiles": {"minimal": "AVAILABLE", "research": "AVAILABLE", "agent-shadow": "DEFAULT", "enforced": "PROHIBITED_UNTIL_GATES_PASS"},
        "automatic_promotion": False,
        "mutating_execution_authorized": False,
        "claim_ceiling": "CANONICAL_PRE2G_MACRORELEASE_WITH_BOUNDED_EXECUTABLE_INTEGRATION",
    }
    write_json(ROOT / "RELEASE_SEAL_v0.11.0.json", seal)

    files = included_files()
    manifest_rows = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in files]
    manifest = {
        "schema": "kch.bundle-manifest.v0.11.0",
        "release": "KCH 0.11",
        "file_count": len(manifest_rows),
        "files": manifest_rows,
        "content_set_sha256": hashlib.sha256(canonical_json(manifest_rows).encode("utf-8")).hexdigest(),
    }
    manifest_path = ROOT / "MANIFEST_SHA256_v0.11.0.json"
    write_json(manifest_path, manifest)

    zip_path = RESULTS / "KCH_0.11_CANONICAL_MACRORELEASE.zip"
    selected = files + [manifest_path]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(selected, key=lambda item: item.relative_to(ROOT).as_posix()):
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(relative, (2026, 8, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    zip_hash = sha256_file(zip_path)
    (RESULTS / "KCH_0.11_CANONICAL_MACRORELEASE.sha256").write_text(f"{zip_hash}  {zip_path.name}\n", encoding="ascii")
    result = {"release": "KCH 0.11", "zip": str(zip_path), "zip_sha256": zip_hash, "manifest_files": manifest["file_count"], "content_set_sha256": manifest["content_set_sha256"], "state": seal["state"]}
    write_json(RESULTS / "KCH_0.11_SEAL_RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
