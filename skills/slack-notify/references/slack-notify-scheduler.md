# slack-notify-scheduler

Same notification pattern for Slurm, SGE, or local Bash. Keep the existing scheduler headers, launcher, environment activation, and paths. Run doctor first; source the installed helper inside the job.

```bash
source "$HOME/.miraeping/miraeping"

if ./run_calculation > run.log 2>&1; then
    rc=0
    message="Completed"
else
    rc=$?
    message="Failed (exit $rc)"
fi
miraeping_send "$message | $PWD/run.log" || true
exit "$rc"
```

Replace the calculation command/log path with the existing ones. If the program returns 0 without converging, use its documented convergence check before reporting completion; send `Convergence failed | /path` and retain a nonzero failure status. Do not invent generic log-matching rules.

For an existing exit handler, add just `miraeping_send "Terminated | $PWD" || true` there; keep its original status and cleanup. Do not add a new trap framework or monitor for this simple use. Forced kills/node loss cannot guarantee a final message. `miraeping_stop` only cleans up; it does not notify completion.
