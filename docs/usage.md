# User Guide

This guide covers the user-side setup for three independent features:

| Feature | What you use | User-side setup |
|---------|--------------|-----------------|
| **1. Notify (`miraeping`)** | Send Slack DM notifications from SGE job scripts or Python code | Add the Slack app, get `SLACK_BOT_TOKEN`, set your `SLACK_USER_ID`, then install the bash helper or Python package |
| **2. Slack slash commands** | Check cluster status from Slack with `/qq`, `/qstat`, `/qwd`, `/gpu`, `/nvidia-smi` | Add the Slack app, copy your Slack member ID, and ask the admin to register your Slack ID with your cluster username |
| **3. GPU availability watcher** | Run `gpu-watch` on a GPU node and receive a Slack DM when a GPU becomes available | Install the standalone executable and export `SLACK_BOT_TOKEN` and `SLACK_USER_ID` |

The features are separate. Notify messages and GPU availability alerts do **not** require the Slack command server to be running. Slack slash commands do **not** require you to install the bash helper or Python package locally.

---

## Common Slack steps

These steps are useful for both features.

**1) Find your Slack member ID**

Open Slack -> click your profile picture -> "Profile" -> three-dot menu -> **"Copy member ID"** (`UXXXXXXXXXX` format).
This is the value used as `SLACK_USER_ID` for notifications and for Slack command registration.
Use the screenshot below as a reference. The value you need is the Slack member ID, not your display name, email address, or cluster username.

<img src="../assets/member_id.png" alt="Copy member ID in Slack" width="720" />

**2) Add the miraebot app in Slack**

Open Slack -> Apps -> search for `miraebot` -> add it to your Slack workspace.
Use the screenshot below as a reference. If `miraebot` does not appear or Slack asks for approval, ask your workspace admin to approve or install the app.

<img src="../assets/add_bot.png" alt="Add miraebot app in Slack" width="720" />

---

## Feature 1 - Notify (`miraeping`)

Use this feature when you want your SGE job script or Python code to send Slack DM notifications.

The notification feature sends messages directly from your job script or Python process. It does **not** require the Slack command server.

### Notify setup

Choose one setup path based on your workflow:

| Workflow | Install | Credentials |
|----------|---------|-------------|
| Bash helper for SGE scripts | `git clone` + `bash setup.sh` | `SLACK_BOT_TOKEN` from the admin + your own Slack member ID (`SLACK_USER_ID`) |
| Python API | `pip install miraeping` in conda, or `uv venv -p 3.7` + `uv pip install miraeping` in uv | Same `SLACK_BOT_TOKEN` + `SLACK_USER_ID`, read from `~/.miraeping/credentials` or environment variables |

**1) Get `SLACK_BOT_TOKEN` from the admin**

The admin will share the bot token (`xoxb-...`) with you.

**2A) Bash helper path: run setup.sh**

```bash
git clone https://github.com/kangmg/miraeping
cd miraeping
bash setup.sh
source ~/.bashrc
```

`setup.sh` prompts for `SLACK_BOT_TOKEN` and `SLACK_USER_ID` (masked input), then installs the bash helper and writes credentials to `~/.miraeping/credentials` (chmod 600).

**2B) Python API path: install from PyPI**

```bash
# conda
conda create -n miraeping python=3.7 -y
conda activate miraeping
pip install miraeping

# uv
uv venv -p 3.7 .venv
uv pip install miraeping
```

**Verify (Bash helper path):**

```bash
miraeping_send "hello from setup test"
```

If a DM arrives in Slack — done.

**Verify (Python API path):**

```python
import miraeping

miraeping.send("hello from setup test")
```

---

### Bash helper

Three functions are available after `source ~/.miraeping/miraeping`:

> **Runtime files** — PID, channel cache, and submit-time stamp are stored in `~/.miraeping/run/` (created automatically, chmod 700). If a job terminates abnormally you can safely delete stale files there: `rm -f ~/.miraeping/run/miraeping_<JOB_ID>.*`

| Function | Description |
|----------|-------------|
| `miraeping_send [comment]` | Send a DM with job header + optional comment |
| `miraeping_monitor [cmd] [interval]` | Start background periodic status DM |
| `miraeping_stop` | Stop monitor and clean up background state |

Every message automatically includes a job header:
```
> JOB_NAME (JOB_ID)  |  submitted: MM:DD:HH:MM  |  runtime: HH:MM:SS
```

---

### SGE job scripts

The examples below keep the original SGE script context and mark only the lines you need to add with `+`.

#### Basic: finish notification

```diff
 #!/bin/bash
 #$ -V
 #$ -S /bin/bash
 #$ -N HER_VASP
 #$ -q all.q
 #$ -pe mpi_48 48
 #$ -j Y
 #$ -o $JOB_NAME.o$JOB_ID
 #$ -cwd

 echo "Got $NSLOTS slots."
 cat "$TMPDIR/machines"
 export OMP_NUM_THREADS=1

+ source ~/.miraeping/miraeping
 cd "$SGE_O_WORKDIR"

 module load vasp/6.3.2-vtst-vaspsol-beef-intel

 mpirun -machinefile "$TMPDIR/machines" -n "$NSLOTS" vasp_std
 rc=$?
+ miraeping_send "VASP finished (exit $rc): $PWD"
 exit "$rc"
```

#### VASP: check convergence from OUTCAR

```diff
 #!/bin/bash
 #$ -V
 #$ -S /bin/bash
 #$ -N HER_VASP
 #$ -q all.q
 #$ -pe mpi_48 48
 #$ -j Y
 #$ -o $JOB_NAME.o$JOB_ID
 #$ -cwd

 echo "Got $NSLOTS slots."
 cat "$TMPDIR/machines"
 export OMP_NUM_THREADS=1

+ source ~/.miraeping/miraeping
 cd "$SGE_O_WORKDIR"

 module load vasp/6.3.2-vtst-vaspsol-beef-intel
 mpirun -machinefile "$TMPDIR/machines" -n "$NSLOTS" vasp_std
 rc=$?
+ miraeping_send "VASP finished (exit $rc): $PWD"
+ grep -q "reached required accuracy" OUTCAR 2>/dev/null && miraeping_send "reached required accuracy"
 exit "$rc"
```

#### Periodic status with `miraeping_monitor`

Sends the last line of OSZICAR every 5 minutes. Use `miraeping_stop` at the end to stop the background monitor and send the final message.

```diff
 #!/bin/bash
 #$ -V
 #$ -S /bin/bash
 #$ -N HER_VASP
 #$ -q all.q
 #$ -pe mpi_48 48
 #$ -j Y
 #$ -o $JOB_NAME.o$JOB_ID
 #$ -cwd

 echo "Got $NSLOTS slots."
 cat "$TMPDIR/machines"
 export OMP_NUM_THREADS=1

+ source ~/.miraeping/miraeping
 cd "$SGE_O_WORKDIR"

 module load vasp/6.3.2-vtst-vaspsol-beef-intel
+ miraeping_monitor "tail -n 1 OSZICAR" 300
 mpirun -machinefile "$TMPDIR/machines" -n "$NSLOTS" vasp_std
 rc=$?
+ miraeping_stop "VASP finished (exit $rc): $PWD"
 exit "$rc"
```

---

### Python API

```python
import miraeping

miraeping.send("hello from Python API")
```

#### One-shot message

```python
import miraeping

miraeping.send("job submitted")

e0 = atoms.get_potential_energy()
miraeping.send(f"E0 = {e0:.4f} eV", name="VASP")  # adds [VASP] prefix
```

#### Job context manager

```python
import miraeping
from pathlib import Path

with miraeping.Job("VASP relax") as job:
    # ... your calculation ...
    if "reached required accuracy" in Path("OUTCAR").read_text(errors="ignore"):
        job.send("required accuracy reached")
    else:
        job.send("finished, convergence not reached")
```

#### Job object without `with`

```python
import miraeping

job = miraeping.Job("preprocessing")
job.send("started")
# ... your script ...
job.send("done")
```

#### Periodic monitor

```python
import miraeping
from pathlib import Path

def status():
    lines = Path("OSZICAR").read_text(errors="ignore").splitlines()
    return lines[-1] if lines else "OSZICAR not ready"

with miraeping.Monitor(status, interval=300, name="VASP relax"):
    # ... your calculation ...
```

#### Manual start / stop

```python
mon = miraeping.Monitor(status, interval=600, name="AIMD 300K")
mon.start()
try:
    # ... your calculation ...
finally:
    mon.stop()
```

> The Python API reads credentials from `~/.miraeping/credentials` automatically (same file `setup.sh` creates), with environment variables taking precedence.

---

## Feature 2 - Slack slash commands

Use this feature when you want to check cluster status directly from Slack.

This feature is powered by a separate Slack command server. You do **not** need to run `setup.sh` or install `miraeping` locally just to use slash commands.

What you need:

| Need | Why |
|------|-----|
| `miraebot` app added in Slack | Makes the bot and slash commands available in your workspace |
| Your Slack member ID | The admin uses this to identify your Slack account |
| Your cluster username (`echo $USER`) | Needed for `/qstat` and `/qwd`, so the command server can show your jobs |
| Admin-run Slack command server | Required for `/qq`, `/qstat`, `/qwd`, `/gpu`, and `/nvidia-smi` to respond |

After the admin registers your Slack member ID and cluster username, these commands are available:

| Command | Description |
|---------|-------------|
| `/qq` | Node availability (48-core / 64-core, queued jobs) |
| `/qstat` | Your running and queued jobs (JOB_ID, NAME, STATE, SLOTS, QUEUE) |
| `/qwd` | Working directories of your current jobs |
| `/gpu` | GPU memory and utilization on the GPU node |
| `/nvidia-smi` | Same as `/gpu` |

### Example output

**`/qq`**
```
+----------+-----------+------------+
| Node     | Available | Queued (qw)|
+----------+-----------+------------+
| 48-core  | 3/10      | 2          |
| 64-core  | 1/4       | 0          |
| Total    | 4/14      | 2          |
+----------+-----------+------------+

Available nodes:
n03 n07 n11 n12
```

**`/qstat`**
```
target user: alice
+--------+----------+-------+-------+-----------+
| JOB_ID | NAME     | STATE | SLOTS | QUEUE     |
+--------+----------+-------+-------+-----------+
| 100234 | HER_VASP | r     | 48    | all.q@n03 |
| 100235 | NEB_run  | qw    | 48    | -         |
+--------+----------+-------+-------+-----------+
```

**`/qwd`**
```
target user: alice
+--------+----------+-------+----------------------------+
| JOB_ID | NAME     | STATE | SUBMISSION_DIR             |
+--------+----------+-------+----------------------------+
| 100234 | HER_VASP | r     | /home/alice/project/run001 |
+--------+----------+-------+----------------------------+
```

**`/gpu`**
```
node: g01
+-----+--------------+-------------------+------+
| GPU | Name         | Mem (GiB)         | Util |
+-----+--------------+-------------------+------+
| 0   | RTX 6000 Ada | 12.3 / 47.5       | 45%  |
| 1   | RTX 6000 Ada |  0.4 / 47.5       |  2%  |
+-----+--------------+-------------------+------+
```

---

## Feature 3 - GPU availability watcher

`gpu-watch` is a standalone Bash executable for Linux GPU nodes. It reads the
exported `SLACK_BOT_TOKEN` and `SLACK_USER_ID` environment variables directly;
it does not source `.bashrc`, load `~/.miraeping/credentials`, or require the
existing miraeping functions. The Slack bot needs the same DM permissions as
the Bash helper (`im:write` and `chat:write`).

### Install and run

From the repository root, on the GPU node:

```bash
install -Dm755 bin/gpu-watch ~/.local/bin/gpu-watch

# Assumes Slack credentials are already exported and ~/.local/bin is on PATH.
gpu-watch
gpu-watch status
gpu-watch stop
gpu-watch -h
gpu-watch --help
```

If `~/.local/bin` is not on `PATH`, use `~/.local/bin/gpu-watch` directly.
Dependencies are Bash 4+, `nvidia-smi`, `curl`, GNU coreutils (including `timeout`
and `nohup`), and util-linux `flock`. No Python installation is needed.

The start command checks GPU access and opens the Slack DM before launching,
so missing credentials, an invalid GPU, or an inaccessible Slack API fail
visibly. It then starts its worker with `nohup`, redirects standard input and
logs, reports the PID, and returns. You do not need to add `nohup` or `&`.
Startup checks can take up to about 20 seconds if external commands stall.

### Availability and time limit

- By default, watch all visible physical GPUs on the current node and notify
  when **any one** uses at most **100 MiB** of VRAM.
- Query immediately. While no candidate is available, check every **10 minutes**.
- When a candidate is available, check again after **1 minute**. The GPU UUID
  must match across both observations. This does not prove uninterrupted
  availability between observations and does not reserve a GPU.
- Send one English Slack DM with the hostname, GPU index, UUID, and used/total
  VRAM, then exit after a successful delivery.
- Stop monitoring after **24 hours** by default. Attempt one final timeout DM,
  bounded to **10 additional seconds** (plus at most 1 second to force-stop a
  stuck external command), then exit even if Slack is unreachable. The time
  limit starts when the worker initializes, after startup checks.
- Failed GPU queries reset confirmation. Missing or nonnumeric memory values
  never count as available. Failed availability notifications trigger another
  GPU check before retrying, within the monitoring deadline.

Example notifications:

```text
GPU available on gpu-node-01
GPU 0 (GPU-...): 50 / 24576 MiB used.
Used VRAM <= 100 MiB at two checks at least 60s apart. This is an observation, not a reservation.

GPU watch timed out on gpu-node-01: no GPU availability notification was delivered within 86400s. Monitoring has stopped.
```

### Options and state

```bash
gpu-watch --gpu 0                       # Watch GPU index 0 only
gpu-watch --gpu GPU-xxxxxxxx-xxxx        # Or select its full NVIDIA GPU UUID
gpu-watch --threshold 200               # Used VRAM <= 200 MiB
gpu-watch --interval 5m --confirm 30s
gpu-watch --max-wait 12h
gpu-watch --foreground                  # For debugging or an external supervisor
```

Durations accept positive integer seconds or an `s`, `m`, `h`, or `d` suffix,
up to 365 days. The VRAM threshold is a nonnegative integer in MiB.

One watcher may run per user per node; another start reports the existing
watcher. To change options, stop it and start it again. Locks, PID identity,
last status, and `monitor.log` are stored under
`~/.miraeping/gpu-watch/<hostname>/`, with private permissions. Separate node
directories allow use with a shared home directory. `status` and `stop` do not
require Slack credentials or GPU access. Manual stop does not send a DM.
Foreground logs go to the terminal instead of `monitor.log`.

Run on the GPU node itself. `nohup` survives ordinary SSH hangups, but cannot
override cluster policies that terminate a session or all processes belonging
to an SGE job, nor survive node reboots. This watcher observes physical GPU
VRAM; it does not determine scheduler allocation or MIG-instance availability.
