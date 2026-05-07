"""
Integration tests — require real SLACK_BOT_TOKEN and SLACK_USER_ID.

Run:
    SLACK_BOT_TOKEN=xoxb-... SLACK_USER_ID=U... uv run pytest tests/test_integration.py -v

All tests are skipped automatically when the env vars are absent.
"""
import os
import time

import pytest

_has_slack = bool(os.environ.get("SLACK_BOT_TOKEN") and os.environ.get("SLACK_USER_ID"))
_has_slack_server = bool(_has_slack and os.environ.get("SLACK_APP_TOKEN"))
requires_slack = pytest.mark.skipif(not _has_slack, reason="SLACK_BOT_TOKEN/SLACK_USER_ID not set")
requires_slack_server = pytest.mark.skipif(
    not _has_slack_server,
    reason="SLACK_BOT_TOKEN/SLACK_USER_ID/SLACK_APP_TOKEN not set",
)


@pytest.fixture(autouse=True)
def reset_channel_cache():
    """Clear the module-level channel cache between tests."""
    import miraeping._api as api
    api._channel_cache = ""
    yield
    api._channel_cache = ""


# ── miraeping.send ─────────────────────────────────────────────────────────

@requires_slack
def test_send_plain_message():
    import miraeping
    miraeping.send("[pytest] send() — plain message")


@requires_slack
def test_send_with_name():
    import miraeping
    miraeping.send("send() with name prefix", name="IntegTest")


@requires_slack
def test_send_multiline():
    import miraeping
    miraeping.send("line1\nline2\nline3")


@requires_slack
def test_send_suppresses_backtick_injection():
    import miraeping
    miraeping.send("value: ```injected```")   # should be escaped to '''


# ── miraeping.Job ──────────────────────────────────────────────────────────

@requires_slack
def test_job_context_manager():
    import miraeping
    with miraeping.Job("pytest-job") as job:
        job.send("job context manager message")


@requires_slack
def test_job_multiple_sends():
    import miraeping
    job = miraeping.Job("pytest-job")
    job.send("step 1 done")
    job.send("step 2 done")


# ── miraeping.Monitor ──────────────────────────────────────────────────────

@requires_slack
def test_monitor_periodic_send():
    import miraeping
    tick = [0]

    def status():
        tick[0] += 1
        return f"[pytest] monitor tick {tick[0]}"

    mon = miraeping.Monitor(status, interval=1, name="IntegTest")
    with mon:
        time.sleep(3.5)

    assert tick[0] >= 3, f"expected >=3 ticks, got {tick[0]}"


@requires_slack
def test_monitor_immediate_send():
    import miraeping
    with miraeping.Monitor(lambda: "bg-status", interval=300, name="IntegTest") as mon:
        mon.send("immediate send — should arrive with runtime header")


@requires_slack
def test_monitor_double_start_sends_once_per_interval(monkeypatch):
    import miraeping
    import miraeping._api as api

    sent = []
    original_post = api.post

    def tracking_post(text):
        sent.append(text)
        original_post(text)

    api.post = tracking_post
    try:
        mon = miraeping.Monitor(lambda: "tick", interval=0.2, name="IntegTest")
        mon.start()
        mon.start()   # double start — must not spawn second thread
        time.sleep(0.7)
        mon.stop()
    finally:
        api.post = original_post

    # Without the guard, two threads → ~6 messages in 0.7s at interval=0.2
    # With the guard, one thread → ~3 messages
    assert len(sent) <= 4, f"too many sends ({len(sent)}), likely two threads running"


# ── server start / stop (local) ─────────────────────────────────────────────

@requires_slack_server
def test_server_lifecycle(tmp_path):
    """Start / status / stop cycle — requires real Slack tokens for Socket Mode."""
    import time
    from miraeping.slack_server import start_main, status_main, stop_main

    pid_file = str(tmp_path / "integ.pid")
    log_file = str(tmp_path / "integ.log")

    rc = start_main(["--pid-file", pid_file, "--log-file", log_file])
    assert rc == 0
    time.sleep(1.5)  # allow WebSocket handshake to complete

    assert status_main(["--pid-file", pid_file]) == 0
    assert stop_main(["--pid-file", pid_file, "--timeout", "3.0"]) == 0
    assert status_main(["--pid-file", pid_file]) == 1
