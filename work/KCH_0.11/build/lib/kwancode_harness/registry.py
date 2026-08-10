from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import sha256_file, sha256_json


class Registry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        value = json.loads(self.path.read_text(encoding="utf-8-sig"))
        if isinstance(value, list):
            value = {
                "schema": "kch.federated-registry.legacy-array",
                "release": "PRE_KCH_0.11",
                "services": value,
                "quarantine": [],
            }
        if not isinstance(value, dict) or not isinstance(value.get("services"), list):
            raise ValueError("invalid KCH registry")
        self.value: dict[str, Any] = value
        self._validate()

    def _validate(self) -> None:
        identities: set[tuple[str, str | None]] = set()
        for row in self.value["services"]:
            if not isinstance(row, dict):
                raise ValueError("registry service row must be an object")
            for field in ("active_name", "family", "state", "jurisdiction"):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise ValueError(f"registry row missing {field}")
            identity = (row["active_name"], row.get("release_id") or row.get("legacy_source_directory"))
            if identity in identities:
                raise ValueError(f"registry identity collision: {identity}")
            identities.add(identity)
            if row.get("authority_inheritance") is not False:
                raise ValueError("registry must deny implicit authority inheritance")

    @property
    def hash(self) -> str:
        return sha256_json(self.value)

    def describe(self) -> dict[str, Any]:
        states: dict[str, int] = {}
        families: dict[str, int] = {}
        for row in self.value["services"]:
            states[row["state"]] = states.get(row["state"], 0) + 1
            families[row["family"]] = families.get(row["family"], 0) + 1
        return {
            **self.value,
            "registry_sha256": self.hash,
            "service_count": len(self.value["services"]),
            "state_counts": dict(sorted(states.items())),
            "family_counts": dict(sorted(families.items())),
        }

    def audit_evidence(self, bundle_root: str | Path | None = None) -> dict[str, Any]:
        root = Path(bundle_root) if bundle_root else self.path.parent
        rows: list[dict[str, Any]] = []
        for service in self.value["services"]:
            expected = service.get("evidence_sha256")
            relative = service.get("bundle_evidence_file")
            source = service.get("evidence_file")
            path = root / relative if relative else Path(source) if source else None
            if not expected or path is None or not path.is_file():
                state, observed = "UNAVAILABLE", None
            else:
                observed = sha256_file(path)
                state = "PASS" if observed == expected else "FAIL"
            rows.append({"active_name": service["active_name"], "path": str(path) if path else None, "expected_sha256": expected, "observed_sha256": observed, "state": state})
        totals = {state: sum(1 for row in rows if row["state"] == state) for state in ("PASS", "FAIL", "UNAVAILABLE")}
        return {"schema": "kch.registry-evidence-audit.v0.11.0", "release": "KCH 0.11", "totals": totals, "rows": rows}
