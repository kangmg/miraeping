"""Slack API calls — stdlib urllib only, no extra deps."""
import json
import os
import urllib.request
from pathlib import Path

_SLACK = "https://slack.com/api"
_channel_cache: str = ""
_credentials_loaded: bool = False


def _load_credentials_file() -> None:
    global _credentials_loaded
    if _credentials_loaded:
        return
    _credentials_loaded = True
    cred_file = Path.home() / ".miraeping" / "credentials"
    if not cred_file.exists():
        return
    try:
        for line in cred_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if key in ("SLACK_BOT_TOKEN", "SLACK_USER_ID") and value:
                os.environ.setdefault(key, value)
    except OSError:
        pass


def _call(endpoint: str, payload: dict) -> dict:
    _load_credentials_file()
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        return {}
    req = urllib.request.Request(
        f"{_SLACK}/{endpoint}",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get_channel() -> str:
    global _channel_cache
    if _channel_cache:
        return _channel_cache
    _load_credentials_file()
    user_id = os.environ.get("SLACK_USER_ID", "")
    if not user_id:
        return ""
    resp = _call("conversations.open", {"users": user_id})
    _channel_cache = resp.get("channel", {}).get("id", "")
    return _channel_cache


def post(text: str) -> None:
    ch = get_channel()
    if ch:
        _call("chat.postMessage", {"channel": ch, "text": text})
