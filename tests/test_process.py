"""Process lifecycle tests — no Slack credentials required for most tests."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from miraeping.slack_server import (
    _is_pid_running,
    restart_main,
    start_main,
    status_main,
    stop_main,
)

# Lifecycle tests that actually start the server need real Slack tokens.
_has_slack = bool(os.environ.get("SLACK_BOT_TOKEN") and os.environ.get("SLACK_APP_TOKEN"))
requires_slack = pytest.mark.skipif(not _has_slack, reason="SLACK_BOT_TOKEN and SLACK_APP_TOKEN required")


# ── _is_pid_running ────────────────────────────────────────────────────────

def test_is_pid_running_self():
    assert _is_pid_running(os.getpid()) is True


def test_is_pid_running_nonexistent():
    pid = 99997
    while _is_pid_running(pid) and pid > 2:
        pid -= 1
    assert _is_pid_running(pid) is False


def test_is_pid_running_eperm_returns_true():
    # PID 1 (init/systemd) is always running; normal users can't signal it → EPERM
    assert _is_pid_running(1) is True


# ── fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def pid_log(tmp_path):
    """Returns (pid_file_str, log_file_str) in a temp dir."""
    return str(tmp_path / "srv.pid"), str(tmp_path / "srv.log")


def _start(pid_log, extra=None):
    pid_file, log_file = pid_log
    argv = ["--pid-file", pid_file, "--log-file", log_file]
    if extra:
        argv += extra
    return start_main(argv)


def _stop(pid_log, extra=None):
    pid_file, _ = pid_log
    argv = ["--pid-file", pid_file, "--timeout", "3.0"]
    if extra:
        argv += extra
    return stop_main(argv)


def _status(pid_log):
    pid_file, _ = pid_log
    return status_main(["--pid-file", pid_file])


def _restart(pid_log):
    pid_file, log_file = pid_log
    return restart_main(["--pid-file", pid_file, "--log-file", log_file, "--timeout", "3.0"])


# ── start / stop / status lifecycle ────────────────────────────────────────

@requires_slack
def test_start_stop_status(pid_log):
    pid_file, _ = pid_log

    assert _start(pid_log) == 0
    assert Path(pid_file).exists()
    time.sleep(0.4)

    assert _status(pid_log) == 0      # running
    assert _stop(pid_log) == 0
    assert not Path(pid_file).exists()
    assert _status(pid_log) == 1      # stopped


@requires_slack
def test_double_start_rejected(pid_log):
    assert _start(pid_log) == 0
    time.sleep(0.3)
    assert _start(pid_log) == 1   # already running
    _stop(pid_log)


def test_stop_with_no_pid_file(pid_log):
    assert _stop(pid_log) == 0


def test_stop_with_stale_pid_file(pid_log):
    pid_file, _ = pid_log
    dead_pid = 99996
    while _is_pid_running(dead_pid) and dead_pid > 2:
        dead_pid -= 1
    Path(pid_file).write_text(f"{dead_pid}\n")
    assert _stop(pid_log) == 0
    assert not Path(pid_file).exists()


def test_status_with_no_pid_file(pid_log):
    assert _status(pid_log) == 1


def test_status_with_stale_pid_file(pid_log):
    pid_file, _ = pid_log
    dead_pid = 99995
    while _is_pid_running(dead_pid) and dead_pid > 2:
        dead_pid -= 1
    Path(pid_file).write_text(f"{dead_pid}\n")
    assert _status(pid_log) == 1
    assert not Path(pid_file).exists()


# ── --force SIGKILL escalation ─────────────────────────────────────────────

def test_stop_force_kills_hung_process(pid_log):
    pid_file, _ = pid_log

    # Process that ignores SIGTERM
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    Path(pid_file).write_text(f"{proc.pid}\n")
    time.sleep(0.1)

    try:
        # Normal stop should time out
        rc = stop_main(["--pid-file", pid_file, "--timeout", "0.3"])
        assert rc == 1
        assert Path(pid_file).exists()   # not cleaned up on timeout

        # --force should SIGKILL it
        rc = stop_main(["--pid-file", pid_file, "--timeout", "0.3", "--force"])
        assert rc == 0
        assert not Path(pid_file).exists()
    finally:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        proc.wait(timeout=2)


# ── restart ────────────────────────────────────────────────────────────────

@requires_slack
def test_restart_when_not_running_starts_server(pid_log):
    pid_file, _ = pid_log
    assert not Path(pid_file).exists()
    assert _restart(pid_log) == 0
    assert Path(pid_file).exists()
    _stop(pid_log)


@requires_slack
def test_restart_replaces_running_server(pid_log):
    pid_file, _ = pid_log
    assert _start(pid_log) == 0
    time.sleep(0.3)
    old_pid = int(Path(pid_file).read_text().strip())

    assert _restart(pid_log) == 0
    time.sleep(0.3)
    new_pid = int(Path(pid_file).read_text().strip())

    assert new_pid != old_pid
    assert not _is_pid_running(old_pid)
    assert _is_pid_running(new_pid)
    _stop(pid_log)


def test_stop_without_force_leaves_pid_file_on_timeout(pid_log):
    pid_file, _ = pid_log

    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    Path(pid_file).write_text(f"{proc.pid}\n")
    time.sleep(0.1)

    try:
        rc = stop_main(["--pid-file", pid_file, "--timeout", "0.3"])
        assert rc == 1
        assert Path(pid_file).exists()
    finally:
        proc.kill()
        proc.wait(timeout=2)
