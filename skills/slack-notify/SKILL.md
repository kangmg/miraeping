---
name: slack-notify
description: Add concise Slack completion, failure, and convergence alerts to scheduler jobs (Slurm/SGE), Bash scripts, or Python calculations using miraeping. Also covers gpu-watch. Run the Bash doctor first; not for Slack server administration.
---

# Slack Notify

## Doctor first

Run on the execution host, after activating the job environment if needed:

```bash
bash "<this-skill-directory>/scripts/miraeping-doctor"
```

Bash is the default; Python and jq are not required. Doctor checks credentials and authenticates without sending a message. Fix only prerequisites it reports for the requested integration. Never print or commit tokens.

## Minimal notifications

- [slack-notify-scheduler](references/slack-notify-scheduler.md): one Bash pattern for Slurm, SGE, or local jobs.
- [slack-notify-python](references/slack-notify-python.md): explicit completion/failure notifications, with sparse batch milestones only.

Default to **one final notification**: `Completed | /path`, `Failed | /path`, or `Convergence failed | /path`. Use the application's actual convergence result; exit code 0 alone does not prove convergence. Keep messages in English and include the result/log directory.

Do not add verbose logging, periodic monitors, full log tails, or per-epoch/step alerts. For many calculations, group progress: e.g. 20 MD runs → milestones after 4, 8, 12, 16, then one final message at 20. Keep existing scientific output unchanged. Choose one notifier (wrapper or Python), not both.

Preserve scheduler directives, environment, working directory, existing traps, and computation exit status. Do not submit jobs or send test messages unless requested. A successful notification function return does not prove delivery.

## GPU watch

On the GPU node, with exported `SLACK_BOT_TOKEN` and `SLACK_USER_ID`:

```bash
gpu-watch
gpu-watch status
gpu-watch stop
gpu-watch --help
```

It detaches automatically: do not source it or add another nohup. Defaults: check every 10 minutes, confirm VRAM ≤100 MiB on the same GPU after 1 minute, notify once; stop with a timeout notice after 24 hours. State/logs: `~/.miraeping/gpu-watch/<hostname>/`; status/stop run on that node. Availability is not a reservation.

Keep its compact node + boxed `GPU | Name | Avail.` format (`✓` / `✗`); no memory or extra metrics.
