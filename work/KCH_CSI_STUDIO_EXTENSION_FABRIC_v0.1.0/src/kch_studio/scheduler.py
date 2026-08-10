from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .contracts import canonical_json, sqlite_connection
from .recovery import RecoveryVault

DDL = """
CREATE TABLE IF NOT EXISTS agendas (
    agenda_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    timezone TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id TEXT PRIMARY KEY,
    agenda_id TEXT NOT NULL REFERENCES agendas(agenda_id),
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    expression TEXT NOT NULL,
    timezone TEXT NOT NULL,
    event_json TEXT NOT NULL,
    next_run_utc TEXT,
    enabled INTEGER NOT NULL,
    announce INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS occurrences (
    occurrence_id TEXT PRIMARY KEY,
    schedule_id TEXT NOT NULL REFERENCES schedules(schedule_id),
    scheduled_for_utc TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    state TEXT NOT NULL,
    launcher_event_id TEXT,
    result_json TEXT,
    completed_at TEXT,
    UNIQUE(schedule_id,scheduled_for_utc)
);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("scheduled time must include a timezone offset")
    return result


def parse_cron_field(expression: str, minimum: int, maximum: int) -> set[int]:
    values: set[int] = set()
    for part in expression.split(","):
        base, slash, step_value = part.partition("/")
        step = int(step_value) if slash else 1
        if step < 1:
            raise ValueError("cron step must be positive")
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            left, right = base.split("-", 1)
            start, end = int(left), int(right)
        else:
            start = end = int(base)
        if start < minimum or end > maximum or start > end:
            raise ValueError("cron field out of range")
        values.update(range(start, end + 1, step))
    return values


class CronExpression:
    def __init__(self, expression: str):
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError("cron requires: minute hour day month weekday")
        self.minute = parse_cron_field(parts[0], 0, 59)
        self.hour = parse_cron_field(parts[1], 0, 23)
        self.day = parse_cron_field(parts[2], 1, 31)
        self.month = parse_cron_field(parts[3], 1, 12)
        self.weekday = parse_cron_field(parts[4], 0, 6)
        self.day_wildcard = parts[2] == "*"
        self.weekday_wildcard = parts[4] == "*"

    def matches(self, value: datetime) -> bool:
        cron_weekday = (value.weekday() + 1) % 7
        day_match = value.day in self.day
        weekday_match = cron_weekday in self.weekday
        if self.day_wildcard:
            calendar_match = weekday_match
        elif self.weekday_wildcard:
            calendar_match = day_match
        else:
            calendar_match = day_match or weekday_match
        return (
            value.minute in self.minute
            and value.hour in self.hour
            and value.month in self.month
            and calendar_match
        )

    def next_after(self, value: datetime) -> datetime:
        cursor = value.replace(second=0, microsecond=0) + timedelta(minutes=1)
        ceiling = cursor + timedelta(days=366 * 5)
        while cursor <= ceiling:
            if self.matches(cursor):
                return cursor
            cursor += timedelta(minutes=1)
        raise ValueError("cron expression produced no occurrence within five years")


class KCHScheduler:
    """Persistent one-shot, interval, cron, agenda, alarm, and notification engine."""

    def __init__(
        self, root: str | Path, event_publisher: Callable[[dict[str, Any]], dict[str, Any]]
    ):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "scheduler.sqlite3"
        self.vault = RecoveryVault(self.root / "recovery")
        self.publish = event_publisher
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        with self.connect() as connection:
            connection.executescript(DDL)
            connection.execute(
                "INSERT OR IGNORE INTO agendas VALUES(?,?,?,?,?)",
                ("AGENDA-DEFAULT", "Principal", "Europe/Madrid", 1, utc_now()),
            )
            connection.commit()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def create_agenda(self, name: str, timezone: str) -> dict[str, Any]:
        ZoneInfo(timezone)
        agenda_id = f"AGENDA-{uuid.uuid4()}"
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO agendas VALUES(?,?,?,?,?)", (agenda_id, name, timezone, 1, utc_now())
            )
            connection.commit()
        return {"agenda_id": agenda_id, "name": name, "timezone": timezone, "enabled": True}

    @staticmethod
    def _next(
        kind: str, expression: str, timezone: str, after_utc: datetime | None = None
    ) -> datetime | None:
        after_utc = after_utc or datetime.now(UTC)
        zone = ZoneInfo(timezone)
        if kind == "ONCE":
            value = parse_iso(expression).astimezone(UTC)
            return value if value > after_utc else None
        if kind == "INTERVAL":
            seconds = int(expression)
            if seconds < 1:
                raise ValueError("interval must be at least one second")
            return after_utc + timedelta(seconds=seconds)
        if kind == "CRON":
            local = after_utc.astimezone(zone)
            return CronExpression(expression).next_after(local).astimezone(UTC)
        raise ValueError("schedule kind must be ONCE, INTERVAL, or CRON")

    def create_schedule(
        self,
        *,
        name: str,
        kind: str,
        expression: str,
        event: dict[str, Any],
        agenda_id: str = "AGENDA-DEFAULT",
        timezone: str | None = None,
        announce: bool = True,
        created_by: str = "USER",
    ) -> dict[str, Any]:
        kind = kind.upper()
        with closing(self.connect()) as connection:
            agenda = connection.execute(
                "SELECT * FROM agendas WHERE agenda_id=? AND enabled=1", (agenda_id,)
            ).fetchone()
            if agenda is None:
                raise KeyError(agenda_id)
        timezone = timezone or str(agenda["timezone"])
        ZoneInfo(timezone)
        next_run = self._next(kind, expression, timezone)
        if next_run is None:
            raise ValueError("schedule has no future occurrence")
        schedule_id = f"SCHED-{uuid.uuid4()}"
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO schedules VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    schedule_id,
                    agenda_id,
                    name,
                    kind,
                    expression,
                    timezone,
                    canonical_json(event),
                    next_run.isoformat().replace("+00:00", "Z"),
                    1,
                    int(announce),
                    created_by,
                    timestamp,
                    timestamp,
                ),
            )
            connection.commit()
        value = self.get_schedule(schedule_id)
        self.vault.save_json(
            f"schedules/{schedule_id}.json",
            value,
            kind="KCH_SCHEDULE",
            actor=created_by,
            operation="CREATE_SCHEDULE",
        )
        self._wake.set()
        return value

    def get_schedule(self, schedule_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM schedules WHERE schedule_id=?", (schedule_id,)
            ).fetchone()
            if row is None:
                raise KeyError(schedule_id)
            value = dict(row)
            value["event"] = json.loads(str(value.pop("event_json")))
            return value

    def set_enabled(
        self, schedule_id: str, enabled: bool, *, actor: str = "USER"
    ) -> dict[str, Any]:
        with self.connect() as connection:
            result = connection.execute(
                "UPDATE schedules SET enabled=?,updated_at=? WHERE schedule_id=?",
                (int(enabled), utc_now(), schedule_id),
            )
            if result.rowcount != 1:
                raise KeyError(schedule_id)
            connection.commit()
        value = self.get_schedule(schedule_id)
        self.vault.save_json(
            f"schedules/{schedule_id}.json",
            value,
            kind="KCH_SCHEDULE",
            actor=actor,
            operation="ENABLE" if enabled else "DISABLE",
        )
        self._wake.set()
        return value

    def run_due(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        due = []
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM schedules WHERE enabled=1 AND next_run_utc IS NOT NULL AND next_run_utc<=? ORDER BY next_run_utc,schedule_id",
                (now.isoformat().replace("+00:00", "Z"),),
            ).fetchall()
            due = [dict(row) for row in rows]
        results = []
        for schedule in due:
            scheduled_for = str(schedule["next_run_utc"])
            occurrence_id = f"OCC-{uuid.uuid4()}"
            try:
                with self.connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        "INSERT INTO occurrences VALUES(?,?,?,?,?,?,?,?)",
                        (
                            occurrence_id,
                            schedule["schedule_id"],
                            scheduled_for,
                            utc_now(),
                            "CLAIMED",
                            None,
                            None,
                            None,
                        ),
                    )
                    next_run = self._next(
                        schedule["kind"],
                        schedule["expression"],
                        schedule["timezone"],
                        parse_iso(scheduled_for),
                    )
                    if schedule["kind"] == "ONCE" or next_run is None:
                        connection.execute(
                            "UPDATE schedules SET enabled=0,next_run_utc=NULL,updated_at=? WHERE schedule_id=?",
                            (utc_now(), schedule["schedule_id"]),
                        )
                    else:
                        connection.execute(
                            "UPDATE schedules SET next_run_utc=?,updated_at=? WHERE schedule_id=?",
                            (
                                next_run.isoformat().replace("+00:00", "Z"),
                                utc_now(),
                                schedule["schedule_id"],
                            ),
                        )
                    connection.commit()
            except sqlite3.IntegrityError:
                continue
            event = json.loads(str(schedule["event_json"]))
            event.update(
                {
                    "type": event.get("type", "scheduled.trigger"),
                    "schedule_id": schedule["schedule_id"],
                    "scheduled_for": scheduled_for,
                    "authority": event.get("authority", "USER_PROGRAM"),
                }
            )
            try:
                published = self.publish(event)
                state = "PUBLISHED_TO_PROACTIVE_LAUNCHER"
                error = None
            except Exception as exc:
                published = None
                state = "PUBLISH_FAILED_PRESERVED"
                error = str(exc)
            body = {"event": event, "published": published, "error": error}
            with self.connect() as connection:
                connection.execute(
                    "UPDATE occurrences SET state=?,launcher_event_id=?,result_json=?,completed_at=? WHERE occurrence_id=?",
                    (
                        state,
                        None if published is None else published.get("event_id"),
                        canonical_json(body),
                        utc_now(),
                        occurrence_id,
                    ),
                )
                connection.commit()
            results.append(
                {
                    "occurrence_id": occurrence_id,
                    "schedule_id": schedule["schedule_id"],
                    "state": state,
                    **body,
                }
            )
        return results

    def start(self) -> dict[str, Any]:
        if self._thread and self._thread.is_alive():
            return self.status()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="kch-scheduler", daemon=True)
        self._thread.start()
        return self.status()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.run_due()
            self._wake.wait(1.0)
            self._wake.clear()

    def stop(self, timeout: float = 5.0) -> dict[str, Any]:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)
        return self.status()

    def status(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            agendas = connection.execute("SELECT COUNT(*) FROM agendas WHERE enabled=1").fetchone()[
                0
            ]
            active = connection.execute(
                "SELECT COUNT(*) FROM schedules WHERE enabled=1"
            ).fetchone()[0]
            occurrences = connection.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0]
        return {
            "schema": "kch.scheduler-status.v0.1.0",
            "running": bool(self._thread and self._thread.is_alive()),
            "active_agendas": agendas,
            "active_schedules": active,
            "occurrences": occurrences,
            "supported": [
                "ONCE",
                "INTERVAL",
                "CRON",
                "MULTIPLE_AGENDAS",
                "ALARMS_AS_EVENTS",
                "NOTIFICATIONS_AS_EVENTS",
            ],
            "double_execution_guard": "UNIQUE(schedule_id,scheduled_for_utc)",
        }
