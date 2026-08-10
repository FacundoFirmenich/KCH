from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    manifest = json.loads((root / "MANIFEST_SHA256_v0.11.0.json").read_text(encoding="utf-8"))
    failures = []
    for row in manifest["files"]:
        path = root / row["path"]
        observed = sha256_file(path) if path.is_file() else None
        if observed != row["sha256"]:
            failures.append({"path": row["path"], "expected": row["sha256"], "observed": observed})
    result = {"release": "KCH 0.11", "gate": "PASS" if not failures else "FAIL", "verified": len(manifest["files"]) - len(failures), "expected": len(manifest["files"]), "failures": failures}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
