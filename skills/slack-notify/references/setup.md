# Setup and diagnostics

Use the execution host's shell, modules, and selected Python environment. Do not install an unrelated global Python environment just for a notification helper.

| Path | What to install | Required runtime |
| --- | --- | --- |
| Bash / SGE | Repository `miraeping.sh`, normally at `~/.miraeping/miraeping` | Bash, curl, standard Unix tools; SGE commands for job submission and timestamps |
| Python | PyPI distribution and import name `miraeping` | Python >= 3.7; user notification code uses the standard library, no third-party runtime package dependencies |
| GPU watcher | Repository `bin/gpu-watch`, normally in `~/.local/bin` | Linux, Bash >= 4, nvidia-smi, curl, GNU coreutils (timeout, nohup), util-linux (flock) |
| Doctor | Bundled `scripts/miraeping-doctor` | Bash >= 4; Python mode also uses GNU timeout and the selected Python; online mode uses curl |

`pytest` is a development dependency, not a notification runtime dependency. Do not install the server extra or ask for an app-level token for user notifications. Confirm dependency names in the target project's `pyproject.toml`/requirements and the selected interpreter if the package differs from this repository.

## Credentials: three different precedence rules

| Path | Effective credentials |
| --- | --- |
| Bash helper | Nonempty keys in `~/.miraeping/credentials` override the environment. File lines use exact `KEY=value` syntax, without shell quotes. |
| Python | Environment keys take precedence; the file fills absent keys. An exported empty variable prevents the file fallback. |
| gpu-watch | Exported `SLACK_BOT_TOKEN` and `SLACK_USER_ID` only; no credential file or shell startup file is sourced. |

Required values are the existing bot token (`xoxb-...`) and the user's Slack member ID (`U...` or `W...`). Ask the user to configure these on the host if absent. Never print the token or dump the environment/credential file. Keep the credential file private (mode 600). If modes disagree, check precedence before replacing a valid token.

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

Run doctor afterward. Python mode reports the imported version and module path: a repository checkout can shadow an installed distribution, so verify the reported path is the intended one.

## Doctor interpretation

```bash
miraeping-doctor --mode bash --helper /path/to/miraeping
miraeping-doctor --mode python --python /path/to/env/bin/python
miraeping-doctor --mode gpu --online
```

- `--help` / `-h` explain usage; `--mode all` deliberately checks every workflow.
- Exit 0 means selected checks passed; warnings can remain. Exit 1 indicates failure; exit 2 indicates invalid arguments.
- Offline credential success only means presence and plausible format. It does not prove authentication.
- `--online` calls [auth.test](https://docs.slack.dev/reference/methods/auth.test), which requires no additional scope, and checks the returned `x-oauth-scopes` header for `im:write` and `chat:write`. It does not verify recipient membership or actual message delivery. Missing permissions should be reported to the existing bot administrator; this skill does not configure the app.
- Missing `qsub`/`qstat` on a workstation is a warning: prepare the script, then verify on the cluster before submitting. A GPU mode failure on a login node likewise needs a GPU-node check.
- Doctor does not source the helper, change configuration, install software, start a monitor, or send messages. Python mode imports the chosen miraeping module but does not invoke its notification APIs.
