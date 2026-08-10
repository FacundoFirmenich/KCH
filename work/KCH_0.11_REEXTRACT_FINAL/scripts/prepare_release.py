from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def sha256_file(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    root.add_argument("--root", type=Path, required=True)
    root.add_argument("--baseline-registry", type=Path, required=True)
    root.add_argument("--current-state", type=Path, required=True)
    root.add_argument("--sco-state", type=Path, required=True)
    root.add_argument("--mis-certificate", type=Path, required=True)
    root.add_argument("--vendor", type=Path, action="append", default=[])
    return root


def main() -> int:
    args = parser().parse_args()
    release_root = args.root.resolve()
    evidence_root = release_root / "evidence"
    registry_evidence = evidence_root / "registry"
    vendor_root = release_root / "vendor"
    registry_evidence.mkdir(parents=True, exist_ok=True)
    vendor_root.mkdir(parents=True, exist_ok=True)

    baseline = json.loads(args.baseline_registry.read_text(encoding="utf-8-sig"))
    if not isinstance(baseline, list):
        raise SystemExit("baseline registry must be the v0.6.0 array")
    services: list[dict] = []
    quarantine: list[dict] = []
    custody_rows: list[dict] = []
    for source_row in baseline:
        row = dict(source_row)
        source = Path(row["evidence_file"])
        expected = row["evidence_sha256"]
        if not source.is_file():
            raise SystemExit(f"registry evidence unavailable: {source}")
        observed = sha256_file(source)
        if observed != expected:
            raise SystemExit(f"registry evidence hash mismatch: {source}")
        destination = registry_evidence / f"{expected}_{source.name}"
        if not destination.exists():
            shutil.copy2(source, destination)
        row["bundle_evidence_file"] = destination.relative_to(release_root).as_posix()
        row["source_evidence_file"] = row.pop("evidence_file")
        row["release_id"] = row.get("legacy_source_directory") or row["active_name"].replace(" ", "_").upper()
        custody_rows.append({"active_name": row["active_name"], "source": str(source), "copy": row["bundle_evidence_file"], "sha256": expected})
        if row["family"] == "QUARANTINED_HISTORICAL_BRANCH":
            quarantine.append(row)
        else:
            services.append(row)

    contract = release_root / "KCH_0.11_RELEASE_CONTRACT.md"
    contract_hash = sha256_file(contract)
    contract_copy = registry_evidence / f"{contract_hash}_{contract.name}"
    shutil.copy2(contract, contract_copy)
    services.append({
        "active_name": "KwanCode Harness",
        "release_id": "KCH_0.11",
        "legacy_source_directory": None,
        "family": "KCH_CANONICAL_MACRORELEASE",
        "state": "CANONICAL_PRE2G_FEDERATED_MACRORELEASE",
        "jurisdiction": "federated governance, evidence custody, reflexive controls and authorized read-only composition; no mutating execution",
        "evidence_sha256": contract_hash,
        "bundle_evidence_file": contract_copy.relative_to(release_root).as_posix(),
        "source_evidence_file": str(contract),
        "authority_inheritance": False,
        "automatic_promotion": False,
        "claim_ceiling": "CANONICAL_PRE2G_MACRORELEASE_WITH_BOUNDED_EXECUTABLE_INTEGRATION",
    })
    custody_rows.append({"active_name": "KwanCode Harness", "source": str(contract), "copy": contract_copy.relative_to(release_root).as_posix(), "sha256": contract_hash})

    registry = {
        "schema": "kch.federated-registry.v0.11.0",
        "release": "KCH 0.11",
        "package_version": "0.11.0",
        "baseline_registry_sha256": sha256_file(args.baseline_registry),
        "services": services,
        "quarantine": quarantine,
        "authority_inheritance_default": False,
        "mutating_execution_authorized": False,
        "enforced_profile": "PROHIBITED_UNTIL_GATES_PASS",
    }
    write_json(release_root / "config" / "KCH_REGISTRY_v0.11.0.json", registry)
    write_json(release_root / "src" / "kwancode_harness" / "data" / "KCH_REGISTRY_v0.11.0.json", registry)
    write_json(release_root / "evidence" / "KCH_REGISTRY_CUSTODY_v0.11.0.json", {"schema": "kch.registry-custody.v0.11.0", "rows": custody_rows})

    state_copies = [
        (args.current_state, evidence_root / "KCH_CURRENT_INTEGRATION_STATE_v0.6.0.sqlite3"),
        (args.sco_state, evidence_root / "KCH_PRE2G_SCO_v0.1.0.sqlite3"),
        (args.mis_certificate, evidence_root / "KCH_MIS_V03_HISTORICAL_CERTIFICATE_v0.1.0.json"),
    ]
    for source, destination in state_copies:
        if not source.is_file():
            raise SystemExit(f"state evidence unavailable: {source}")
        shutil.copy2(source, destination)

    wheels = []
    for source in args.vendor:
        if not source.is_file() or source.suffix != ".whl":
            raise SystemExit(f"invalid vendor wheel: {source}")
        destination = vendor_root / source.name
        shutil.copy2(source, destination)
        wheels.append({"filename": destination.name, "sha256": sha256_file(destination), "source": str(source), "authority_inherited": False})
    write_json(release_root / "config" / "VENDOR_WHEEL_LOCK_v0.11.0.json", {"schema": "kch.vendor-wheel-lock.v0.11.0", "release": "KCH 0.11", "wheels": sorted(wheels, key=lambda row: row["filename"])})
    print(json.dumps({"services": len(services), "quarantine": len(quarantine), "custody": len(custody_rows), "vendor_wheels": len(wheels)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
