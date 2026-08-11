import os

from kch_studio.commitment_monitor import CommitmentMonitor


def test_live_process_is_monitored(tmp_path):
    monitor = CommitmentMonitor(tmp_path)
    receipt = monitor.register(label="self", pid=os.getpid(), logs=[], artifacts=[], poll_seconds=1)
    assert receipt["initial_observation"]["status"] == "MONITORING"


def test_terminal_alert_is_exactly_once(tmp_path):
    monitor = CommitmentMonitor(tmp_path)
    receipt = monitor.register(label="missing", pid=2147483647, logs=[], artifacts=[str(tmp_path / "expected")], poll_seconds=1)
    assert receipt["initial_observation"]["alert_emitted_now"] is True
    assert monitor.check(receipt["commitment_id"])["alert_emitted_now"] is False
