# Bash, SGE, and logging

Run the bundled doctor with `bash` first; it automatically checks Bash, the installed helper, curl, credentials, and SGE tools; Python is checked only when available. Use the user's existing SGE script as the starting point: retain queue, resource requests, MPI launcher, module/conda activation, and working-directory setup. Notification changes must not quietly change the computation.

## Actual helper API

```bash
source "$HOME/.miraeping/miraeping"
miraeping_send "Finished"
miraeping_send --metric elapsed "Status update"
miraeping_monitor 'tail -n 20 output.log' 600
miraeping_stop
```

`miraeping_monitor` runs the supplied shell command periodically in a background child tied to the job. Its first report is after the interval, not immediate. The command is evaluated as shell code: use trusted commands written by the job author and quote filenames. Output is limited to 30 lines. It is not a detached GPU watcher.

`miraeping_stop` stops the monitor and cleans state; it does **not** send a completion message. Passing a message to it does not change that. Use `miraeping_send` explicitly. The helper can install TERM/INT/EXIT traps in noninteractive scripts when `MIRAEPING_AUTO_TRAP` is enabled. If the job already manages traps, integrate cleanup into those handlers and disable helper auto-traps before starting its monitor.

## Pattern for a new job with explicit cleanup

The following is a pattern to adapt, not a reason to replace an existing trap framework. Keep the user's scheduler directives above executable lines. Replace `python -u run.py` with the actual command.

```bash
#!/usr/bin/env bash
#$ -S /bin/bash
#$ -cwd
#$ -j y

set -uo pipefail
export MIRAEPING_AUTO_TRAP=0
notify_ready=0
if [[ -r "$HOME/.miraeping/miraeping" ]]; then
    source "$HOME/.miraeping/miraeping" && notify_ready=1
fi
log_file="run.${JOB_ID:-local}.log"

finish() {
    rc=$?
    trap - EXIT
    if (( notify_ready )); then
        if (( rc == 0 )); then result=Completed; else result=Failed; fi
        miraeping_send "$result (exit $rc). Log: $PWD/$log_file" || true
        MIRAEPING_LAST_RC="$rc" miraeping_stop || true
    fi
    exit "$rc"
}
trap finish EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

if (( notify_ready )); then
    printf -v status_cmd 'tail -n 10 -- %q' "$log_file"
    miraeping_monitor "$status_cmd" 600 || true
fi
if python -u run.py > "$log_file" 2>&1; then
    rc=0
else
    rc=$?
fi
exit "$rc"
```

This explicitly captures the computation's status before notification commands. For scripts already using `set -e`, put the computation in an `if` or use a suitable existing EXIT trap so failure still triggers notification. Do not put `|| true` around the computation itself. In pipelines with `tee`, enable `pipefail` and capture `PIPESTATUS[0]` immediately if the application status is what must be preserved.

## Logging decisions

- Prefer SGE stdout/stderr logs plus an application log when useful. SGE opens its output path before the script runs, so create directories before `qsub` if using `#$ -o logs/...`.
- `python -u` or `PYTHONUNBUFFERED=1` makes redirected Python progress visible promptly. Do not add `stdbuf` or flush settings to unrelated programs without need.
- Send a concise status or log tail every 5–10 minutes, not each line. Include the local log path in the final message. Omit secrets and noisy full tracebacks from Slack; retain them locally.
- Preserve existing scheduler environment forwarding. Environment-only credentials must reach the job, but do not add `#$ -V` merely to export every environment variable when the job already has a narrower mechanism. The Bash credential file can be read directly on nodes with the shared home mounted.
- For MPI jobs, send notifications from the submission wrapper or a single designated rank, not from every worker.
- TERM/INT handling is best effort. SIGKILL, node failure, and some scheduler cleanup paths cannot run final notification code.

Before handoff, run `bash -n` on edited scripts, review their traps and exit-code handling, and check log paths. A request to edit a script does not itself request `qsub`.
