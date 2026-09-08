"""Linux integration tests using fake NVIDIA and Slack executables (no network)."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gpu-watch"
FREE = "GPU-aaa, 0, 50, 24000, NVIDIA RTX 6000 Ada\nGPU-bbb, 1, 2000, 24000, NVIDIA RTX A6000"
BUSY = "GPU-aaa, 0, 2000, 24000, NVIDIA RTX 6000 Ada\nGPU-bbb, 1, 2000, 24000, NVIDIA RTX A6000"
OTHER_FREE = "GPU-aaa, 0, 2000, 24000, NVIDIA RTX 6000 Ada\nGPU-bbb, 1, 50, 24000, NVIDIA RTX A6000"
FAKE = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time
root = pathlib.Path(os.environ["MOCK_ROOT"])
name = pathlib.Path(sys.argv[0]).name
if name == "hostname":
    print(os.environ.get("MOCK_NODE", "gpu-test"))
    sys.exit(0)
if name == "nvidia-smi":
    assert "--query-gpu=uuid,index,memory.used,memory.total,name" in sys.argv
    counter = root / "queries"
    count = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(count + 1))
    sequence = json.loads((root / "sequence.json").read_text())
    position = count % len(sequence) if os.environ.get("MOCK_SEQUENCE_REPEAT") else min(count, len(sequence) - 1)
    value = sequence[position]
    if value is None:
        sys.exit(1)
    if isinstance(value, dict):
        time.sleep(value["sleep"])
        value = value["output"]
    print(value)
    sys.exit(0)
config = sys.stdin.read()
assert "Authorization: Bearer xoxb-test-token" in config
assert not any("xoxb-test-token" in arg for arg in sys.argv)
if sys.argv[-1].endswith("conversations.open"):
    if os.environ.get("MOCK_OPEN_FAIL"):
        print('{"ok": false, "error": "invalid_auth"}')
    else:
        print('{"ok": true, "channel": {"id": "DTEST123"}}')
    sys.exit(0)
text = next(arg[5:] for arg in sys.argv if arg.startswith("text="))
with (root / "messages.jsonl").open("a") as handle:
    handle.write(json.dumps(text) + "\n")
count_file = root / "posts"
count = int(count_file.read_text()) if count_file.exists() else 0
count_file.write_text(str(count + 1))
if os.environ.get("MOCK_POST_HANG"):
    time.sleep(60)
fail = count < int(os.environ.get("MOCK_POST_FAILURES", "0"))
print(json.dumps({"ok": not fail}))
'''


@unittest.skipUnless(
    sys.platform.startswith("linux")
    and all(shutil.which(cmd) for cmd in ("bash", "timeout", "flock", "nohup")),
    "Requires Linux, Bash, GNU timeout, flock, and nohup",
)
class GpuWatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gpu-watch-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        for name in ("nvidia-smi", "curl", "hostname"):
            executable = self.fake_bin / name
            executable.write_text(FAKE)
            executable.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.root), MOCK_ROOT=str(self.root),
                        PATH=str(self.fake_bin) + os.pathsep + os.environ["PATH"],
                        SLACK_BOT_TOKEN="xoxb-test-token", SLACK_USER_ID="UTEST123")
        for key in list(self.env):
            if key.startswith("MOCK_") and key != "MOCK_ROOT":
                del self.env[key]
        self.state = self.root / ".miraeping" / "gpu-watch" / "gpu-test"
        self.sequence(BUSY)
        self.addCleanup(self.stop)

    def stop(self):
        self.run_watch("stop", check=False)

    def sequence(self, *values):
        (self.root / "sequence.json").write_text(json.dumps(values))

    def run_watch(self, *args, check=True, timeout=20, env=None):
        result = subprocess.run(["bash", str(SCRIPT), *args], env=env or self.env,
                                capture_output=True, text=True, timeout=timeout)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def messages(self):
        path = self.root / "messages.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def foreground(self, *args, **kwargs):
        return self.run_watch("--foreground", "--interval", "1s", "--confirm", "1s",
                              "--max-wait", "8s", *args, **kwargs)

    def test_help_without_gpu_or_credentials(self):
        env = dict(self.env)
        env.pop("SLACK_BOT_TOKEN")
        env.pop("SLACK_USER_ID")
        for option in ("-h", "--help"):
            result = self.run_watch(option, env=env)
            for expected in ("Usage:", "status|stop", "24h", "SLACK_BOT_TOKEN", "--confirm"):
                self.assertIn(expected, result.stdout)
        self.assertFalse(self.state.exists())

    def test_invalid_options(self):
        for args in (("--max-wait", "0"), ("--interval", "-1"), ("--confirm", "1.5"),
                     ("--threshold", "-1"), ("--gpu", "bad"), ("--max-wait",), ("--wat",),
                     ("status", "--foreground"), ("stop", "--max-wait", "1s")):
            self.assertNotEqual(self.run_watch(*args, check=False).returncode, 0)

    def test_preflight_errors_do_not_start_worker(self):
        env = dict(self.env)
        env.pop("SLACK_BOT_TOKEN")
        result = self.run_watch(env=env, check=False)
        self.assertIn("SLACK_BOT_TOKEN", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        result = self.run_watch("--gpu", "7", check=False)
        self.assertIn("GPU not found", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.env["MOCK_OPEN_FAIL"] = "1"
        self.assertNotEqual(self.run_watch(check=False).returncode, 0)
        self.assertFalse((self.state / "monitor.pid").exists())
        self.assertEqual(self.messages(), [])

    def test_same_gpu_confirmed_once(self):
        self.sequence(FREE)
        self.foreground()
        self.assertEqual(len(self.messages()), 1)
        self.assertEqual(self.messages()[0], "\n".join([
            "node: gpu-test", "```",
            "+-----+--------------+--------+",
            "| GPU | Name         | Avail. |",
            "+-----+--------------+--------+",
            "| 0   | RTX 6000 Ada |   ✓    |",
            "| 1   | RTX A6000    |   ✗    |",
            "+-----+--------------+--------+", "```",
        ]))
        self.assertIn("Notified:", self.run_watch("status").stdout)
        self.assertFalse((self.state / "monitor.pid").exists())

    def test_gpu_filter_and_inclusive_threshold(self):
        self.sequence(FREE, "GPU-aaa, 0, 0, 24000, NVIDIA RTX 6000 Ada\nGPU-bbb, 1, 100, 24000, NVIDIA RTX A6000")
        self.foreground("--gpu", "GPU-bbb")
        self.assertEqual(len(self.messages()), 1)
        self.assertIn("| 1   | RTX A6000    |   ✓    |", self.messages()[0])
        self.assertNotIn("| 0   |", self.messages()[0])

    def test_different_free_gpus_do_not_confirm_each_other(self):
        # Keep alternating for the entire watch, regardless of poll count.
        self.env["MOCK_SEQUENCE_REPEAT"] = "1"
        self.sequence(FREE, OTHER_FREE)
        self.foreground("--max-wait", "4s")
        self.assertEqual(len(self.messages()), 1)
        self.assertIn("Monitoring stopped after", self.messages()[0])

    def test_table_only_checks_confirmed_gpus_in_c_locale(self):
        self.env["LC_ALL"] = "C"
        self.sequence(BUSY, FREE, FREE.replace("2000", "50"))
        self.foreground()
        message = self.messages()[0]
        self.assertIn("| 0   | RTX 6000 Ada |   ✓    |", message)
        self.assertIn("| 1   | RTX A6000    |   ✗    |", message)
        lines = message.splitlines()[2:-1]
        self.assertEqual(len({len(line) for line in lines}), 1)

    def test_timeout_table_has_no_extra_metrics(self):
        self.foreground("--max-wait", "1s")
        message = self.messages()[0]
        self.assertTrue(message.startswith("node: gpu-test\n```\n"))
        self.assertIn("| 0   | RTX 6000 Ada |   ✗    |", message)
        self.assertIn("| 1   | RTX A6000    |   ✗    |", message)
        self.assertTrue(message.endswith("```\nMonitoring stopped after 1 second."))
        for unwanted in ("Mem", "MiB", "GiB", "UUID", "GPU-aaa", "runtime", "started", "Threshold"):
            self.assertNotIn(unwanted, message)

    def test_query_failure_resets_confirmation(self):
        self.sequence(BUSY, FREE, None, FREE, FREE)
        result = self.foreground()
        self.assertIn("Confirmation reset", result.stdout)
        self.assertGreaterEqual(int((self.root / "queries").read_text()), 5)
        self.assertEqual(len(self.messages()), 1)
        self.assertIn("| 0   | RTX 6000 Ada |   ✓    |", self.messages()[0])

    def test_unavailable_memory_is_not_free(self):
        self.sequence(BUSY, "GPU-aaa, 0, N/A, 24000, NVIDIA RTX 6000 Ada")
        self.foreground("--max-wait", "1s")
        self.assertIn("Monitoring stopped after", self.messages()[0])

    def test_long_confirmation_is_capped_by_deadline(self):
        self.sequence(FREE)
        started = time.monotonic()
        self.foreground("--confirm", "60s", "--max-wait", "1s")
        self.assertLess(time.monotonic() - started, 4)
        self.assertIn("Monitoring stopped after", self.messages()[0])

    def test_hung_gpu_query_is_capped_by_deadline(self):
        self.sequence(BUSY, {"sleep": 60, "output": FREE})
        started = time.monotonic()
        self.foreground("--max-wait", "1s")
        self.assertLess(time.monotonic() - started, 4)
        self.assertIn("Monitoring stopped after", self.messages()[0])

    def test_slack_failure_rechecks_before_retry(self):
        self.sequence(BUSY, FREE, FREE, BUSY, FREE, FREE)
        self.env["MOCK_POST_FAILURES"] = "1"
        result = self.foreground()
        self.assertIn("Slack delivery failed", result.stdout)
        self.assertGreaterEqual(int((self.root / "queries").read_text()), 6)
        self.assertEqual(len(self.messages()), 2)
        self.assertIn("Notified:", self.run_watch("status").stdout)

    def test_timeout_delivery_failure_exits(self):
        self.env["MOCK_POST_FAILURES"] = "100"
        result = self.foreground("--max-wait", "1s", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Slack delivery failed", self.run_watch("status").stdout)
        self.assertFalse((self.state / "monitor.pid").exists())

    def test_hung_timeout_notification_is_bounded(self):
        self.env["MOCK_POST_HANG"] = "1"
        started = time.monotonic()
        result = self.foreground("--max-wait", "1s", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.messages()), 1)
        self.assertIn("Monitoring stopped after", self.messages()[0])
        self.assertLess(time.monotonic() - started, 14)
        self.assertFalse((self.state / "monitor.pid").exists())

    def test_background_survives_hangup_duplicate_and_stop(self):
        started = time.monotonic()
        result = self.run_watch("--max-wait", "1m")
        self.assertIn("Started GPU watcher", result.stdout)
        self.assertLess(time.monotonic() - started, 4)
        pid = int((self.state / "monitor.pid").read_text().split()[0])
        os.kill(pid, signal.SIGHUP)
        self.assertIn("Running on", self.run_watch("status").stdout)
        self.assertIn("Already watching", self.run_watch().stdout)
        self.assertEqual(pid, int((self.state / "monitor.pid").read_text().split()[0]))
        env = dict(self.env)
        env.pop("SLACK_BOT_TOKEN")
        self.assertIn("Stopped watcher", self.run_watch("stop", env=env).stdout)
        self.assertIn("Not running", self.run_watch("status", env=env).stdout)
        self.assertEqual(self.messages(), [])

    def test_default_no_argument_start_with_busy_gpus(self):
        result = self.run_watch()
        self.assertIn("Started GPU watcher", result.stdout)
        self.assertIn("maximum wait: 86400s", result.stdout)
        self.assertTrue((self.state / "monitor.log").is_file())
        # Allow the first busy snapshot to reach the empty-candidate path.
        time.sleep(0.3)
        self.assertIn("Running on", self.run_watch("status").stdout)
        self.assertNotIn("unbound variable", (self.state / "monitor.log").read_text())
        self.assertIn("Stopped watcher", self.run_watch("stop").stdout)
        self.assertEqual(self.messages(), [])

    def test_shared_home_uses_separate_node_state(self):
        self.run_watch("--max-wait", "1m")
        env = dict(self.env, MOCK_NODE="another-node")
        self.assertIn("Not running on another-node", self.run_watch("status", env=env).stdout)
        self.assertIn("No watcher", self.run_watch("stop", env=env).stdout)
        self.assertIn("Running on gpu-test", self.run_watch("status").stdout)

    def test_stale_pid_cannot_kill_unrelated_process(self):
        unrelated = subprocess.Popen(["sleep", "60"])
        self.addCleanup(unrelated.wait)
        self.addCleanup(unrelated.terminate)
        self.state.mkdir(parents=True)
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        (self.state / "monitor.pid").write_text(f"{unrelated.pid} 0 {boot}\n")
        self.assertIn("No watcher", self.run_watch("stop").stdout)
        self.assertIsNone(unrelated.poll())


if __name__ == "__main__":
    unittest.main()
