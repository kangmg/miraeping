---
name: slack-notify
description: Add user-side Slack notifications and local logging to SGE submission scripts, Bash jobs, and Python computations with miraeping, or watch GPU availability with gpu-watch. Check credentials and dependencies first using the bundled doctor. Not for Slack slash commands or notification server administration.
---

# Slack Notify

Use `miraeping` for user notifications and `gpu-watch` for one-shot GPU availability alerts. Repository: https://github.com/kangmg/miraeping. Keep generated notification text in English unless the user requests otherwise.

## Start with doctor

Identify the **execution host and job environment**, then run the bundled diagnostic there before adding or starting notifications:

```bash
bash "<this-skill-directory>/scripts/miraeping-doctor" --mode bash
bash "<this-skill-directory>/scripts/miraeping-doctor" --mode python --python /path/to/job/env/bin/python
bash "<this-skill-directory>/scripts/miraeping-doctor" --mode gpu
```

Choose the relevant mode, not `all` by default. A CPU SGE job does not need a GPU driver; a Bash job does not need the Python package. The script can run before miraeping is installed. If the target cannot be reached, continue preparing the code and provide the command to run there; do not report a local workstation check as cluster readiness.

Doctor prints presence, source, and format results without exposing values. Default checks are offline. For online setup verification, add `--online`: it only calls Slack `auth.test` and checks reported DM scopes, never opens a DM or sends a test message. Distinguish local readiness, accepted credentials, and actual delivery. Missing credentials must be configured by the user on the target, not pasted into chat or committed to scripts. Installation does not itself authorize sending a test message or submitting a job.

On failure, fix only prerequisites relevant to the requested path, then rerun that mode in the same environment. If credentials are missing, continue independent script work but do not launch the notifier. Read [setup and diagnostics](references/setup.md) for dependency names, installation, and credential precedence.

## Choose the integration

- **SGE or Bash submission scripts:** Read [Bash and SGE](references/bash-sge.md). Preserve scheduler directives, resources, working directory, existing traps, and exit status. Source the helper explicitly in the job; interactive shell functions do not automatically exist there.
- **Python computations and application logs:** Read [Python notifications](references/python.md). Install distribution `miraeping` into the interpreter that actually runs the job. Use the public `send`, `Job`, and `Monitor` APIs; add explicit completion/failure messages.
- **Waiting for an available GPU:** Read [GPU watcher](references/gpu-watch.md). Use the standalone executable on the GPU node. It detaches itself and is separate from job-lifetime monitors.

## Integration rules

Keep local logs authoritative; Slack should contain concise status or selected log tails, not complete logs. Preserve the computation's original success/failure status when notification delivery fails. Do not add token values to logs, source files, command-line arguments, or reports.

Inspect the installed version/source before relying on unfamiliar behavior. In the maintained code, Bash `miraeping_stop` only cleans up; it does not send a final message. Python `Job`/`Monitor` contexts do not automatically notify success or failure, and Python notification errors can be swallowed. A successful computation or function return is not evidence of Slack delivery.

When the user asks to edit a submission script, edit it and perform a syntax/logic check; do not infer permission to submit it. Preserve any existing authorization to run jobs or send notifications. Test edits with fake transport or mocked callbacks unless a real send was requested. Report the selected runtime, doctor result, changed files, validation, and any remaining target-side setup.
