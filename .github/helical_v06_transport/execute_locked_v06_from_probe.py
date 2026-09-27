from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

EXPECTED = {
    "CAHUILLA_SWARM_2016_2019": {
        "sha256": "ad49e97a24c6325417550b899919e67c209b510eaba3ba8921512b82cf206cf0",
        "bytes": 4040600,
        "relative_path": "sources/CAHUILLA_SWARM_2016_2019/out.growclust_cat",
    },
    "RIDGECREST_QTM_2019": {
        "sha256": "dcb0035f69c6ea9a960e45544f31bdacb38cb7f502c3d29af827da4ff6850849",
        "bytes": 4460469,
        "relative_path": "sources/RIDGECREST_QTM_2019/ridgecrest_qtm.tar.gz",
    },
    "CALMEX_BORDER_2012_2020": {
        "sha256": "92bfc33d2d7d8b549a52a71939505b1ee8a82f0d07d7293abfe9646328acd229",
        "bytes": 3686364,
        "relative_path": "sources/CALMEX_BORDER_2012_2020/out.hypoDD.reloc",
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_helper(repo_root: Path):
    helper_path = repo_root / ".github" / "helical_v06_transport" / "run_remote_v06.py"
    spec = importlib.util.spec_from_file_location("kch_v06_remote_helper", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_probe_root(root: Path) -> Path:
    candidates = [root, *[p for p in root.iterdir() if p.is_dir()]]
    for candidate in candidates:
        if (candidate / "FAST_PROBE_REPORT.json").exists():
            return candidate
    found = list(root.rglob("FAST_PROBE_REPORT.json"))
    if len(found) != 1:
        raise RuntimeError(f"expected one FAST_PROBE_REPORT.json under {root}, found {found}")
    return found[0].parent


def validate_and_stage(probe_root: Path, data_root: Path) -> dict[str, object]:
    report = json.loads((probe_root / "FAST_PROBE_REPORT.json").read_text(encoding="utf-8"))
    staged: list[dict[str, object]] = []
    (data_root / "transport" / "headers").mkdir(parents=True, exist_ok=True)
    (data_root / "transport" / "curl").mkdir(parents=True, exist_ok=True)

    for catalog_id, expected in EXPECTED.items():
        official = probe_root / f"{catalog_id}__official.body"
        convergent = probe_root / f"{catalog_id}__cloudfront.body"
        official_headers = probe_root / f"{catalog_id}__official.headers"
        official_meta = probe_root / f"{catalog_id}__official.meta.json"
        if not all(p.exists() for p in [official, convergent, official_headers, official_meta]):
            raise RuntimeError(f"{catalog_id}: missing probe files")

        observed_sha = sha256(official)
        convergent_sha = sha256(convergent)
        if observed_sha != expected["sha256"] or convergent_sha != expected["sha256"]:
            raise RuntimeError(
                f"{catalog_id}: digest mismatch direct={observed_sha} convergent={convergent_sha} expected={expected['sha256']}"
            )
        if official.read_bytes() != convergent.read_bytes():
            raise RuntimeError(f"{catalog_id}: route bodies differ despite digest expectation")
        if official.stat().st_size != expected["bytes"]:
            raise RuntimeError(f"{catalog_id}: size mismatch")

        meta = json.loads(official_meta.read_text(encoding="utf-8"))
        if int(meta.get("response_code", 0)) != 200:
            raise RuntimeError(f"{catalog_id}: direct official HTTP response is not 200")
        if int(float(meta.get("size_download", -1))) != expected["bytes"]:
            raise RuntimeError(f"{catalog_id}: curl size_download mismatch")
        if meta.get("url_effective") is None or "service.scedc.caltech.edu/ftp/" not in str(meta.get("url_effective")):
            raise RuntimeError(f"{catalog_id}: unexpected direct effective URL {meta.get('url_effective')!r}")

        source_report = report["sources"][catalog_id]
        routes_for_digest = source_report["digest_groups"].get(expected["sha256"], [])
        if sorted(routes_for_digest) != ["cloudfront", "official"]:
            raise RuntimeError(f"{catalog_id}: unexpected digest convergence routes {routes_for_digest}")

        destination = data_root / str(expected["relative_path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(official, destination)
        shutil.copy2(official_headers, data_root / "transport" / "headers" / f"{catalog_id}.headers")
        shutil.copy2(official_meta, data_root / "transport" / "curl" / f"{catalog_id}.json")
        staged.append(
            {
                "catalog_id": catalog_id,
                "destination": destination.as_posix(),
                "bytes": destination.stat().st_size,
                "sha256": sha256(destination),
                "direct_official_http": 200,
                "convergent_transport_body_equal": True,
                "convergent_route_effective_origin": "service.scedc.caltech.edu",
            }
        )

    receipt_body = {
        "format": "KCH_HELICAL_V0_6_BYTE_RESUME_RECEIPT",
        "protocol_id": "h6p:144c4aef47e8b9a88b2c74a92fae66a251581b5dd67295caaa4da6cef6e0827c",
        "source_probe_run_id": 36289187730,
        "source_probe_artifact_id": 10921731900,
        "source_probe_artifact_digest": "sha256:d1b43fbcb52057b1e4a4a7a3b6dd43cbfa75f428a8a7c4a27f85d2d4eca85b5f",
        "staged_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "datasets": staged,
        "all_or_none_pass": len(staged) == 3,
        "source_substitution": False,
        "text_normalization": False,
        "scientific_runtime_changed": False,
        "authority_ceiling": "NONE",
    }
    canonical = json.dumps(receipt_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt = {"receipt_id": "h6r:" + hashlib.sha256(canonical).hexdigest(), **receipt_body}
    write_json(data_root / "BYTE_RESUME_RECEIPT_V0_6.json", receipt)
    return receipt


def seal(root: Path) -> None:
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name not in {"SHA256SUMS.txt", "FILE_SIZES.txt"})
    (root / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(p)}  {p.relative_to(root).as_posix()}\n" for p in files), encoding="utf-8"
    )
    all_files = sorted(p for p in root.rglob("*") if p.is_file())
    (root / "FILE_SIZES.txt").write_text(
        "".join(f"{p.relative_to(root).as_posix()}\t{p.stat().st_size} bytes\n" for p in all_files), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--probe-artifact-root", required=True, type=Path)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    args = parser.parse_args()

    args.artifact_root.mkdir(parents=True, exist_ok=True)
    status = 1
    try:
        helper = load_helper(args.repo_root)
        runtime_root, transport_diag = helper.reconstruct_locked_bundle(args.repo_root, args.work_root)
        write_json(args.work_root / "LOCKED_RUNTIME_RECONSTRUCTION.json", transport_diag)
        protocol = helper.verify_protocol(runtime_root)
        probe_root = find_probe_root(args.probe_artifact_root)
        data_root = args.work_root / "data"
        validate_and_stage(probe_root, data_root)
        helper.audit_acquisition(protocol, data_root)

        results_root = args.work_root / "results"
        results_root.mkdir(parents=True, exist_ok=True)
        stdout_path = results_root / "EXECUTION_STDOUT.log"
        command = [
            sys.executable,
            str(runtime_root / "runtime" / "helical_v06.py"),
            "run-gate",
            "--protocol", str(runtime_root / "spec" / "HELICAL_LOCAL_PIECEWISE_GATE_V0_6_LOCKED.json"),
            "--data-root", str(data_root),
            "--output-dir", str(results_root),
        ]
        with stdout_path.open("w", encoding="utf-8") as out:
            subprocess.run(command, check=True, text=True, stdout=out, stderr=subprocess.STDOUT)
        gate_path = results_root / "V0_6_GATE_RESULT.json"
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        if gate.get("outcome") in {None, "BLOCKED_EXACT_BYTE_ACQUISITION"}:
            raise RuntimeError(f"scientific execution did not reach adjudication: {gate.get('outcome')}")
        status = 0
    except Exception as exc:
        write_json(
            args.work_root / "FAIL_CLOSED_RECEIPT.json",
            {
                "format": "KCH_HELICAL_V0_6_RESUME_FAIL_CLOSED_RECEIPT",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "scientific_claim_authorized": False,
                "authority_ceiling": "NONE",
                "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )
        print(traceback.format_exc(), file=sys.stderr)
    finally:
        for name in ["locked_bundle", "data", "results"]:
            source = args.work_root / name
            if source.exists():
                shutil.copytree(source, args.artifact_root / name, dirs_exist_ok=True)
        for name in ["LOCKED_RUNTIME_RECONSTRUCTION.json", "FAIL_CLOSED_RECEIPT.json"]:
            source = args.work_root / name
            if source.exists():
                shutil.copy2(source, args.artifact_root / name)
        seal(args.artifact_root)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
