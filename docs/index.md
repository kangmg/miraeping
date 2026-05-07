# miraeping

Slack DM notifications for SGE jobs and Python computations, plus Slack-based cluster status checks.

---

## What this project provides

`miraeping` contains two separate workflows:

| Workflow | What it is | Where to start |
|----------|------------|----------------|
| **Job notifications** | User-side Slack DM alerts from SGE job scripts or Python code | [User guide -> Notify](usage.md#feature-1-notify-miraeping) |
| **Slack cluster commands** | Optional Slack slash commands for queue, job, and GPU status. A lab/admin server operator must run the command server first | [User guide -> Slash commands](usage.md#feature-2-slack-slash-commands) |
| **Command server setup** | Admin-side Slack app, Socket Mode, slash command, token, mapping, and allowlist setup | [Developer guide ->](develop.md) |

Most users only need the User Guide. Server operators should use the Developer Guide.

---

Choose by role:

| Role | Description | Guide |
|------|-------------|-------|
| **User** | Send job notifications or use existing Slack commands | [User guide ->](usage.md) |
| **Admin** | Create the Slack app and run the command server | [Developer guide ->](develop.md) |
