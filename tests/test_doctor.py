"""Bash-first doctor integration tests. Fake Slack transport; no live calls."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv

REPO = Path(__file__).resolve().parents[1]
DOCTOR = REPO / "skills/slack-notify/scripts/miraeping-doctor"

@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("bash"), "Linux/Bash required")
class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bash-doctor-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        # Deliberately NO python, python3, jq, awk, sed, or cat on PATH.
        for name in ("bash", "grep", "stat", "mktemp", "rm", "timeout"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.env = {"PATH": str(self.bin), "HOME": str(self.root),
                    "SLACK_BOT_TOKEN": "xoxb-env-secret", "SLACK_USER_ID": "U012ABCDEF",
                    "MOCK_ROOT": str(self.root)}
        self.helper = self.root / ".miraeping/miraeping"
        self.helper.parent.mkdir()
        self.helper.write_text("miraeping_send() { :; }\nmiraeping_monitor() { :; }\nmiraeping_stop() { :; }\n")
        self.executable("curl", r'''#!/bin/bash
for arg in "$@"; do
    [[ "$arg" != *xoxb-* ]] || exit 90
done
[[ "${!#}" == https://slack.com/api/auth.test ]] || exit 91
[[ "$1" == --disable ]] || exit 92
IFS= read -r config
printf '%s\n' "$config" >> "$MOCK_ROOT/auth-calls"
headers=''
while (( $# )); do
    if [[ "$1" == --dump-header ]]; then headers="$2"; shift; fi
    shift
done
[[ "${MOCK_NETWORK_FAIL:-}" != 1 ]] || exit 28
printf 'HTTP/1.1 200 OK\r\n' > "$headers"
if [[ "${MOCK_NO_SCOPES:-}" != 1 ]]; then
    printf 'X-OAuth-Scopes: %s\r\n' "${MOCK_SCOPES-im:write,chat:write}" >> "$headers"
fi
printf '\r\n' >> "$headers"
printf '%s\n' "${MOCK_RESPONSE-{\"ok\":true}}"
''')

    def executable(self, name, content):
        path = self.bin / name
        path.write_text(content.replace("#!/bin/bash", "#!" + shutil.which("bash"), 1))
        path.chmod(0o755)
        return path

    def run_doctor(self, expected=0, args=()):
        result = subprocess.run([str(self.bin / "bash"), str(DOCTOR), *args],
                                cwd=self.root, env=self.env, capture_output=True,
                                text=True, timeout=20)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        for secret in ("xoxb-env-secret", "xoxb-file-secret", "U012ABCDEF"):
            self.assertNotIn(secret, result.stdout + result.stderr)
        return result.stdout

    def credentials(self, text="SLACK_BOT_TOKEN=xoxb-file-secret\nSLACK_USER_ID=U012ABCDEF\n"):
        path = self.helper.parent / "credentials"
        path.write_text(text)
        path.chmod(0o600)
        return path

    def add_python(self):
        (self.bin / "python3").symlink_to(sys.executable)
        (self.root / "miraeping.py").write_text(
            "__version__='test'\ndef send(): pass\nclass Job: pass\nclass Monitor: pass\n")

    def gpu(self):
        self.executable("gpu-watch", "#!/bin/bash\nexit 99\n")
        for name in ("nohup", "flock"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.executable("nvidia-smi", "#!/bin/bash\nprintf '%s\\n' \"${MOCK_GPU-GPU-aaa, 0, 50, 24000}\"\n")

    def test_no_python_or_jq_bash_and_online_work(self):
        output = self.run_doctor()
        self.assertIn("bash: ready", output)
        self.assertIn("optional Python check skipped", output)
        self.assertIn("auth.test succeeded", output)
        self.assertFalse((self.bin / "python3").exists())
        self.assertFalse((self.bin / "jq").exists())

    def test_help_without_any_external_commands(self):
        self.env["PATH"] = str(self.root / "empty")
        self.env.pop("SLACK_BOT_TOKEN")
        for flag in ("-h", "--help"):
            self.assertIn("Python is optional", self.run_doctor(args=(flag,)))

    def test_old_flags_rejected(self):
        for flag in ("--mode", "--python", "--online"):
            self.run_doctor(expected=2, args=(flag,))

    def test_missing_token_skips_network(self):
        self.env.pop("SLACK_BOT_TOKEN")
        self.run_doctor(expected=1)
        self.assertFalse((self.root / "auth-calls").exists())

    def test_missing_curl_reports_failure_not_python_error(self):
        (self.bin / "curl").unlink()
        self.assertIn("require curl", self.run_doctor(expected=1))

    def test_bad_helper_syntax(self):
        self.helper.write_text("broken() {\n")
        self.assertIn("syntax check failed", self.run_doctor(expected=1))

    def test_missing_helper_api(self):
        self.helper.write_text("# not a helper\n")
        self.assertIn("missing the expected", self.run_doctor(expected=1))

    def test_helper_and_credentials_never_executed(self):
        marker = self.root / "executed"
        self.helper.write_text(self.helper.read_text() + "printf bad > " + str(marker) + "\n")
        path = self.credentials("SLACK_BOT_TOKEN=xoxb-file-secret\nSLACK_USER_ID=U012ABCDEF\nprintf bad > " + str(marker) + "\n")
        original = path.read_bytes()
        self.run_doctor()
        self.assertFalse(marker.exists())
        self.assertEqual(path.read_bytes(), original)

    def test_bash_file_overrides_environment(self):
        self.credentials()
        self.run_doctor()
        calls = (self.root / "auth-calls").read_text()
        self.assertIn("xoxb-file-secret", calls)
        self.assertNotIn("xoxb-env-secret", calls)

    def test_optional_python_import_and_same_token_auth_once(self):
        self.add_python()
        output = self.run_doctor()
        self.assertIn("python: ready", output)
        self.assertEqual(len((self.root / "auth-calls").read_text().splitlines()), 1)

    def test_python_credentials_keep_environment_precedence(self):
        self.add_python()
        self.credentials()
        self.run_doctor()
        calls = (self.root / "auth-calls").read_text()
        self.assertIn("xoxb-file-secret", calls)
        self.assertIn("xoxb-env-secret", calls)

    def test_empty_python_env_does_not_use_file(self):
        self.add_python()
        self.credentials()
        self.env["SLACK_BOT_TOKEN"] = ""
        self.assertIn("missing or malformed [python]", self.run_doctor(expected=1))

    def test_missing_python_package_does_not_block_bash(self):
        (self.bin / "python3").symlink_to(sys.executable)
        self.assertIn("Optional Python API unavailable", self.run_doctor())

    def test_broken_active_environment_does_not_block_bash(self):
        self.env["CONDA_PREFIX"] = str(self.root / "missing")
        self.assertIn("Activated environment has no Python", self.run_doctor())

    def test_conda_and_venv_selection(self):
        for variable in ("CONDA_PREFIX", "VIRTUAL_ENV"):
            with self.subTest(variable=variable):
                environment = self.root / variable
                (environment / "bin").mkdir(parents=True)
                (environment / "bin/python3").symlink_to(sys.executable)
                self.env[variable] = str(environment)
                self.assertIn(str(environment / "bin/python3"), self.run_doctor())

    def test_network_failure(self):
        self.env["MOCK_NETWORK_FAIL"] = "1"
        self.assertIn("auth.test failed", self.run_doctor(expected=1))

    def test_false_or_unrecognized_auth_responses_are_not_accepted(self):
        for response in ('{"ok":false}', '{"nested":{"ok":true}}', '{"ok":trueish}', 'not JSON'):
            self.env["MOCK_RESPONSE"] = response
            self.assertNotIn("auth.test succeeded", self.run_doctor(expected=1))

    def test_scopes(self):
        self.env["MOCK_SCOPES"] = "im:write"
        self.assertIn("Missing DM scope: chat:write", self.run_doctor(expected=1))
        self.env["MOCK_NO_SCOPES"] = "1"
        self.assertIn("permissions are unverified", self.run_doctor())

    def test_gpu_without_python(self):
        self.gpu()
        self.assertIn("gpu: ready", self.run_doctor())
        self.env["MOCK_GPU"] = "GPU-aaa, 0, N/A, 24000"
        self.assertIn("VRAM data is missing or unsupported", self.run_doctor(expected=1))

    def test_gpu_does_not_use_credential_file(self):
        self.gpu()
        self.credentials()
        self.env.pop("SLACK_BOT_TOKEN")
        self.assertIn("missing or malformed [gpu]", self.run_doctor(expected=1))

    def test_missing_helper_without_other_integration_is_failure(self):
        self.helper.unlink()
        self.assertIn("No notification path is ready", self.run_doctor(expected=1))


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("bash"), "Linux/Bash required")
class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-copy-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("SLACK_", "CONDA_", "VIRTUAL_ENV", "CODEX_HOME"))}
        self.env["HOME"] = str(self.root)

    def install(self):
        result = subprocess.run(["bash", str(REPO / "setup_skill.sh")], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_both_agents_get_independent_copies_and_backups(self):
        self.install()
        for agent in (".claude", ".codex"):
            target = self.root / agent / "skills/slack-notify"
            self.assertFalse(target.is_symlink())
            self.assertEqual((target / "SKILL.md").read_bytes(), (REPO / "skills/slack-notify/SKILL.md").read_bytes())
            self.assertTrue((target / "scripts/miraeping-doctor").is_file())
            (target / "local-note").write_text("preserve")
        self.install()
        for agent in (".claude", ".codex"):
            target = self.root / agent / "skills/slack-notify"
            self.assertFalse((target / "local-note").exists())
            backups = list((self.root / agent / "skill-backups").glob("slack-notify.*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "local-note").read_text(), "preserve")

    def test_existing_symlink_is_replaced_without_changing_referent(self):
        original = self.root / "original"
        original.mkdir()
        (original / "keep").write_text("safe")
        target = self.root / ".claude/skills/slack-notify"
        target.parent.mkdir(parents=True)
        target.symlink_to(original, target_is_directory=True)
        self.env["CODEX_HOME"] = str(self.root / "custom-codex")
        self.install()
        self.assertFalse(target.is_symlink())
        self.assertEqual((original / "keep").read_text(), "safe")
        self.assertTrue((self.root / "custom-codex/skills/slack-notify/SKILL.md").exists())

    def test_real_project_venv_detection_and_help(self):
        # Missing credentials guarantee that this subprocess cannot contact Slack.
        project = self.root / "project"
        project.mkdir()
        environment = project / ".venv"
        venv.EnvBuilder(with_pip=False).create(str(environment))
        result = subprocess.run(["bash", str(DOCTOR)], cwd=project, env=self.env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(str(environment / "bin/python3"), result.stdout)
        self.assertIn("SLACK_BOT_TOKEN missing", result.stdout)
        for flag in ("-h", "--help"):
            result = subprocess.run(["bash", str(DOCTOR), flag], env=self.env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0)
        for flag in ("--mode", "--online"):
            result = subprocess.run(["bash", str(DOCTOR), flag], env=self.env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
