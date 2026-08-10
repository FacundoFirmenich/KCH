from __future__ import annotations

import re
import sqlite3
import unicodedata
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import canonical_json, sha256_json, sqlite_connection
from .recovery import RecoveryVault

DDL = """
CREATE TABLE IF NOT EXISTS lexicon (
    entry_id TEXT PRIMARY KEY,
    canonical_term TEXT NOT NULL,
    variant TEXT NOT NULL,
    normalized_variant TEXT NOT NULL,
    source_layer TEXT NOT NULL,
    status TEXT NOT NULL,
    scope TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(normalized_variant,canonical_term,scope)
);
CREATE TABLE IF NOT EXISTS resolutions (
    resolution_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    raw_transcription TEXT NOT NULL,
    normalized_transcription TEXT NOT NULL,
    confidence_state TEXT NOT NULL,
    replacements_json TEXT NOT NULL,
    clarification_required INTEGER NOT NULL,
    source_audio_id TEXT,
    resolver_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS corrections (
    correction_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    resolution_id TEXT,
    raw_token TEXT NOT NULL,
    corrected_term TEXT NOT NULL,
    confirmed_by_user INTEGER NOT NULL,
    source_layer TEXT NOT NULL,
    phl_state TEXT NOT NULL,
    evidence_json TEXT NOT NULL
);
"""

CANONICAL_SEED = {
    "KwanCode": ["Juan Code", "Quant Code", "Kwan Code"],
    "KwanDocs": ["Juan Docs", "Quant Docs", "Quandox"],
    "KwanData": ["Juan Data", "Quant Data", "Kwan Data"],
    "KwanForks": ["Juan Forks", "Kwan Forks"],
    "KwanPrompts": ["Juan Prompts", "Kwan Prompts"],
    "KCH": ["K C H", "KHC"],
    "CSI": ["C S I"],
    "MIS": ["M I S", "MSI"],
    "PHL": ["P H L"],
    "OBL": ["O B L"],
    "SCO": ["S C O"],
    "Super-MCP": ["Super MCP", "super eme ce pe"],
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalized(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(character for character in folded if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


class DictionLearning:
    """OBL lexicon plus authorized, future-only PHL correction staging."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "diction.sqlite3"
        self.vault = RecoveryVault(self.root / "recovery")
        with self.connect() as connection:
            connection.executescript(DDL)
            if connection.execute("SELECT COUNT(*) FROM lexicon").fetchone()[0] == 0:
                for canonical, variants in CANONICAL_SEED.items():
                    for variant in [canonical, *variants]:
                        self._insert(
                            connection,
                            canonical,
                            variant,
                            source_layer="OBL_CANONICAL_SEED",
                            scope="KCH",
                            evidence={"seed": True},
                        )
                connection.commit()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _insert(
        self,
        connection: sqlite3.Connection,
        canonical: str,
        variant: str,
        *,
        source_layer: str,
        scope: str,
        evidence: dict[str, Any],
    ) -> str:
        entry_id = f"DICT-{uuid.uuid4()}"
        connection.execute(
            "INSERT OR IGNORE INTO lexicon VALUES(?,?,?,?,?,?,?,?,?)",
            (
                entry_id,
                canonical,
                variant,
                normalized(variant),
                source_layer,
                "ACTIVE",
                scope,
                canonical_json(evidence),
                utc_now(),
            ),
        )
        return entry_id

    def obl_add(
        self,
        canonical: str,
        variants: list[str],
        *,
        scope: str = "USER",
        pronunciation_note: str = "",
    ) -> dict[str, Any]:
        if not canonical.strip() or not variants:
            raise ValueError("OBL diction entry requires canonical term and variants")
        with self.connect() as connection:
            for variant in [canonical, *variants]:
                self._insert(
                    connection,
                    canonical,
                    variant,
                    source_layer="OBL_USER_DECLARED",
                    scope=scope,
                    evidence={"pronunciation_note": pronunciation_note},
                )
            connection.commit()
        value = {
            "canonical_term": canonical,
            "variants": variants,
            "scope": scope,
            "source_layer": "OBL_USER_DECLARED",
        }
        self.vault.save_json(
            f"obl/{uuid.uuid4()}.json",
            value,
            kind="OBL_DICTION_ENTRY",
            actor="USER",
            operation="DECLARE_DICTION",
        )
        return value

    def resolve(
        self, raw_transcription: str, *, source_audio_id: str | None = None
    ) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            entries = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM lexicon WHERE status='ACTIVE' ORDER BY length(variant) DESC,canonical_term"
                )
            ]
        working = raw_transcription
        replacements: list[dict[str, Any]] = []
        competing: list[dict[str, Any]] = []
        by_variant: dict[str, set[str]] = {}
        for entry in entries:
            by_variant.setdefault(entry["normalized_variant"], set()).add(entry["canonical_term"])
        for variant, candidates in sorted(by_variant.items(), key=lambda item: -len(item[0])):
            if not variant:
                continue
            if len(candidates) == 1:
                canonical = next(iter(candidates))
                before = working
                raw_variant = next(
                    entry["variant"]
                    for entry in entries
                    if entry["normalized_variant"] == variant
                    and entry["canonical_term"] == canonical
                )
                raw_pattern = re.compile(
                    r"(?i)(?<!\w)"
                    + r"\s+".join(
                        re.escape(part) for part in re.split(r"\s+", raw_variant.strip())
                    )
                    + r"(?!\w)"
                )
                working = raw_pattern.sub(canonical, working)
                if working != before:
                    replacements.append(
                        {
                            "raw_token": raw_variant,
                            "normalized_term": canonical,
                            "confidence_state": "resolved_lexicon",
                        }
                    )
            else:
                normalized_pattern = re.compile(
                    r"(?i)(?<!\w)"
                    + r"\s+".join(re.escape(part) for part in variant.split())
                    + r"(?!\w)"
                )
                if normalized_pattern.search(normalized(working)):
                    competing.append({"raw_variant": variant, "candidates": sorted(candidates)})
        confidence = (
            "unresolved_competing"
            if competing
            else ("resolved_lexicon" if replacements else "raw_only")
        )
        resolution_id = f"DRES-{uuid.uuid4()}"
        body = {
            "resolution_id": resolution_id,
            "raw_transcription": raw_transcription,
            "normalized_transcription": working,
            "confidence_state": confidence,
            "replacements": replacements,
            "competing": competing,
            "clarification_required": bool(competing),
            "source_audio_id": source_audio_id,
            "phl_authorized": True,
            "phl_training_executed": False,
        }
        digest = sha256_json(body)
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO resolutions VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    resolution_id,
                    utc_now(),
                    raw_transcription,
                    working,
                    confidence,
                    canonical_json(replacements + competing),
                    int(bool(competing)),
                    source_audio_id,
                    digest,
                ),
            )
            connection.commit()
        custody = self.vault.save_json(
            f"resolutions/{resolution_id}.json",
            body,
            kind="DICTION_RESOLUTION",
            actor="KCH_SYSTEM",
            operation="RESOLVE_WITHOUT_OVERWRITING_RAW",
        )
        return {**body, "resolver_hash": digest, "custody": custody}

    def record_correction(
        self,
        *,
        raw_token: str,
        corrected_term: str,
        confirmed_by_user: bool,
        resolution_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        correction_id = f"DCORR-{uuid.uuid4()}"
        source_layer = "PHL_USER_FEEDBACK_STAGED"
        phl_state = "STAGED_USER_CONFIRMED_UNTRAINED" if confirmed_by_user else "STAGED_UNCONFIRMED"
        value = {
            "correction_id": correction_id,
            "raw_token": raw_token,
            "corrected_term": corrected_term,
            "confirmed_by_user": confirmed_by_user,
            "resolution_id": resolution_id,
            "source_layer": source_layer,
            "phl_state": phl_state,
            "context": context or {},
            "timestamp": utc_now(),
        }
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO corrections VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    correction_id,
                    value["timestamp"],
                    resolution_id,
                    raw_token,
                    corrected_term,
                    int(confirmed_by_user),
                    source_layer,
                    value["phl_state"],
                    canonical_json(context or {}),
                ),
            )
            connection.commit()
        custody = self.vault.save_json(
            f"corrections/{correction_id}.json",
            value,
            kind="PHL_DICTION_FEEDBACK_CANDIDATE",
            actor="USER" if confirmed_by_user else "KCH_SYSTEM",
            operation="RECORD_AUTHORIZED_PHL_CANDIDATE_NO_TRAINING",
        )
        return {**value, "custody": custody}

    def status(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            entries = connection.execute(
                "SELECT COUNT(*) FROM lexicon WHERE status='ACTIVE'"
            ).fetchone()[0]
            resolutions = connection.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0]
            corrections = connection.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
            confirmed = connection.execute(
                "SELECT COUNT(*) FROM corrections WHERE confirmed_by_user=1"
            ).fetchone()[0]
            promoted = connection.execute(
                "SELECT COUNT(*) FROM corrections WHERE phl_state LIKE 'PROMOTED%'"
            ).fetchone()[0]
        return {
            "schema": "kch.diction-learning-status.v0.2.0",
            "obl_entries": entries,
            "resolutions": resolutions,
            "phl_correction_candidates": corrections,
            "phl_user_confirmed_candidates": confirmed,
            "phl_promoted_corrections": promoted,
            "phl_mode": "AUTHORIZED_UNTRAINED"
            if promoted == 0
            else "TRAINED_WITH_APPROVED_PROMOTIONS",
            "phl_authorized": True,
            "phl_training_executed": promoted > 0,
            "phl_real_executed": promoted > 0,
            "automatic_promotion": False,
            "activation_requires": "PHL_PACKET_REPLAY_AND_EXPLICIT_USER_APPROVAL",
        }
