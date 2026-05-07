# miraeping

<img src="docs/assets/miraeping.png" alt="miraeping" width="420" />

Slack DM notifications for SGE jobs and Python computations on SGE-based clusters, plus Slack slash commands for server and queue status checks (`/qq`, `/qstat`, `/gpu`, `/nvidia-smi`).

## What this project provides

`miraeping` contains two separate workflows:

| Workflow | What it is | Where to start |
|----------|------------|----------------|
| **Job notifications** | User-side Slack DM alerts from SGE job scripts or Python code | [User Guide](docs/usage.md) |
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
