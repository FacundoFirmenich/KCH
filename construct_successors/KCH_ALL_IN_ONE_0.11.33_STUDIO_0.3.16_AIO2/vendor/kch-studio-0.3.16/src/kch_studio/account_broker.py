from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import uuid
import webbrowser
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .contracts import canonical_json, safe_child, sqlite_connection
from .permissions import PermissionGovernor
from .recovery import RecoveryVault

DDL = """
CREATE TABLE IF NOT EXISTS account_requests (
    request_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    account_hint TEXT,
    scopes_json TEXT NOT NULL,
    purpose TEXT NOT NULL,
    preferred_surface TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS account_leases (
    lease_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES account_requests(request_id),
    duration_class TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    max_uses INTEGER,
    used_count INTEGER NOT NULL,
    state TEXT NOT NULL,
    local_enforcement TEXT NOT NULL,
    remote_revocation_contract TEXT NOT NULL,
    profile_root TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS account_events (
    event_id TEXT PRIMARY KEY,
    lease_id TEXT,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    state TEXT NOT NULL,
    evidence_json TEXT NOT NULL
);
"""

PROVIDERS: dict[str, dict[str, Any]] = {
    "SSH": {
        "surface": "TERMINAL",
        "command": "ssh-add",
        "remote_revocation": "AGENT_KEY_LIFETIME_ENFORCED",
        "web": None,
    },
    "GITHUB": {
        "surface": "TERMINAL_THEN_WEB",
        "command": "gh",
        "remote_revocation": "GH_LOGOUT_LOCAL_ONLY_REMOTE_TOKEN_NOT_REVOKED",
        "web": "https://github.com/settings/personal-access-tokens/new",
    },
    "GOOGLE_DRIVE": {
        "surface": "SYSTEM_BROWSER_REQUIRED",
        "command": None,
        "remote_revocation": "PROVIDER_TOKEN_EXPIRY_OR_EXPLICIT_GOOGLE_REVOCATION_REQUIRED",
        "web": "https://myaccount.google.com/permissions",
    },
    "COLAB": {
        "surface": "SYSTEM_BROWSER_REQUIRED",
        "command": None,
        "remote_revocation": "GOOGLE_SESSION_EXTERNAL_TO_KCH",
        "web": "https://colab.research.google.com/",
    },
    "KAGGLE": {
        "surface": "TERMINAL_THEN_WEB",
        "command": "kaggle",
        "remote_revocation": "LOCAL_ISOLATED_PROFILE_REMOVAL_REMOTE_OAUTH_REVOCATION_UNVERIFIED",
        "web": "https://www.kaggle.com/settings/account",
    },
    "GENERIC_OAUTH": {
        "surface": "DEVICE_OR_SYSTEM_BROWSER",
        "command": None,
        "remote_revocation": "PROVIDER_SPECIFIC_REQUIRED",
        "web": None,
    },
}

DURATIONS = {
    "PUNCTUAL": timedelta(minutes=15),
    "DAILY": timedelta(days=1),
    "WEEKLY": timedelta(days=7),
    "MONTHLY": timedelta(days=30),
    "QUARTERLY": timedelta(days=90),
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class AccountPermissionBroker:
    """Finite account-access leases with terminal-first authentication surfaces."""

    def __init__(self, root: str | Path, permissions: PermissionGovernor):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "accounts.sqlite3"
        self.profiles = self.root / "profiles"
        self.profiles.mkdir(exist_ok=True)
        self.permissions = permissions
        self.vault = RecoveryVault(self.root / "recovery")
        with self.connect() as connection:
            connection.executescript(DDL)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def request(
        self, *, provider: str, scopes: list[str], purpose: str, account_hint: str | None = None
    ) -> dict[str, Any]:
        provider = provider.upper()
        if provider not in PROVIDERS:
            raise ValueError(
                f"unsupported provider; use GENERIC_OAUTH with an explicit adapter: {provider}"
            )
        if not scopes or not purpose.strip():
            raise ValueError("least-privilege scopes and purpose are required")
        request_id = f"AREQ-{uuid.uuid4()}"
        timestamp = utc_now()
        descriptor = PROVIDERS[provider]
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO account_requests VALUES(?,?,?,?,?,?,?,?)",
                (
                    request_id,
                    provider,
                    account_hint,
                    canonical_json(sorted(set(scopes))),
                    purpose,
                    descriptor["surface"],
                    "AWAITING_USER_DURATION",
                    timestamp,
                ),
            )
            connection.commit()
        value = {
            "request_id": request_id,
            "provider": provider,
            "account_hint": account_hint,
            "scopes": sorted(set(scopes)),
            "purpose": purpose,
            "preferred_surface": descriptor["surface"],
            "duration_choices": [*DURATIONS, "CUSTOM_FINITE"],
            "forever_available": False,
            "remote_revocation_contract": descriptor["remote_revocation"],
            "state": "AWAITING_USER_DURATION",
        }
        self.vault.save_json(
            f"requests/{request_id}.json",
            value,
            kind="ACCOUNT_PERMISSION_REQUEST",
            actor="KCH_SYSTEM",
            operation="REQUEST",
        )
        return value

    def approve(
        self, request_id: str, *, duration_class: str, custom_expires_at: str | None = None
    ) -> dict[str, Any]:
        with self.connect() as connection:
            request = connection.execute(
                "SELECT * FROM account_requests WHERE request_id=? AND state='AWAITING_USER_DURATION'",
                (request_id,),
            ).fetchone()
            if request is None:
                raise KeyError(request_id)
            now = datetime.now(UTC)
            duration_class = duration_class.upper()
            if duration_class == "CUSTOM_FINITE":
                if custom_expires_at is None:
                    raise ValueError("custom finite lease requires expires_at")
                expires = datetime.fromisoformat(custom_expires_at.replace("Z", "+00:00"))
                if expires.tzinfo is None or expires <= now:
                    raise ValueError(
                        "custom expiration must be finite, timezone-aware, and in the future"
                    )
            elif duration_class in DURATIONS:
                expires = now + DURATIONS[duration_class]
            else:
                raise ValueError(
                    "duration must be punctual, daily, weekly, monthly, quarterly, or custom finite"
                )
            lease_id = f"LEASE-{uuid.uuid4()}"
            profile = safe_child(self.profiles, lease_id)
            profile.mkdir()
            marker = {
                "lease_id": lease_id,
                "request_id": request_id,
                "expires_at": expires.isoformat(),
                "disposable": True,
            }
            (profile / ".kch-account-profile.json").write_text(
                canonical_json(marker) + "\n", encoding="utf-8"
            )
            max_uses = 1 if duration_class == "PUNCTUAL" else None
            descriptor = PROVIDERS[str(request["provider"])]
            connection.execute(
                "INSERT INTO account_leases VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    lease_id,
                    request_id,
                    duration_class,
                    now.isoformat(),
                    expires.isoformat(),
                    max_uses,
                    0,
                    "APPROVED_NOT_AUTHENTICATED",
                    "KCH_PERMISSION_AND_ISOLATED_PROFILE_EXPIRY",
                    descriptor["remote_revocation"],
                    str(profile),
                    utc_now(),
                ),
            )
            connection.execute(
                "UPDATE account_requests SET state='LEASE_APPROVED' WHERE request_id=?",
                (request_id,),
            )
            connection.commit()
        value = self.get_lease(lease_id)
        self.vault.save_json(
            f"leases/{lease_id}.json",
            value,
            kind="FINITE_ACCOUNT_LEASE",
            actor="USER",
            operation="APPROVE_FINITE",
        )
        return value

    def get_lease(self, lease_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT l.*,r.provider,r.account_hint,r.scopes_json,r.purpose,r.preferred_surface FROM account_leases l JOIN account_requests r USING(request_id) WHERE lease_id=?",
                (lease_id,),
            ).fetchone()
            if row is None:
                raise KeyError(lease_id)
            value = dict(row)
            value["scopes"] = json.loads(str(value.pop("scopes_json")))
            value["forever"] = False
            return value

    def _command(
        self, lease: dict[str, Any], *, ssh_key: str | None = None
    ) -> tuple[list[str] | None, dict[str, str]]:
        provider = lease["provider"]
        scopes = lease["scopes"]
        profile = lease["profile_root"]
        environment = dict(os.environ)
        if provider == "SSH":
            if not ssh_key:
                raise ValueError("SSH terminal flow requires an explicit key path")
            seconds = max(
                1,
                int(
                    (
                        datetime.fromisoformat(lease["expires_at"]) - datetime.now(UTC)
                    ).total_seconds()
                ),
            )
            return ["ssh-add", "-t", str(seconds), str(Path(ssh_key).resolve())], environment
        if provider == "GITHUB":
            environment["GH_CONFIG_DIR"] = str(Path(profile) / "gh")
            return [
                "gh",
                "auth",
                "login",
                "--hostname",
                "github.com",
                "--web",
                "--clipboard",
                "--scopes",
                ",".join(scopes),
            ], environment
        if provider == "KAGGLE":
            environment["KAGGLE_CONFIG_DIR"] = str(Path(profile) / "kaggle")
            return ["kaggle", "auth", "login"], environment
        return None, environment

    def launch_auth(self, lease_id: str, *, ssh_key: str | None = None) -> dict[str, Any]:
        lease = self.get_lease(lease_id)
        if datetime.fromisoformat(lease["expires_at"]) <= datetime.now(UTC):
            raise ValueError("lease already expired")
        command, environment = self._command(lease, ssh_key=ssh_key)
        descriptor = PROVIDERS[lease["provider"]]
        if command is not None:
            if shutil.which(command[0]) is None:
                state = "TERMINAL_COMMAND_UNAVAILABLE_WEB_FALLBACK_REQUIRED"
                process_id = None
            else:
                flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
                process = subprocess.Popen(
                    command,
                    cwd=lease["profile_root"],
                    env=environment,
                    creationflags=flags,
                    shell=False,
                )
                state = "INTERACTIVE_TERMINAL_LAUNCHED"
                process_id = process.pid
        elif descriptor["web"]:
            webbrowser.open(descriptor["web"], new=2)
            state = "SYSTEM_BROWSER_LAUNCHED_REQUIRED_BY_PROVIDER"
            process_id = None
        else:
            state = "PROVIDER_ADAPTER_CONFIGURATION_REQUIRED"
            process_id = None
        event = {
            "lease_id": lease_id,
            "state": state,
            "pid": process_id,
            "command": None if command is None else command,
            "secret_logged": False,
        }
        self._event(lease_id, "LAUNCH_AUTH", state, event)
        return event

    def _event(
        self, lease_id: str | None, action: str, state: str, evidence: dict[str, Any]
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO account_events VALUES(?,?,?,?,?,?)",
                (
                    f"AEVT-{uuid.uuid4()}",
                    lease_id,
                    utc_now(),
                    action,
                    state,
                    canonical_json(evidence),
                ),
            )
            connection.commit()

    def authorize_use(self, lease_id: str) -> dict[str, Any]:
        lease = self.get_lease(lease_id)
        now = datetime.now(UTC)
        if now >= datetime.fromisoformat(lease["expires_at"]):
            self.expire_due()
            raise PermissionError("account lease expired")
        if lease["max_uses"] is not None and int(lease["used_count"]) >= int(lease["max_uses"]):
            raise PermissionError("punctual account lease already consumed")
        with self.connect() as connection:
            connection.execute(
                "UPDATE account_leases SET used_count=used_count+1,state='ACTIVE' WHERE lease_id=?",
                (lease_id,),
            )
            connection.commit()
        receipt = {
            "lease_id": lease_id,
            "provider": lease["provider"],
            "authorized": True,
            "expires_at": lease["expires_at"],
            "use_number": int(lease["used_count"]) + 1,
        }
        self._event(lease_id, "AUTHORIZE_USE", "ACTIVE", receipt)
        return receipt

    def expire_due(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or datetime.now(UTC)
        results = []
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT lease_id FROM account_leases WHERE state NOT IN ('EXPIRED_LOCAL','REVOKED') AND expires_at<=?",
                (now.isoformat(),),
            ).fetchall()
        for row in rows:
            lease = self.get_lease(row["lease_id"])
            profile = Path(lease["profile_root"])
            marker = profile / ".kch-account-profile.json"
            cleanup = "PROFILE_ALREADY_ABSENT"
            if (
                marker.is_file()
                and json.loads(marker.read_text(encoding="utf-8"))["lease_id"] == lease["lease_id"]
            ):
                shutil.rmtree(profile)
                cleanup = "ISOLATED_PROFILE_REMOVED"
            with self.connect() as connection:
                connection.execute(
                    "UPDATE account_leases SET state='EXPIRED_LOCAL' WHERE lease_id=?",
                    (lease["lease_id"],),
                )
                connection.commit()
            result = {
                "lease_id": lease["lease_id"],
                "state": "EXPIRED_LOCAL",
                "cleanup": cleanup,
                "KCH_access": "DENIED_AFTER_EXPIRY",
                "remote_revocation": lease["remote_revocation_contract"],
                "remote_revocation_verified": lease["remote_revocation_contract"]
                == "AGENT_KEY_LIFETIME_ENFORCED",
            }
            self._event(lease["lease_id"], "EXPIRE", "EXPIRED_LOCAL", result)
            results.append(result)
        return results

    def status(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            active = connection.execute(
                "SELECT COUNT(*) FROM account_leases WHERE state IN ('ACTIVE','APPROVED_NOT_AUTHENTICATED')"
            ).fetchone()[0]
            expired = connection.execute(
                "SELECT COUNT(*) FROM account_leases WHERE state='EXPIRED_LOCAL'"
            ).fetchone()[0]
        return {
            "schema": "kch.account-permission-broker-status.v0.1.0",
            "providers": PROVIDERS,
            "active_leases": active,
            "expired_local_leases": expired,
            "allowed_duration_classes": [*DURATIONS, "CUSTOM_FINITE"],
            "indefinite_lease_supported": False,
            "terminal_first": True,
        }
