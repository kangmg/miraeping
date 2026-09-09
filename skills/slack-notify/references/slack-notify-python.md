# slack-notify-python

Run the Bash doctor in the job environment first. Distribution/import: `miraeping` (Python ≥3.7, no third-party notification runtime dependencies). Use explicit `send`; no monitor or logging framework is needed.

Adapt `run_calculation()` and `result.converged` to the application's actual API:

```python
from pathlib import Path
import miraeping

path = Path.cwd()
try:
    result = run_calculation()
except Exception:
    miraeping.send(f"Failed | {path}")
    raise
else:
    if not result.converged:
        miraeping.send(f"Convergence failed | {path}")
        raise RuntimeError("Calculation did not converge")
    miraeping.send(f"Completed | {path}")
```

If convergence is not applicable, omit that check. Preserve the original exception/exit status; notification errors must not hide the calculation result. Job/Monitor contexts do not automatically send final notifications, and a normal return from `send` does not prove delivery.

## Sparse progress only

Default: one final message. **Never add logs or Slack alerts for every epoch, MD step, frame, or inner-loop iteration.** No verbose handlers, automatic log forwarding, or polling monitors. Do not remove the application's existing scientific output.

For 20 MD calculations, report every 4 completed runs, not every run. Inside the outer loop, after a run completes:

```python
if completed % 4 == 0 and completed < total:
    miraeping.send(f"MD {completed}/{total} completed | {path}")
```

Send one final summary at the end (no duplicate 20/20 progress alert). Adjust batch size to workload size. Report a terminal failure immediately; aggregate repeated recoverable/convergence failures into the next milestone or final summary. Notify from one process/rank only.
