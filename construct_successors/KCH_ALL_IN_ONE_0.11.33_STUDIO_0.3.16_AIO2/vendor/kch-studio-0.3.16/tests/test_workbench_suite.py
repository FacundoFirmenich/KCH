from pathlib import Path

from kch_studio.workbench_suite import WorkbenchSuite

EVIDENCE_TEXT = """\
Primero, el paso de software debe leer el archivo completo y calcular su hash.
Después, el segundo paso debe contrastar todas las líneas con el objetivo inicial.
Fallo registrado: se afirmó una lectura completa después de consultar sólo fragmentos del archivo.
Decisión vinculante: toda lectura exhaustiva debe producir recibo de bytes, líneas y SHA-256.
Este caso no demuestra validez industrial ni superioridad causal del arnés.
"""


def test_evidence_generates_dated_protocol_and_staged_skill(tmp_path: Path) -> None:
    suite = WorkbenchSuite(tmp_path / "workbench")
    receipt = suite.ingest(
        source_kind="SESSION",
        title="Caso de lectura completa",
        raw_text=EVIDENCE_TEXT,
        workspace_id="KCH-PREPILOT",
        provenance={"author_role": "USER", "turn_id": "TURN-001"},
    )

    assert receipt["raw_preserved"] is True
    assert Path(receipt["stored_path"]).read_text(encoding="utf-8") == EVIDENCE_TEXT
    assert Path(receipt["normalized_path"]).read_text(encoding="utf-8") == EVIDENCE_TEXT
    protocols = suite.protocols("KCH-PREPILOT")
    skills = suite.skills()
    assert len(protocols) == 1
    assert len(skills) == 1
    assert protocols[0]["pre_generation_hash"] == skills[0]["pre_generation_hash"]
    assert protocols[0]["created_at"][:10] in Path(protocols[0]["path"]).read_text(encoding="utf-8")
    skill_root = Path(skills[0]["path"])
    assert (skill_root / "SKILL.md").is_file()
    assert (skill_root / "references" / "PROTOCOL.md").is_file()
    assert (skill_root / "references" / "PROVENANCE.json").is_file()
    assert (skill_root / "evals" / "evals.json").is_file()
    assert skills[0]["status"] == "STAGED_UNEVALUATED"
    assert skills[0]["installed"] is False
    assert skills[0]["activated"] is False
    assert suite.verify()["gate"] == "PASS"


def test_secret_values_are_never_persisted(tmp_path: Path) -> None:
    suite = WorkbenchSuite(tmp_path / "workbench")
    fake_token = "example_secret_value_for_redaction_123456"
    fake_private_key = """-----BEGIN PRIVATE KEY-----
example-private-material-never-persist
-----END PRIVATE KEY-----"""
    receipt = suite.ingest(
        source_kind="CHAT",
        title="Entrada con referencias secretas",
        raw_text=f"token={fake_token}\n{fake_private_key}\nPrimero, no copies secretos.",
        session_id="SECRET-TEST",
    )

    assert receipt["raw_preserved"] is False
    assert receipt["storage_state"] == "REDACTED_TEXT_ONLY_ORIGINAL_SECRET_BYTES_NOT_STORED"
    assert len(receipt["secret_references"]) == 2
    for path in suite.root.rglob("*"):
        if path.is_file():
            payload = path.read_bytes()
            assert fake_token.encode() not in payload
            assert b"example-private-material-never-persist" not in payload
    assert suite.verify()["gate"] == "PASS"


def test_raw_and_normalized_are_distinct_traceable_layers(tmp_path: Path) -> None:
    def normalize(text: str) -> dict[str, object]:
        normalized = text.replace("MSI", "MIS")
        return {
            "normalized_transcription": normalized,
            "resolution_id": "RESOLUTION-1",
            "resolver_hash": "a" * 64,
            "competing_candidates": ["MSI", "MIS"],
        }

    suite = WorkbenchSuite(tmp_path / "workbench", normalizer=normalize)
    receipt = suite.ingest(
        source_kind="DICTATION",
        title="Corrección de dictado",
        raw_text="Perdón: MSI debe interpretarse como MIS en esta sesión.",
        session_id="DICTATION-1",
    )

    assert "MSI" in Path(receipt["stored_path"]).read_text(encoding="utf-8")
    assert "MIS debe" in Path(receipt["normalized_path"]).read_text(encoding="utf-8")
    assert receipt["normalization"]["normalized_changed"] is True
    assert suite.verify()["gate"] == "PASS"


def test_code_file_bypasses_diction_normalization_and_preserves_identifiers(
    tmp_path: Path,
) -> None:
    def dangerous_normalizer(text: str) -> dict[str, object]:
        return {"normalized_transcription": text.replace("mis", "MIS")}

    source = tmp_path / "permissions.py"
    source.write_text("permission = 'MIS'\npermissions = []\n", encoding="utf-8")
    suite = WorkbenchSuite(tmp_path / "workbench", normalizer=dangerous_normalizer)
    receipt = suite.ingest(source_kind="FILE", title=source.name, source_path=source)

    normalized = Path(receipt["normalized_path"]).read_text(encoding="utf-8")
    assert normalized == source.read_text(encoding="utf-8")
    assert "perMISsion" not in normalized
    assert receipt["normalization"]["state"] == "BYPASSED_NON_TRANSCRIPTION_SOURCE"
    assert receipt["normalization"]["normalized_changed"] is False


def test_nested_archive_graph_and_click_resolution(tmp_path: Path) -> None:
    suite = WorkbenchSuite(tmp_path / "workbench")
    source = suite.ingest(
        source_kind="FILE",
        title="Fuente archivada",
        raw_text="Primero se conserva el caso y después se verifica el hash.",
        workspace_id="WS-GRAPH",
    )
    project = suite.create_group(title="Proyecto", group_kind="PROJECT")
    campaign = suite.create_group(
        title="Campaña", group_kind="CAMPAIGN", parent_group_id=project["group_id"]
    )
    suite.attach(group_id=campaign["group_id"], item_type="SOURCE", item_id=source["source_id"])

    graph = suite.graph()
    node_ids = {node["id"] for node in graph["nodes"]}
    assert project["group_id"] in node_ids
    assert campaign["group_id"] in node_ids
    assert source["source_id"] in node_ids
    assert suite.resolve_node(source["source_id"])["state"] == "RESOLVED"
    assert suite.set_group_archived(campaign["group_id"], True)["archived"] is True
    assert suite.set_group_archived(campaign["group_id"], False)["archived"] is False


def test_budget_receipt_controls_cadence_and_local_handoff_only(tmp_path: Path) -> None:
    suite = WorkbenchSuite(tmp_path / "workbench")
    initial = suite.budget_status()
    assert initial["aggregate"]["state"] == "NOT_ESTIMABLE"
    suite.configure_budget_account(
        account_id="CODEX-WEEKLY",
        provider="OPENAI_CODEX",
        unit="TOKENS",
        weekly_limit=1000,
        currency=None,
        week_anchor="2026-08-10T00:00:00Z",
        telemetry_source="MANUAL_RECEIPT",
    )
    sample = suite.record_budget_sample(
        account_id="CODEX-WEEKLY",
        used_value=900,
        available_percent=None,
        source_receipt={
            "source": "USER_ACCOUNT_UI",
            "observed_at": "2026-08-10T12:00:00Z",
            "used_tokens": 900,
        },
    )

    assert sample["adjudication"]["available_percent"] == 10.0
    assert sample["adjudication"]["cadence_level"] == "HANDOFF"
    assert sample["automatic_maintenance"]["handoff"]["state"] == "READY_FOR_HOST_CONNECTOR"
    handoff_path = Path(sample["automatic_maintenance"]["handoff"]["path"])
    handoff_text = handoff_path.read_text(encoding="utf-8")
    assert '"external_task_created": false' in handoff_text
    assert '"previous_external_task_archived": false' in handoff_text
    assert suite.budget_status()["prices_inferred"] is False
    assert suite.verify()["gate"] == "PASS"
