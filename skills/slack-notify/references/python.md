# Python notifications and local logging

Run doctor with `--mode python --python /path/to/job/env/bin/python`. The package and import name are both `miraeping`; notification code uses only the Python standard library. Avoid installing dependencies for a Slack server into a computation environment.

## Public API

```python
import miraeping

miraeping.send("Checkpoint saved", name="Training")
job = miraeping.Job("Relaxation")
job.send("Energy: ", -123.4)

monitor = miraeping.Monitor(status_fn, interval=600, name="Training")
monitor.start()
try:
    # computation
    pass
finally:
    monitor.stop()
```

`send(message, name=None)` takes one message object; concatenate or format multiple values first. `Job.send(*args)` and `Monitor.send(*args)` concatenate arguments. `Job` is a labeling context; it does not send started/completed/failed messages on entry/exit. A `Monitor` context starts/stops the thread but also does not send completion automatically. Its periodic callback runs on a background thread after the first interval; manual `monitor.send(...)` is immediate.

## Integrating application logs

Add handlers to the application's existing logger instead of overwriting its logging setup. For a small standalone program, adapt this pattern around its real `run_computation` function:

```python
import logging
from pathlib import Path
import miraeping

log_path = Path("run.log").resolve()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(str(log_path)), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

def status():
    # Prefer a small thread-safe progress snapshot maintained by the job.
    return "Computation running. Log: {}".format(log_path)

try:
    with miraeping.Monitor(status, interval=600, name="Computation"):
        logger.info("Computation started")
        run_computation()
except Exception:
    logger.exception("Computation failed")
    miraeping.send("Failed. See log: {}".format(log_path), name="Computation")
    raise
else:
    logger.info("Computation completed")
    miraeping.send("Completed. Log: {}".format(log_path), name="Computation")
```

Keep heavy file reads, mutable shared state, and calls into non-thread-safe simulation objects out of the callback. For log tails, read a bounded amount and handle missing files/partial writes; do not reread multi-gigabyte logs every interval. Do not attach an automatic Slack handler to every log record unless specifically requested.

The Python API swallows many notification errors, and its transport does not reliably raise for Slack `ok: false`. Do not use `miraeping.send(...)` returning normally as proof of delivery. Doctor's offline/online checks also do not send a test DM. If the user requests a real delivery test, send one concise test using their chosen path and verify the observed result; do not retry indefinitely or mask a failed computation.

For Python inside SGE, preserve job environment activation and choose one owner for final notifications (Python or the wrapper) to avoid duplicate DMs. MPI/multiprocessing workers should not each create a monitor.
