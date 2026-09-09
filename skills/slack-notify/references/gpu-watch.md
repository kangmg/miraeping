# GPU availability watcher

Run doctor with `--mode gpu` on the actual GPU node. It must see `gpu-watch`, `nvidia-smi`, and exported `SLACK_BOT_TOKEN` / `SLACK_USER_ID`; a credential file alone is insufficient.

```bash
gpu-watch
gpu-watch status
gpu-watch stop
gpu-watch --help
gpu-watch --gpu 0 --threshold 100 --interval 10m --confirm 1m --max-wait 24h
```

The standalone Bash executable detaches itself using `nohup` and `&`; do not wrap it in another `nohup` or source it. Normal invocation checks prerequisites, opens its DM, starts the worker, and returns. Start only when the user requests the monitoring/notification, not as a setup test.

Defaults: inspect immediately, poll every 10 minutes while busy, treat used VRAM <= 100 MiB as a candidate, and recheck the same UUID after 1 minute. Notify once after successful confirmation and delivery. Default maximum monitoring time is 24 hours; timeout delivery gets a separate bounded 10-second attempt, plus at most 1 second to force-stop a hung call. A confirmation shortened by the deadline does not qualify.

One watcher runs per user per node. State and `monitor.log` are under `~/.miraeping/gpu-watch/<hostname>/`; `status` and `stop` must run on that same node. Another start does not update options: stop and restart to change them. `--foreground` is for debugging/supervisors. After installing an updated executable, restart an existing watcher to apply it.

## Notification format

Keep the approved compact format: `node: <hostname>` followed by a fenced box with only `GPU`, `Name`, `Avail.`. Use `✓` for confirmed availability and `✗` otherwise. No memory, utilization, UUID, or runtime columns. Strip the `NVIDIA ` name prefix and use the existing 12-character name width.

```text
+-----+--------------+--------+
| GPU | Name         | Avail. |
+-----+--------------+--------+
| 0   | RTX 6000 Ada |   ✓    |
| 1   | RTX A6000    |   ✗    |
+-----+--------------+--------+
```

`✗` also covers a pending confirmation or unavailable measurement; it is not proof that the GPU is occupied. A `--gpu` selection limits the table to that GPU. Timeout messages use the last observed list and append only `Monitoring stopped after 24 hours.` (adjusted for the chosen wait).

VRAM availability is an observation, not a reservation or scheduler allocation. Do not automatically submit a computation or claim that the GPU is reserved. This physical-GPU watcher does not determine MIG-instance availability. `nohup` survives ordinary SSH hangups but not node reboots or scheduler policies that kill all job/session processes. Keep job-lifetime Bash/Python monitors distinct from this detached watcher.
