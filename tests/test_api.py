import miraeping._api as api


def test_get_channel_uses_cache(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_USER_ID", "U012ABCDEF")
    monkeypatch.setattr(api, "_channel_cache", "")

    calls = []

    def fake_call(endpoint, payload):
        calls.append((endpoint, payload))
        return {"channel": {"id": "D123456"}}

    monkeypatch.setattr(api, "_call", fake_call)

    assert api.get_channel() == "D123456"
    assert api.get_channel() == "D123456"
    assert calls == [("conversations.open", {"users": "U012ABCDEF"})]


def test_post_does_nothing_when_channel_missing(monkeypatch) -> None:
    monkeypatch.setattr(api, "get_channel", lambda: "")

    called = []

    def fake_call(endpoint, payload):
        called.append((endpoint, payload))
        return {}

    monkeypatch.setattr(api, "_call", fake_call)

    api.post("hello")
    assert called == []
