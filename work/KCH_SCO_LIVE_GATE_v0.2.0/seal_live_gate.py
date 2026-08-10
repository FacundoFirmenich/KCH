from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


root = Path(__file__).resolve().parent
output = root / "results" / "SCO_LIVE_GATE_BUILD_MANIFEST_v0.2.0.json"
if output.exists():
    raise SystemExit(f"refusing to overwrite: {output}")
files = []
for path in root.rglob("*"):
    if not path.is_file() or "__pycache__" in path.parts or path.name.endswith(("-wal", "-shm")) or path.name == output.name:
        continue
    files.append(path.resolve())
files.sort(key=lambda item: str(item).lower())
entries = [{"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)} for path in files]
manifest = {
    "schema": "kch.sco.live-gate-build-manifest.v0.2.0",
    "gate_id": "GATE_SCO_CODEX_LIVE_TRANSPORT_AND_KCH_DECISION_ADAPTER_v0.2.0",
    "release_state": "PASS_BOUNDED_EVIDENCE_PACKAGE",
    "file_count": len(entries),
    "files": entries,
    "exclusions": ["__pycache__", "SQLite WAL/SHM sidecars", "manifest self"],
    "live_gate_result_sha256": sha_file(root / "results" / "SCO_LIVE_GATE_RESULT_v0.2.0.json"),
    "decision_adapter_result_sha256": sha_file(root / "results" / "SCO_DECISION_ADAPTER_GATE_RESULT_v0.2.0.json"),
    "native_response_sha256": sha_file(root / "native_response_SCO-LIVE-DISPATCH-20260809-01.json"),
    "authority_created": False,
}
output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": len(entries), "manifest": str(output), "gate_result_sha256": manifest["live_gate_result_sha256"]}))
