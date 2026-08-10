from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kch_studio.account_broker import AccountPermissionBroker
from kch_studio.checkpoints import CheckpointManager
from kch_studio.clipboard_hub import ClipboardHub
from kch_studio.constitutional import Actor, ConstitutionalAuthorityError, ConstitutionalWorkspace
from kch_studio.construct_mode import ConstructMode
from kch_studio.diction_learning import DictionLearning
from kch_studio.kwandata import KwanData
from kch_studio.permissions import PermissionGovernor
from kch_studio.persistence import PersistenceHub
from kch_studio.proactive import ProgrammedPolicy
from kch_studio.scheduler import CronExpression
from kch_studio.universal_text import UniversalAssetStore


def test_constitution_is_user_sovereign_and_every_edit_is_recoverable(tmp_path: Path) -> None:
    workspace = ConstitutionalWorkspace(tmp_path / "constitution")
    initial = workspace.state()
    assert len(initial["boxes"]) == 1 and initial["boxes"][0]["content"] == ""
    box_id = initial["first_box_id"]
    with pytest.raises(ConstitutionalAuthorityError):
        workspace.update_box(box_id, "modelo no autorizado", actor=Actor.MODEL)
    workspace.update_box(box_id, "no abandonar la misión inicial", actor=Actor.USER)
    workspace.update_box(box_id, "misión inicial inviolable", actor=Actor.USER)
    assert workspace.effective_mandates()["mandates"][0]["content"] == "misión inicial inviolable"
    assert workspace.vault.revision(workspace.key, 2, decode=True)["seq"] == 2
    proposal = workspace.propose({"operation": "add_box", "content": "solo propuesta"})
    assert proposal["status"] == "PROPOSED_NOT_ENACTED"
    assert len(workspace.state()["boxes"]) == 1


def test_programmed_policy_is_direct_default_and_model_cannot_rewrite_it(tmp_path: Path) -> None:
    policy = ProgrammedPolicy(tmp_path / "policy")
    decisions = policy.evaluate_all(
        {"type": "change.proposed", "proposal": {"deletes_history": True}}
    )
    assert decisions[0]["decision"] == "DIRECT"
    assert decisions[0]["tool"] == "risk_assess"
    state = policy.state()
    with pytest.raises(ConstitutionalAuthorityError):
        policy.replace(state, actor=Actor.MODEL)
    changed = policy.set_preferences(announce_on_session_start=False, actor=Actor.USER)
    assert changed["policy"]["announce_on_session_start"] is False


def test_universal_text_exact_roundtrip_and_derivative(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(bytes(range(256)) * 3)
    store = UniversalAssetStore(tmp_path / "universal")
    manifest = store.ingest(source)
    restored = store.restore_original(manifest["asset_id"], "roundtrip/source.bin")
    assert restored["state"] == "RESTORED_EXACT_BYTES"
    assert Path(restored["path"]).read_bytes() == source.read_bytes()

    text = tmp_path / "note.txt"
    text.write_text("KCH exacto\n", encoding="utf-8")
    text_asset = store.ingest(text)
    docx = store.transform(text_asset["asset_id"], "docx")
    assert Path(docx["path"]).read_bytes().startswith(b"PK")
    assert docx["exact_original_recovery"] is True


def test_persistence_keeps_chat_identity_and_sco_does_not_merge(tmp_path: Path) -> None:
    hub = PersistenceHub(tmp_path / "persistence")
    a = hub.create_chat(platform="Codex", title="arquitectura")
    b = hub.create_chat(platform="Cline", title="implementación")
    hub.append_turn(a["chat_id"], role="user", payload={"text": "objetivo"})
    assert hub.verify_chat(a["chat_id"])["passed"] is True
    sco = hub.create_superchat(
        title="KCH",
        members=[
            {"chat_id": a["chat_id"], "subsystem_role": "ARCHITECT", "rank": 1},
            {"chat_id": b["chat_id"], "subsystem_role": "BUILDER", "rank": 2},
        ],
    )
    assert sco["context_fusion"] is False
    assert sco["member_independence_preserved"] is True
    assert {m["chat_id"] for m in sco["members"]} == {a["chat_id"], b["chat_id"]}


def test_persistence_never_promotes_caller_eof_to_verified_transport(tmp_path: Path) -> None:
    hub = PersistenceHub(tmp_path / "persistence")
    chat = hub.create_chat(
        platform="Codex",
        title="external source",
        source_uri="codex://threads/example",
        capture_mode="HOST_HOOK_CONNECTED",
    )
    receipt = {
        "source_system": "Codex",
        "source_uri": "codex://threads/example",
        "page_ordinal": 1,
        "payload_sha256": "a" * 64,
        "eof_attested": True,
    }
    marked = hub.mark_page(chat["chat_id"], None, source_receipt=receipt)
    assert marked["completeness"] == "EOF_ATTESTED_UNVERIFIED"
    assert marked["page_adjudication"]["transport_completeness_verified"] is False
    assert marked["page_adjudication"]["claim_ceiling"] == "CALLER_ATTESTATION_ONLY"
    assert hub.verify_chat(chat["chat_id"])["passed"] is True

    with pytest.raises(ValueError, match="must agree"):
        hub.mark_page(chat["chat_id"], "cursor-2", source_receipt=receipt)


def test_kwandata_structures_csv_tsv_json_and_supertags(tmp_path: Path) -> None:
    csv_path = tmp_path / "items.csv"
    csv_path.write_text("name,kind\nKCH,harness\nMIS,service\n", encoding="utf-8")
    tsv_path = tmp_path / "items.tsv"
    tsv_path.write_text("name\tkind\nSCO\torchestrator\n", encoding="utf-8")
    json_path = tmp_path / "items.json"
    json_path.write_text(json.dumps([{"name": "KwanData", "kind": "data"}]), encoding="utf-8")
    data = KwanData(tmp_path / "kwandata")
    for source in (csv_path, tsv_path, json_path):
        assert data.ingest(source)["record_count"] >= 1
    assert any(item["data"].get("name") == "SCO" for item in data.query("SCO"))
    # Creation accepts tag names and retains relations; exact availability is asserted by state.
    supertag = data.create_supertag("kch:core", ["source:csv", "source:json"])
    assert supertag["child_count"] == 2
    assert data.status()["records"] == 4


def test_permissions_and_account_leases_are_finite(tmp_path: Path) -> None:
    governor = PermissionGovernor(tmp_path / "permissions")
    denied = governor.decide(
        actor="MODEL", resource="file://external/C:/evidence.txt", operation="READ"
    )
    assert denied["authorized"] is False
    expiry = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
    rule = governor.grant(
        actor_pattern="MODEL",
        resource_pattern="file://external/C:/evidence.txt",
        operation_pattern="READ",
        effect="ALLOW",
        priority=5000,
        expires_at=expiry,
        rationale="lectura puntual",
        enacting_actor=Actor.USER,
    )
    assert (
        governor.decide(
            actor="MODEL", resource="file://external/C:/evidence.txt", operation="READ"
        )["authorized"]
        is True
    )
    with pytest.raises(ConstitutionalAuthorityError):
        governor.revoke(rule["rule_id"], enacting_actor=Actor.MODEL)

    broker = AccountPermissionBroker(tmp_path / "accounts", governor)
    request = broker.request(provider="GITHUB", scopes=["repo:read"], purpose="gate")
    assert request["forever_available"] is False
    lease = broker.approve(request["request_id"], duration_class="PUNCTUAL")
    assert lease["forever"] is False and lease["max_uses"] == 1


def test_clipboard_postit_versions_and_sensitive_default(tmp_path: Path) -> None:
    hub = ClipboardHub(tmp_path / "clipboard")
    secret = hub.capture(
        "ghp_abcdefghijklmnopqrstuvwxyz0123456789", kind="TEXT", media_type="text/plain"
    )
    assert secret["sensitive"] is True and secret["persisted"] is False
    note = hub.create_postit(title="Misión", body="persistir todo", tags=["kch"])
    edited = hub.edit_postit(note["postit_id"], body="persistir absolutamente todo")
    assert edited["revision"] == 2
    assert hub.search("absolutamente")["postits"][0]["postit_id"] == note["postit_id"]


def test_diction_corrects_msi_to_mis_without_real_phl(tmp_path: Path) -> None:
    diction = DictionLearning(tmp_path / "diction")
    result = diction.resolve(
        "el gobierno de MSI no está integrado; permission y permissions quedan intactos"
    )
    assert "MIS" in result["normalized_transcription"]
    assert "permission y permissions" in result["normalized_transcription"]
    assert "perMISsion" not in result["normalized_transcription"]
    assert result["raw_transcription"].startswith("el gobierno de MSI")
    correction = diction.record_correction(
        raw_token="MSI", corrected_term="MIS", confirmed_by_user=True
    )
    assert correction["phl_state"] == "STAGED_USER_CONFIRMED_UNTRAINED"
    assert diction.status()["phl_real_executed"] is False
    assert diction.resolve("MSI")["normalized_transcription"] == "MIS"


def test_structured_checkpoint_deduplicates_traces_and_restores(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    managed.mkdir()
    (managed / "a.txt").write_text("uno", encoding="utf-8")
    manager = CheckpointManager(tmp_path / "checkpoint-engine", {"project": managed})
    first = manager.create_structured("primero", actor=Actor.USER)
    (managed / "a.txt").write_text("dos", encoding="utf-8")
    (managed / "b.txt").write_text("uno", encoding="utf-8")
    second = manager.create_structured("segundo", actor=Actor.USER)
    assert second["graph"]["modified"] == [["project", "a.txt"]]
    assert second["deduplicated_reused_bytes"] >= 3
    trace = manager.trace_file("project", "a.txt")
    assert len(trace) == 2 and trace[0]["sha256"] != trace[1]["sha256"]
    destination = tmp_path / "restore"
    restored = manager.restore_to_new_root(first["checkpoint_id"], destination, actor=Actor.USER)
    assert restored["all_hashes_verified"] is True
    assert (destination / "project" / "a.txt").read_text(encoding="utf-8") == "uno"
    plan = manager.full_plan("gran checkpoint")
    assert (
        manager.create_full(plan["plan_id"], confirm_large_checkpoint=False, actor=Actor.USER)[
            "state"
        ]
        == "NOT_EXECUTED_USER_DID_NOT_CONFIRM"
    )


def test_construct_creates_validated_successor_and_rolls_pointer_back(tmp_path: Path) -> None:
    stable = tmp_path / "stable"
    stable.mkdir()
    (stable / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    construct = ConstructMode(tmp_path / "construct", stable)
    session = construct.start("elevar versión", actor=Actor.USER)
    assert Path(session["stable_backup"]["path"]).is_file()
    assert session["runtime_active_bytes_modified"] is False
    construct.write_file(session["session_id"], "module.py", "VALUE = 2\n", actor=Actor.USER)
    validated = construct.validate(session["session_id"], actor=Actor.USER)
    assert validated["passed"] is True
    promoted = construct.promote_for_next_start(session["session_id"], actor=Actor.USER)
    assert promoted["pointer"]["effective"] == "NEXT_START_ONLY"
    rolled = construct.rollback_pointer(actor=Actor.USER)
    assert rolled["state"] == "ROLLED_BACK_NEXT_START_POINTER"
    assert (stable / "module.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_cron_uses_standard_day_or_weekday_semantics() -> None:
    # Midnight on day 1 OR Sunday when both day fields are constrained.
    expression = CronExpression("0 0 1 * 0")
    assert expression.matches(datetime(2026, 2, 1, 0, 0))
    assert expression.matches(datetime(2026, 2, 8, 0, 0))
