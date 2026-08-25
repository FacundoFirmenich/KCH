from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

from kch_native_state import canonical, connect, set_setting, sha256_text, utc_now, verify_chain


def require_user_gesture(challenge: str) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SystemExit("DENIED_NOT_A_TRUSTED_INTERACTIVE_USER_GESTURE")
    typed = input(f"Escriba exactamente [{challenge}]: ")
    if typed != challenge:
        raise SystemExit("DENIED_CHALLENGE_MISMATCH")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_from_resource(resource: str) -> Path | None:
    return Path(resource[5:]) if resource.startswith("file:") else None


def main() -> int:
    parser = argparse.ArgumentParser(description="KCH Native 0.11.33 user control surface")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    config = sub.add_parser("config")
    config.add_argument("key", choices=["locks_enabled", "startup_notice", "response_mode", "persist_exact_inputs"])
    config.add_argument("value")
    lock = sub.add_parser("lock-add")
    lock.add_argument("kind", choices=["EXACT", "PREFIX", "GLOB"])
    lock.add_argument("pattern")
    bundle = sub.add_parser("lock-bundle")
    bundle.add_argument("manifest")
    disable = sub.add_parser("lock-disable")
    disable.add_argument("lock_id")
    sub.add_parser("lock-verify")
    propose = sub.add_parser("propose")
    propose.add_argument("proposal_id")
    propose.add_argument("--reason", required=True)
    propose.add_argument("--impact", required=True)
    propose.add_argument("--recovery", required=True)
    authorize = sub.add_parser("authorize")
    authorize.add_argument("proposal_id")
    args = parser.parse_args()

    db = connect()
    try:
        if args.command == "status":
            settings = {row["key"]: row["value"] for row in db.execute("SELECT * FROM settings ORDER BY key")}
            locks = [dict(row) for row in db.execute("SELECT * FROM locks ORDER BY created_at,id")]
            pending = [dict(row) for row in db.execute(
                "SELECT id,created_at,session_id,tool_name,args_sha256,reason,impact,recovery,status "
                "FROM proposals WHERE status IN ('DRAFT','PROPOSED','AUTHORIZED') ORDER BY created_at"
            )]
            valid, events = verify_chain(db)
            print(json.dumps({"settings": settings, "locks": locks, "pending": pending, "ledger_chain_valid": valid, "events": events}, ensure_ascii=False, indent=2))
        elif args.command == "config":
            allowed = {
                "locks_enabled": {"true", "false"},
                "startup_notice": {"true", "false"},
                "persist_exact_inputs": {"true", "false"},
                "response_mode": {"concise", "explanatory", "extended"},
            }
            if args.value not in allowed[args.key]:
                raise SystemExit("INVALID_VALUE")
            challenge = f"KCH CONFIG {args.key}={args.value}"
            require_user_gesture(challenge)
            set_setting(db, args.key, args.value)
            print("CONFIGURED")
        elif args.command == "lock-add":
            lock_id = str(uuid.uuid4())
            challenge = f"KCH LOCK {args.kind} {args.pattern}"
            require_user_gesture(challenge)
            baseline = None
            target = file_from_resource(args.pattern) if args.kind == "EXACT" else None
            if target and target.is_file():
                baseline = file_sha256(target)
            db.execute(
                "INSERT INTO locks(id,kind,pattern,enabled,created_at,baseline_sha256) VALUES(?,?,?,?,?,?)",
                (lock_id, args.kind, args.pattern, 1, utc_now(), baseline),
            )
            db.commit()
            print(json.dumps({"status": "LOCK_CREATED", "lock_id": lock_id}))
        elif args.command == "lock-bundle":
            manifest_path = Path(args.manifest).resolve()
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            if document.get("schema") != "kch.native-lock-bundle.v0.1.0":
                raise SystemExit("INVALID_LOCK_BUNDLE_SCHEMA")
            locks = document.get("locks")
            if not isinstance(locks, list) or not locks:
                raise SystemExit("EMPTY_LOCK_BUNDLE")
            normalized = []
            seen = set()
            for item in locks:
                kind = item.get("kind")
                pattern = item.get("pattern")
                baseline = item.get("baseline_sha256")
                if kind not in {"EXACT", "PREFIX", "GLOB"} or not isinstance(pattern, str):
                    raise SystemExit("INVALID_LOCK_BUNDLE_ENTRY")
                key = (kind, os.path.normcase(pattern))
                if key in seen:
                    raise SystemExit("DUPLICATE_LOCK_BUNDLE_ENTRY")
                seen.add(key)
                if baseline is not None and (
                    not isinstance(baseline, str) or len(baseline) != 64
                    or any(ch not in "0123456789abcdef" for ch in baseline.lower())
                ):
                    raise SystemExit("INVALID_BASELINE_SHA256")
                normalized.append((kind, pattern, baseline.lower() if baseline else None))
            bundle_sha = sha256_text(canonical(document))
            challenge = f"KCH LOCK BUNDLE {bundle_sha[:16]} {len(normalized)}"
            require_user_gesture(challenge)
            db.execute("BEGIN IMMEDIATE")
            created = []
            for kind, pattern, baseline in normalized:
                lock_id = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO locks(id,kind,pattern,enabled,created_at,baseline_sha256) VALUES(?,?,?,?,?,?)",
                    (lock_id, kind, pattern, 1, utc_now(), baseline),
                )
                created.append(lock_id)
            db.commit()
            set_setting(db, "locks_enabled", "true")
            print(json.dumps({"status": "LOCK_BUNDLE_CREATED", "bundle_sha256": bundle_sha, "locks": created}))
        elif args.command == "lock-disable":
            challenge = f"KCH UNLOCK {args.lock_id}"
            require_user_gesture(challenge)
            changed = db.execute(
                "UPDATE locks SET enabled=0,disabled_at=? WHERE id=? AND enabled=1",
                (utc_now(), args.lock_id),
            ).rowcount
            db.commit()
            if changed != 1:
                raise SystemExit("LOCK_NOT_ACTIVE")
            print("LOCK_DISABLED")
        elif args.command == "lock-verify":
            results = []
            for row in db.execute("SELECT * FROM locks WHERE enabled=1 ORDER BY created_at,id"):
                target = file_from_resource(row["pattern"]) if row["kind"] == "EXACT" else None
                if not row["baseline_sha256"]:
                    state = "NO_FILE_BASELINE"
                    observed = None
                elif not target or not target.is_file():
                    state = "MISSING"
                    observed = None
                else:
                    observed = file_sha256(target)
                    state = "MATCH" if observed == row["baseline_sha256"] else "DRIFT"
                results.append({
                    "lock_id": row["id"], "pattern": row["pattern"], "state": state,
                    "baseline_sha256": row["baseline_sha256"], "observed_sha256": observed,
                })
            print(json.dumps({"status": "PASS" if all(r["state"] in {"MATCH", "NO_FILE_BASELINE"} for r in results) else "FAIL", "locks": results}, ensure_ascii=False, indent=2))
        elif args.command == "propose":
            changed = db.execute(
                "UPDATE proposals SET reason=?,impact=?,recovery=?,status='PROPOSED' WHERE id=? AND status='DRAFT'",
                (args.reason, args.impact, args.recovery, args.proposal_id),
            ).rowcount
            db.commit()
            if changed != 1:
                raise SystemExit("PROPOSAL_NOT_DRAFT")
            print("PROPOSED_FOR_EXACT_USER_AUTHORIZATION")
        elif args.command == "authorize":
            row = db.execute("SELECT * FROM proposals WHERE id=?", (args.proposal_id,)).fetchone()
            if not row or row["status"] != "PROPOSED":
                raise SystemExit("PROPOSAL_NOT_READY")
            challenge = f"AUTORIZO {row['id']} {row['args_sha256'][:16]}"
            require_user_gesture(challenge)
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO authorizations(proposal_id,session_id,args_sha256,authorized_at) VALUES(?,?,?,?)",
                (row["id"], row["session_id"], row["args_sha256"], utc_now()),
            )
            db.execute("UPDATE proposals SET status='AUTHORIZED' WHERE id=?", (row["id"],))
            db.commit()
            print("AUTHORIZED_ONCE_EXACT_ATTEMPT_ONLY")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
