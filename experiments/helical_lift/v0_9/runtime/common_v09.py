from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.parse
from typing import Any, Iterable


SECRET_NAME_FRAGMENTS = (
    "token", "secret", "password", "passwd", "api_key", "apikey", "private_key",
    "github_pat", "gh_token", "gitlab_token", "hf_token", "kaggle_key",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, *, chunk_bytes: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_bytes), b""):
            h.update(block)
    return h.hexdigest()


def git_blob_sha1(path: Path, *, chunk_bytes: int = 8 * 1024 * 1024) -> str:
    size = path.stat().st_size
    h = hashlib.sha1()
    h.update(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_bytes), b""):
            h.update(block)
    return h.hexdigest()


def fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    fsync_directory(path.parent)


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}:{sha256_bytes(canonical_json_bytes(value))}"


def safe_url_descriptor(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(url)
    query_names = sorted({key for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)})
    return {
        "scheme": parsed.scheme.lower(),
        "host": (parsed.hostname or "").lower(),
        "port": parsed.port,
        "path": parsed.path,
        "query_parameter_names": query_names,
        "query_values_recorded": False,
        "url_sha256": sha256_bytes(url.encode("utf-8")),
    }


def sanitize_text(text: str) -> str:
    # Remove URL query values from exception text while preserving the endpoint path.
    def replace_url(match: re.Match[str]) -> str:
        raw = match.group(0)
        parsed = urllib.parse.urlsplit(raw)
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "<redacted>", ""))

    cleaned = re.sub(r"https://[^\s'\"<>]+", replace_url, str(text))
    for name, value in os.environ.items():
        lname = name.lower()
        if value and len(value) >= 8 and any(fragment in lname for fragment in SECRET_NAME_FRAGMENTS):
            cleaned = cleaned.replace(value, f"<{name}:redacted>")
    return cleaned


def assert_no_known_secret_names(environment: dict[str, str] | None = None) -> list[str]:
    env = os.environ if environment is None else environment
    return sorted(
        name for name in env
        if any(fragment in name.lower() for fragment in SECRET_NAME_FRAGMENTS)
    )


def strip_known_secret_environment() -> list[str]:
    removed = assert_no_known_secret_names()
    for name in removed:
        os.environ.pop(name, None)
    return removed


def iter_files(root: Path, *, exclude: Iterable[Path] = ()) -> list[Path]:
    excluded = {p.resolve() for p in exclude}
    return [
        p for p in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if p.is_file() and p.resolve() not in excluded
    ]
