#!/usr/bin/env python3
"""Backward-compatible wrapper for the packaged Slack server CLI."""

from miraeping.slack_server import serve_main


if __name__ == "__main__":
    raise SystemExit(serve_main())
