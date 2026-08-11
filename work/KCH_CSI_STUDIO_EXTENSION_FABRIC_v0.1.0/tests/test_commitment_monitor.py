import json
import os
import sys
import time
from pathlib import Path

import kch_studio.commitment_monitor as commitment_monitor_module
from kch_studio.commitment_monitor import (
    CommitmentMonitor,
    canonical_sha256,
    process_identity,
)


def test_live_process_identity_is_captured(tmp_path):
    monitor = CommitmentMonitor(tmp_path)
    receipt = monitor.register(
        label="self",
        pid=os.getpid(),
        logs=[],
        artifacts=[],
        poll_seconds=1,
    )
    assert receipt["initial_observation"]["status"] == "MONITORING"
    assert receipt["process_identity_captured"] is (process_identity(os.getpid()) is not None)
    assert receipt["commitment_id"] in monitor.active_ids()


def test_terminal_alert_is_exactly_once(tmp_path):
    monitor = CommitmentMonitor(tmp_path)
    receipt = monitor.register(
        label="missing",
        pid=2147483647,
        logs=[],
        artifacts=[str(tmp_path / "expected")],
        poll_seconds=1,
    )
    first = receipt["initial_observation"]
    assert first["status"] == "TERMINATED_MISSING_ARTIFACT_ALERT_REQUIRED"
    assert first["alert_emitted_now"] is True
    assert monitor.check(receipt["commitment_id"])["alert_emitted_now"] is False


def test_owned_success_has_exit_zero_log_hashes_and_valid_receipt(tmp_path):
    monitor = CommitmentMonitor(tmp_path / "monitor")
    artifact = tmp_path / "done.txt"
    code = (
        "from pathlib import Path; "
        f"Path({str(artifact)!r}).write_text('done', encoding='utf-8'); "
        "print('OWNED_SUCCESS')"
    )
    launch = monitor.launch(
        label="success",
        argv=[sys.executable, "-c", code],
        cwd=str(tmp_path),
        environment={"PYTHONUTF8": "1"},
        expected_artifacts=[str(artifact)],
        poll_seconds=1,
    )
    waited = monitor.wait_terminal(
        launch["commitment_id"],
        timeout_seconds=10,
        poll_seconds=0.05,
    )
    observation = waited["observation"]
    assert waited["gate"] == "TERMINAL_OBSERVED"
    assert observation["status"] == "COMPLETED_PASS"
    assert observation["exit_code"] == 0
    assert observation["terminal_receipt"]["valid"] is True
    assert observation["artifacts"][str(artifact.resolve())]["sha256"]
    stdout = Path(launch["stdout_path"])
    assert observation["logs"][str(stdout)]["sha256"]
    assert "OWNED_SUCCESS" in stdout.read_text(encoding="utf-8")
    evidence = monitor.evidence(launch["commitment_id"])
    assert evidence["sha256"] == canonical_sha256(evidence)


def test_launch_rebinds_wrapper_pid_to_canonical_running_worker(tmp_path, monkeypatch):
    monitor = CommitmentMonitor(tmp_path / "monitor")
    wrapper_pid = 2147483647

    class WrapperPopen:
        pid = wrapper_pid

        def __init__(self, argv, **_kwargs):
            request = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
            monitor._atomic_json(
                Path(request["running_path"]),
                {
                    "schema": "kch.monitored-process-running.v0.1.0",
                    "commitment_id": request["commitment_id"],
                    "worker_pid": os.getpid(),
                    "child_pid": os.getpid(),
                    "started_at": "2026-08-11T00:00:00Z",
                    "request_sha256": request["sha256"],
                },
            )

        @staticmethod
        def poll():
            return 0

    monkeypatch.setattr(commitment_monitor_module.subprocess, "Popen", WrapperPopen)
    launch = monitor.launch(
        label="wrapper-pid-rebind",
        argv=[sys.executable, "-c", "print('never-executed-by-test-double')"],
        cwd=str(tmp_path),
        poll_seconds=1,
    )
    assert launch["launcher_pid"] == wrapper_pid
    assert launch["worker_pid"] == os.getpid()
    assert launch["worker_pid_source"] == "CANONICAL_RUNNING_RECEIPT"
    assert launch["launcher_worker_pid_match"] is False
    assert launch["startup_receipt_sha256"]
    assert launch["process_identity_captured"] is True
    assert launch["initial_observation"]["status"] == "MONITORING"


def test_owned_nonzero_process_is_terminal_failure(tmp_path):
    monitor = CommitmentMonitor(tmp_path / "monitor")
    launch = monitor.launch(
        label="exit-seven",
        argv=[sys.executable, "-c", "import sys; print('ADVERSE'); sys.exit(7)"],
        cwd=str(tmp_path),
        expected_exit_codes=[0],
        poll_seconds=1,
    )
    waited = monitor.wait_terminal(
        launch["commitment_id"],
        timeout_seconds=10,
        poll_seconds=0.05,
    )
    assert waited["observation"]["status"] == "COMPLETED_FAIL"
    assert waited["observation"]["exit_code"] == 7
    assert waited["observation"]["alert_emitted_now"] is True


def test_wait_timeout_keeps_same_commitment_active_without_relaunch(tmp_path):
    monitor = CommitmentMonitor(tmp_path / "monitor")
    launch = monitor.launch(
        label="slow",
        argv=[sys.executable, "-c", "import time; time.sleep(0.8)"],
        cwd=str(tmp_path),
        poll_seconds=1,
    )
    timed = monitor.wait_terminal(
        launch["commitment_id"],
        timeout_seconds=0.05,
        poll_seconds=0.01,
    )
    assert timed["gate"] == "WAIT_TIMEOUT_COMMITMENT_REMAINS_ACTIVE"
    assert timed["terminal"] is False
    assert timed["relaunch_performed"] is False
    finished = monitor.wait_terminal(
        launch["commitment_id"],
        timeout_seconds=10,
        poll_seconds=0.05,
    )
    assert finished["observation"]["worker_pid"] == launch["worker_pid"]
    assert finished["observation"]["status"] == "COMPLETED_PASS"


def test_invalid_terminal_receipt_fails_closed(tmp_path):
    terminal = tmp_path / "terminal.json"
    terminal.write_text(
        json.dumps(
            {
                "schema": "kch.monitored-process-terminal.v0.1.0",
                "worker_pid": 2147483647,
                "status": "EXIT_ZERO",
                "exit_code": 0,
                "sha256": "false",
            }
        ),
        encoding="utf-8",
    )
    monitor = CommitmentMonitor(tmp_path / "monitor")
    receipt = monitor.register(
        label="invalid-terminal",
        pid=2147483647,
        logs=[],
        artifacts=[],
        terminal_receipt=str(terminal),
        poll_seconds=1,
    )
    observation = receipt["initial_observation"]
    assert observation["terminal"] is True
    assert observation["status"] == "TERMINAL_EVIDENCE_INVALID_ALERT_REQUIRED"
    assert observation["exit_code"] is None


def test_background_reconciliation_survives_one_commitment_error(tmp_path, monkeypatch):
    monitor = CommitmentMonitor(tmp_path)
    first = monitor.register(
        label="broken-check",
        pid=os.getpid(),
        logs=[],
        artifacts=[],
        poll_seconds=1,
    )["commitment_id"]
    second = monitor.register(
        label="healthy-check",
        pid=os.getpid(),
        logs=[],
        artifacts=[],
        poll_seconds=1,
    )["commitment_id"]
    original = monitor.check

    def isolated(identifier):
        if identifier == first:
            raise RuntimeError("isolated reconciliation defect")
        return original(identifier)

    monkeypatch.setattr(monitor, "check", isolated)
    monitor.start()
    time.sleep(1.3)
    status = monitor.status()
    assert status["background_running"] is True
    assert status["monitor_errors"] >= 1
    assert original(second)["status"] == "MONITORING"
    assert monitor.stop()["running"] is False


def test_terminal_evidence_is_recoverable_after_monitor_restart(tmp_path):
    root = tmp_path / "monitor"
    first_monitor = CommitmentMonitor(root)
    launch = first_monitor.launch(
        label="restart-recovery",
        argv=[sys.executable, "-c", "import time; print('RECOVER'); time.sleep(0.2)"],
        cwd=str(tmp_path),
        poll_seconds=1,
    )
    restarted_monitor = CommitmentMonitor(root)
    waited = restarted_monitor.wait_terminal(
        launch["commitment_id"],
        timeout_seconds=10,
        poll_seconds=0.05,
    )
    assert waited["observation"]["status"] == "COMPLETED_PASS"
    evidence = restarted_monitor.evidence(launch["commitment_id"])
    assert evidence["sha256"] == canonical_sha256(evidence)
    assert evidence["check_sequence"] >= 1
