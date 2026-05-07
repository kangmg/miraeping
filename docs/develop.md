# Developer Guide

This guide is for **Feature 2: Slack command server**.

The command server answers Slack slash commands such as `/qq`, `/qstat`, `/qwd`, `/gpu`, and `/nvidia-smi`. It is separate from **Feature 1: Notify (`miraeping`)**. Users can send job notifications without this server, and this server does not install the user-side bash helper automatically.

What the server operator needs:

| Requirement | Why |
|-------------|-----|
| Slack app with Socket Mode enabled | Allows the cluster server to receive slash commands over an outbound WebSocket |
| `SLACK_BOT_TOKEN` (`xoxb-...`) | Sends command responses and user DMs |
| `SLACK_APP_TOKEN` (`xapp-...`) | Opens the Socket Mode connection |
| Slash commands | Registers `/qq`, `/qstat`, `/qwd`, `/gpu`, `/nvidia-smi` in Slack |
| Optional user mapping and allowlists | Maps Slack users to cluster usernames and limits who can run commands |

---

## Step 1 — Create a Slack app

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) → click **"Create New App"** → **"From scratch"**
2. Enter a name (e.g. `miraeping`) and select your workspace
3. Click **Create App**

---

## Step 2 — Enable Socket Mode

App Settings → **Socket Mode** → toggle **Enable Socket Mode** to on.

---

## Step 3 — Generate App-Level Token

App Settings → **Basic Information** → scroll to **App-Level Tokens** → **Generate Token and Scopes**

- Token name: anything (e.g. `miraeping-socket`)
- Scope: `connections:write`
- Click **Generate** → copy the token (starts with `xapp-...`)

---

## Step 4 — Add OAuth scopes

App Settings → **OAuth & Permissions** → **Bot Token Scopes** → **Add an OAuth Scope**

Add all three:

- `chat:write`
- `im:write`
- `commands`

---

## Step 5 — Create slash commands

App Settings → **Slash Commands** → **Create New Command** — repeat for each command below:

| Command | Short Description |
|---------|-------------------|
| `/qq` | Current node usage status |
| `/qstat` | Your submitted job status |
| `/qwd` | Show working directories of your current jobs |
| `/gpu` | Show GPU memory and utilization on the GPU node |
| `/nvidia-smi` | Alias for /gpu |

For each command: leave the **Request URL field empty**. Socket Mode routes commands via WebSocket — no URL is needed.

---

## Step 6 — Install app to workspace

App Settings → **Install App** → **Install to Workspace** → click **Allow**.

Copy the **Bot User OAuth Token** (starts with `xoxb-...`).

---

## Step 7 — Collect credentials

You now have:

- `SLACK_BOT_TOKEN` = `xoxb-...` (Bot User OAuth Token)
- `SLACK_APP_TOKEN` = `xapp-...` (App-Level Token)

Share only `SLACK_BOT_TOKEN` with each user.  
Each user should copy their own `SLACK_USER_ID` in Slack and enter it during `setup.sh`.  
Keep `SLACK_APP_TOKEN` on the server only.

---

## Step 8 — Install miraeping on the server

Run these commands inside the conda or uv environment that will host the Slack command server.

```bash
# From PyPI into a uv environment:
uv venv -p 3.7 .venv
uv pip install "miraeping[server]"

# From a source checkout:
git clone https://github.com/kangmg/miraeping
cd miraeping
uv sync --extra server

# Or run directly with uv from the checkout:
uv run --extra server miraeping-slack-serve --help
```

---

## Step 9 — Set environment variables

Required:

```bash
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_APP_TOKEN="xapp-..."
```

Optional:

```bash
# Map Slack user IDs to Unix usernames (needed for /qstat and /qwd)
# Multi-line format is supported; trailing commas are allowed.
SLACK_QSTAT_USER_MAP="
UXXXXXXXXXX:alice,
UYYYYYYYYYY:bob
"
export SLACK_QSTAT_USER_MAP

# SSH host for /gpu and /nvidia-smi (default: g01)
# Must be a valid hostname: letters, digits, hyphens, dots (no leading hyphen).
export SLACK_GPU_SSH_HOST="g01"

# Comma-separated Slack user IDs allowed to use slash commands.
export SLACK_ALLOWED_USER_IDS="UXXXXXXXXXX,UYYYYYYYYYY"

# Comma-separated Slack channel IDs allowed to invoke slash commands.
export SLACK_ALLOWED_CHANNEL_IDS="C0XXXXXXXXX"

# Whether to enforce the allowlists. 1 = enforce, 0 = disabled.
# Default: automatically enabled when the corresponding ALLOWED_* list is set.
export SLACK_ENFORCE_USER_ALLOWLIST=1
export SLACK_ENFORCE_CHANNEL_ALLOWLIST=0
```

---

## Step 10 — Run the server

Foreground (for testing):

```bash
miraeping-slack-serve
```

Background (production):

```bash
miraeping-slack-start
miraeping-slack-status
miraeping-slack-restart
miraeping-slack-stop
```

Logs are written to `~/.miraeping_slack_server.log`.

---

## Step 11 — Register users and share credentials

Ask each user to:

1. Find their Slack user ID: Slack → Profile → three-dot menu → **"Copy member ID"**
2. Run `echo $USER` on the cluster and tell you both values

Add them to `SLACK_QSTAT_USER_MAP` (multi-line format supported):

```bash
SLACK_QSTAT_USER_MAP="
UXXXXXXXXXX:alice,
UYYYYYYYYYY:bob
"
export SLACK_QSTAT_USER_MAP
```

Share `SLACK_BOT_TOKEN` with each user so they can run `setup.sh` on their own account.
Keep `SLACK_APP_TOKEN` on the server only — users do not need it.

---

## Why Socket Mode? (Architecture note)

```
Lab server (172.20.x.x, private)
  └─ miraeping-slack-serve
       └─ outbound WebSocket ──────► Slack API (api.slack.com)
                                          ▲
                               User types /qq in Slack
```

No public URL, no port forwarding, no reverse proxy needed. The server initiates the connection outbound.

---

## Security notes

**Shared bot token**

All users share the same `SLACK_BOT_TOKEN`. This is a Slack bot architecture constraint — a single bot token cannot be scoped per user. To limit the blast radius:

- The token is granted only the minimum required scopes: `chat:write`, `im:write`, `commands`. A leaked token can send DMs but cannot read messages, access files, or manage the workspace.
- If a token is suspected compromised, revoke it immediately in **App Settings → OAuth & Permissions → Revoke Token**, then reinstall the app to generate a new one. Share the new token with all users.
- Encourage users to store credentials in `~/.miraeping/credentials` (chmod 600) rather than exporting tokens in `.bashrc`.
- Set `SLACK_ALLOWED_USER_IDS` on the server so the slash commands are only usable by registered lab members, regardless of who holds the token.

**Other notes**

- Never commit `SLACK_BOT_TOKEN` or `SLACK_APP_TOKEN` to version control — store in a `chmod 600` env file
- Keep `SLACK_APP_TOKEN` on the server only; share only `SLACK_BOT_TOKEN` with users
- Always set `SLACK_ALLOWED_USER_IDS` + `SLACK_ENFORCE_USER_ALLOWLIST=1`; the server will print a WARNING at startup if the allowlist is not configured
- SSL cert issue on servers using uv-managed Python: `export SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt`
- Credentials file (`~/.miraeping/credentials`) must use plain `KEY=VALUE` format — no quotes around values

---

## Release checklist

1. Update `miraeping/_version.py`
2. `uv run --extra dev pytest -q`
3. `uv build`
4. `uv run --with twine twine check --strict dist/*`
5. Upload with Twine + PyPI token
