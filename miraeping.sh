#!/usr/bin/env bash
# miraeping.sh - SGE/bash Slack notification helper
#
# INSTALL:
#   mkdir -p ~/.miraeping && chmod 700 ~/.miraeping
#   cp miraeping.sh ~/.miraeping/miraeping && chmod 700 ~/.miraeping/miraeping
#   printf 'SLACK_USER_ID=...\nSLACK_BOT_TOKEN=xoxb-...\n' > ~/.miraeping/credentials
#   chmod 600 ~/.miraeping/credentials
#   source ~/.miraeping/miraeping
#
# CREDENTIALS:
#   1) ~/.miraeping/credentials (preferred)
#   2) Environment variables (fallback): SLACK_BOT_TOKEN / SLACK_USER_ID
#
# USAGE (SGE script):
#   source ~/.miraeping/miraeping
#
#   miraeping_monitor "tail -n 20 output.log" 300
#   python run.py
#   miraeping_send "Done"
#   miraeping_stop

# -- internal helpers ----------------------------------------------------------

_mp_rundir() {
    local d="${HOME}/.miraeping/run"
    [ -d "${d}" ] || { mkdir -p "${d}"; chmod 700 "${d}"; }
    printf '%s' "${d}"
}

_mp_prefix() { printf '%s/miraeping_%s' "$(_mp_rundir)" "${JOB_ID:-$$}"; }
_mp_load_credentials() {
    local file="${HOME}/.miraeping/credentials"
    [ -f "${file}" ] || return 0

    local key value
    while IFS='=' read -r key value || [[ -n "${key}" ]]; do
        key="${key%$'\r'}"
        value="${value%$'\r'}"
        case "${key}" in
            ""|\#*) continue ;;
            SLACK_BOT_TOKEN|SLACK_USER_ID)
                [ -n "${value}" ] || continue
                printf -v "${key}" '%s' "${value}"
                export "${key}"
                ;;
        esac
    done < "${file}"
}

_mp_valid_pid() {
    [[ "${1:-}" =~ ^[0-9]+$ ]] && [ "${1}" -gt 1 ]
}

_mp_pid_state() {
    local pid="${1:-}"
    local status_file="/proc/${pid}/status"
    if [ -f "${status_file}" ]; then
        awk '/^State:/ {print $2; exit}' "${status_file}" 2>/dev/null
        return
    fi
    ps -o stat= -p "${pid}" 2>/dev/null | awk '{print $1; exit}'
}

_mp_pid_ppid() {
    local pid="${1:-}"
    local status_file="/proc/${pid}/status"
    if [ -f "${status_file}" ]; then
        awk '/^PPid:/ {print $2; exit}' "${status_file}" 2>/dev/null
        return
    fi
    ps -o ppid= -p "${pid}" 2>/dev/null | awk '{print $1; exit}'
}

_mp_pid_is_zombie() {
    local state
    state="$(_mp_pid_state "${1:-}")"
    [[ "${state}" == Z* || "${state}" == *Z* ]]
}

_mp_reap_pid() {
    local pid="${1:-}"
    wait "${pid}" 2>/dev/null || true
}

# Returns 0 only if <pid> is alive, non-zombie, and a direct child of this shell.
# Prevents acting on a reused PID that belongs to an unrelated process.
_mp_pid_is_ours() {
    local pid="${1:-}"
    _mp_valid_pid "${pid}" || return 1
    kill -0 "${pid}" 2>/dev/null || return 1
    _mp_pid_is_zombie "${pid}" && return 1
    local ppid
    ppid="$(_mp_pid_ppid "${pid}")"
    [[ "${ppid}" =~ ^[0-9]+$ ]] && [ "${ppid}" = "$$" ]
}

_mp_csv_has() {
    local csv="${1:-}"
    local needle="${2:-}"
    [ -n "${needle}" ] || return 1
    case ",${csv}," in
        *,"${needle}",*) return 0 ;;
        *) return 1 ;;
    esac
}

_mp_kill_pid() {
    local pid="${1:-}"
    _mp_valid_pid "${pid}" || return 1

    if ! _mp_pid_is_ours "${pid}"; then
        return 0
    fi

    kill "${pid}" 2>/dev/null || true
    local _i
    for _i in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "${pid}" 2>/dev/null || return 0
        if _mp_pid_is_zombie "${pid}"; then
            _mp_reap_pid "${pid}"
            return 0
        fi
        sleep 0.05
    done

    kill -9 "${pid}" 2>/dev/null || true
    for _i in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "${pid}" 2>/dev/null || return 0
        if _mp_pid_is_zombie "${pid}"; then
            _mp_reap_pid "${pid}"
            return 0
        fi
        sleep 0.05
    done

    return 1
}

_mp_write_private() {
    local file="$1"
    local value="$2"
    ( umask 077; printf '%s' "${value}" > "${file}" )
}

_mp_ensure_submit_file() {
    local submit_file; submit_file="$(_mp_prefix).submit"
    if [ -s "${submit_file}" ]; then
        return 0
    fi
    local t0
    t0="$(_mp_sge_submitted_epoch 2>/dev/null || true)"
    if [[ "${t0}" =~ ^[0-9]+$ ]] && [ "${t0}" -gt 0 ]; then
        _mp_write_private "${submit_file}" "${t0}"
    fi
}

_mp_parse_datetime_epoch() {
    local dt="${1:-}"
    [ -n "${dt}" ] || return 1
    local ts
    ts="$(
        date -d "${dt}" +%s 2>/dev/null \
            || date -j -f "%a %b %e %H:%M:%S %Y" "${dt}" +%s 2>/dev/null \
            || date -j -f "%a %b %d %H:%M:%S %Y" "${dt}" +%s 2>/dev/null \
            || date -j -f "%m/%d/%Y %H:%M:%S" "${dt}" +%s 2>/dev/null \
            || true
    )"
    [[ "${ts}" =~ ^[0-9]+$ ]] || return 1
    printf '%s' "${ts}"
}

_mp_sge_submitted_epoch() {
    [ -n "${JOB_ID:-}" ] || return 1
    command -v qstat >/dev/null 2>&1 || return 1
    local dt t0
    dt="$(
        qstat -j "${JOB_ID}" 2>/dev/null | awk '
            /^[[:space:]]*submission_time[[:space:]]*:/ {
                line=$0;
                sub(/^[[:space:]]*submission_time[[:space:]]*:[[:space:]]*/, "", line);
                print line;
                exit;
            }
        '
    )"
    [ -n "${dt}" ] || return 1
    t0="$(_mp_parse_datetime_epoch "${dt}" 2>/dev/null || true)"
    [[ "${t0}" =~ ^[0-9]+$ ]] || return 1
    printf '%s' "${t0}"
}

_mp_resolve_submitted_epoch() {
    local submit_file; submit_file="$(_mp_prefix).submit"
    local t0=""
    if [ -f "${submit_file}" ]; then
        t0="$(cat "${submit_file}" 2>/dev/null || true)"
        if [[ "${t0}" =~ ^[0-9]+$ ]] && [ "${t0}" -gt 0 ]; then
            printf '%s' "${t0}"
            return 0
        fi
    fi

    t0="$(_mp_sge_submitted_epoch 2>/dev/null || true)"
    if [[ "${t0}" =~ ^[0-9]+$ ]] && [ "${t0}" -gt 0 ]; then
        _mp_write_private "${submit_file}" "${t0}"
        printf '%s' "${t0}"
        return 0
    fi
    return 1
}

_mp_sanitize_code() {
    local text="${1:-}"
    local repl="'''"
    text="${text//$'\r'/}"
    text="${text//\`\`\`/${repl}}"
    printf '%s' "${text}"
}

_mp_job_label() {
    printf '%s (%s)' "${JOB_NAME:-unknown}" "${JOB_ID:-unknown}"
}

_mp_code_block() {
    local body
    body="$(_mp_sanitize_code "${1:-}")"
    printf '```\n%s\n```' "${body}"
}

_mp_resp_ok() {
    printf '%s' "$1" | grep -Eq '"ok"[[:space:]]*:[[:space:]]*true'
}

_mp_resp_channel_id() {
    printf '%s' "$1" | sed -n 's/.*"channel"[[:space:]]*:[[:space:]]*{[^}]*"id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1
}

_mp_api_call() {
    local endpoint="$1"
    shift
    curl -sS \
        --connect-timeout 5 \
        --max-time 10 \
        -X POST \
        -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
        "$@" \
        "https://slack.com/api/${endpoint}"
}

# Opens DM channel (cached to file). Prints channel ID.
_mp_channel() {
    local cache; cache="$(_mp_prefix).ch"
    if [ -s "$cache" ]; then cat "$cache"; return; fi
    [ -f "$cache" ] && rm -f "$cache"

    [ -z "${SLACK_BOT_TOKEN:-}" ] && return 1
    [ -z "${SLACK_USER_ID:-}" ] && return 1
    command -v curl >/dev/null 2>&1 || return 1

    local resp
    resp="$(_mp_api_call conversations.open --data-urlencode "users=${SLACK_USER_ID}" 2>/dev/null)" || return 1
    _mp_resp_ok "${resp}" || return 1

    local ch
    ch="$(_mp_resp_channel_id "${resp}")"

    if [ -n "$ch" ]; then
        _mp_write_private "$cache" "$ch"
        printf '%s' "$ch"
    fi
}

# Sends a message to the cached DM channel.
_mp_post() {
    local text="$1"
    [ -z "${SLACK_BOT_TOKEN:-}" ] && return 0
    [ -z "${SLACK_USER_ID:-}" ]   && return 0
    command -v curl >/dev/null 2>&1 || return 1

    local ch; ch=$(_mp_channel)
    [ -z "$ch" ] && return 1

    local resp
    resp="$(_mp_api_call chat.postMessage \
        --data-urlencode "channel=${ch}" \
        --data-urlencode "text=${text}" \
        2>/dev/null)" || return 1
    _mp_resp_ok "${resp}"
}

_mp_interrupt_trap() {
    miraeping_send --metric elapsed "Interrupted" >/dev/null 2>&1 || true
    miraeping_stop >/dev/null 2>&1 || true
    exit 143
}

_mp_exit_trap() {
    local rc=$?
    [ "${MIRAEPING_SUPPRESS_EXIT_TRAP:-0}" = "1" ] && return "${rc}"
    MIRAEPING_SUPPRESS_EXIT_TRAP=1 MIRAEPING_LAST_RC="${rc}" miraeping_stop >/dev/null 2>&1 || true
    return "${rc}"
}

# -- public functions ----------------------------------------------------------

# miraeping_send [--metric runtime|elapsed] [comment]
#
# Default format:
#   > job_name (job_id)  |  submitted: MM:DD:HH:MM  |  runtime: HH:MM:SS
#   `comment` (optional)
miraeping_send() {
    local metric="runtime"
    if [ "${1:-}" = "--metric" ]; then
        metric="${2:-runtime}"
        shift 2
    fi
    case "${metric}" in
        runtime|elapsed) ;;
        *) metric="runtime" ;;
    esac

    local comment="${1:-}"
    local name="${JOB_NAME:-unknown}"
    local jid="${JOB_ID:-unknown}"
    local submitted="N/A" elapsed="N/A"

    local t0 t1 d
    t0="$(_mp_resolve_submitted_epoch 2>/dev/null || true)"
    if [[ "${t0}" =~ ^[0-9]+$ ]] && [ "${t0}" -gt 0 ]; then
        t1=$(date +%s)
        submitted=$(date -d "@${t0}" '+%m:%d:%H:%M' 2>/dev/null \
               || date -r "${t0}"  '+%m:%d:%H:%M' 2>/dev/null \
               || printf 'N/A')
        d=$((t1 - t0))
        if [ "${d}" -lt 0 ]; then
            d=0
        fi
        elapsed=$(printf "%02d:%02d:%02d" $((d/3600)) $(((d%3600)/60)) $((d%60)))
    fi

    local msg="> ${name} (${jid})  |  submitted: ${submitted}  |  ${metric}: ${elapsed}"
    if [ -n "$comment" ]; then
        msg="${msg}
$(_mp_code_block "${comment}")"
    fi

    _mp_post "$msg"
}

# miraeping_monitor [command] [interval_seconds]
#
# Runs <command> every <interval> seconds in background and sends output to DM.
# Default command: qstat -j $JOB_ID  (falls back to qstat if JOB_ID unset)
# Default interval: 300 (5 min)
miraeping_monitor() {
    local cmd="${1:-}"
    if [ -z "${cmd}" ]; then
        if [ -n "${JOB_ID:-}" ]; then
            cmd="qstat -j ${JOB_ID} 2>/dev/null || qstat"
        else
            cmd="qstat"
        fi
    fi
    local interval="${2:-300}"
    local prefix; prefix=$(_mp_prefix)

    if [ -f "${prefix}.pid" ]; then
        local old_pid
        old_pid="$(cat "${prefix}.pid" 2>/dev/null || true)"
        _mp_kill_pid "${old_pid}" || true
        rm -f "${prefix}.pid"
    fi

    _mp_ensure_submit_file
    _mp_channel > /dev/null || true  # cache early, before fork

    (
        _mp_mon_child=""
        _mp_mon_cleanup() {
            [ -n "${_mp_mon_child}" ] && kill "${_mp_mon_child}" 2>/dev/null || true
            [ -n "${_mp_mon_child}" ] && wait "${_mp_mon_child}" 2>/dev/null || true
            exit 0
        }
        trap '_mp_mon_cleanup' TERM INT
        while true; do
            sleep "${interval}" &
            _mp_mon_child=$!
            wait "${_mp_mon_child}" 2>/dev/null || break
            _mp_mon_child=""
            local out
            # eval is intentional: miraeping_monitor accepts an arbitrary
            # shell command written by the job-script author (already trusted).
            out=$(eval "${cmd}" 2>&1 | head -30)
            if [ -n "$out" ]; then
                _mp_post "$(_mp_code_block "[$(_mp_job_label)] ${out}")"
            fi
        done
    ) &

    _mp_write_private "${prefix}.pid" "$!"

    # If TERM/INT traps are not configured, install a safe default so qdel
    # stops the monitor and sends an "Interrupted" message.
    if [[ $- != *i* ]] && [ "${MIRAEPING_AUTO_TRAP:-1}" != "0" ]; then
        local term_trap int_trap exit_trap
        term_trap="$(trap -p TERM || true)"
        int_trap="$(trap -p INT || true)"
        exit_trap="$(trap -p EXIT || true)"
        [ -z "$term_trap" ] && trap '_mp_interrupt_trap' TERM
        [ -z "$int_trap" ] && trap '_mp_interrupt_trap' INT
        [ -z "$exit_trap" ] && trap '_mp_exit_trap' EXIT
    fi
}

# miraeping_stop
#
# Kills the background monitor and performs cleanup only.
# Safe to call even if monitor was never started.
# Returns the status code of the previous command.
miraeping_stop() {
    local prev_rc="${MIRAEPING_LAST_RC:-$?}"
    [[ "${prev_rc}" =~ ^[0-9]+$ ]] || prev_rc=1

    local prefix; prefix=$(_mp_prefix)

    if [ -f "${prefix}.pid" ]; then
        local pid
        pid="$(cat "${prefix}.pid" 2>/dev/null || true)"
        _mp_kill_pid "${pid}" || true
        rm -f "${prefix}.pid"
    fi

    rm -f "${prefix}.submit" "${prefix}.start" "${prefix}.ch"
    return "${prev_rc}"
}

# Load user credentials from ~/.miraeping/credentials first.
# If the file is missing or a key is absent, existing environment variables are used.
_mp_load_credentials

# Auto-init submit timestamp when sourced in SGE job context.
if [ -n "${JOB_ID:-}" ] && [ "${MIRAEPING_AUTO_INIT_SUBMIT:-${MIRAEPING_AUTO_INIT_START:-1}}" != "0" ]; then
    _mp_ensure_submit_file
fi
