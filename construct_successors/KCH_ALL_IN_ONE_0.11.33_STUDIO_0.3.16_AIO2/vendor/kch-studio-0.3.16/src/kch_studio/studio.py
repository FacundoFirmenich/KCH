from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import (
    ArtifactSpec,
    LifecycleState,
    ValidationCheck,
    file_manifest,
    safe_child,
    sha256_bytes,
    sha256_json,
)
from .generators import ProviderRegistry, write_json
from .store import EventStore


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class Studio:
    """View-independent transactional kernel for CSI artifact construction."""

    def __init__(
        self,
        root: str | Path,
        *,
        governance_dist: str | Path | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.stage_root = self.root / "staging"
        self.stage_root.mkdir(exist_ok=True)
        self.seal_root = self.root / "seals"
        self.seal_root.mkdir(exist_ok=True)
        self.store = EventStore(self.root / "state" / "studio.sqlite3")
        self.providers = ProviderRegistry()
        if governance_dist is None:
            candidates = [
                Path(os.environ["KCH_GOVERNANCE_DIST"]).resolve()
                if os.environ.get("KCH_GOVERNANCE_DIST")
                else None,
                Path(__file__).resolve().parent / "data" / "governance",
                Path(__file__).resolve().parents[3] / "KCH_CSI_SELF_GOVERNANCE_v0.1.0" / "dist",
            ]
            governance_dist = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate is not None
                    and (candidate / "csi" / "governance_graph.json").is_file()
                ),
                candidates[-1],
            )
        self.governance_dist = Path(governance_dist).resolve()
        self.governance = self._load_governance()

    def _load_governance(self) -> dict[str, Any]:
        graph_path = self.governance_dist / "csi" / "governance_graph.json"
        lock_path = self.governance_dist / "governance.lock.json"
        if not graph_path.is_file() or not lock_path.is_file():
            raise FileNotFoundError(f"compiled KCH governance unavailable: {self.governance_dist}")
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        observed = sha256_json(graph)
        if observed != lock.get("source_graph_sha256"):
            raise ValueError("compiled governance graph no longer matches its lock")
        if graph.get("hierarchy") != ["HARNESS", "AGENTS", "RULES"]:
            raise ValueError("canonical HARNESS > AGENTS > RULES hierarchy missing")
        if (
            graph.get("install_authority") is not False
            or lock.get("installation_authorized") is not False
        ):
            raise ValueError("preinstallation governance unexpectedly grants install authority")
        node_by_id = {item["id"]: item for item in graph.get("nodes", [])}
        locked_by_id = {item["id"]: item for item in lock.get("source_nodes", [])}
        if set(node_by_id) != set(locked_by_id):
            raise ValueError("compiled governance nodes do not match locked source nodes")
        source_root = self.governance_dist / "source"
        for node_id, node in node_by_id.items():
            locked = locked_by_id[node_id]
            if node != locked:
                raise ValueError(f"compiled/locked governance node mismatch: {node_id}")
            source = safe_child(source_root, str(node["path"]))
            if not source.is_file() or sha256_bytes(source.read_bytes()) != node["sha256"]:
                raise ValueError(f"governance source bytes missing or changed: {node_id}")
        for artifact in lock.get("artifacts", []):
            path = safe_child(self.governance_dist, str(artifact["path"]))
            if not path.is_file() or path.stat().st_size != int(artifact["bytes"]):
                raise ValueError(
                    f"compiled governance artifact missing or resized: {artifact['path']}"
                )
            if sha256_bytes(path.read_bytes()) != artifact["sha256"]:
                raise ValueError(f"compiled governance artifact hash mismatch: {artifact['path']}")
        required_integral_nodes = {
            "AGENT-CORAL-INTEGRATION-AUDITOR",
            "AGENT-EVIDENCE-SKILL-CONTINUITY",
            "RULE-ALL-STRATEGIC-CORAL-INTEGRATION",
            "RULE-EVIDENCE-DERIVED-SKILL-LIFECYCLE",
        }
        if not required_integral_nodes.issubset(node_by_id):
            raise ValueError("integral coral-governance nodes are missing")
        harness = (source_root / "HARNESS.md").read_text(encoding="utf-8")
        if "ABSOLUTAMENTE_TODO_ES_ESTRATÉGICO_SIN_EXCEPCIÓN" not in harness:
            raise ValueError("binding all-strategic invariant is missing from HARNESS")
        return {
            "graph": graph,
            "lock": lock,
            "graph_hash": observed,
            "state": "VERIFIED_COMPILED_GOVERNANCE",
            "source_nodes_verified": len(node_by_id),
            "compiled_artifacts_verified": len(lock.get("artifacts", [])),
            "all_strategic_invariant": True,
        }

    def status(self) -> dict[str, Any]:
        return {
            "schema": "kch.csi-studio-status.v0.1.0",
            "root": str(self.root),
            "governance": {
                "state": self.governance["state"],
                "graph_hash": self.governance["graph_hash"],
                "hierarchy": self.governance["graph"]["hierarchy"],
                "node_count": self.governance["graph"]["node_count"],
                "agent_count": self.governance["graph"]["agent_count"],
                "rule_count": self.governance["graph"]["rule_count"],
                "source_nodes_verified": self.governance["source_nodes_verified"],
                "compiled_artifacts_verified": self.governance["compiled_artifacts_verified"],
                "all_strategic_invariant": self.governance["all_strategic_invariant"],
            },
            "providers": self.providers.describe(),
            "sessions": self.store.list_sessions(),
            "installation_authorized": False,
            "phl_authorized": True,
            "phl_training_executed": False,
            "phl_real_executed": False,
        }

    def create_session(self, spec: ArtifactSpec) -> dict[str, Any]:
        return self.store.create(spec)

    def generate(self, session_id: str) -> dict[str, Any]:
        session = self.store.get(session_id)
        if session["state"] != LifecycleState.SPECIFIED.value:
            raise ValueError(f"generation requires SPECIFIED, got {session['state']}")
        spec = ArtifactSpec.from_dict(session["spec"])
        # The ledger retains the full UUID. The filesystem uses a collision-resistant
        # compact projection to preserve Windows path budget for nested skills/plugins.
        session_root = safe_child(self.stage_root, f"s-{sha256_json(session_id)[:12]}")
        session_root.mkdir(parents=True, exist_ok=False)
        try:
            artifact_root = self.providers.get(spec.kind).generate(spec, session_root)
        except OSError as exc:
            raise OSError(
                f"artifact generation failed at the actual filesystem boundary {session_root}: {exc}"
            ) from exc
        binding = {
            "schema": "kch.csi-governance-binding.v0.1.0",
            "session_id": session_id,
            "spec_hash": sha256_json(spec.to_dict()),
            "governance_graph_hash": self.governance["graph_hash"],
            "hierarchy": ["HARNESS", "AGENTS", "RULES"],
            "authority_ceiling": sorted(spec.authority_ceiling),
            "authority_inherited": False,
            "installation_authorized": False,
        }
        write_json(artifact_root / "kch-csi-governance-binding.json", binding)
        manifest = file_manifest(artifact_root)
        return self.store.record_generation(session_id, artifact_root, manifest)

    def validate(self, session_id: str) -> dict[str, Any]:
        session = self.store.get(session_id)
        if session["state"] != LifecycleState.GENERATED_STAGED.value:
            raise ValueError(f"validation requires GENERATED_STAGED, got {session['state']}")
        spec = ArtifactSpec.from_dict(session["spec"])
        artifact_root = Path(str(session["artifact_root"])).resolve()
        current_manifest = file_manifest(artifact_root)
        checks = self.providers.get(spec.kind).validate(spec, artifact_root)
        checks.append(
            ValidationCheck(
                "artifact.manifest_integrity",
                current_manifest == session["files"],
                "staged bytes match the generation ledger",
                {
                    "current_manifest_hash": sha256_json(current_manifest),
                    "recorded_manifest_hash": sha256_json(session["files"]),
                },
            )
        )
        chain = self.store.verify_chain(session_id)
        checks.append(
            ValidationCheck(
                "ledger.hash_chain",
                bool(chain["passed"]),
                f"{chain['event_count']} chained events",
                chain,
            )
        )
        check_values = [check.to_dict() for check in checks]
        report = {
            "schema": "kch.csi-artifact-validation.v0.1.0",
            "session_id": session_id,
            "artifact_kind": spec.kind.value,
            "passed": all(check.passed for check in checks),
            "checks": check_values,
            "validated_at": utc_now(),
            "installation_authorized": False,
        }
        write_json(artifact_root / "KCH_VALIDATION_RESULT.json", report)
        # The validation report is itself evidence and is deliberately added only after
        # byte-integrity comparison with the generated state.
        if not report["passed"]:
            return {**session, "validation": report}
        # Record the report as a post-generation evidence event by refreshing file custody.
        with self.store.connect() as connection:
            result_manifest = file_manifest(artifact_root)
            connection.execute("DELETE FROM files WHERE session_id=?", (session_id,))
            for item in result_manifest:
                connection.execute(
                    "INSERT INTO files(session_id,path,bytes,sha256) VALUES(?,?,?,?)",
                    (session_id, item["path"], item["bytes"], item["sha256"]),
                )
            self.store._append(
                connection,
                session_id,
                "VALIDATION_EVIDENCE_RECORDED",
                {"manifest_hash": sha256_json(result_manifest), "report_hash": sha256_json(report)},
            )
            connection.commit()
        state = self.store.record_validation(session_id, check_values)
        return {**state, "validation": report}

    def seal(self, session_id: str) -> dict[str, Any]:
        session = self.store.get(session_id)
        if session["state"] != LifecycleState.VALIDATED.value:
            raise ValueError(f"sealing requires VALIDATED, got {session['state']}")
        chain = self.store.verify_chain(session_id)
        if not chain["passed"]:
            raise ValueError(f"event ledger failed verification: {chain['errors']}")
        artifact_root = Path(str(session["artifact_root"])).resolve()
        manifest = file_manifest(artifact_root)
        if manifest != session["files"]:
            raise ValueError("staged bytes changed after validation")
        seal = {
            "schema": "kch.csi-artifact-seal.v0.1.0",
            "session_id": session_id,
            "state": LifecycleState.SEALED_CANDIDATE.value,
            "spec_hash": sha256_json(session["spec"]),
            "governance_graph_hash": self.governance["graph_hash"],
            "artifact_manifest": manifest,
            "artifact_manifest_hash": sha256_json(manifest),
            "event_head_before_seal": chain["head_hash"],
            "claim_ceiling": "VALIDATED_STAGED_ARTIFACT_NO_EXTERNAL_INSTALLATION",
            "installation_authorized": False,
            "activation_authorized": False,
            "phl_real_executed": False,
            "sealed_at": utc_now(),
        }
        write_json(self.seal_root / f"{session_id}.json", seal)
        state = self.store.record_seal(session_id, seal)
        return {**state, "seal_body": seal}

    def build_and_seal(self, spec: ArtifactSpec) -> dict[str, Any]:
        session = self.create_session(spec)
        self.generate(session["session_id"])
        validated = self.validate(session["session_id"])
        if not validated["validation"]["passed"]:
            return validated
        return self.seal(session["session_id"])
