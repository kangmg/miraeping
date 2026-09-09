# miraeping

<img src="docs/assets/miraeping.png" alt="miraeping" width="420" />

Slack DM notifications for SGE jobs and Python computations on SGE-based clusters, plus Slack slash commands for server and queue status checks (`/qq`, `/qstat`, `/gpu`, `/nvidia-smi`).

## What this project provides

`miraeping` contains three separate workflows:

| Workflow | What it is | Where to start |
|----------|------------|----------------|
| **Job notifications** | User-side Slack DM alerts from SGE job scripts or Python code | [User Guide](docs/usage.md) |
| **GPU availability watcher** | Standalone `gpu-watch` command: wait for a free GPU on the current node and send a Slack DM | [GPU watcher guide](docs/usage.md#feature-3---gpu-availability-watcher) |
| **Slack cluster commands** | Optional slash commands such as `/qq`, `/qstat`, `/qwd`, `/gpu`, `/nvidia-smi`. A lab/admin server operator must run the command server first | [User Guide](docs/usage.md) for usage, [Developer Guide](docs/develop.md) for setup |

## Notify Installation

Choose one path depending on how you use `miraeping`:

1. **Bash helper for SGE job scripts** (`miraeping_send`, `miraeping_monitor`, `miraeping_stop`): use `git clone` + `setup.sh`
2. **Python package API** (`import miraeping`): install from PyPI inside your `conda` or `uv` environment

### A) Bash helper setup (git clone + setup.sh)

1. Find your Slack member ID: Slack → Profile → three-dot menu → **Copy member ID**
2. Send it to your lab admin to get registered, and receive `SLACK_BOT_TOKEN`

```bash
git clone https://github.com/kangmg/miraeping
cd miraeping
bash setup.sh
source ~/.bashrc
```

`setup.sh` prompts for `SLACK_BOT_TOKEN` and `SLACK_USER_ID` (masked input), installs the bash helper to `~/.miraeping/miraeping`, and writes credentials to `~/.miraeping/credentials` (chmod 600).

### B) Python package install from PyPI (conda or uv)

```bash
# conda example
conda create -n miraeping python=3.11 -y
conda activate miraeping
pip install miraeping

# uv example
uv venv -p 3.11 .venv
uv pip install miraeping
```

## GPU Availability Watcher

On a Linux GPU node with `SLACK_BOT_TOKEN` and `SLACK_USER_ID` already exported:

```bash
install -Dm755 bin/gpu-watch ~/.local/bin/gpu-watch
gpu-watch --help
gpu-watch
gpu-watch status
gpu-watch stop
```

Ensure `~/.local/bin` is on `PATH`, or run `~/.local/bin/gpu-watch` directly.
This standalone Bash executable does not require `setup.sh`, `source`, Python,
or the Slack command server. It requires Bash 4+, `nvidia-smi`, `curl`, GNU
coreutils (`timeout`, `nohup`), and `flock` on Linux.

`gpu-watch` starts a `nohup` background process and returns after startup checks.
It checks immediately, then every 10 minutes while busy. When any GPU uses at
most 100 MiB of VRAM, it checks that same GPU again after 1 minute, sends one
Slack DM, and exits. After 24 hours without a successful availability alert,
it attempts a timeout DM and exits. The final timeout DM has a separate
10-second network timeout (plus at most 1 second to force-stop a stuck call).
All messages and help are in English. See the [GPU watcher guide](docs/usage.md#feature-3---gpu-availability-watcher)
for options and operational details.

## User Notification Doctor and Agent Skill

The `slack-notify` skill covers user-side SGE/Bash notifications, the Python
package, local logging, and `gpu-watch`. It starts with an automatic doctor
check and excludes Slack command server administration.

```bash
bash setup_skill.sh
# Activate the job's conda/venv environment first, if applicable.
bash skills/slack-notify/scripts/miraeping-doctor

# Optional standalone command; ~/.local/bin must be on PATH.
install -Dm755 skills/slack-notify/scripts/miraeping-doctor ~/.local/bin/miraeping-doctor
miraeping-doctor
```

Doctor runs in Bash 4+ with standard Unix tools and curl; neither Python nor jq
is required. Bash/helper/curl and SGE checks run by default. Optional Python
checks use active venv/conda, an existing project `.venv` (including uv), or Python
on PATH; missing Python or miraeping does not block Bash checks. It also checks
GPU prerequisites when available, without printing secrets. A configured bot
token automatically triggers Slack authentication and reported DM-scope checks.
It does not install software, source the helper, start a watcher, or send a DM;
actual recipient/delivery checks remain separate. Use `miraeping-doctor --help`
for usage. There are no mode or online switches.

`setup_skill.sh` installs independent copies of the complete
[skill folder](skills/slack-notify/SKILL.md) into both
`~/.claude/skills/slack-notify` and `~/.codex/skills/slack-notify`
(or `$CODEX_HOME/skills/slack-notify`), using `cp -rL`, not symlinks.
Previous installations are preserved in `skill-backups` beside each agent's
`skills` directory. Rerun the installer after updating the repository.
Invoke it with `$slack-notify` when preparing a job or adding notifications.
The Python notification package is `miraeping`; no server extra is required.

## Slack Command Server (Admin)

Uses **Socket Mode** — outbound WebSocket to Slack, no public IP or port forwarding needed.

```bash
uv venv -p 3.11 .venv
uv pip install "miraeping[server]"

export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_APP_TOKEN="xapp-..."
miraeping-slack-serve
```

Background:

```bash
miraeping-slack-start
miraeping-slack-status
miraeping-slack-restart
miraeping-slack-stop
```

## Documentation

- [User Guide](docs/usage.md) — setup, bash helper, Python API, slash commands
- [Developer Guide](docs/develop.md) — create Slack app, run command server, register users
