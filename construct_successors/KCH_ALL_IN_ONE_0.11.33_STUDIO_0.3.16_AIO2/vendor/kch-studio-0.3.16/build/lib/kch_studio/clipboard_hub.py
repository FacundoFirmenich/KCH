from __future__ import annotations

import base64
import ctypes
import io
import os
import re
import sqlite3
import threading
import uuid
from contextlib import closing
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .contracts import sha256_bytes, sqlite_connection
from .recovery import RecoveryVault

WINDOWS_CLIPBOARD_LOCK = threading.RLock()


def _windows_clipboard_api() -> tuple[Any, Any]:
    """Return 64-bit-safe Win32 clipboard APIs with explicit signatures."""
    if os.name != "nt":
        raise OSError("Win32 clipboard API is unavailable")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    return user32, kernel32


DDL = """
CREATE TABLE IF NOT EXISTS clipboard_items (
    item_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    media_type TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    byte_count INTEGER NOT NULL,
    preview TEXT NOT NULL,
    sensitive INTEGER NOT NULL,
    pinned INTEGER NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    seen_count INTEGER NOT NULL,
    vault_key TEXT,
    UNIQUE(kind,content_sha256)
);
CREATE TABLE IF NOT EXISTS postits (
    postit_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    rank INTEGER NOT NULL,
    parent_postit_id TEXT,
    source_item_id TEXT,
    color TEXT NOT NULL,
    pinned INTEGER NOT NULL,
    archived INTEGER NOT NULL,
    revision INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS postit_tags (
    postit_id TEXT NOT NULL REFERENCES postits(postit_id),
    tag TEXT NOT NULL,
    PRIMARY KEY(postit_id,tag)
);
CREATE TABLE IF NOT EXISTS postit_links (
    link_id TEXT PRIMARY KEY,
    postit_id TEXT NOT NULL REFERENCES postits(postit_id),
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,})\b"),
    re.compile(r"(?i)\b(?:password|passwd|api[_ -]?key|secret|token)\s*[:=]\s*\S{8,}"),
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ClipboardHub:
    """Clipboard history plus persistent, versioned post-it database."""

    def __init__(self, root: str | Path, *, persist_sensitive_automatically: bool = False):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "clipboard.sqlite3"
        self.vault = RecoveryVault(self.root / "recovery")
        self.persist_sensitive_automatically = persist_sensitive_automatically
        self._ephemeral: dict[str, bytes] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_fingerprint: tuple[str, str] | None = None
        self._last_monitor_error: str | None = None
        with self.connect() as connection:
            connection.executescript(DDL)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _sensitive(raw: bytes, kind: str) -> bool:
        if kind != "TEXT":
            return False
        text = raw.decode("utf-8", errors="ignore")
        return any(pattern.search(text) for pattern in SECRET_PATTERNS)

    @staticmethod
    def _preview(raw: bytes, kind: str, sensitive: bool) -> str:
        if sensitive:
            return "[POTENTIALLY SENSITIVE - PREVIEW SUPPRESSED]"
        if kind == "TEXT":
            return raw.decode("utf-8", errors="replace").replace("\n", " ")[:240]
        return f"[{kind} {len(raw)} bytes]"

    def capture(
        self, content: bytes | str, *, kind: str, media_type: str, explicit_persist: bool = False
    ) -> dict[str, Any]:
        raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        digest = sha256_bytes(raw)
        sensitive = self._sensitive(raw, kind)
        timestamp = utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM clipboard_items WHERE kind=? AND content_sha256=?", (kind, digest)
            ).fetchone()
            if existing:
                connection.execute(
                    "UPDATE clipboard_items SET last_seen=?,seen_count=seen_count+1 WHERE item_id=?",
                    (timestamp, existing["item_id"]),
                )
                connection.commit()
                return {
                    **dict(existing),
                    "state": "DEDUPLICATED",
                    "last_seen": timestamp,
                    "seen_count": int(existing["seen_count"]) + 1,
                }
            item_id = f"CLIP-{uuid.uuid4()}"
            should_persist = (
                explicit_persist or not sensitive or self.persist_sensitive_automatically
            )
            vault_key = None
            if should_persist:
                vault_key = f"clipboard/items/{item_id}"
                self.vault.save(
                    vault_key,
                    raw,
                    kind=f"CLIPBOARD_{kind}",
                    actor="KCH_SYSTEM",
                    operation="CAPTURE",
                    media_type=media_type,
                )
            else:
                self._ephemeral[item_id] = raw
            preview = self._preview(raw, kind, sensitive)
            connection.execute(
                "INSERT INTO clipboard_items VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item_id,
                    kind,
                    media_type,
                    digest,
                    len(raw),
                    preview,
                    int(sensitive),
                    int(explicit_persist),
                    timestamp,
                    timestamp,
                    1,
                    vault_key,
                ),
            )
            connection.commit()
        return {
            "item_id": item_id,
            "kind": kind,
            "media_type": media_type,
            "content_sha256": digest,
            "bytes": len(raw),
            "preview": preview,
            "sensitive": sensitive,
            "persisted": should_persist,
            "persistence_policy": "EXPLICIT_OR_NON_SENSITIVE"
            if not self.persist_sensitive_automatically
            else "ALL_LOCAL",
        }

    def _content(self, item_id: str) -> tuple[dict[str, Any], bytes]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM clipboard_items WHERE item_id=?", (item_id,)
            ).fetchone()
            if row is None:
                raise KeyError(item_id)
            item = dict(row)
        if item["vault_key"]:
            raw = self.vault.latest(item["vault_key"])["content"]
        elif item_id in self._ephemeral:
            raw = self._ephemeral[item_id]
        else:
            raise ValueError("ephemeral clipboard bytes are no longer available")
        if sha256_bytes(raw) != item["content_sha256"]:
            raise ValueError("clipboard custody hash mismatch")
        return item, raw

    def pin(self, item_id: str) -> dict[str, Any]:
        item, raw = self._content(item_id)
        if not item["vault_key"]:
            key = f"clipboard/items/{item_id}"
            self.vault.save(
                key,
                raw,
                kind=f"CLIPBOARD_{item['kind']}",
                actor="USER",
                operation="PIN_PERSISTENT",
                media_type=item["media_type"],
            )
            with self.connect() as connection:
                connection.execute(
                    "UPDATE clipboard_items SET pinned=1,vault_key=? WHERE item_id=?",
                    (key, item_id),
                )
                connection.commit()
            self._ephemeral.pop(item_id, None)
        else:
            with self.connect() as connection:
                connection.execute(
                    "UPDATE clipboard_items SET pinned=1 WHERE item_id=?", (item_id,)
                )
                connection.commit()
        return {"item_id": item_id, "state": "PINNED_PERSISTENT"}

    def create_postit(
        self,
        *,
        title: str = "",
        body: str = "",
        source_item_id: str | None = None,
        parent_postit_id: str | None = None,
        rank: int | None = None,
        color: str = "#FFF4A3",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        if source_item_id:
            item, raw = self._content(source_item_id)
            if not body:
                body = (
                    raw.decode("utf-8", errors="replace")
                    if item["kind"] == "TEXT"
                    else item["preview"]
                )
            self.pin(source_item_id)
        timestamp = utc_now()
        postit_id = f"POSTIT-{uuid.uuid4()}"
        with self.connect() as connection:
            if rank is None:
                rank = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(rank),0)+1 FROM postits WHERE parent_postit_id IS ?",
                        (parent_postit_id,),
                    ).fetchone()[0]
                )
            connection.execute(
                "INSERT INTO postits VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    postit_id,
                    title,
                    body,
                    rank,
                    parent_postit_id,
                    source_item_id,
                    color,
                    1,
                    0,
                    1,
                    timestamp,
                    timestamp,
                ),
            )
            for tag in sorted(set(tags or [])):
                connection.execute(
                    "INSERT INTO postit_tags VALUES(?,?)", (postit_id, tag.strip().lower())
                )
            connection.commit()
        value = self.get_postit(postit_id)
        custody = self.vault.save_json(
            f"postits/{postit_id}.json",
            value,
            kind="PERSISTENT_POSTIT",
            actor="USER",
            operation="CREATE",
        )
        return {**value, "custody": custody}

    def edit_postit(
        self,
        postit_id: str,
        *,
        title: str | None = None,
        body: str | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        current = self.get_postit(postit_id)
        title = current["title"] if title is None else title
        body = current["body"] if body is None else body
        color = current["color"] if color is None else color
        with self.connect() as connection:
            connection.execute(
                "UPDATE postits SET title=?,body=?,color=?,revision=revision+1,updated_at=? WHERE postit_id=?",
                (title, body, color, utc_now(), postit_id),
            )
            connection.commit()
        value = self.get_postit(postit_id)
        custody = self.vault.save_json(
            f"postits/{postit_id}.json",
            value,
            kind="PERSISTENT_POSTIT",
            actor="USER",
            operation="AUTOSAVE_EDIT",
        )
        return {**value, "custody": custody}

    def link_postit(
        self, postit_id: str, *, target_type: str, target_id: str, relation: str
    ) -> dict[str, Any]:
        link_id = f"PLINK-{uuid.uuid4()}"
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO postit_links VALUES(?,?,?,?,?,?)",
                (link_id, postit_id, target_type, target_id, relation, utc_now()),
            )
            connection.commit()
        return {
            "link_id": link_id,
            "postit_id": postit_id,
            "target_type": target_type,
            "target_id": target_id,
            "relation": relation,
        }

    def get_postit(self, postit_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM postits WHERE postit_id=?", (postit_id,)
            ).fetchone()
            if row is None:
                raise KeyError(postit_id)
            tags = [
                item[0]
                for item in connection.execute(
                    "SELECT tag FROM postit_tags WHERE postit_id=? ORDER BY tag", (postit_id,)
                )
            ]
            links = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM postit_links WHERE postit_id=? ORDER BY created_at", (postit_id,)
                )
            ]
            return {**dict(row), "tags": tags, "links": links}

    def search(self, query: str, *, limit: int = 50) -> dict[str, Any]:
        pattern = f"%{query}%"
        with closing(self.connect()) as connection:
            clips = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM clipboard_items WHERE preview LIKE ? ORDER BY pinned DESC,last_seen DESC LIMIT ?",
                    (pattern, limit),
                )
            ]
            notes = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM postits WHERE archived=0 AND (title LIKE ? OR body LIKE ?) ORDER BY pinned DESC,rank LIMIT ?",
                    (pattern, pattern, limit),
                )
            ]
        return {"clipboard_items": clips, "postits": notes}

    def explanation_context(self, item_id: str) -> dict[str, Any]:
        item, raw = self._content(item_id)
        content = (
            raw.decode("utf-8", errors="replace")
            if item["kind"] == "TEXT"
            else base64.b64encode(raw).decode("ascii")
        )
        return {
            "schema": "kch.clipboard-explanation-context.v0.1.0",
            "item": item,
            "content": content,
            "content_encoding": "utf-8" if item["kind"] == "TEXT" else "base64",
            "user_selected_context": True,
        }

    def capture_region(
        self, bbox: tuple[int, int, int, int], *, copy_to_system_clipboard: bool = True
    ) -> dict[str, Any]:
        if len(bbox) != 4 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            raise ValueError("bbox must have positive area")
        try:
            from PIL import ImageGrab
        except ImportError as exc:
            raise RuntimeError("Pillow is required for screen-region capture") from exc
        image = ImageGrab.grab(bbox=bbox, all_screens=True)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        raw = buffer.getvalue()
        item = self.capture(raw, kind="IMAGE", media_type="image/png", explicit_persist=True)
        copied = False
        if copy_to_system_clipboard:
            copied = self._copy_image_windows(image)
        return {
            **item,
            "bbox": list(bbox),
            "pixel_size": list(image.size),
            "copied_to_system_clipboard": copied,
        }

    @staticmethod
    def _copy_image_windows(image: Any) -> bool:
        if os.name != "nt":
            return False
        bmp = io.BytesIO()
        image.convert("RGB").save(bmp, "BMP")
        dib = bmp.getvalue()[14:]
        user32, kernel32 = _windows_clipboard_api()
        with WINDOWS_CLIPBOARD_LOCK:
            handle = kernel32.GlobalAlloc(0x0002, len(dib))
            if not handle:
                raise OSError("GlobalAlloc failed")
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                kernel32.GlobalFree(handle)
                raise OSError("GlobalLock failed")
            try:
                ctypes.memmove(pointer, dib, len(dib))
            finally:
                kernel32.GlobalUnlock(handle)
            if not user32.OpenClipboard(None):
                kernel32.GlobalFree(handle)
                raise OSError("OpenClipboard failed")
            try:
                if not user32.EmptyClipboard():
                    raise OSError("EmptyClipboard failed")
                if not user32.SetClipboardData(8, handle):
                    raise OSError("SetClipboardData(CF_DIB) failed")
                handle = None
            finally:
                user32.CloseClipboard()
                if handle:
                    kernel32.GlobalFree(handle)
        return True

    @staticmethod
    def read_system_text() -> str | None:
        if os.name != "nt":
            return None
        user32, kernel32 = _windows_clipboard_api()
        with WINDOWS_CLIPBOARD_LOCK:
            if not user32.IsClipboardFormatAvailable(13) or not user32.OpenClipboard(None):
                return None
            try:
                handle = user32.GetClipboardData(13)
                if not handle:
                    return None
                size = int(kernel32.GlobalSize(handle))
                if size <= 0:
                    return None
                pointer = kernel32.GlobalLock(handle)
                if not pointer:
                    return None
                try:
                    maximum_characters = size // ctypes.sizeof(ctypes.c_wchar)
                    return ctypes.wstring_at(pointer, maximum_characters).split("\x00", 1)[0]
                finally:
                    kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()

    def poll_once(self) -> dict[str, Any] | None:
        text = self.read_system_text()
        if text is None:
            return None
        fingerprint = ("TEXT", sha256_bytes(text.encode("utf-8")))
        if fingerprint == self._last_fingerprint:
            return None
        self._last_fingerprint = fingerprint
        return self.capture(text, kind="TEXT", media_type="text/plain; charset=utf-8")

    def start_monitor(self, interval: float = 0.35) -> dict[str, Any]:
        if self._thread and self._thread.is_alive():
            return self.status()
        self._stop.clear()

        def loop() -> None:
            while not self._stop.is_set():
                try:
                    self.poll_once()
                    self._last_monitor_error = None
                except Exception as exc:
                    observed = f"{type(exc).__name__}: {exc}"
                    if observed != self._last_monitor_error:
                        self._last_monitor_error = observed
                        self.vault.save_json(
                            f"monitor-errors/{uuid.uuid4()}.json",
                            {
                                "timestamp": utc_now(),
                                "error": observed,
                                "operation": "CLIPBOARD_POLL",
                            },
                            kind="CLIPBOARD_MONITOR_ERROR",
                            actor="KCH_SYSTEM",
                            operation="PRESERVE_BACKGROUND_FAILURE",
                        )
                self._stop.wait(interval)

        self._thread = threading.Thread(target=loop, name="kch-clipboard-monitor", daemon=True)
        self._thread.start()
        return self.status()

    def stop_monitor(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread:
            self._thread.join(2)
        return self.status()

    def status(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            items = connection.execute("SELECT COUNT(*) FROM clipboard_items").fetchone()[0]
            postits = connection.execute(
                "SELECT COUNT(*) FROM postits WHERE archived=0"
            ).fetchone()[0]
        return {
            "schema": "kch.clipboard-hub-status.v0.1.0",
            "monitor_running": bool(self._thread and self._thread.is_alive()),
            "clipboard_items": items,
            "persistent_postits": postits,
            "sensitive_automatic_persistence": self.persist_sensitive_automatically,
            "region_capture_available": os.name == "nt",
            "last_monitor_error": self._last_monitor_error,
        }


class RegionSelector:
    """Transparent Tk overlay that returns a user-drawn screen rectangle."""

    def __init__(self, master: Any, callback: Callable[[tuple[int, int, int, int]], None]):
        import tkinter as tk

        self.callback = callback
        self.start: tuple[int, int] | None = None
        self.rectangle = None
        self.window = tk.Toplevel(master)
        self.window.attributes("-fullscreen", True)
        self.window.attributes("-alpha", 0.25)
        self.window.attributes("-topmost", True)
        self.window.configure(cursor="crosshair", background="black")
        self.canvas = tk.Canvas(self.window, highlightthickness=0, background="black")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.window.bind("<Escape>", lambda _event: self.window.destroy())

    def _press(self, event: Any) -> None:
        self.start = (event.x_root, event.y_root)
        self.rectangle = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="red", width=3
        )

    def _drag(self, event: Any) -> None:
        if self.start and self.rectangle:
            x0, y0 = self.start
            self.canvas.coords(self.rectangle, x0, y0, event.x_root, event.y_root)

    def _release(self, event: Any) -> None:
        if not self.start:
            self.window.destroy()
            return
        x0, y0 = self.start
        bbox = (
            min(x0, event.x_root),
            min(y0, event.y_root),
            max(x0, event.x_root),
            max(y0, event.y_root),
        )
        self.window.destroy()
        if bbox[2] > bbox[0] and bbox[3] > bbox[1]:
            self.callback(bbox)
