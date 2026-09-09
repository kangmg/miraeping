"""Doctor integration tests: isolated homes, fake Slack and NVIDIA, no real DMs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

DOCTOR = Path(__file__).resolve().parents[1] / "skills/slack-notify/scripts/miraeping-doctor"
MOCK = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
root = pathlib.Path(os.environ["MOCK_ROOT"])
command = pathlib.Path(sys.argv[0]).name
if command == "nvidia-smi":
    print(os.environ.get("MOCK_GPU", "GPU-aaa, 0, 2000, 24000"))
elif command == "curl":
    assert sys.argv[-1] == "https://slack.com/api/auth.test", "Unexpected Slack write"
    assert not any("xoxb-" in arg for arg in sys.argv)
    assert os.environ.get("MOCK_EXPECT_TOKEN", "xoxb-env-secret") in sys.stdin.read()
    with (root / "calls").open("a") as handle:
        handle.write("auth.test\n")
    headers = pathlib.Path(sys.argv[sys.argv.index("--dump-header") + 1])
    headers.write_text("x-oauth-scopes: " + os.environ.get("MOCK_SCOPES", "im:write,chat:write") + "\r\n")
    if os.environ.get("MOCK_AUTH_FAIL"):
        print(json.dumps({"ok": False, "error": "invalid_auth"}))
    else:
        print(json.dumps({"ok": True}))
elif command == "gpu-watch":
    raise AssertionError("Doctor must not launch the watcher")
elif command in ("qsub", "qstat"):
    raise AssertionError("Doctor must not submit or query jobs")
'''


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("bash"), "Linux/Bash required")
class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="miraeping-doctor-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("curl", "gpu-watch", "nvidia-smi", "qsub", "qstat"):
            path = self.bin / name
            path.write_text(MOCK)
            path.chmod(0o755)
        self.config = self.root / ".miraeping"
        self.config.mkdir()
        self.helper = self.config / "miraeping"
        self.helper.write_text("miraeping_send() { :; }\nmiraeping_monitor() { :; }\nmiraeping_stop() { :; }\n")
        self.package = self.root / "packages" / "miraeping"
        self.package.mkdir(parents=True)
        (self.package / "__init__.py").write_text(
            "__version__ = '0.0.test'\ndef send(*args): raise AssertionError('No send')\n"
            "class Job: pass\nclass Monitor: pass\n")
        self.env = {key: value for key, value in os.environ.items() if not key.startswith(("MOCK_", "SLACK_"))}
        self.env.update(HOME=str(self.root), MOCK_ROOT=str(self.root),
                        PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        PYTHONPATH=str(self.package.parent),
                        SLACK_BOT_TOKEN="xoxb-env-secret", SLACK_USER_ID="U012ABCDEF")

    def run_doctor(self, *args, expected=0, trace=False):
        command = ["bash"] + (["-x"] if trace else []) + [str(DOCTOR), *args]
        result = subprocess.run(command, env=self.env, cwd=self.root,
                                capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, expected, output)
        for secret in ("xoxb-env-secret", "xoxb-file-secret", "U012ABCDEF"):
            self.assertNotIn(secret, output)
        return output

    def credentials(self, contents="SLACK_BOT_TOKEN=xoxb-file-secret\nSLACK_USER_ID=U012ABCDEF\n"):
        path = self.config / "credentials"
        path.write_text(contents)
        path.chmod(0o600)
        return path

    def test_help_and_invalid_arguments(self):
        self.env.pop("SLACK_BOT_TOKEN")
        for flag in ("-h", "--help"):
            self.assertIn("Usage:", self.run_doctor(flag))
        self.run_doctor("--mode", "server", expected=2)
        self.run_doctor("--python", expected=2)
        self.run_doctor("--unknown", expected=2)

    def test_bash_local_does_not_send_or_require_other_modes(self):
        output = self.run_doctor()
        self.assertIn("0 failure(s)", output)
        self.assertNotIn("[python]", output)
        self.assertNotIn("[gpu]", output)
        self.assertFalse((self.root / "calls").exists())

    def test_missing_credentials_fail(self):
        self.env.pop("SLACK_BOT_TOKEN")
        output = self.run_doctor(expected=1)
        self.assertIn("SLACK_BOT_TOKEN missing", output)

    def test_bash_prefers_file_and_never_sources_it(self):
        marker = self.root / "executed"
        contents = "SLACK_BOT_TOKEN=xoxb-file-secret\nSLACK_USER_ID=U012ABCDEF\ntouch " + str(marker) + "\n"
        path = self.credentials(contents)
        self.helper.write_text(self.helper.read_text() + "touch " + str(marker) + "\n")
        self.env["SLACK_BOT_TOKEN"] = "invalid-env"
        output = self.run_doctor()
        self.assertIn("source: credentials file", output)
        self.assertFalse(marker.exists())
        self.assertEqual(path.read_text(), contents)

    def test_python_prefers_environment_in_selected_interpreter(self):
        self.credentials("SLACK_BOT_TOKEN=invalid-file\nSLACK_USER_ID=U012ABCDEF\n")
        output = self.run_doctor("--mode", "python", "--python", sys.executable)
        self.assertIn("miraeping version: 0.0.test", output)
        self.assertIn(str(self.package), output)
        self.assertIn("source: environment", output)

    def test_python_absent_environment_uses_file(self):
        self.credentials()
        self.env.pop("SLACK_BOT_TOKEN")
        self.env.pop("SLACK_USER_ID")
        self.assertIn("source: credentials file", self.run_doctor("--mode", "python"))

    def test_python_empty_environment_does_not_fall_back(self):
        self.credentials()
        self.env["SLACK_BOT_TOKEN"] = ""
        self.run_doctor("--mode", "python", expected=1)

    def test_gpu_ignores_credential_file(self):
        self.credentials()
        self.env.pop("SLACK_BOT_TOKEN")
        self.run_doctor("--mode", "gpu", expected=1)

    def test_gpu_valid_and_unsupported_vram(self):
        self.assertIn("Readable GPU VRAM data: 1", self.run_doctor("--mode", "gpu"))
        self.env["MOCK_GPU"] = "GPU-aaa, 0, N/A, 24000"
        self.run_doctor("--mode", "gpu", expected=1)

    def test_missing_helper_or_api_definition(self):
        self.run_doctor("--helper", str(self.root / "missing"), expected=1)
        self.helper.write_text("# empty helper\n")
        self.assertIn("missing the expected", self.run_doctor(expected=1))

    def test_python_missing_or_broken_package(self):
        self.run_doctor("--mode", "python", "--python", "/not/a/python", expected=1)
        (self.package / "__init__.py").write_text("raise ImportError('not installed correctly')\n")
        self.assertIn("install miraeping", self.run_doctor("--mode", "python", expected=1))

    def test_online_only_auth_test_and_no_secret_in_trace(self):
        output = self.run_doctor("--online", trace=True)
        self.assertIn("auth.test succeeded", output)
        self.assertIn("DM scope present: chat:write", output)
        self.assertEqual((self.root / "calls").read_text(), "auth.test\n")

    def test_online_uses_effective_file_token(self):
        self.credentials()
        self.env["MOCK_EXPECT_TOKEN"] = "xoxb-file-secret"
        self.run_doctor("--online")

    def test_online_rejected_token_and_missing_scope(self):
        self.env["MOCK_AUTH_FAIL"] = "1"
        self.assertIn("invalid_auth", self.run_doctor("--online", expected=1))
        self.env.pop("MOCK_AUTH_FAIL")
        self.env["MOCK_SCOPES"] = "im:write"
        self.assertIn("Missing DM scope: chat:write", self.run_doctor("--online", expected=1))

    def test_missing_scope_header_warns_and_all_checks_accumulate(self):
        self.env["MOCK_SCOPES"] = ""
        self.assertIn("DM permissions are unverified", self.run_doctor("--online"))
        self.env.pop("SLACK_BOT_TOKEN")
        output = self.run_doctor("--mode", "all", expected=1)
        for mode in ("[bash]", "[python]", "[gpu]"):
            self.assertIn(mode, output)
        self.assertIn("3 failure(s)", output)

    def test_loose_file_permissions_warn(self):
        path = self.credentials()
        path.chmod(0o644)
        self.assertIn("chmod 600", self.run_doctor())


if __name__ == "__main__":
    unittest.main()
