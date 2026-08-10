from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


root = Path(__file__).resolve().parent
output = root / "results" / "BUILD_MANIFEST_v0.1.1.json"
if output.exists():
    raise SystemExit(f"refusing to overwrite: {output}")
files = []
for path in root.rglob("*"):
    if not path.is_file():
        continue
    text = str(path)
    if "__pycache__" in path.parts or ".egg-info" in text or "wheel_smoke" in path.parts:
        continue
    if path.name.endswith(("-wal", "-shm")) or path.name == output.name:
        continue
    files.append(path.resolve())
files.sort(key=lambda item: str(item).lower())
entries = [{"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in files]
manifest = {
    "schema": "kch.sco.build-manifest.v0.1.1",
    "canonical_name": "KCH SuperChats Orchestrators (SCO)",
    "software_version": "0.1.0",
    "seal_revision": "0.1.1",
    "release_state": "LOCAL_VALIDATED_INTEGRATION_CANDIDATE",
    "file_count": len(entries),
    "files": entries,
    "exclusions": ["__pycache__", "*.egg-info", "runtime/wheel_smoke", "SQLite WAL/SHM sidecars", "manifest self"],
    "wheel_sha256": sha256_file(root / "dist" / "kch_superchats_orchestrators-0.1.0-py3-none-any.whl"),
    "validation_sha256": sha256_file(root / "results" / "SCO_VALIDATION_RESULT_v0.1.0.json"),
    "integration_descriptor_sha256": sha256_file(root / "results" / "SCO_KCH_INTEGRATION_DESCRIPTOR_v0.1.0.json"),
    "registry_v0_5_sha256": sha256_file(root / "results" / "KCH_SUPER_MCP_FEDERATED_REGISTRY_v0.5.0.json"),
    "authority_created": False,
}
output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"manifest": str(output), "files": len(entries), "wheel_sha256": manifest["wheel_sha256"]}))
