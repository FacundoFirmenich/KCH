from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def load_contract() -> dict[str, Any]:
    candidates = []
    if os.environ.get("KCH_CONSTRUCT_CONTRACT"):
        candidates.append(Path(os.environ["KCH_CONSTRUCT_CONTRACT"]))
    candidates.extend(
        [
            Path(__file__).resolve().parents[1] / "config" / "construct_persistence.v1.json",
            Path(__file__).resolve().parents[3] / "contracts" / "construct_persistence.v1.json",
        ]
    )
    for path in candidates:
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema") != "kch.csi.construct-persistence-contract.v1":
                raise ValueError("unsupported CONSTRUCT persistence contract schema")
            return payload
    raise FileNotFoundError("construct_persistence.v1.json")


CONTRACT = load_contract()
UPSTREAM = str(CONTRACT["canonical_upstream"])
PLUGIN_NAME = "kch-all-in-one-0-11-33"


class Scope(str, Enum):
    LOCAL_CURRENT_INSTALLATION = "LOCAL_CURRENT_INSTALLATION"
    LOCAL_ALL_REGISTERED_INSTALLATIONS = "LOCAL_ALL_REGISTERED_INSTALLATIONS"
    PUBLIC_FORK_BRANCH = "PUBLIC_FORK_BRANCH"


class Decision(str, Enum):
    YES = "Sí"
    NO = "No"
    NEVER_SESSION = "Nunca en esta sesión"
    ALWAYS_SESSION = "Siempre en esta sesión"


@dataclass(frozen=True)
class Policy:
    schema: str
    scope: str
    decision: str
    lease: str
    session_id: str | None
    targets: tuple[str, ...]
    public_fork: dict[str, str] | None
    upstream_write_allowed: bool
    created_at: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run(command: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr.strip()}")
    return completed.stdout.strip()


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(rendered, encoding="utf-8", newline="\n")
    os.replace(temp, path)


def validate_installation(path: Path) -> str:
    root = path.resolve()
    manifest = root / ".codex-plugin" / "plugin.json"
    if not manifest.is_file():
        raise ValueError(f"not a KCH plugin installation: {root}")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("name") != PLUGIN_NAME:
        raise ValueError(f"unexpected plugin at {root}: {payload.get('name')}")
    return str(root)


def registered_installations(registry_path: Path) -> tuple[str, ...]:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    rows = payload.get("installations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("installation registry is empty")
    targets = [validate_installation(Path(row["path"])) for row in rows if row.get("enabled", True)]
    if not targets:
        raise ValueError("installation registry has no enabled KCH targets")
    return tuple(sorted(set(targets), key=str.casefold))


def github_repo_slug(remote_url: str) -> str:
    match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", remote_url.strip(), re.I)
    if not match:
        raise ValueError("remote is not a recognizable GitHub repository")
    return f"{match.group(1)}/{match.group(2)}"


def public_fork(repo: Path, remote: str, branch: str) -> dict[str, str]:
    root = Path(run(["git", "rev-parse", "--show-toplevel"], repo)).resolve()
    current = run(["git", "branch", "--show-current"], root)
    if not current:
        raise PermissionError("PUBLIC_FORK_BRANCH denied from detached HEAD")
    remote_url = run(["git", "remote", "get-url", remote], root)
    slug = github_repo_slug(remote_url)
    details = json.loads(run(["gh", "repo", "view", slug, "--json", "nameWithOwner,parent,defaultBranchRef"], root))
    owner_repo = str(details["nameWithOwner"])
    parent = details.get("parent") or {}
    parent_name = str(parent.get("nameWithOwner", ""))
    default_branch = str((details.get("defaultBranchRef") or {}).get("name", ""))
    if owner_repo.casefold() == UPSTREAM.casefold():
        raise PermissionError("generic KCH installations cannot persist into the official upstream")
    if parent_name.casefold() != UPSTREAM.casefold():
        raise PermissionError(f"repository is not a verified fork of {UPSTREAM}: {owner_repo}")
    if not branch or branch.casefold() in {"main", "master", default_branch.casefold()}:
        raise PermissionError("public constructs require a non-default fork branch")
    return {
        "repo_root": str(root),
        "remote": remote,
        "remote_url": remote_url,
        "fork": owner_repo,
        "parent": parent_name,
        "branch": branch,
        "observed_current_branch": current,
        "default_branch": default_branch,
    }


def make_policy(args: argparse.Namespace) -> Policy:
    scope = Scope(args.scope)
    decision = Decision(args.decision)
    if decision in {Decision.NEVER_SESSION, Decision.ALWAYS_SESSION} and not args.session_id:
        raise ValueError("session-scoped decisions require --session-id")
    lease = {
        Decision.YES: "ONE_USE",
        Decision.NO: "DENIED_ONCE",
        Decision.NEVER_SESSION: "DENIED_THIS_SESSION",
        Decision.ALWAYS_SESSION: "ALLOWED_THIS_SESSION",
    }[decision]
    targets: tuple[str, ...] = ()
    fork: dict[str, str] | None = None
    if decision in {Decision.YES, Decision.ALWAYS_SESSION}:
        if scope is Scope.LOCAL_CURRENT_INSTALLATION:
            if not args.plugin_root:
                raise ValueError("LOCAL_CURRENT_INSTALLATION requires --plugin-root")
            targets = (validate_installation(args.plugin_root),)
        elif scope is Scope.LOCAL_ALL_REGISTERED_INSTALLATIONS:
            if not args.registry:
                raise ValueError("LOCAL_ALL_REGISTERED_INSTALLATIONS requires --registry")
            targets = registered_installations(args.registry)
        else:
            if not args.repo or not args.branch:
                raise ValueError("PUBLIC_FORK_BRANCH requires --repo and --branch")
            fork = public_fork(args.repo, args.remote, args.branch)
            targets = (fork["repo_root"],)
    return Policy(
        schema="kch.construct-persistence-policy.v1",
        scope=scope.value,
        decision=decision.value,
        lease=lease,
        session_id=args.session_id,
        targets=targets,
        public_fork=fork,
        upstream_write_allowed=False,
        created_at=utc_now(),
    )


def policy_allows(policy: dict[str, Any], target: Path, session_id: str | None) -> tuple[bool, str]:
    if policy.get("upstream_write_allowed") is not False:
        return False, "invalid policy: upstream write ceiling missing"
    lease = policy.get("lease")
    if lease in {"DENIED_ONCE", "DENIED_THIS_SESSION"}:
        return False, str(lease)
    if lease == "ALLOWED_THIS_SESSION" and policy.get("session_id") != session_id:
        return False, "session authority mismatch"
    resolved = str(target.resolve())
    if resolved not in policy.get("targets", []):
        return False, "target outside authorized construct scope"
    fork = policy.get("public_fork")
    if fork and fork.get("parent", "").casefold() != UPSTREAM.casefold():
        return False, "fork parent drift"
    return True, "AUTHORIZED_WITHIN_DECLARED_SCOPE"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Govern KCH CONSTRUCT persistence without transferring upstream authority")
    commands = root.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("configure")
    configure.add_argument("--scope", required=True, choices=[item.value for item in Scope])
    configure.add_argument("--decision", required=True, choices=[item.value for item in Decision])
    configure.add_argument("--session-id")
    configure.add_argument("--plugin-root", type=Path)
    configure.add_argument("--registry", type=Path)
    configure.add_argument("--repo", type=Path)
    configure.add_argument("--remote", default="origin")
    configure.add_argument("--branch")
    configure.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("check")
    check.add_argument("--policy", type=Path, required=True)
    check.add_argument("--target", type=Path, required=True)
    check.add_argument("--session-id")
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "configure":
        policy = make_policy(args)
        payload = asdict(policy)
        atomic_write(args.output, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    allowed, reason = policy_allows(policy, args.target, args.session_id)
    print(json.dumps({"allowed": allowed, "reason": reason}, ensure_ascii=False))
    return 0 if allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())