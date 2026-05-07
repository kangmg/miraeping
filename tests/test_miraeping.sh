#!/usr/bin/env bash
# Bash test suite for miraeping.sh
#
# Usage (no Slack):
#   bash tests/test_miraeping.sh
#
# Usage (with real Slack):
#   SLACK_BOT_TOKEN=xoxb-... SLACK_USER_ID=U... bash tests/test_miraeping.sh

set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export MIRAEPING_AUTO_TRAP=0        # don't install traps during test
export MIRAEPING_AUTO_FINAL=0       # suppress auto Done/Failed sends
export MIRAEPING_AUTO_INIT_SUBMIT=0

# Use a fixed unique JOB_ID so _mp_prefix is predictable throughout the suite.
export JOB_ID="miraeping_test_$$"

# shellcheck source=../miraeping.sh
source "${REPO_DIR}/miraeping.sh"

# ── mini test framework ─────────────────────────────────────────────────────

_PASS=0; _FAIL=0; _SKIP=0

_assert() {
    local desc="$1" got="$2" want="${3:-0}"
    if [ "${got}" = "${want}" ]; then
        printf '  PASS  %s\n' "${desc}"
        _PASS=$((_PASS + 1))
    else
        printf '  FAIL  %s  (got=%s want=%s)\n' "${desc}" "${got}" "${want}"
        _FAIL=$((_FAIL + 1))
    fi
}

_skip() {
    printf '  SKIP  %s  (%s)\n' "$1" "${2:-}"
    _SKIP=$((_SKIP + 1))
}

_run() {
    printf '\n── %s\n' "$1"
    "$1"
}

_summary() {
    printf '\n─────────────────────────────────────\n'
    printf 'Results: %d passed  %d failed  %d skipped\n' "${_PASS}" "${_FAIL}" "${_SKIP}"
    [ "${_FAIL}" -eq 0 ]
}

# ── helpers ─────────────────────────────────────────────────────────────────

_test_prefix() { _mp_prefix; }

_cleanup() {
    local p; p="$(_test_prefix)"
    rm -f "${p}.pid" "${p}.submit" "${p}.ch" "${p}.start"
}

# ── test_valid_pid ───────────────────────────────────────────────────────────

test_valid_pid() {
    _mp_valid_pid "1234"; _assert "accepts valid PID" $?  0
    _mp_valid_pid "2";    _assert "accepts PID 2"    $?  0

    _mp_valid_pid "1"   && _assert "rejects PID 1"    1  0 || _assert "rejects PID 1"    $? 1
    _mp_valid_pid "0"   && _assert "rejects PID 0"    1  0 || _assert "rejects PID 0"    $? 1
    _mp_valid_pid "abc" && _assert "rejects non-num"  1  0 || _assert "rejects non-num"  $? 1
    _mp_valid_pid ""    && _assert "rejects empty"    1  0 || _assert "rejects empty"    $? 1
    _mp_valid_pid "-5"  && _assert "rejects negative" 1  0 || _assert "rejects negative" $? 1
}

# ── test_kill_pid_sigterm ────────────────────────────────────────────────────

test_kill_pid_sigterm() {
    sleep 60 &
    local pid=$!
    sleep 0.1

    _mp_kill_pid "${pid}"
    _assert "_mp_kill_pid returns 0 on SIGTERM kill" $? 0

    sleep 0.3
    ! kill -0 "${pid}" 2>/dev/null
    _assert "process is dead after _mp_kill_pid" $? 0
}

# ── test_kill_pid_sigkill_escalation ────────────────────────────────────────

test_kill_pid_sigkill_escalation() {
    bash -c 'trap "" TERM; sleep 60' &
    local pid=$!
    sleep 0.1

    _mp_kill_pid "${pid}"
    _assert "_mp_kill_pid returns 0 after SIGKILL escalation" $? 0

    sleep 0.3
    ! kill -0 "${pid}" 2>/dev/null
    _assert "process dead after SIGKILL" $? 0
}

# ── test_kill_pid_already_dead ───────────────────────────────────────────────

test_kill_pid_already_dead() {
    local dead=99994
    while kill -0 "${dead}" 2>/dev/null; do dead=$((dead - 1)); done

    _mp_kill_pid "${dead}" 2>/dev/null
    _assert "_mp_kill_pid on dead PID returns 0" $? 0
}

# ── test_monitor_lifecycle ───────────────────────────────────────────────────

test_monitor_lifecycle() {
    _cleanup

    miraeping_monitor "echo tick" 60
    local pid_file; pid_file="$(_test_prefix).pid"

    [ -f "${pid_file}" ]
    _assert "PID file created after monitor start" $? 0

    local mon_pid
    mon_pid="$(cat "${pid_file}")"
    kill -0 "${mon_pid}" 2>/dev/null
    _assert "monitor process is alive" $? 0

    sleep 0.2
    MIRAEPING_LAST_RC=0 miraeping_stop --no-notify
    sleep 0.3

    ! kill -0 "${mon_pid}" 2>/dev/null
    _assert "monitor process dead after stop" $? 0

    ! [ -f "${pid_file}" ]
    _assert "PID file removed after stop" $? 0

    _cleanup
}

# ── test_monitor_sleep_child_killed ─────────────────────────────────────────

test_monitor_sleep_child_killed() {
    _cleanup

    miraeping_monitor "echo tick" 120   # long interval so sleep is running when we kill

    local mon_pid
    mon_pid="$(cat "$(_test_prefix).pid")"

    sleep 0.4   # give subshell time to start sleep

    # Find the sleep child of the monitor subshell
    local sleep_pid=""
    sleep_pid="$(ps -o pid= --ppid "${mon_pid}" 2>/dev/null | tr -d ' ' | grep -v '^$' | head -1 || true)"

    _mp_kill_pid "${mon_pid}" || true
    sleep 0.4

    if [ -n "${sleep_pid}" ]; then
        ! kill -0 "${sleep_pid}" 2>/dev/null
        _assert "sleep child killed when monitor stopped" $? 0
    else
        _skip "sleep child PID not found" "timing / ps unavailable"
    fi

    _cleanup
}

# ── test_monitor_replaces_old ────────────────────────────────────────────────

test_monitor_replaces_old() {
    _cleanup

    miraeping_monitor "echo first" 60
    local pid1; pid1="$(cat "$(_test_prefix).pid")"

    miraeping_monitor "echo second" 60
    local pid2; pid2="$(cat "$(_test_prefix).pid")"

    [ "${pid1}" != "${pid2}" ]
    _assert "second monitor gets new PID" $? 0

    sleep 0.3
    ! kill -0 "${pid1}" 2>/dev/null
    _assert "first monitor killed by second start" $? 0

    MIRAEPING_LAST_RC=0 miraeping_stop --no-notify
    _cleanup
}

# ── test_stop_idempotent ─────────────────────────────────────────────────────

test_stop_idempotent() {
    _cleanup

    MIRAEPING_LAST_RC=0 miraeping_stop --no-notify
    _assert "stop with no monitor is safe" $? 0

    MIRAEPING_LAST_RC=0 miraeping_stop --no-notify
    _assert "second stop is also safe" $? 0
}

# ── test_stop_preserves_exit_code ────────────────────────────────────────────

test_stop_preserves_exit_code() {
    _cleanup

    local rc
    MIRAEPING_LAST_RC=42 miraeping_stop --no-notify && rc=$? || rc=$?
    _assert "miraeping_stop returns previous exit code" "${rc}" 42
}

# ── test_send_no_token ───────────────────────────────────────────────────────

test_send_no_token() {
    local saved="${SLACK_BOT_TOKEN:-}"
    unset SLACK_BOT_TOKEN

    miraeping_send "test without token" >/dev/null 2>&1
    _assert "miraeping_send silently no-ops without token" $? 0

    [ -n "${saved}" ] && export SLACK_BOT_TOKEN="${saved}" || true
}

# ── test_send_metric_flags ───────────────────────────────────────────────────

test_send_metric_flags() {
    local saved="${SLACK_BOT_TOKEN:-}"
    unset SLACK_BOT_TOKEN

    miraeping_send --metric runtime  "msg" >/dev/null 2>&1
    _assert "--metric runtime accepted" $? 0

    miraeping_send --metric elapsed  "msg" >/dev/null 2>&1
    _assert "--metric elapsed accepted" $? 0

    miraeping_send --metric invalid  "msg" >/dev/null 2>&1
    _assert "--metric invalid falls back silently" $? 0

    [ -n "${saved}" ] && export SLACK_BOT_TOKEN="${saved}" || true
}

# ── test_send_with_slack (Slack required) ────────────────────────────────────

test_send_with_slack() {
    if [ -z "${SLACK_BOT_TOKEN:-}" ] || [ -z "${SLACK_USER_ID:-}" ]; then
        _skip "test_send_with_slack" "SLACK_BOT_TOKEN / SLACK_USER_ID not set"
        return
    fi

    miraeping_send "bash integration test: miraeping_send"
    _assert "miraeping_send sends DM" $? 0

    miraeping_send --metric elapsed "bash integration test: elapsed label"
    _assert "miraeping_send --metric elapsed sends DM" $? 0
}

# ── test_monitor_lifecycle_with_slack (Slack required) ───────────────────────

test_monitor_lifecycle_with_slack() {
    if [ -z "${SLACK_BOT_TOKEN:-}" ] || [ -z "${SLACK_USER_ID:-}" ]; then
        _skip "test_monitor_lifecycle_with_slack" "SLACK_BOT_TOKEN / SLACK_USER_ID not set"
        return
    fi

    _cleanup

    # Create submit file so stop sends final message
    _mp_write_private "$(_test_prefix).submit" "$(date +%s)"

    miraeping_monitor "echo 'status tick'" 3
    sleep 4   # wait for one periodic send

    miraeping_stop "bash integration test done"
    _assert "miraeping_stop with final send succeeds" $? 0

    _cleanup
}

# ── run ──────────────────────────────────────────────────────────────────────

_run test_valid_pid
_run test_kill_pid_sigterm
_run test_kill_pid_sigkill_escalation
_run test_kill_pid_already_dead
_run test_monitor_lifecycle
_run test_monitor_sleep_child_killed
_run test_monitor_replaces_old
_run test_stop_idempotent
_run test_stop_preserves_exit_code
_run test_send_no_token
_run test_send_metric_flags
_run test_send_with_slack
_run test_monitor_lifecycle_with_slack

_summary
