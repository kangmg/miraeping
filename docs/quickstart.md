# <i class="fa-solid fa-fire"></i> Quick Start

Get started with miraeping in minutes! This guide covers the essential setup for both Bash and Python usage.

## Prerequisites

- Python 3.7 or higher
- A Slack workspace with bot permissions
- Your Slack User ID and Bot Token ([Setup Guide](develop.md))

## Environment Setup

Choose your preferred Python environment manager:

=== "uv"
    ```bash
    uv venv -p 3.7
    ```

=== "conda"
    ```bash
    conda create -n miraeping python=3.7
    conda activate miraeping
    ```

## Installation

Clone the repository and run the setup script:

```bash
git clone https://github.com/kangmg/miraeping
cd miraeping && bash setup.sh && cd ..
```

During setup, you'll be prompted to enter:

- **Slack User ID**: `U0XXXXXXXXX` (your member ID)
- **Bot Token**: `xoxb-YOUR-BOT-TOKEN-HERE` (starts with `xoxb-`)

After setup completes, reload your shell configuration:

```bash
source ~/.bashrc
```

!!! tip "What does setup.sh do?"
    - Installs the bash helper to `~/.miraeping/miraeping`
    - Creates `~/.miraeping/credentials` with your Slack credentials (permission `600`)
    - Appends `source ~/.miraeping/miraeping` to `~/.bashrc` if not already present

## Bash Usage

Test your bash setup with a simple message:

```bash
miraeping_send 'Hello from miraeping!'
```

You should receive a Slack DM from your bot. For more advanced usage:

```bash
miraeping_send 'More Usage: https://kangmg.github.io/miraeping/usage/#bash-helper'
```

### Quick Example: SGE Job Notification

```bash
#!/bin/bash
#$ -V
#$ -S /bin/bash
#$ -N my_job
#$ -cwd

source ~/.miraeping/miraeping

# Your computation here
./run_simulation.sh

# Notify when done
miraeping_send "Job $JOB_NAME completed in $PWD"
```

## Python Usage

Install the Python package:

```bash
pip install miraeping
```

Test your Python setup:

```bash
python3 - <<'PY'
import miraeping

miraeping.send("Hello from miraeping Python API!")
miraeping.send("More info: https://kangmg.github.io/miraeping/usage/#python-api")
PY
```

### Quick Example: Computation Monitoring

```python
import miraeping
import time

with miraeping.Job("Training Model") as job:
    for epoch in range(10):
        # Your training code here
        time.sleep(1)
        job.send(f"Epoch {epoch+1}/10 completed")
    
job.send("Training finished!")
```

## Next Steps

- **[User Guide](usage.md)**: Detailed usage examples for Bash and Python
- **[Developer Guide](develop.md)**: Set up Slack bot and command server
- **[GitHub Repository](https://github.com/kangmg/miraeping)**: Source code and issues

## Troubleshooting

!!! warning "Credentials not found?"
    Make sure you've run `source ~/.bashrc` after setup. The bash helper and Python API both read from `~/.miraeping/credentials`.

!!! warning "Not receiving messages?"
    - Verify your Slack User ID is correct (see [Developer Guide](develop.md#finding-your-slack-user-id))
    - Ensure the bot is added to your workspace
