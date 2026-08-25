from __future__ import annotations

import base64
import io
import json
import mimetypes
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from .contracts import canonical_json, safe_child, sha256_bytes
from .recovery import RecoveryVault

MAGIC = "KCH-UTXT/1"
TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".py",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".csv",
    ".tsv",
    ".xml",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".tex",
    ".bib",
    ".sql",
    ".sh",
    ".ps1",
    ".bat",
    ".cmd",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".swift",
    ".rb",
    ".php",
    ".r",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def encode_utxt(raw: bytes, *, filename: str, media_type: str | None = None) -> str:
    media_type = media_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    header = {
        "schema": "kch.universal-text-envelope.v0.1.0",
        "filename": filename,
        "media_type": media_type,
        "byte_count": len(raw),
        "sha256": sha256_bytes(raw),
        "encoding": "base64",
        "roundtrip": "EXACT_BYTES",
    }
    encoded = base64.b64encode(raw).decode("ascii")
    lines = [encoded[index : index + 76] for index in range(0, len(encoded), 76)]
    return f"{MAGIC}\n{canonical_json(header)}\n---BASE64---\n" + "\n".join(lines) + "\n---END---\n"


def decode_utxt(value: str) -> tuple[dict[str, Any], bytes]:
    lines = value.splitlines()
    if (
        len(lines) < 5
        or lines[0] != MAGIC
        or lines[2] != "---BASE64---"
        or lines[-1] != "---END---"
    ):
        raise ValueError("invalid KCH universal text envelope")
    header = json.loads(lines[1])
    raw = base64.b64decode("".join(lines[3:-1]), validate=True)
    if len(raw) != int(header["byte_count"]) or sha256_bytes(raw) != header["sha256"]:
        raise ValueError("universal text envelope failed exact-byte verification")
    return header, raw


class UniversalAssetStore:
    """Exact original custody plus explicitly loss-labelled readable derivatives."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.vault = RecoveryVault(self.root / "recovery")
        self.export_root = self.root / "exports"
        self.export_root.mkdir(exist_ok=True)

    @staticmethod
    def _extract_pdf(raw: bytes) -> tuple[str | None, dict[str, Any]]:
        try:
            from pypdf import PdfReader
        except ImportError:
            return None, {
                "state": "UNAVAILABLE_DEPENDENCY",
                "dependency": "pypdf",
                "layout_fidelity": False,
            }
        reader = PdfReader(io.BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages)
        return text, {
            "state": "EXTRACTED",
            "engine": "pypdf",
            "page_count": len(reader.pages),
            "layout_fidelity": False,
            "ocr_performed": False,
        }

    @staticmethod
    def _extract_docx(raw: bytes) -> tuple[str | None, dict[str, Any]]:
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                xml = archive.read("word/document.xml")
        except (zipfile.BadZipFile, KeyError):
            return None, {"state": "INVALID_DOCX", "layout_fidelity": False}
        root = ElementTree.fromstring(xml)
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs: list[str] = []
        for paragraph in root.iter(namespace + "p"):
            paragraphs.append("".join(node.text or "" for node in paragraph.iter(namespace + "t")))
        return "\n".join(paragraphs), {
            "state": "EXTRACTED",
            "engine": "OOXML_STANDARD_LIBRARY",
            "layout_fidelity": False,
            "tracked_changes_semantics_guaranteed": False,
        }

    @staticmethod
    def _readable_projection(raw: bytes, suffix: str) -> tuple[str | None, dict[str, Any]]:
        if suffix in TEXT_SUFFIXES:
            for encoding in ("utf-8-sig", "utf-8"):
                try:
                    text = raw.decode(encoding)
                    return text, {
                        "state": "EXACT_TEXT_PROJECTION",
                        "encoding": encoding,
                        "byte_roundtrip_from_projection": text.encode("utf-8") == raw,
                        "layout_fidelity": suffix not in {".html", ".htm", ".tex"},
                    }
                except UnicodeDecodeError:
                    continue
            return None, {"state": "TEXT_ENCODING_UNRESOLVED", "layout_fidelity": False}
        if suffix == ".pdf":
            return UniversalAssetStore._extract_pdf(raw)
        if suffix == ".docx":
            return UniversalAssetStore._extract_docx(raw)
        return None, {
            "state": "BINARY_ENVELOPE_ONLY",
            "layout_fidelity": False,
            "ocr_performed": False,
            "transcription_performed": False,
        }

    def ingest(self, source: str | Path, *, actor: str = "USER") -> dict[str, Any]:
        path = Path(source).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        raw = path.read_bytes()
        asset_id = f"UASSET-{uuid.uuid4()}"
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        original = self.vault.save(
            f"universal/{asset_id}/original/{path.name}",
            raw,
            kind="UNIVERSAL_ORIGINAL",
            actor=actor,
            operation="INGEST_EXACT_ORIGINAL",
            media_type=media_type,
        )
        envelope_text = encode_utxt(raw, filename=path.name, media_type=media_type)
        envelope = self.vault.save(
            f"universal/{asset_id}/envelope.txt",
            envelope_text,
            kind="UNIVERSAL_TEXT_ENVELOPE",
            actor="KCH_SYSTEM",
            operation="ENCODE_EXACT_BYTES_AS_TEXT",
        )
        _, decoded = decode_utxt(envelope_text)
        if decoded != raw:
            raise ValueError("universal text roundtrip gate failed")
        projection, extraction = self._readable_projection(raw, path.suffix.lower())
        projection_receipt = None
        if projection is not None:
            projection_receipt = self.vault.save(
                f"universal/{asset_id}/readable.txt",
                projection,
                kind="READABLE_DERIVATIVE",
                actor="KCH_SYSTEM",
                operation="EXTRACT_READABLE_DERIVATIVE",
            )
        manifest = {
            "schema": "kch.universal-asset-manifest.v0.1.0",
            "asset_id": asset_id,
            "source_name": path.name,
            "source_path_recorded": str(path),
            "media_type": media_type,
            "original": original,
            "universal_text_envelope": envelope,
            "exact_roundtrip_verified": True,
            "readable_projection": extraction,
            "readable_projection_receipt": projection_receipt,
            "original_retained": True,
            "ingested_at": utc_now(),
        }
        self.vault.save_json(
            f"universal/{asset_id}/manifest.json",
            manifest,
            kind="UNIVERSAL_ASSET_MANIFEST",
            actor="KCH_SYSTEM",
            operation="SEAL_INGEST_MANIFEST",
        )
        return manifest

    def restore_original(self, asset_id: str, relative_target: str | Path) -> dict[str, Any]:
        manifest = json.loads(
            str(self.vault.latest(f"universal/{asset_id}/manifest.json", decode=True)["content"])
        )
        envelope = self.vault.latest(f"universal/{asset_id}/envelope.txt", decode=True)["content"]
        header, raw = decode_utxt(str(envelope))
        target = safe_child(self.export_root, relative_target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        observed = sha256_bytes(target.read_bytes())
        if observed != header["sha256"] or observed != manifest["original"]["content_sha256"]:
            raise ValueError("restored original failed hash verification")
        return {
            "state": "RESTORED_EXACT_BYTES",
            "path": str(target),
            "bytes": len(raw),
            "sha256": observed,
        }

    @staticmethod
    def _minimal_docx(text: str) -> bytes:
        paragraphs = []
        for line in text.splitlines() or [""]:
            preserved = (
                ' xml:space="preserve"' if line.startswith(" ") or line.endswith(" ") else ""
            )
            paragraphs.append(f"<w:p><w:r><w:t{preserved}>{escape(line)}</w:t></w:r></w:p>")
        document = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{"".join(paragraphs)}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        )
        rels = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("_rels/.rels", rels)
            archive.writestr("word/document.xml", document)
        raw = buffer.getvalue()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if archive.testzip() is not None or "word/document.xml" not in archive.namelist():
                raise ValueError("generated DOCX failed structural verification")
        return raw

    def transform(self, asset_id: str, target_format: str) -> dict[str, Any]:
        target_format = target_format.lower().lstrip(".")
        manifest = json.loads(
            str(self.vault.latest(f"universal/{asset_id}/manifest.json", decode=True)["content"])
        )
        if target_format == "original":
            return self.restore_original(asset_id, manifest["source_name"])
        projection_key = f"universal/{asset_id}/readable.txt"
        try:
            text = str(self.vault.latest(projection_key, decode=True)["content"])
        except KeyError as exc:
            raise ValueError(
                "no readable projection exists; original remains exactly recoverable"
            ) from exc
        if target_format == "txt":
            raw = text.encode("utf-8")
            suffix = ".txt"
            media_type = "text/plain"
        elif target_format == "md":
            raw = (f"# {manifest['source_name']}\n\n" + text).encode("utf-8")
            suffix = ".md"
            media_type = "text/markdown"
        elif target_format == "docx":
            raw = self._minimal_docx(text)
            suffix = ".docx"
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            raise ValueError("supported derivative targets: txt, md, docx, original")
        output_name = f"{Path(manifest['source_name']).stem}{suffix}"
        target = safe_child(self.export_root, f"{asset_id}/{output_name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        receipt = self.vault.save(
            f"universal/{asset_id}/derivatives/{output_name}",
            raw,
            kind="UNIVERSAL_DERIVATIVE",
            actor="KCH_SYSTEM",
            operation=f"TRANSFORM_TO_{target_format.upper()}",
            media_type=media_type,
        )
        return {
            "schema": "kch.universal-transform-receipt.v0.1.0",
            "asset_id": asset_id,
            "target_format": target_format,
            "path": str(target),
            "sha256": sha256_bytes(raw),
            "original_retained": True,
            "exact_original_recovery": True,
            "derivative_semantic_fidelity": "LOSSLESS_TEXT"
            if manifest["readable_projection"]["state"] == "EXACT_TEXT_PROJECTION"
            else "LOSSY_READABLE_DERIVATIVE",
            "layout_fidelity": False
            if manifest["source_name"].lower().endswith((".pdf", ".docx", ".html", ".htm"))
            else None,
            "visual_qa": "NOT_RUN_BY_CONVERTER",
            "custody": receipt,
        }


class PlanBuildEngine:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.assets = UniversalAssetStore(self.root / "universal_assets")
        self.vault = RecoveryVault(self.root / "recovery")

    def plan(self, operations: list[dict[str, Any]]) -> dict[str, Any]:
        plan_id = f"PLAN-{uuid.uuid4()}"
        normalized = []
        for index, operation in enumerate(operations, start=1):
            kind = str(operation.get("kind", "")).upper()
            if kind not in {"INGEST", "TRANSFORM", "RESTORE"}:
                raise ValueError(f"unsupported build operation: {kind}")
            normalized.append({"step": index, **operation, "kind": kind})
        plan = {
            "schema": "kch.plan-build.v0.1.0",
            "plan_id": plan_id,
            "state": "PLANNED_NOT_EXECUTED",
            "operations": normalized,
            "original_bytes_retained": True,
            "created_at": utc_now(),
        }
        receipt = self.vault.save_json(
            f"plans/{plan_id}.json", plan, kind="PLAN_BUILD", actor="USER", operation="PLAN"
        )
        return {**plan, "custody": receipt}

    def run(self, plan_id: str) -> dict[str, Any]:
        plan = json.loads(str(self.vault.latest(f"plans/{plan_id}.json", decode=True)["content"]))
        if plan["state"] != "PLANNED_NOT_EXECUTED":
            raise ValueError("plan has already been built")
        snapshot = self.vault.snapshot(f"before-build:{plan_id}")
        results: list[dict[str, Any]] = []
        aliases: dict[str, str] = {}
        for operation in plan["operations"]:
            kind = operation["kind"]
            if kind == "INGEST":
                result = self.assets.ingest(operation["source"])
                if operation.get("as"):
                    aliases[str(operation["as"])] = result["asset_id"]
            else:
                requested = str(operation["asset_id"])
                asset_id = aliases.get(requested, requested)
                if kind == "TRANSFORM":
                    result = self.assets.transform(asset_id, str(operation["target_format"]))
                else:
                    result = self.assets.restore_original(
                        asset_id, str(operation["relative_target"])
                    )
            results.append({"step": operation["step"], "result": result})
        built = {
            **plan,
            "state": "RUN_COMPLETED",
            "results": results,
            "run_at": utc_now(),
            "recovery_snapshot": snapshot,
        }
        receipt = self.vault.save_json(
            f"plans/{plan_id}.json", built, kind="PLAN_RUN", actor="KCH_SYSTEM", operation="RUN"
        )
        return {**built, "custody": receipt}

    def build(self, plan_id: str) -> dict[str, Any]:
        """Compatibility alias; the canonical KCH mode name is RUN."""
        return self.run(plan_id)
