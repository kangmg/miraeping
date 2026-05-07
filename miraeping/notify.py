"""miraeping — Slack notifications for lab computations.

Usage
-----
import miraeping

# One-shot message
miraeping.send("Calculation done!")
miraeping.send("Calculation done!", name="Trainer")

# Job-namespaced messages
with miraeping.Job("MD simulation") as job:
    run_md()
    job.send("step : ", step)        # → [MD simulation] step : 1000
    job.send("energy : ", energy)    # → [MD simulation] energy : -123.4

# Periodic status + immediate send
with miraeping.Monitor(lambda: f"loss={loss:.4f}", interval=300, name="MiraePing") as mon:
    train()
    mon.send("checkpoint saved")     # → header + `checkpoint saved` (immediate)
"""
import threading
import time
from typing import Callable, Optional
from miraeping._api import post


def _sanitize_code(text: object) -> str:
    return str(text).replace("\r", "").replace("```", "'''")


def _code_block(text: object) -> str:
    body = _sanitize_code(text)
    return f"```\n{body}\n```"


def _prefix_content(name: Optional[str], text: object) -> str:
    content = _sanitize_code(text)
    if name is None:
        return content
    return f"[{name}] {content}"


def _format_elapsed(started_at: Optional[float]) -> str:
    if started_at is None:
        return "N/A"
    sec = int(max(0, time.time() - started_at))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _format_started(started_at: Optional[float]) -> str:
    if started_at is None:
        return "N/A"
    return time.strftime("%m:%d:%H:%M", time.localtime(started_at))


def _monitor_header(name: Optional[str], started_at: Optional[float], metric: str) -> str:
    label = "unknown" if name is None else str(name)
    header = (
        f"> {label}  |  started: {_format_started(started_at)}"
        f"  |  {metric}: {_format_elapsed(started_at)}"
    )
    return header


def send(message: object, name: Optional[str] = None) -> None:
    """Send an immediate DM.

    - Default (`name=None`): sends message content only.
    - If `name` is provided: sends `[name] <message>`.
    """
    try:
        post(_code_block(_prefix_content(name, message)))
    except Exception:
        pass


# ── job ───────────────────────────────────────────────────────────────────────

class Job:
    """Context manager for job-namespaced DM messages.

    Example
    -------
    with miraeping.Job("VASP relax") as job:
        run_vasp()
        job.send("ionic step : ", step)   # → [VASP relax] ionic step : 42
        job.send("done!")                 # → [VASP relax] done!
    """

    def __init__(self, name: str):
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False  # never suppress exceptions

    def send(self, *args) -> None:
        """Send [name] <args> in a code block — args are string-concatenated."""
        content = "".join(str(a) for a in args)
        try:
            post(_code_block(f"[{self.name}] {content}"))
        except Exception:
            pass


# ── monitor ───────────────────────────────────────────────────────────────────

class Monitor:
    """Periodic status sender with immediate send capability.

    Example
    -------
    with miraeping.Monitor(lambda: f"loss={loss:.4f}", interval=300, name="MiraePing") as mon:
        train()
        mon.send("checkpoint saved")   # immediate status send

    # Manual start/stop
    mon = miraeping.Monitor(status_fn, interval=300, name="MiraePing").start()
    train()
    mon.stop()
    """

    def __init__(
        self,
        status_fn: Callable[[], object],
        interval: int = 300,
        name: Optional[str] = "MiraePing",
    ):
        if not callable(status_fn):
            raise TypeError("status_fn must be callable")
        if interval <= 0:
            raise ValueError("interval must be a positive integer")

        self._fn = status_fn
        self._interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started_at: Optional[float] = None
        self._name = name

    def start(self):
        if self._thread and self._thread.is_alive():
            return self
        self._stop.clear()
        self._started_at = time.time()

        def _loop():
            while not self._stop.wait(self._interval):
                try:
                    msg = self._fn()
                    if msg is not None:
                        post(_code_block(_prefix_content(self._name, msg)))
                except Exception:
                    pass

        self._thread = threading.Thread(
            target=_loop, daemon=True, name="miraeping-monitor"
        )
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def send(self, *args) -> None:
        """Send an immediate status DM without waiting for the next interval."""
        content = "".join(str(a) for a in args)
        try:
            header = _monitor_header(self._name, self._started_at, "runtime")
            body = _code_block(_prefix_content(self._name, content))
            post(f"{header}\n{body}")
        except Exception:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.stop()
