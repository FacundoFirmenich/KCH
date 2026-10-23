#!/usr/bin/env python3
"""Fetch an anonymous.4open.science repository with an auditable manifest."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import quote

import requests

USER_AGENT = "NO-LIFT-CERTID-acquisition/0.7 (+research artifact fetch)"


def iter_paths(node, prefix=()):
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, dict):
                yield from iter_paths(value, prefix + (key,))
            else:
                yield "/".join(prefix + (key,))
    elif isinstance(node, list):
        for value in node:
            yield from iter_paths(value, prefix)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_one(base: str, repo_id: str, rel: str, root: Path, retries: int = 5):
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"{base}/api/repo/{repo_id}/file/{quote(rel, safe='/')}"
    headers = {"User-Agent": USER_AGENT}
    last = None
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=120)
            response.raise_for_status()
            target.write_bytes(response.content)
            return {
                "path": rel,
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
                "url": url,
            }
        except Exception as exc:  # preserve exact failure after retries
            last = repr(exc)
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"failed after {retries} attempts: {rel}: {last}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", default="https://anonymous.4open.science")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": USER_AGENT}
    list_url = f"{args.base}/api/repo/{args.repo_id}/files/"
    response = requests.get(list_url, headers=headers, timeout=120)
    response.raise_for_status()
    listing = response.json()
    paths = sorted(set(iter_paths(listing)))
    if not paths:
        raise RuntimeError("remote repository listing is empty")

    files = []
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {
            pool.submit(fetch_one, args.base, args.repo_id, rel, args.output): rel
            for rel in paths
        }
        for future in concurrent.futures.as_completed(future_map):
            rel = future_map[future]
            try:
                files.append(future.result())
            except Exception as exc:
                failures.append({"path": rel, "error": repr(exc)})

    files.sort(key=lambda row: row["path"])
    manifest = {
        "repo_id": args.repo_id,
        "base": args.base,
        "listing_url": list_url,
        "listed_paths": len(paths),
        "downloaded_files": len(files),
        "failures": failures,
        "files": files,
    }
    manifest_path = args.output / "ACQUISITION_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    digest_lines = [f'{row["sha256"]}  {row["path"]}' for row in files]
    (args.output / "MANIFEST.sha256").write_text("\n".join(digest_lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "repo_id": args.repo_id,
        "listed_paths": len(paths),
        "downloaded_files": len(files),
        "failures": len(failures),
        "manifest_sha256": sha256(manifest_path),
    }, indent=2, sort_keys=True))
    if failures or len(files) != len(paths):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
