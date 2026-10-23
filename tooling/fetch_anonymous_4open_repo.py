#!/usr/bin/env python3
"""Fetch an anonymous.4open.science repository with an auditable manifest."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import quote

import requests

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Safari/605.1.15"
)


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


def request_headers(base: str, repo_id: str) -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Referer": f"{base}/r/{repo_id}/",
        "Origin": base,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def fetch_one(
    session: requests.Session,
    base: str,
    repo_id: str,
    rel: str,
    root: Path,
    retries: int = 5,
):
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"{base}/api/repo/{repo_id}/file/{quote(rel, safe='/')}"
    last = None
    for attempt in range(retries):
        try:
            response = session.get(
                url,
                headers=request_headers(base, repo_id),
                timeout=120,
                allow_redirects=True,
            )
            response.raise_for_status()
            target.write_bytes(response.content)
            return {
                "path": rel,
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
                "url": url,
                "status_code": response.status_code,
            }
        except Exception as exc:
            last = repr(exc)
            time.sleep(0.75 * (attempt + 1))
    raise RuntimeError(f"failed after {retries} attempts: {rel}: {last}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", default="https://anonymous.4open.science")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    landing_url = f"{args.base}/r/{args.repo_id}/"
    landing = session.get(
        landing_url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
        timeout=120,
        allow_redirects=True,
    )
    landing.raise_for_status()

    list_url = f"{args.base}/api/repo/{args.repo_id}/files/"
    response = session.get(
        list_url,
        headers=request_headers(args.base, args.repo_id),
        timeout=120,
        allow_redirects=True,
    )
    response.raise_for_status()
    listing = response.json()
    paths = sorted(set(iter_paths(listing)))
    if not paths:
        raise RuntimeError("remote repository listing is empty")

    files = []
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {
            pool.submit(
                fetch_one,
                session,
                args.base,
                args.repo_id,
                rel,
                args.output,
            ): rel
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
        "landing_url": landing_url,
        "landing_status": landing.status_code,
        "listing_url": list_url,
        "listing_status": response.status_code,
        "listed_paths": len(paths),
        "downloaded_files": len(files),
        "failures": failures,
        "files": files,
    }
    manifest_path = args.output / "ACQUISITION_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    digest_lines = [f'{row["sha256"]}  {row["path"]}' for row in files]
    (args.output / "MANIFEST.sha256").write_text(
        "\n".join(digest_lines) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "repo_id": args.repo_id,
                "landing_status": landing.status_code,
                "listing_status": response.status_code,
                "listed_paths": len(paths),
                "downloaded_files": len(files),
                "failures": len(failures),
                "manifest_sha256": sha256(manifest_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if failures or len(files) != len(paths):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
