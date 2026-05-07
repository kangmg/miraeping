import miraeping.slack_server as ss


def test_parse_submission_dir_extracts_workdir():
    raw = """
==============================================================
sge_o_workdir:           /home/user/project/run1
hard resource_list:      h_rt=24:00:00
""".strip()
    assert ss._parse_submission_dir(raw) == "/home/user/project/run1"


def test_parse_submission_dir_returns_dash_when_missing():
    raw = "job_name: test_job\nowner: alice"
    assert ss._parse_submission_dir(raw) == "-"


def test_build_qwd_response_formats_rows(monkeypatch):
    def fake_resolve(_slack_user_id: str):
        return "alice"

    def fake_run(args, timeout=10.0):
        if args == ["qstat", "-u", "alice"]:
            return """
job-ID  prior   name       user         state submit/start at
---------------------------------------------------------------------
123     0.55500 job_alpha  alice        r     01/01/2026 09:00:00
124     0.55500 job_beta   alice        qw    01/01/2026 09:05:00
""".strip()
        if args == ["qstat", "-j", "123"]:
            return "sge_o_workdir: /work/alice/a"
        if args == ["qstat", "-j", "124"]:
            return "sge_o_workdir: /work/alice/b"
        raise AssertionError(f"unexpected args: {args}")

    monkeypatch.setattr(ss, "_resolve_qstat_target_user", fake_resolve)
    monkeypatch.setattr(ss, "_run_command", fake_run)

    out = ss._build_qwd_response("U01")
    assert "target user: alice" in out
    assert "JOB_ID" in out and "SUBMISSION_DIR" in out
    assert "123" in out and "/work/alice/a" in out
    assert "124" in out and "/work/alice/b" in out


def test_build_qwd_response_unregistered_user(monkeypatch):
    monkeypatch.setattr(ss, "_resolve_qstat_target_user", lambda _uid: None)
    out = ss._build_qwd_response("U_UNKNOWN")
    assert "not registered yet" in out


def test_build_command_response_routes_qwd(monkeypatch):
    monkeypatch.setattr(ss, "_build_qwd_response", lambda uid: f"qwd:{uid}")
    out = ss._build_command_response("/qwd", "U123ABC")
    assert out == "qwd:U123ABC"
