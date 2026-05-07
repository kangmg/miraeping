#!/usr/bin/env python3
"""Slack slash-command server (Socket Mode) + local process management CLI.

CLI entrypoints (via pyproject scripts):
  - miraeping-slack-serve
  - miraeping-slack-start
  - miraeping-slack-stop
  - miraeping-slack-status
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("slack_bolt"):
        App = None  # type: ignore[assignment]
        SocketModeHandler = None  # type: ignore[assignment]
    else:
        raise

from miraeping._version import __version__

MAX_OUTPUT_BYTES = 256 * 1024
DEFAULT_PID_FILE = Path.home() / ".miraeping_slack_server.pid"
DEFAULT_LOG_FILE = Path.home() / ".miraeping_slack_server.log"
DEFAULT_GPU_HOST = "g01"
_VALID_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$")


def _require_slack_server_dependency() -> None:
    if App is not None and SocketModeHandler is not None:
        return
    print(
        "[miraeping] ERROR: Slack command server requires optional dependency 'slack-bolt'.",
        file=sys.stderr,
    )
    print(
        "[miraeping]        Install with: pip install 'miraeping[server]'",
        file=sys.stderr,
    )
    raise SystemExit(2)


def _parse_csv_env(name: str) -> Set[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    val = raw.strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    if val in {"0", "false", "no", "off"}:
        return False
    return default


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # process exists but owned by another user
    # On Linux, treat zombie processes (dead but un-reaped) as not running.
    try:
        state_line = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
        for line in state_line.splitlines():
            if line.startswith("State:"):
                return "Z" not in line
    except OSError:
        pass
    return True


def _read_pid(pid_file: Path) -> Optional[int]:
    if not pid_file.exists():
        return None
    try:
        text = pid_file.read_text(encoding="utf-8").strip()
        pid = int(text)
    except (OSError, ValueError):
        return None
    return pid if pid > 1 else None


def _write_pid(pid_file: Path, pid: int) -> None:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = pid_file.with_suffix(".tmp")
    tmp.write_text(f"{pid}\n", encoding="utf-8")
    tmp.replace(pid_file)


def _remove_pid(pid_file: Path) -> None:
    try:
        pid_file.unlink()
    except FileNotFoundError:
        pass


def _run_command(args: List[str], timeout: float = 10.0) -> str:
    proc = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    output = proc.stdout or ""
    if len(output.encode("utf-8")) > MAX_OUTPUT_BYTES:
        output = output[: MAX_OUTPUT_BYTES // 2] + "\n... (truncated)\n"
    if proc.returncode != 0:
        snippet = "\n".join(output.strip().splitlines()[-8:])
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(args)}\n{snippet}")
    return output


def _parse_user_map_env(name: str = "SLACK_QSTAT_USER_MAP") -> Dict[str, str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return {}
    result: Dict[str, str] = {}
    for item in raw.split(","):
        pair = item.strip()
        if not pair or ":" not in pair:
            continue
        slack_id, unix_user = pair.split(":", 1)
        slack_id = slack_id.strip()
        unix_user = unix_user.strip()
        if not slack_id or not unix_user:
            continue
        if not re.match(r"^[UW][A-Z0-9]+$", slack_id):
            continue
        if not re.match(r"^[A-Za-z0-9._-]+$", unix_user):
            continue
        result[slack_id] = unix_user
    return result


def _resolve_qstat_target_user(slack_user_id: str) -> Optional[str]:
    user_map = _parse_user_map_env()
    return user_map.get(slack_user_id)


def _parse_qhost_ncpu(text: str) -> Dict[str, int]:
    host_cpu: Dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        host = parts[0]
        if not re.fullmatch(r"n\d+", host):
            continue
        try:
            ncpu = int(parts[2])
        except ValueError:
            continue
        host_cpu[host] = ncpu
    return host_cpu


def _parse_available_nodes_from_qq(text: str) -> List[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    last = lines[-1]
    match = re.match(r"^(\d+)\s+nodes\s+available:\s*(.*)$", last)
    if not match:
        return []
    tail = match.group(2).strip()
    if not tail:
        return []
    return [node for node in tail.split() if node]


def _parse_qw_count(qstat_text: str) -> int:
    count = 0
    for line in qstat_text.splitlines():
        if not line.strip() or line.startswith("-") or line.startswith("job-ID"):
            continue
        parts = line.split()
        if len(parts) >= 5 and parts[4] == "qw":
            count += 1
    return count


def _extract_slots_from_qstat_parts(parts: List[str]) -> Optional[int]:
    for token in reversed(parts):
        if token.isdigit():
            try:
                return int(token)
            except ValueError:
                return None
    return None


def _parse_qw_counts_by_slots(qstat_text: str) -> Tuple[int, int, int]:
    qw_48 = 0
    qw_64 = 0
    qw_other = 0
    for line in qstat_text.splitlines():
        if not line.strip() or line.startswith("-") or line.startswith("job-ID"):
            continue
        parts = line.split()
        if len(parts) < 5 or parts[4] != "qw":
            continue
        slots = _extract_slots_from_qstat_parts(parts)
        if slots == 48:
            qw_48 += 1
        elif slots == 64:
            qw_64 += 1
        else:
            qw_other += 1
    return qw_48, qw_64, qw_other


def _ascii_table(headers: List[str], rows: List[List[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    border = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    out_lines = [border]
    out_lines.append("| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |")
    out_lines.append(border)
    for row in rows:
        out_lines.append("| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |")
    out_lines.append(border)
    return "\n".join(out_lines)


def _build_qq_response() -> str:
    qq_raw = _run_command(["bash", "-lc", "qq"], timeout=12.0)
    qhost_raw = _run_command(["qhost"], timeout=12.0)
    qstat_all_raw = _run_command(["qstat", "-u", "*"], timeout=12.0)

    available_nodes = _parse_available_nodes_from_qq(qq_raw)
    if not available_nodes:
        raise RuntimeError("failed to parse available nodes from qq output")
    available_set = set(available_nodes)

    host_cpu = _parse_qhost_ncpu(qhost_raw)
    total_48 = sum(1 for cpu in host_cpu.values() if cpu == 48)
    total_64 = sum(1 for cpu in host_cpu.values() if cpu == 64)
    available_48 = sum(1 for host, cpu in host_cpu.items() if cpu == 48 and host in available_set)
    available_64 = sum(1 for host, cpu in host_cpu.items() if cpu == 64 and host in available_set)
    total_nodes = total_48 + total_64
    available_total = available_48 + available_64
    qw_48, qw_64, qw_other = _parse_qw_counts_by_slots(qstat_all_raw)
    qw_total = _parse_qw_count(qstat_all_raw)

    rows: List[List[str]] = [
        ["48-core", f"{available_48}/{total_48}", str(qw_48)],
        ["64-core", f"{available_64}/{total_64}", str(qw_64)],
        ["Total", f"{available_total}/{total_nodes}", str(qw_total)],
    ]
    if qw_other > 0:
        rows.append(["Other slots", "-", str(qw_other)])

    table = _ascii_table(["Node", "Available", "Queued (qw)"], rows)
    lines = [
        "```text",
        table,
        "```",
        "",
        "Available nodes:",
        " ".join(available_nodes),
    ]
    return "\n".join(lines)


def _parse_qstat_rows(qstat_text: str) -> List[Tuple[str, str, str, str, str]]:
    rows: List[Tuple[str, str, str, str, str]] = []
    for line in qstat_text.splitlines():
        if not line.strip() or line.startswith("-") or line.startswith("job-ID"):
            continue
        parts = line.split()
        if len(parts) < 7:
            continue
        job_id = parts[0]
        name = parts[2]
        state = parts[4]
        # Running jobs have a queue column; pending/waiting jobs don't.
        if len(parts) >= 9 and not parts[7].isdigit():
            queue = parts[7]
            slots = parts[8]
        else:
            queue = "-"
            slots = parts[7] if len(parts) > 7 else "-"
        rows.append((job_id, name, state, slots, queue))
    return rows


def _build_qstat_response(slack_user_id: str) -> str:
    target_user = _resolve_qstat_target_user(slack_user_id)
    if not target_user:
        return (
            "Your Slack user ID is not registered yet.\n"
            "To monitor your jobs, We need these two details for ID mapping:\n"
            "1) Server user ID (`echo $USER`)\n"
            "2) Slack user ID (e.g. UXXXXXXXXXX)\n"
            "Share both values and We will register your mapping."
        )

    qstat_raw = _run_command(["qstat", "-u", target_user], timeout=12.0)
    rows = _parse_qstat_rows(qstat_raw)
    if not rows:
        return f"target user: {target_user}\nNo jobs found."

    max_rows = 40
    shown = rows[:max_rows]
    table_rows = [[job_id, name[:20], state, slots, queue] for job_id, name, state, slots, queue in shown]
    table = _ascii_table(["JOB_ID", "NAME", "STATE", "SLOTS", "QUEUE"], table_rows)
    lines = [f"target user: {target_user}", "```text", table]
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows)")
    lines.append("```")
    return "\n".join(lines)


def _parse_submission_dir(qstat_job_text: str) -> str:
    for line in qstat_job_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() == "sge_o_workdir":
            subdir = value.strip()
            return subdir or "-"
    return "-"


def _build_qwd_response(slack_user_id: str) -> str:
    target_user = _resolve_qstat_target_user(slack_user_id)
    if not target_user:
        return (
            "Your Slack user ID is not registered yet.\n"
            "To monitor your jobs, We need these two details for ID mapping:\n"
            "1) Server user ID (`echo $USER`)\n"
            "2) Slack user ID (e.g. UXXXXXXXXXX)\n"
            "Share both values and We will register your mapping."
        )

    qstat_raw = _run_command(["qstat", "-u", target_user], timeout=12.0)
    rows = _parse_qstat_rows(qstat_raw)
    if not rows:
        return f"target user: {target_user}\nNo running job found."

    max_rows = 25
    shown = rows[:max_rows]
    table_rows: List[List[str]] = []
    for job_id, name, state, _slots, _queue in shown:
        try:
            qstat_job_raw = _run_command(["qstat", "-j", job_id], timeout=8.0)
            subdir = _parse_submission_dir(qstat_job_raw)
        except RuntimeError:
            # Job may disappear between qstat and qstat -j lookup.
            subdir = "-"
        table_rows.append([job_id, name[:20], state, subdir])
    table = _ascii_table(["JOB_ID", "NAME", "STATE", "SUBMISSION_DIR"], table_rows)
    lines = [f"target user: {target_user}", "```text", table]
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows)")
    lines.append("```")
    return "\n".join(lines)

def _parse_gpu_rows(nvidia_smi_text: str) -> List[Tuple[str, str, str, str, str]]:
    rows: List[Tuple[str, str, str, str, str]] = []
    for raw in nvidia_smi_text.splitlines():
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) == 5 and parts[0].isdigit():
            idx, name, mem_used, mem_total, util = parts
            rows.append((idx, name, mem_used, mem_total, util))
    return rows


def _build_gpu_response() -> str:
    gpu_host = os.environ.get("SLACK_GPU_SSH_HOST", DEFAULT_GPU_HOST).strip() or DEFAULT_GPU_HOST
    if not _VALID_HOST_RE.match(gpu_host):
        raise RuntimeError("invalid SSH host name")
    cmd = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        "--",
        gpu_host,
        "nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits",
    ]
    raw = _run_command(cmd, timeout=15.0)
    rows = _parse_gpu_rows(raw)
    if not rows:
        raise RuntimeError("failed to parse GPU rows from nvidia-smi output")

    table_rows: List[List[str]] = []
    for idx, name, mem_used_str, mem_total_str, util in rows:
        short_name = name.replace("NVIDIA ", "").strip()[:12]
        try:
            mem_str = f"{int(mem_used_str) / 1024:4.1f} / {int(mem_total_str) / 1024:4.1f}"
        except ValueError:
            mem_str = f"{mem_used_str} / {mem_total_str}"
        table_rows.append([idx, short_name, mem_str, f"{util}%"])

    table = _ascii_table(["GPU", "Name", "Mem (GiB)", "Util"], table_rows)
    return f"node: {gpu_host}\n```text\n{table}\n```"


def _build_command_response(command: str, user_id: str = "") -> str:
    if command == "/qq":
        return _build_qq_response()
    if command == "/qstat":
        return _build_qstat_response(user_id)
    if command == "/qwd":
        return _build_qwd_response(user_id)
    if command in {"/gpu", "/nvidia-smi"}:
        return _build_gpu_response()
    return "Unsupported command."


def serve_main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run Slack slash-command server (Socket Mode).")
    parser.parse_args(argv)  # no args yet, but keeps the interface extensible
    _require_slack_server_dependency()

    bot_token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    app_token = os.environ.get("SLACK_APP_TOKEN", "").strip()

    if not bot_token:
        print("[miraeping] ERROR: SLACK_BOT_TOKEN is required.", file=sys.stderr)
        raise SystemExit(2)
    if not app_token:
        print(
            "[miraeping] ERROR: SLACK_APP_TOKEN (xapp-...) is required for Socket Mode.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if not app_token.startswith("xapp-"):
        print("[miraeping] WARNING: SLACK_APP_TOKEN should start with 'xapp-'.", file=sys.stderr)

    allowed_user_ids = _parse_csv_env("SLACK_ALLOWED_USER_IDS")
    allowed_channel_ids = _parse_csv_env("SLACK_ALLOWED_CHANNEL_IDS")
    enforce_user = _parse_bool_env("SLACK_ENFORCE_USER_ALLOWLIST", bool(allowed_user_ids))
    enforce_channel = _parse_bool_env("SLACK_ENFORCE_CHANNEL_ALLOWLIST", bool(allowed_channel_ids))

    if enforce_user and not allowed_user_ids:
        print(
            "[miraeping] ERROR: SLACK_ENFORCE_USER_ALLOWLIST=1 but SLACK_ALLOWED_USER_IDS is empty.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if enforce_channel and not allowed_channel_ids:
        print(
            "[miraeping] ERROR: SLACK_ENFORCE_CHANNEL_ALLOWLIST=1 but SLACK_ALLOWED_CHANNEL_IDS is empty.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    app = App(token=bot_token)

    def _authorized(command: dict, respond) -> bool:
        if enforce_user and command.get("user_id", "") not in allowed_user_ids:
            respond("Not authorized (user)")
            return False
        if enforce_channel and command.get("channel_id", "") not in allowed_channel_ids:
            respond("Not authorized (channel)")
            return False
        return True

    def _make_handler(slash_command: str):
        def handler(ack, respond, command):
            ack()  # must acknowledge within 3 seconds
            if not _authorized(command, respond):
                return
            try:
                text = _build_command_response(slash_command, command.get("user_id", ""))
            except Exception as exc:
                print(f"[miraeping] {slash_command} error: {exc}", file=sys.stderr)
                text = f"{slash_command} failed — check server logs."
            respond(text)
        return handler

    for cmd in ["/qq", "/qstat", "/qwd", "/gpu", "/nvidia-smi"]:
        app.command(cmd)(_make_handler(cmd))

    if not enforce_user:
        print(
            "[miraeping] WARNING: User allowlist is DISABLED — any workspace member can invoke slash commands.\n"
            "[miraeping]          Set SLACK_ALLOWED_USER_IDS=U...,U... to restrict access.",
            file=sys.stderr,
        )

    print(f"[miraeping] miraeping-slack {__version__} starting (Socket Mode)")
    print(f"[miraeping] User allowlist:    {'ENFORCED' if enforce_user else 'disabled'}")
    print(f"[miraeping] Channel allowlist: {'ENFORCED' if enforce_channel else 'disabled'}")
    print("[miraeping] Commands: /qq  /qstat  /qwd  /gpu  /nvidia-smi")

    SocketModeHandler(app, app_token).start()
    return 0


def start_main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Start Slack command server in background.")
    parser.add_argument("--pid-file", default=str(DEFAULT_PID_FILE))
    parser.add_argument("--log-file", default=str(DEFAULT_LOG_FILE))
    args = parser.parse_args(argv)
    _require_slack_server_dependency()

    pid_file = Path(args.pid_file).expanduser()
    log_file = Path(args.log_file).expanduser()
    existing = _read_pid(pid_file)
    if existing and _is_pid_running(existing):
        print(f"[miraeping] already running (pid={existing})")
        return 1
    _remove_pid(pid_file)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as log:
        cmd = [sys.executable, "-m", "miraeping.slack_server"]
        proc = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    _write_pid(pid_file, proc.pid)
    time.sleep(0.25)
    if proc.poll() is not None:
        _remove_pid(pid_file)
        print(f"[miraeping] failed to start (exit={proc.returncode}). See log: {log_file}")
        return int(proc.returncode or 1)

    print(f"[miraeping] started (pid={proc.pid})")
    print(f"[miraeping] pid file: {pid_file}")
    print(f"[miraeping] log file: {log_file}")
    return 0


def stop_main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Stop background Slack command server.")
    parser.add_argument("--pid-file", default=str(DEFAULT_PID_FILE))
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--force", action="store_true", help="Send SIGKILL if still running after timeout.")
    args = parser.parse_args(argv)

    pid_file = Path(args.pid_file).expanduser()
    pid = _read_pid(pid_file)
    if not pid:
        print("[miraeping] not running (no pid file)")
        return 0
    if not _is_pid_running(pid):
        _remove_pid(pid_file)
        print("[miraeping] not running (stale pid file removed)")
        return 0

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _remove_pid(pid_file)
        print(f"[miraeping] stopped (pid={pid})")
        return 0
    deadline = time.time() + max(0.1, args.timeout)
    while time.time() < deadline:
        if not _is_pid_running(pid):
            _remove_pid(pid_file)
            print(f"[miraeping] stopped (pid={pid})")
            return 0
        time.sleep(0.1)

    if args.force:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # already dead between our check and the kill
        _remove_pid(pid_file)
        print(f"[miraeping] force-killed (pid={pid})")
        return 0

    print(f"[miraeping] still running after {args.timeout:.1f}s (pid={pid}) — use --force to kill")
    return 1


def status_main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Show Slack command server status.")
    parser.add_argument("--pid-file", default=str(DEFAULT_PID_FILE))
    args = parser.parse_args(argv)

    pid_file = Path(args.pid_file).expanduser()
    pid = _read_pid(pid_file)
    if pid and _is_pid_running(pid):
        print(f"running (pid={pid})")
        return 0
    if pid:
        _remove_pid(pid_file)
    print("stopped")
    return 1


def restart_main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Restart background Slack command server.")
    parser.add_argument("--pid-file", default=str(DEFAULT_PID_FILE))
    parser.add_argument("--log-file", default=str(DEFAULT_LOG_FILE))
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args(argv)

    stop_rc = stop_main(["--pid-file", args.pid_file, "--timeout", str(args.timeout), "--force"])
    if stop_rc != 0:
        return stop_rc
    return start_main(["--pid-file", args.pid_file, "--log-file", args.log_file])


def main() -> int:
    return serve_main()


def start_cli() -> int:
    return start_main()


def stop_cli() -> int:
    return stop_main()


def status_cli() -> int:
    return status_main()


def restart_cli() -> int:
    return restart_main()


if __name__ == "__main__":
    raise SystemExit(serve_main())
