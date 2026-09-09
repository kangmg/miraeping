# Setup and diagnostics

Use the execution host's shell, modules, and selected Python environment. Do not install an unrelated global Python environment just for a notification helper.

| Path | What to install | Required runtime |
| --- | --- | --- |
| Bash / SGE | Repository `miraeping.sh`, normally at `~/.miraeping/miraeping` | Bash, curl, standard Unix tools; SGE commands for job submission and timestamps |
| Python | PyPI distribution and import name `miraeping` | Python >= 3.7; user notification code uses the standard library, no third-party runtime package dependencies |
| GPU watcher | Repository `bin/gpu-watch`, normally in `~/.local/bin` | Linux, Bash >= 4, nvidia-smi, curl, GNU coreutils (timeout, nohup), util-linux (flock) |
| Doctor | Bundled `scripts/miraeping-doctor` | Bash >= 4, standard Unix tools (grep, mktemp, rm, stat); curl for automatic Slack authentication. No Python or jq dependency; GNU timeout is used only for optional Python/GPU probes |

`pytest` is a development dependency, not a notification runtime dependency. Do not install the server extra or ask for an app-level token for user notifications. Confirm dependency names in the target project's `pyproject.toml`/requirements and the selected interpreter if the package differs from this repository.

## Credentials: three different precedence rules

| Path | Effective credentials |
| --- | --- |
| Bash helper | Nonempty keys in `~/.miraeping/credentials` override the environment. File lines use exact `KEY=value` syntax, without shell quotes. |
| Python | Environment keys take precedence; the file fills absent keys. An exported empty variable prevents the file fallback. |
| gpu-watch | Exported `SLACK_BOT_TOKEN` and `SLACK_USER_ID` only; no credential file or shell startup file is sourced. |

Required values are the existing bot token (`xoxb-...`) and the user's Slack member ID (`U...` or `W...`). Ask the user to configure these on the host if absent. Never print the token or dump the environment/credential file. Keep the credential file private (mode 600). If workflows disagree, check precedence before replacing a valid token.

## Install the agent skill

From the repository, run `bash setup_skill.sh`. It copies the entire skill with `cp -rL` into both `~/.claude/skills/slack-notify` and `${CODEX_HOME:-$HOME/.codex}/skills/slack-notify`. These are independent copies, not symlinks. Existing copies or links are moved to a timestamped `skill-backups` directory beside each agent's `skills` directory before replacement. Rerun after repository updates; credentials and shell startup files are not changed.

## Install only the selected path

From a checked-out miraeping repository:

```bash
# Standalone commands; ~/.local/bin must be on PATH, or use full paths.
install -Dm755 bin/gpu-watch ~/.local/bin/gpu-watch
install -Dm755 skills/slack-notify/scripts/miraeping-doctor ~/.local/bin/miraeping-doctor

# Bash helper when credentials are already configured:
install -Dm700 miraeping.sh ~/.miraeping/miraeping
```

For the guided Bash setup, `bash setup.sh` prompts for credentials, writes `~/.miraeping/credentials`, and adds a source line to `.bashrc`. Use it when that configuration is intended; it can replace existing stored credentials. The minimal install above does not configure credentials or `.bashrc`.

For Python, use the job interpreter explicitly:

```bash
/path/to/env/bin/python -m pip install miraeping
# Or for uv-managed environments (pip need not be installed inside them):
uv pip install --python /path/to/env/bin/python miraeping
```

Run doctor afterward. It reports the selected Python executable and whether the notification API can be imported. A checkout can shadow an installed distribution; when investigating versions, inspect `miraeping.__version__` and `miraeping.__file__` with that interpreter.

## Doctor interpretation

```bash
# After activating the job environment, run either:
miraeping-doctor
bash "<this-skill-directory>/scripts/miraeping-doctor"
```

- `--help` / `-h` explain usage. No `--mode`, `--python`, or `--online` flags are needed or accepted.
- Doctor itself always runs in Bash. Optional Python priority: `VIRTUAL_ENV`, `CONDA_PREFIX`, nearest existing project `.venv`, then `python3`/`python` on PATH. Project search stops at a `pyproject.toml` or `.git` boundary. No Python means the Python check is skipped. Broken detected environments, Python older than 3.7, missing packages, or missing timeout warn/skip that optional check without failing Bash readiness. Do not install Python unless the requested integration needs it.
- For uv, activate its environment, use `uv run --no-sync bash <doctor-path>` with an already-prepared project, or run from the project containing `.venv`. Doctor does not create environments, install packages, or run uv itself.
- Optional Python package import, Bash runtime, `~/.miraeping/miraeping` syntax/API definitions, curl, and SGE command availability are checked automatically. Bash credentials are always checked; Python credentials are checked only after the optional package probe succeeds. Each checked workflow uses its own credential precedence; identical tokens share one authentication result.
- A plausible bot token automatically triggers [auth.test](https://docs.slack.dev/reference/methods/auth.test) with a 10-second timeout and checks the returned `x-oauth-scopes` header for `im:write` and `chat:write`. Missing tokens skip the network call. Missing scopes fail; an absent scope header warns. It does not verify recipient membership or actual message delivery. Report missing permissions to the existing bot administrator; this skill does not configure the app.
- Exit 0 means no failures were found and at least one notification path is ready; warnings can remain. Exit 1 indicates failure; exit 2 indicates invalid arguments. Read the individual readiness lines: an unused path's failure does not imply another path is broken.
- Missing optional integrations warn. Missing `qsub`/`qstat` is informational: verify on SGE before submission. With no `nvidia-smi`, GPU checks are skipped; run on the GPU node when needed. If both GPU tools are present, doctor checks dependencies, Linux `/proc`, exported credentials, and readable VRAM data.
- Doctor does not source the helper, change configuration, install software, start a monitor, or send messages. It imports the chosen miraeping module in a bounded subprocess but does not invoke its notification APIs.
