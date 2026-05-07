"""Thread-behavior tests for Monitor — no env vars required."""
import time

import pytest

import miraeping.notify as notify


def _noop_post(monkeypatch):
    monkeypatch.setattr(notify, "post", lambda _: None)


# ── start guard ────────────────────────────────────────────────────────────

def test_start_returns_self(monkeypatch):
    _noop_post(monkeypatch)
    mon = notify.Monitor(lambda: "x", interval=60)
    assert mon.start() is mon
    mon.stop()


def test_double_start_returns_same_instance(monkeypatch):
    _noop_post(monkeypatch)
    mon = notify.Monitor(lambda: "x", interval=60)
    mon.start()
    thread_before = mon._thread
    mon.start()  # second call — should be no-op
    assert mon._thread is thread_before
    mon.stop()


def test_double_start_does_not_spawn_extra_thread(monkeypatch):
    _noop_post(monkeypatch)
    mon = notify.Monitor(lambda: "x", interval=60)
    mon.start()
    mon.start()
    assert threading_count(mon) == 1
    mon.stop()


def threading_count(mon):
    import threading
    return sum(1 for t in threading.enumerate() if t.name == "miraeping-monitor" and t.is_alive())


# ── stop ───────────────────────────────────────────────────────────────────

def test_stop_resets_thread_to_none(monkeypatch):
    _noop_post(monkeypatch)
    mon = notify.Monitor(lambda: "x", interval=60)
    mon.start()
    assert mon._thread is not None
    mon.stop()
    assert mon._thread is None


def test_stop_is_idempotent(monkeypatch):
    _noop_post(monkeypatch)
    mon = notify.Monitor(lambda: "x", interval=60)
    mon.start()
    mon.stop()
    mon.stop()  # must not raise


def test_stop_before_start_is_safe(monkeypatch):
    _noop_post(monkeypatch)
    mon = notify.Monitor(lambda: "x", interval=60)
    mon.stop()  # never started — must not raise


# ── restart ────────────────────────────────────────────────────────────────

def test_can_restart_after_stop(monkeypatch):
    _noop_post(monkeypatch)
    mon = notify.Monitor(lambda: "x", interval=60)
    mon.start()
    mon.stop()
    mon.start()
    assert mon._thread is not None
    assert mon._thread.is_alive()
    mon.stop()


# ── periodic loop ──────────────────────────────────────────────────────────

def test_loop_calls_status_fn_periodically(monkeypatch):
    _noop_post(monkeypatch)
    calls = []
    mon = notify.Monitor(lambda: calls.append(1) or "tick", interval=0.05)
    with mon:
        time.sleep(0.3)
    assert len(calls) >= 3


def test_loop_sends_messages_periodically(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "post", sent.append)
    mon = notify.Monitor(lambda: "loop-status", interval=0.05)
    with mon:
        time.sleep(0.3)
    assert len(sent) >= 3
    assert all("loop-status" in m for m in sent)


def test_loop_skips_none_return(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "post", sent.append)
    mon = notify.Monitor(lambda: None, interval=0.05)
    with mon:
        time.sleep(0.25)
    assert sent == []


def test_loop_survives_status_fn_exception(monkeypatch):
    _noop_post(monkeypatch)
    calls = []

    def flaky():
        calls.append(1)
        raise RuntimeError("intentional error")

    mon = notify.Monitor(flaky, interval=0.05)
    with mon:
        time.sleep(0.3)
    assert len(calls) >= 3


# ── context manager ────────────────────────────────────────────────────────

def test_context_manager_starts_and_stops(monkeypatch):
    _noop_post(monkeypatch)
    mon = notify.Monitor(lambda: "x", interval=60)
    with mon as m:
        assert m is mon
        assert mon._thread is not None
        assert mon._thread.is_alive()
    assert mon._thread is None


def test_context_manager_stops_on_exception(monkeypatch):
    _noop_post(monkeypatch)
    mon = notify.Monitor(lambda: "x", interval=60)
    try:
        with mon:
            raise ValueError("test error")
    except ValueError:
        pass
    assert mon._thread is None
