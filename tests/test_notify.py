import pytest
from time import struct_time

import miraeping.notify as notify


def test_send_with_name_formats_code_block(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = []
    monkeypatch.setattr(notify, "post", sent.append)

    notify.send("Calculation done!", name="Trainer")

    assert sent == ["```\n[Trainer] Calculation done!\n```"]


def test_send_without_name_formats_code_block(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = []
    monkeypatch.setattr(notify, "post", sent.append)

    notify.send("Done")

    assert sent == ["```\nDone\n```"]


def test_monitor_send_adds_runtime_header(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = []
    monkeypatch.setattr(notify, "post", sent.append)
    monkeypatch.setattr(notify.time, "time", lambda: 1061.0)
    monkeypatch.setattr(
        notify.time,
        "localtime",
        lambda _ts: struct_time((2026, 5, 6, 14, 5, 0, 0, 0, -1)),
    )

    mon = notify.Monitor(lambda: "ignored", interval=1, name="MiraePing")
    mon._started_at = 1000.0
    mon.send("checkpoint saved")

    assert len(sent) == 1
    assert "started: 05:06:14:05" in sent[0]
    assert "runtime: 00:01:01" in sent[0]
    assert "checkpoint saved" in sent[0]


def test_monitor_requires_callable_status_fn() -> None:
    with pytest.raises(TypeError):
        notify.Monitor("not-callable")  # type: ignore[arg-type]


def test_monitor_requires_positive_interval() -> None:
    with pytest.raises(ValueError):
        notify.Monitor(lambda: None, interval=0)
