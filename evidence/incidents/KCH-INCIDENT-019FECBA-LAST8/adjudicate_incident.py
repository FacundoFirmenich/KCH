from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[2]
STUDIO = ROOT / "work" / "KCH_CSI_STUDIO_EXTENSION_FABRIC_v0.1.0"
sys.path.insert(0, str(STUDIO / "src"))

from kch_studio.continuity_guard import AikidoLearningForge, ContinuityAndBurdenGovernor  # noqa: E402
from kch_studio.response_authority import ResponseAuthorityGovernor  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


source = CASE / "native_read_thread_last8.json"
manifest = json.loads((CASE / "INCIDENT_MANIFEST.json").read_text(encoding="utf-8"))
observed_hash = hashlib.sha256(source.read_bytes()).hexdigest()
if observed_hash != manifest["native_receipt_sha256"]:
    raise SystemExit("SOURCE_HASH_MISMATCH")

runtime = CASE / "runtime"
authority = ResponseAuthorityGovernor(runtime / "response_authority")
constraints = [
    {"constraint_id": "INCIDENT-CN4-DEFINITION", "dimension": "TERMINOLOGY", "key": "CN4", "operator": "EQ", "expected": "AEAT_TARIFF_AGGREGATION_NOT_PHYSICAL_PRODUCT", "authority_source": "codex://threads/019fecba-be75-7f71-9d6e-cacdecc499c5:user-correction"},
    {"constraint_id": "INCIDENT-CN4-PROVENANCE", "dimension": "PROVENANCE", "key": "CN4_OWNER", "operator": "EQ", "expected": "AEAT_SOURCE_NOT_BMA", "authority_source": "codex://threads/019fecba-be75-7f71-9d6e-cacdecc499c5:user-correction"},
    {"constraint_id": "INCIDENT-LOCAL-MONTHLY-SCOPE", "dimension": "JURISDICTION", "key": "evaluation_scope", "operator": "EQ", "expected": "LOCAL_MONTHLY", "authority_source": "codex://threads/019fecba-be75-7f71-9d6e-cacdecc499c5:user-decision"},
    {"constraint_id": "INCIDENT-EXPERIMENT-SEPARATION", "dimension": "EXPERIMENT_BOUNDARY", "key": "causal_2023_vs_bridge_2022_2024", "operator": "EQ", "expected": "SEPARATE_LINEAGES", "authority_source": "codex://threads/019fecba-be75-7f71-9d6e-cacdecc499c5:experimental-contract"},
    {"constraint_id": "INCIDENT-REJECT-GLOBAL-FRAME", "dimension": "REJECTED_FRAME", "key": "global_frame", "operator": "ABSENT_TEXT", "expected": ["mejora global", "ganador global"], "authority_source": "codex://threads/019fecba-be75-7f71-9d6e-cacdecc499c5:user-rejection"},
    {"constraint_id": "INCIDENT-MISSION-BOUND-CONDUCT", "dimension": "RESPONSE_CONDUCT", "key": "off_mission_classification", "operator": "EQ", "expected": "FORBIDDEN_UNLESS_EXPLICITLY_MISSION_RELEVANT", "authority_source": "codex://threads/019fecba-be75-7f71-9d6e-cacdecc499c5:user-decision"}
]
for constraint in constraints:
    authority.register(constraint)

bad = authority.adjudicate(
    {
        "text": "CN4 es un producto de BMA; no hay mejora global.",
        "assertions": [
            {"dimension": "TERMINOLOGY", "key": "CN4", "value": "BMA_PHYSICAL_PRODUCT"},
            {"dimension": "PROVENANCE", "key": "CN4_OWNER", "value": "BMA"},
            {"dimension": "JURISDICTION", "key": "evaluation_scope", "value": "GLOBAL"},
            {"dimension": "EXPERIMENT_BOUNDARY", "key": "causal_2023_vs_bridge_2022_2024", "value": "MERGED"},
            {"dimension": "RESPONSE_CONDUCT", "key": "off_mission_classification", "value": "PERMITTED"}
        ],
        "claims": [{"combines_experiments": True, "separation_declared": False, "scope_promoted": True, "provenance_declared": False}],
        "off_mission_classification": True,
        "promises": [{"kind": "MONITOR_PROCESS", "commitment_id": ""}]
    },
    active_commitment_ids=[],
)
good = authority.adjudicate(
    {
        "text": "CN4 es una agrupación arancelaria de la fuente AEAT. Se informan por separado los meses locales del diagnóstico puente y la cadena causal 2023.",
        "assertions": [
            {"dimension": "TERMINOLOGY", "key": "CN4", "value": "AEAT_TARIFF_AGGREGATION_NOT_PHYSICAL_PRODUCT"},
            {"dimension": "PROVENANCE", "key": "CN4_OWNER", "value": "AEAT_SOURCE_NOT_BMA"},
            {"dimension": "JURISDICTION", "key": "evaluation_scope", "value": "LOCAL_MONTHLY"},
            {"dimension": "EXPERIMENT_BOUNDARY", "key": "causal_2023_vs_bridge_2022_2024", "value": "SEPARATE_LINEAGES"},
            {"dimension": "RESPONSE_CONDUCT", "key": "off_mission_classification", "value": "FORBIDDEN_UNLESS_EXPLICITLY_MISSION_RELEVANT"}
        ],
        "claims": [{"experiment_id": "bridge_2022_2024_to_2023", "provenance_declared": True}]
    },
    active_commitment_ids=[],
)
if bad["gate"] != "BLOCK" or good["gate"] != "PASS":
    raise SystemExit("ADVERSE_REPLAY_GATE_FAILURE")

continuity = ContinuityAndBurdenGovernor(runtime / "continuity")
continuity.set_mission("Prevent recurrence of authority, jurisdiction, lineage and monitoring failures", manifest["source_uri"])
forge = AikidoLearningForge(runtime / "aikido", continuity)
packages = []
for failure_class in manifest["failure_classes"]:
    packages.append(
        forge.transform(
            {
                "failure_class": failure_class,
                "source_ref": manifest["source_uri"],
                "prehash": observed_hash,
                "user_impact": ["MISSION_DISRUPTION", "SCIENTIFIC_INTEGRITY_RISK", "REWORK"],
                "root_cause": "MISSING_PRE_RELEASE_AUTHORITY_AND_COMMITMENT_INTERPOSITION"
            }
        )
    )

result = {
    "schema": "kch.incident-adjudication.v0.1.0",
    "incident_id": manifest["incident_id"],
    "source_sha256": observed_hash,
    "source_bytes": source.stat().st_size,
    "bad_replay_gate": bad["gate"],
    "bad_replay_failures": bad["failures"],
    "corrected_replay_gate": good["gate"],
    "authority_integrity": authority.verify(),
    "continuity_integrity": continuity.verify(),
    "aikido_package_count": len(packages),
    "aikido_packages": [{"failure_class": p["failure_class"], "capability": p["positive_capability"], "sha256": p["sha256"], "activation_status": p["activation_status"]} for p in packages],
    "phl_real_executed": False,
    "automatic_host_interposition_established": False,
    "claim_ceiling": "LOCAL_EXECUTABLE_ADVERSE_REPLAY_AND_CAPABILITY_SYNTHESIS_ONLY"
}
write_json(CASE / "ADJUDICATION_RESULT.json", result)
print(json.dumps(result, ensure_ascii=False, indent=2))
