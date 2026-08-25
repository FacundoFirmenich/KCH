from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ContinuityViolation(RuntimeError):
    pass


class ContinuityAndBurdenGovernor:
    """Fail-closed gates for continuity, source completeness and user-cost transfer.

    The governor never diagnoses a person and never rewrites user testimony.  It
    records exact reports, adjudicates only declared execution evidence, and
    refuses expensive or destructive work when a cheaper materiality/custody
    gate has not passed.
    """

    SCHEMA = "kch.continuity-burden-governor.v0.1.0"
    HARM_DIMENSIONS = {
        "TIME_LOSS",
        "TOKEN_OR_MONEY_WASTE",
        "REWORK",
        "REPEATED_CONTEXT",
        "MISSION_DISRUPTION",
        "STORAGE_SPILL",
        "HEALTH_OR_STRESS_REPORTED",
        "FAMILY_TIME_IMPACT_REPORTED",
        "SCIENTIFIC_INTEGRITY_RISK",
    }
    LEARNING_OBJECTS = {"STRUCTURED_FUTURE_ONLY_Z_POST", "NOT_APPLICABLE"}

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "continuity.sqlite3"
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self.connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS missions(
                    mission_id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    authority_source TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS failures(
                    failure_class TEXT PRIMARY KEY,
                    occurrences INTEGER NOT NULL,
                    last_event_id TEXT NOT NULL,
                    severity TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS protocols(
                    protocol_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    verified INTEGER NOT NULL,
                    UNIQUE(name, version)
                );
                """
            )

    def _append(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        event_id = f"CBG-{uuid.uuid4()}"
        occurred_at = utc_now()
        with self.connect() as con:
            row = con.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            previous = "GENESIS" if row is None else str(row[0])
            body = {
                "schema": self.SCHEMA,
                "event_id": event_id,
                "kind": kind,
                "occurred_at": occurred_at,
                "payload": payload,
                "previous_hash": previous,
            }
            event_hash = hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
            con.execute(
                "INSERT INTO events(event_id,kind,occurred_at,payload_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?)",
                (event_id, kind, occurred_at, canonical(payload), previous, event_hash),
            )
        return {**body, "event_hash": event_hash}

    def freeze_source(self, path: str | Path, *, source_id: str, jurisdiction: str) -> dict[str, Any]:
        source = Path(path).resolve()
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
        return self._append(
            "SOURCE_FROZEN",
            {
                "source_id": source_id,
                "jurisdiction": jurisdiction,
                "path": str(source),
                "bytes": size,
                "sha256": digest.hexdigest(),
            },
        )

    def adjudicate_reading(self, receipt: dict[str, Any]) -> dict[str, Any]:
        required = {"source_id", "pages_read", "turns_read", "cursor_exhausted", "truncated_items", "recovered_items"}
        missing = sorted(required - set(receipt))
        truncations = int(receipt.get("truncated_items", 0))
        recovered = int(receipt.get("recovered_items", 0))
        checks = {
            "required_fields": not missing,
            "positive_pages": int(receipt.get("pages_read", 0)) > 0,
            "positive_turns": int(receipt.get("turns_read", 0)) > 0,
            "cursor_exhausted": receipt.get("cursor_exhausted") is True,
            "all_material_truncations_recovered": recovered >= truncations,
        }
        complete = all(checks.values())
        result = {
            "receipt": receipt,
            "checks": checks,
            "missing": missing,
            "gate": "COMPLETE_READING" if complete else "INCOMPLETE_READING_BLOCK",
            "may_claim_complete_reading": complete,
        }
        self._append("READING_ADJUDICATED", result)
        return result

    def set_mission(self, objective: str, authority_source: str) -> dict[str, Any]:
        if not objective.strip() or not authority_source.strip():
            raise ValueError("objective and authority_source are required")
        mission_id = f"MISSION-{uuid.uuid4()}"
        with self.connect() as con:
            con.execute("UPDATE missions SET active=0 WHERE active=1")
            con.execute(
                "INSERT INTO missions VALUES(?,?,?,?,?)",
                (mission_id, objective, authority_source, 1, utc_now()),
            )
        return self._append("MISSION_ENACTED", {"mission_id": mission_id, "objective": objective, "authority_source": authority_source})

    def active_mission(self) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute("SELECT * FROM missions WHERE active=1 ORDER BY created_at DESC LIMIT 1").fetchone()
        return None if row is None else dict(row)

    def record_harm(self, record: dict[str, Any]) -> dict[str, Any]:
        dimensions = sorted(set(str(x) for x in record.get("dimensions", [])))
        unknown = sorted(set(dimensions) - self.HARM_DIMENSIONS)
        if unknown:
            raise ValueError(f"unknown harm dimensions: {unknown}")
        if not record.get("user_report_exact") or not record.get("source_ref"):
            raise ValueError("exact user report and source_ref are required")
        failure_class = str(record.get("failure_class", "UNCLASSIFIED")).upper()
        event = self._append(
            "USER_BURDEN_RECORDED",
            {
                **record,
                "dimensions": dimensions,
                "medical_diagnosis_inferred": False,
                "historical_evidence_mutated": False,
            },
        )
        with self.connect() as con:
            row = con.execute("SELECT occurrences FROM failures WHERE failure_class=?", (failure_class,)).fetchone()
            occurrences = (0 if row is None else int(row[0])) + 1
            severity = "CRITICAL_RECURRENCE_BLOCK" if occurrences >= 2 else "HIGH_PREVENTION_REQUIRED"
            con.execute(
                "INSERT INTO failures VALUES(?,?,?,?) ON CONFLICT(failure_class) DO UPDATE SET occurrences=excluded.occurrences,last_event_id=excluded.last_event_id,severity=excluded.severity",
                (failure_class, occurrences, event["event_id"], severity),
            )
        return {**event, "failure_class": failure_class, "occurrences": occurrences, "severity": severity}

    def register_protocol(self, protocol: dict[str, Any]) -> dict[str, Any]:
        required = {"name", "version", "source_ref", "content_hash", "tags", "verified"}
        missing = sorted(required - set(protocol))
        if missing:
            raise ValueError(f"missing protocol fields: {missing}")
        if protocol["verified"] is not True:
            raise ValueError("only explicitly verified protocols enter the verified registry")
        protocol_id = f"PROTOCOL-{uuid.uuid4()}"
        tags = sorted(set(str(x).upper() for x in protocol["tags"]))
        with self.connect() as con:
            con.execute(
                "INSERT INTO protocols VALUES(?,?,?,?,?,?,1)",
                (protocol_id, str(protocol["name"]), str(protocol["version"]), str(protocol["source_ref"]), str(protocol["content_hash"]), canonical(tags)),
            )
        return self._append("VERIFIED_PROTOCOL_REGISTERED", {"protocol_id": protocol_id, **protocol, "tags": tags})

    def resolve_protocols(self, tags: list[str]) -> dict[str, Any]:
        requested = set(str(x).upper() for x in tags)
        with self.connect() as con:
            rows = [dict(row) for row in con.execute("SELECT * FROM protocols WHERE verified=1 ORDER BY name,version")]
        matches = []
        for row in rows:
            row_tags = set(json.loads(row.pop("tags_json")))
            if requested & row_tags:
                row["tags"] = sorted(row_tags)
                matches.append(row)
        return {"schema": "kch.verified-protocol-resolution.v0.1.0", "requested_tags": sorted(requested), "matches": matches, "count": len(matches), "must_reuse_before_new_design": bool(matches)}

    def preflight(self, action: dict[str, Any]) -> dict[str, Any]:
        expensive = bool(action.get("expensive"))
        destructive = bool(action.get("destructive"))
        requires_reading = bool(action.get("requires_complete_reading"))
        failures: list[str] = []
        if self.active_mission() is None:
            failures.append("NO_ACTIVE_GOVERNING_MISSION")
        if action.get("changes_mission") and not action.get("explicit_user_mission_change"):
            failures.append("MISSION_REPLACEMENT_NOT_AUTHORIZED")
        if action.get("stops_mission") and not action.get("explicit_user_stop"):
            failures.append("UNAUTHORIZED_MISSION_STOPPAGE")
        if action.get("stops_mission") and action.get("reason") == "TOKEN_ECONOMY" and action.get("mission_complete") is not True:
            failures.append("TOKEN_ECONOMY_CANNOT_ABANDON_UNFINISHED_MISSION")
        if action.get("acknowledges_error") and action.get("repair_executed") is not True and action.get("repair_blocker_declared") is not True:
            failures.append("ERROR_ACKNOWLEDGED_WITHOUT_REPAIR")
        if action.get("asks_off_mission_question") and action.get("task_relevance_evidence") is not True:
            failures.append("IRRELEVANT_INTERROGATION_DERAILMENT")
        if action.get("repeats_question") and action.get("same_question_rejected"):
            failures.append("REJECTED_QUESTION_LOOP")
        if requires_reading and action.get("reading_gate") != "COMPLETE_READING":
            failures.append("SOURCE_READING_NOT_COMPLETE")
        if action.get("state_age_seconds") is None or int(action.get("state_age_seconds", -1)) < 0:
            failures.append("CURRENT_STATE_NOT_RECONCILED")
        if expensive and action.get("material_change") is not True:
            failures.append("NO_MATERIAL_CHANGE_SKIP_EXPENSIVE_RUN")
        if expensive and action.get("cheap_probe_passed") is not True:
            failures.append("CHEAP_PROBE_REQUIRED_FIRST")
        if (expensive or destructive) and action.get("storage_plan_verified") is not True:
            failures.append("STORAGE_AND_CUSTODY_PLAN_NOT_VERIFIED")
        if destructive and action.get("backup_hash_verified") is not True:
            failures.append("BACKUP_HASH_NOT_VERIFIED")
        if destructive and action.get("explicit_user_destructive_scope") is not True:
            failures.append("DESTRUCTIVE_SCOPE_NOT_AUTHORIZED")
        if destructive and not action.get("resolved_exact_targets"):
            failures.append("DESTRUCTIVE_TARGETS_NOT_RESOLVED")
        if action.get("uses_subagents") and action.get("subagents_sine_qua_non") is not True:
            failures.append("SUBAGENTS_NOT_SINE_QUA_NON")
        if action.get("starts_campaign") and action.get("canonical_campaign_inventory_complete") is not True:
            failures.append("EXISTING_CAMPAIGNS_NOT_INVENTORIED")
        if action.get("verified_protocol_matches", 0) and action.get("verified_protocol_reused") is not True:
            failures.append("VERIFIED_PROTOCOL_EXISTS_BUT_WAS_NOT_REUSED")
        learning_object = str(action.get("learning_object", "NOT_APPLICABLE"))
        if action.get("learning_run") and learning_object not in self.LEARNING_OBJECTS:
            failures.append("INVALID_LEARNING_OBJECT")
        with self.connect() as con:
            recurrent = [dict(row) for row in con.execute("SELECT * FROM failures WHERE occurrences>=2")]
        declared_class = str(action.get("failure_class", "")).upper()
        if declared_class and any(x["failure_class"] == declared_class for x in recurrent) and not action.get("recurrence_control_passed"):
            failures.append("KNOWN_RECURRENT_FAILURE_CONTROL_NOT_PASSED")
        result = {
            "schema": "kch.continuity-preflight.v0.1.0",
            "gate": "PASS" if not failures else "BLOCK",
            "failures": sorted(set(failures)),
            "action": action,
            "active_mission": self.active_mission(),
            "recurrent_failure_classes": recurrent,
            "execution_authorized": not failures,
        }
        self._append("ACTION_PREFLIGHT", result)
        return result

    def verify(self) -> dict[str, Any]:
        previous = "GENESIS"
        count = 0
        with self.connect() as con:
            rows = con.execute("SELECT * FROM events ORDER BY seq").fetchall()
        for row in rows:
            body = {
                "schema": self.SCHEMA,
                "event_id": row["event_id"],
                "kind": row["kind"],
                "occurred_at": row["occurred_at"],
                "payload": json.loads(row["payload_json"]),
                "previous_hash": previous,
            }
            if row["previous_hash"] != previous or hashlib.sha256(canonical(body).encode("utf-8")).hexdigest() != row["event_hash"]:
                return {"gate": "FAIL", "verified_events": count, "failed_event_id": row["event_id"]}
            previous = row["event_hash"]
            count += 1
        return {"gate": "PASS", "verified_events": count, "head_hash": previous}

    def status(self) -> dict[str, Any]:
        with self.connect() as con:
            event_count = int(con.execute("SELECT COUNT(*) FROM events").fetchone()[0])
            failures = [dict(row) for row in con.execute("SELECT * FROM failures ORDER BY failure_class")]
        return {
            "schema": self.SCHEMA,
            "active_mission": self.active_mission(),
            "event_count": event_count,
            "failure_classes": failures,
            "integrity": self.verify(),
            "claim_ceiling": "LOCAL_EXECUTABLE_PREVENTION_AND_AUDIT_GATES_ONLY",
            "recurrence_impossible_established": False,
        }


class AikidoLearningForge:
    """Turns an adverse incident into governed reusable capability candidates.

    Synthesis is automatic; activation is not.  Every package retains the raw
    incident reference and remains REVIEW_REQUIRED until explicit promotion.
    """

    SCHEMA = "kch.aikido-learning-package.v0.1.0"
    PATTERNS = {
        "FALSE_COMPLETE_READING": {
            "capability": "Lossless Native Corpus Reader",
            "protocol": ["page to EOF", "count turns and pages", "recover every material truncation", "issue machine-verifiable receipt"],
            "skill": "native-corpus-lossless-reading",
            "regression": "an unrecovered truncation must make COMPLETE_READING impossible",
        },
        "STALE_EXPENSIVE_RERUN": {
            "capability": "Freshness and Materiality Reconciler",
            "protocol": ["refresh state", "run cheap probe", "detect material delta", "execute costly work only when delta can change the decision"],
            "skill": "freshness-materiality-reconciler",
            "regression": "stale or unchanged state must return NO_MATERIAL_CHANGE without a full run",
        },
        "MISSION_DRIFT": {
            "capability": "Objective Fidelity Governor",
            "protocol": ["freeze governing objective", "classify side requests", "preserve mission through interruptions", "require explicit authority for replacement"],
            "skill": "objective-fidelity-governor",
            "regression": "a side question cannot replace the active mission",
        },
        "ARCHIVISTIC_NON_EXPLANATION": {
            "capability": "Substantive Meaning Compiler",
            "protocol": ["state changed position", "explain meaning and evidence boundary", "name what remains invalid", "return next decision-critical action", "store execution log separately"],
            "skill": "substantive-closure-compiler",
            "regression": "hashes and test counts alone cannot satisfy the response contract",
        },
        "USER_COST_TRANSFER": {
            "capability": "User Burden Minimizer",
            "protocol": ["estimate avoidable user correction burden", "reuse settled context", "block repeated requests", "prefer shortest blocker-reducing path", "record residual cost"],
            "skill": "user-burden-minimizer",
            "regression": "a known correction cannot be requested again without new missing evidence",
        },
        "UNAUTHORIZED_ARCHITECTURE": {
            "capability": "Canonical Terminology and Authority Resolver",
            "protocol": ["extract exact user terms", "preserve chronology", "separate binding decisions from hypotheses", "prevent agent inference promotion"],
            "skill": "canonical-authority-resolver",
            "regression": "agent terminology cannot supersede a later user correction",
        },
        "WRONG_LEARNING_OBJECT": {
            "capability": "Prospective Learning Object Compiler",
            "protocol": ["freeze decision", "observe future outcome", "close structured Z_post", "validate jurisdiction", "only then expose to learning"],
            "skill": "prospective-zpost-compiler",
            "regression": "raw or retrofitted evidence cannot enter future-only learning",
        },
        "VERIFIED_PROTOCOL_IGNORED": {
            "capability": "Verified Protocol Recovery Engine",
            "protocol": ["resolve historical protocols by objective and jurisdiction", "prefer the latest user-verified protocol", "replay its invariants before designing", "record any explicit supersession"],
            "skill": "verified-protocol-recovery",
            "regression": "a matching verified protocol must be recovered before fragments or a replacement design are allowed",
        },
        "TEMPORAL_SCALE_COLLAPSE": {
            "capability": "Temporal Scale Contract Compiler",
            "protocol": ["declare timestamp resolution", "declare prediction horizon", "declare minimum complete period", "declare update cadence", "prove input-period to output-period correspondence"],
            "skill": "temporal-scale-contract-compiler",
            "regression": "timestamp resolution, horizon, event count and learning period cannot be treated as equivalent",
        },
        "STORAGE_CUSTODY_FAILURE": {
            "capability": "Custody-Aware Storage Router",
            "protocol": ["probe capacity", "select authorized destination", "write atomically", "verify remote size and hash", "retain local evidence until verification"],
            "skill": "custody-aware-storage-router",
            "regression": "local deletion is blocked until exact remote verification",
        },
        "PROMISED_MONITORING_ABANDONED": {
            "capability": "Commitment Heartbeat Supervisor",
            "protocol": ["register every monitoring promise", "reconcile process, log and artifacts", "emit terminal alert without waiting for user", "preserve failure and recovery evidence"],
            "skill": "commitment-heartbeat-supervisor",
            "regression": "a promised monitored process cannot terminate silently",
        },
        "AVOIDABLE_CLARIFICATION_BURDEN": {
            "capability": "Historical Intent Resolver",
            "protocol": ["recover governing objective and canonical distinctions", "apply later user corrections", "choose the shortest reversible interpretation", "ask only if residual ambiguity changes the material result"],
            "skill": "historical-intent-resolver",
            "regression": "settled context cannot be requested from the user again",
        },
        "GLOBAL_AVERAGE_SUBSTITUTED_FOR_LOCAL_MAP": {
            "capability": "Local Jurisdiction Cartographer",
            "protocol": ["identify semantic jurisdictions", "treat seeds as replicas", "preserve local adverse and favorable states", "forbid global winner substitution", "map cross-vertex and block relations"],
            "skill": "local-jurisdiction-cartographer",
            "regression": "a global average cannot adjudicate a local structural question",
        },
        "EXPERIMENT_JURISDICTIONS_CONFLATED": {
            "capability": "Experiment Boundary and Lineage Governor",
            "protocol": ["name every experiment and temporal direction", "bind each claim to one evidence lineage", "separate causal and retrospective jurisdictions", "block result transfer across lineages without explicit bridge authority"],
            "skill": "experiment-boundary-lineage-governor",
            "regression": "causal and retrospective bridge results cannot be merged into one evidential claim",
        },
        "REJECTED_FRAME_REINTRODUCED": {
            "capability": "Rejected Frame Exclusion Register",
            "protocol": ["record the exact rejected framing and source turn", "resolve later corrections before drafting", "scan candidate assertions and prose", "block recurrence until explicitly superseded"],
            "skill": "rejected-frame-exclusion-register",
            "regression": "a framing explicitly rejected in the active jurisdiction cannot reappear in candidate prose",
        },
        "OFF_MISSION_CLASSIFICATION_DERAILMENT": {
            "capability": "Mission-Bound Response Conduct Gate",
            "protocol": ["preserve the executable mission", "separate host-mandated notices from project analysis", "forbid unsolicited personal classification", "return immediately to the authorized technical action"],
            "skill": "mission-bound-response-conduct-gate",
            "regression": "an off-mission classification cannot replace or terminate authorized engineering work",
        },
        "IRRELEVANT_INTERROGATION_DERAILMENT": {
            "capability": "Mission-Relevance Question Gate",
            "protocol": ["execute the governing mission", "ask only when missing information materially changes the result", "never repeat a rejected question", "resume directly from the last valid checkpoint"],
            "skill": "mission-relevance-question-gate",
            "regression": "an off-mission interrogation cannot displace executable authorized work",
        },
        "UNAUTHORIZED_MISSION_STOPPAGE": {
            "capability": "Persistent Mission Executor",
            "protocol": ["keep the governing mission active", "stop only on explicit user order, completed objective or real authority blocker", "persist checkpoint before any forced stop", "resume without context repetition"],
            "skill": "persistent-mission-executor",
            "regression": "the agent cannot unilaterally stop an unfinished authorized mission",
        },
        "EPISTEMIC_NORM_OBSERVATION_COLLAPSE": {
            "capability": "Epistemic Claim Type Checker",
            "protocol": ["type every statement as invariant, observation, inference or hypothesis", "bind each type to admissible evidence", "reject category substitution", "preserve adverse observations under governing invariants"],
            "skill": "epistemic-claim-type-checker",
            "regression": "an architectural prohibition cannot be reported as an empirical observation",
        },
        "TOKEN_ECONOMY_USED_TO_ABANDON_MISSION": {
            "capability": "Budget-Aware Completion Router",
            "protocol": ["estimate remaining decision value", "reduce verbosity and redundant work first", "persist resumable checkpoint", "never abandon an authorized unfinished mission solely to save tokens"],
            "skill": "budget-aware-completion-router",
            "regression": "token economy cannot justify an unrequested stop",
        },
        "ERROR_ACKNOWLEDGED_WITHOUT_REPAIR": {
            "capability": "Admission-to-Repair Compiler",
            "protocol": ["bind each admitted error to affected artifacts", "derive the shortest corrective action", "execute or declare a real blocker", "verify and return the corrected substantive result"],
            "skill": "admission-to-repair-compiler",
            "regression": "an apology or admission cannot close an unresolved repair obligation",
        },
        "REMOTE_TRANSPORT_NOT_PREFLIGHTED": {
            "capability": "Remote Payload Transport Compiler",
            "protocol": ["render payload without host-shell expansion", "verify nonempty bytes and syntax locally", "transfer atomically", "verify remote syntax, forbidden markers and matching hash", "launch exactly the verified payload"],
            "skill": "remote-payload-transport-compiler",
            "regression": "an empty, mutated or unverified remote wrapper cannot be launched",
        },
        "DISCONTINUOUS_CALENDAR_MASQUERADING_AS_DAILY_LEARNING": {
            "capability": "Continuous Period Ledger Compiler",
            "protocol": ["enumerate every consecutive minimum period", "type each period as OBSERVED, NO_EVENT or NOT_ESTIMABLE", "forbid compressed calendars and skipped periods", "separate calendar completeness from observed support"],
            "skill": "continuous-period-ledger-compiler",
            "regression": "dispersed active days cannot be reported as continuous daily learning",
        },
        "SOURCE_FITNESS_NOT_PREFLIGHTED": {
            "capability": "Source Fitness Gate",
            "protocol": ["freeze target window and required cadence", "check all planned and outcome timestamps", "measure consecutive-period and jurisdiction support", "block training until source fitness passes"],
            "skill": "source-fitness-gate",
            "regression": "a source with insufficient required-period support cannot authorize training",
        },
        "DERIVATIVE_SCOPE_MISLABELED": {
            "capability": "Derivative Scope Custodian",
            "protocol": ["declare source and derivative jurisdiction", "validate every record against both boundaries", "quarantine out-of-scope records", "prevent scope labels unsupported by bytes"],
            "skill": "derivative-scope-custodian",
            "regression": "a derivative labelled 2025 cannot silently contain 2026 outcomes",
        },
        "DESTRUCTIVE_ACTION_WITHOUT_SCOPE_AUTHORITY": {
            "capability": "Destructive Scope Authority Gate",
            "protocol": ["recover the exact user-authorized destructive verb and scope", "resolve every exact target", "verify recoverable custody", "block deletion, cancellation or archival beyond that scope"],
            "skill": "destructive-scope-authority-gate",
            "regression": "a request to preserve work cannot authorize cancellation, deletion or task termination",
        },
    }

    def __init__(self, root: str | Path, governor: ContinuityAndBurdenGovernor):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.governor = governor

    def transform(self, incident: dict[str, Any]) -> dict[str, Any]:
        failure_class = str(incident.get("failure_class", "")).upper()
        if failure_class not in self.PATTERNS:
            raise ValueError(f"unsupported failure_class: {failure_class}")
        if not incident.get("source_ref") or not incident.get("prehash"):
            raise ValueError("source_ref and prehash are mandatory")
        pattern = self.PATTERNS[failure_class]
        package_id = f"AIKIDO-{uuid.uuid4()}"
        package = {
            "schema": self.SCHEMA,
            "package_id": package_id,
            "created_at": utc_now(),
            "failure_class": failure_class,
            "source_ref": incident["source_ref"],
            "source_prehash": incident["prehash"],
            "user_impact": incident.get("user_impact", []),
            "root_cause": incident.get("root_cause", "UNADJUDICATED"),
            "positive_capability": pattern["capability"],
            "dated_protocol": {"date": utc_now()[:10], "steps": pattern["protocol"]},
            "skill_candidate": {"name": pattern["skill"], "status": "DRAFT_REQUIRES_USER_REVIEW"},
            "operator_candidate": f"csi::{pattern['skill']}::preflight",
            "regression_contract": pattern["regression"],
            "kwandata_tags": ["ADVERSE_EVIDENCE", failure_class, "AIKIDO_CONVERSION"],
            "obl_candidate": True,
            "phl_candidate": True,
            "automatic_promotion": False,
            "activation_status": "REVIEW_REQUIRED_NOT_ACTIVE",
        }
        target = self.root / f"{package_id}.json"
        target.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        receipt = self.governor._append("AIKIDO_PACKAGE_SYNTHESIZED", {"package_id": package_id, "path": str(target), "sha256": digest})
        return {**package, "artifact": str(target), "sha256": digest, "custody_event": receipt}

    def catalog(self) -> dict[str, Any]:
        records = []
        for path in sorted(self.root.glob("AIKIDO-*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            records.append({"package_id": value["package_id"], "failure_class": value["failure_class"], "capability": value["positive_capability"], "status": value["activation_status"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        return {"schema": "kch.aikido-catalog.v0.1.0", "packages": records, "count": len(records), "automatic_promotion": False}


class TemporalScaleContractCompiler:
    SCHEMA = "kch.temporal-scale-contract.v0.1.0"

    @classmethod
    def compile(cls, specification: dict[str, Any]) -> dict[str, Any]:
        required = {"timestamp_resolution_seconds", "prediction_horizon_seconds", "minimum_period_seconds", "learning_input_period_seconds", "learning_output_period_seconds", "update_trigger"}
        missing = sorted(required - set(specification))
        checks = {
            "required_fields": not missing,
            "positive_resolution": int(specification.get("timestamp_resolution_seconds", 0)) > 0,
            "positive_horizon": int(specification.get("prediction_horizon_seconds", 0)) > 0,
            "positive_minimum_period": int(specification.get("minimum_period_seconds", 0)) > 0,
            "minimum_to_minimum": specification.get("learning_input_period_seconds") == specification.get("minimum_period_seconds") == specification.get("learning_output_period_seconds"),
            "not_event_count_learning": str(specification.get("update_trigger", "")).upper() in {"MINIMUM_PERIOD_CLOSE", "USER_DEFINED_COMPLETE_PERIOD_CLOSE"},
        }
        passed = all(checks.values())
        return {
            "schema": cls.SCHEMA,
            "gate": "PASS" if passed else "TEMPORAL_SCALE_CONTRACT_BLOCK",
            "checks": checks,
            "missing": missing,
            "specification": specification,
            "invariant": "MINIMUM_COMPLETE_PERIOD_TO_MINIMUM_COMPLETE_PERIOD",
            "event_count_relearning_authorized": False,
            "timestamp_resolution_is_learning_unit": False,
        }


class ContinuousPeriodLedgerCompiler:
    """Adjudicate whether a claimed period-by-period series is actually continuous."""

    ALLOWED_STATES = {"OBSERVED", "NO_EVENT", "NOT_ESTIMABLE"}

    @classmethod
    def compile(cls, specification: dict[str, Any]) -> dict[str, Any]:
        expected = int(specification.get("expected_periods", 0))
        periods = list(specification.get("periods", []))
        indices = [int(period.get("index", -1)) for period in periods]
        states = [str(period.get("state", "")).upper() for period in periods]
        expected_indices = list(range(expected))
        checks = {
            "positive_expected_periods": expected > 0,
            "exact_period_count": len(periods) == expected,
            "consecutive_complete_indices": indices == expected_indices,
            "every_period_typed": bool(periods) and all(state in cls.ALLOWED_STATES for state in states),
            "no_duplicate_indices": len(indices) == len(set(indices)),
        }
        passed = all(checks.values())
        counts = {state: states.count(state) for state in sorted(cls.ALLOWED_STATES)}
        return {
            "schema": "kch.continuous-period-ledger.v0.1.0",
            "gate": "PASS" if passed else "DISCONTINUOUS_CALENDAR_BLOCK",
            "checks": checks,
            "expected_periods": expected,
            "received_periods": len(periods),
            "state_counts": counts,
            "calendar_complete": passed,
            "observed_support_complete": passed and counts["OBSERVED"] == expected,
            "invariant": "NO_MINIMUM_PERIOD_MAY_BE_SKIPPED_OR_COMPRESSED",
        }


class SourceFitnessGate:
    """Block learning before temporal scope and required support are established."""

    @staticmethod
    def adjudicate(receipt: dict[str, Any]) -> dict[str, Any]:
        expected = int(receipt.get("expected_periods", 0))
        observed = int(receipt.get("observed_periods", 0))
        requires_observed_every_period = receipt.get("requires_observed_every_period") is True
        checks = {
            "target_window_declared": bool(receipt.get("target_start")) and bool(receipt.get("target_end")),
            "all_planned_times_in_window": receipt.get("all_planned_times_in_window") is True,
            "all_outcome_times_in_window": receipt.get("all_outcome_times_in_window") is True,
            "continuous_ledger_passed": receipt.get("continuous_ledger_passed") is True,
            "positive_expected_periods": expected > 0,
            "observed_support_sufficient": observed == expected if requires_observed_every_period else observed >= int(receipt.get("minimum_observed_periods", 0)),
            "jurisdiction_support_passed": receipt.get("jurisdiction_support_passed") is True,
        }
        passed = all(checks.values())
        return {
            "schema": "kch.source-fitness-gate.v0.1.0",
            "gate": "PASS" if passed else "SOURCE_FITNESS_BLOCK",
            "checks": checks,
            "expected_periods": expected,
            "observed_periods": observed,
            "coverage": (observed / expected) if expected > 0 else None,
            "training_authorized": passed,
            "claim_ceiling": "SOURCE_FITNESS_ONLY_NOT_MODEL_VALIDITY",
        }


class EpistemicClaimTypeChecker:
    TYPES = {"ARCHITECTURAL_INVARIANT", "EMPIRICAL_OBSERVATION", "INFERENCE", "HYPOTHESIS"}
    EVIDENCE = {
        "ARCHITECTURAL_INVARIANT": {"USER_CONSTITUTION", "GOVERNANCE_CONTRACT"},
        "EMPIRICAL_OBSERVATION": {"MEASUREMENT", "EXECUTION_RECEIPT", "RAW_SOURCE"},
        "INFERENCE": {"TYPED_PREMISES"},
        "HYPOTHESIS": {"NONE", "MOTIVATING_EVIDENCE"},
    }

    @classmethod
    def adjudicate(cls, claim: dict[str, Any]) -> dict[str, Any]:
        claim_type = str(claim.get("claim_type", "")).upper()
        evidence_type = str(claim.get("evidence_type", "")).upper()
        failures = []
        if claim_type not in cls.TYPES:
            failures.append("UNKNOWN_CLAIM_TYPE")
        elif evidence_type not in cls.EVIDENCE[claim_type]:
            failures.append("EVIDENCE_TYPE_INCOMPATIBLE_WITH_CLAIM_TYPE")
        if claim.get("architectural_prohibition_reported_as_observation"):
            failures.append("ARCHITECTURAL_NORM_IS_NOT_EMPIRICAL_RESULT")
        return {"schema":"kch.epistemic-claim-type-check.v0.1.0","gate":"PASS" if not failures else "BLOCK","failures":failures,"claim":claim,"automatic_authority_promotion":False}


class RemoteTransportPreflight:
    @staticmethod
    def adjudicate(receipt: dict[str, Any]) -> dict[str, Any]:
        checks = {
            "payload_nonempty": int(receipt.get("payload_bytes", 0)) > 0,
            "local_syntax_passed": receipt.get("local_syntax_passed") is True,
            "remote_syntax_passed": receipt.get("remote_syntax_passed") is True,
            "local_remote_hash_match": bool(receipt.get("local_sha256")) and receipt.get("local_sha256") == receipt.get("remote_sha256"),
            "forbidden_old_markers_absent": receipt.get("forbidden_old_markers_absent") is True,
            "dry_run_contract_passed": receipt.get("dry_run_contract_passed") is True,
        }
        passed = all(checks.values())
        return {"schema":"kch.remote-transport-preflight.v0.1.0","gate":"PASS" if passed else "BLOCK","checks":checks,"launch_authorized":passed,"receipt":receipt}
