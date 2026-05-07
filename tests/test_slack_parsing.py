"""Parsing-function unit tests — no env vars, no network."""
import pytest

from miraeping.slack_server import (
    _ascii_table,
    _parse_available_nodes_from_qq,
    _parse_gpu_rows,
    _parse_qhost_ncpu,
    _parse_qw_count,
    _parse_qw_counts_by_slots,
    _parse_user_map_env,
)


# ── user map parsing ───────────────────────────────────────────────────────

def test_parse_user_map_valid(monkeypatch):
    monkeypatch.setenv("SLACK_QSTAT_USER_MAP", "U01:alice,U02:bob")
    assert _parse_user_map_env() == {"U01": "alice", "U02": "bob"}


def test_parse_user_map_empty(monkeypatch):
    monkeypatch.delenv("SLACK_QSTAT_USER_MAP", raising=False)
    assert _parse_user_map_env() == {}


def test_parse_user_map_whitespace_tolerance(monkeypatch):
    monkeypatch.setenv("SLACK_QSTAT_USER_MAP", " U01 : alice , U02 : bob ")
    result = _parse_user_map_env()
    assert result.get("U01") == "alice"
    assert result.get("U02") == "bob"


def test_parse_user_map_skips_entry_without_colon(monkeypatch):
    monkeypatch.setenv("SLACK_QSTAT_USER_MAP", "U01:alice,badentry,U02:bob")
    result = _parse_user_map_env()
    assert "U01" in result
    assert "U02" in result
    assert len(result) == 2


def test_parse_user_map_rejects_path_traversal(monkeypatch):
    monkeypatch.setenv("SLACK_QSTAT_USER_MAP", "U01:../etc/passwd")
    result = _parse_user_map_env()
    assert result == {}


def test_parse_user_map_rejects_shell_special_chars(monkeypatch):
    monkeypatch.setenv("SLACK_QSTAT_USER_MAP", "U01:alice;rm -rf /")
    result = _parse_user_map_env()
    assert result == {}


# ── qhost parsing ──────────────────────────────────────────────────────────

QHOST_SAMPLE = """\
HOSTNAME      ARCH         NCPU NSOC NCOR NTHR  LOAD  MEMTOT  MEMUSE  SWAPTO  SWAPUS
global                        -    -    -    -     -       -       -       -       -
n01           lx-amd64       48    2   24   48  0.01   251.5G   12.3G    0.0G    0.0G
n02           lx-amd64       64    2   32   64  0.02   503.0G   80.1G    0.0G    0.0G
n03           lx-amd64       48    2   24   48  0.50   251.5G   30.0G    0.0G    0.0G
"""

def test_parse_qhost_ncpu():
    result = _parse_qhost_ncpu(QHOST_SAMPLE)
    assert result == {"n01": 48, "n02": 64, "n03": 48}


def test_parse_qhost_ncpu_empty():
    assert _parse_qhost_ncpu("") == {}


def test_parse_qhost_ncpu_ignores_global_row():
    result = _parse_qhost_ncpu(QHOST_SAMPLE)
    assert "global" not in result


def test_parse_qhost_ncpu_ignores_non_node_hosts():
    text = "login01  lx-amd64  8  ...\nn01  lx-amd64  48  ..."
    result = _parse_qhost_ncpu(text)
    assert "login01" not in result
    assert result.get("n01") == 48


# ── qq / available-nodes parsing ──────────────────────────────────────────

QQ_SAMPLE = """\
queue  total  used  available
all.q  96     72    24
3 nodes available: n01 n02 n03
"""

def test_parse_available_nodes_from_qq():
    assert _parse_available_nodes_from_qq(QQ_SAMPLE) == ["n01", "n02", "n03"]


def test_parse_available_nodes_from_qq_no_match():
    assert _parse_available_nodes_from_qq("nothing relevant here") == []


def test_parse_available_nodes_from_qq_zero_nodes():
    text = "0 nodes available: "
    assert _parse_available_nodes_from_qq(text) == []


def test_parse_available_nodes_from_qq_empty():
    assert _parse_available_nodes_from_qq("") == []


# ── qstat / qw count parsing ───────────────────────────────────────────────

QSTAT_SAMPLE = """\
job-ID  prior   name       user         state submit/start at
----------------------------------------------------------------------
1001    0.55500 train_run  alice        r     01/01/2024 09:00:00
1002    0.55500 prep_data  alice        qw    01/01/2024 08:50:00
1003    0.55500 val_run    bob          qw    01/01/2024 08:55:00
1004    0.55500 cleanup    carol        t     01/01/2024 09:01:00
"""

def test_parse_qw_count():
    assert _parse_qw_count(QSTAT_SAMPLE) == 2


def test_parse_qw_count_empty():
    assert _parse_qw_count("") == 0


def test_parse_qw_count_no_qw_jobs():
    assert _parse_qw_count("1001  0.5  train  alice  r  ...") == 0


QSTAT_SLOTS_SAMPLE = """\
job-ID  prior  name  user  state  date  queue  slots
1001    0.5    a     u     qw     d     q      48
1002    0.5    b     u     qw     d     q      64
1003    0.5    c     u     qw     d     q      48
1004    0.5    d     u     qw     d     q      32
1005    0.5    e     u     r      d     q      48
"""

def test_parse_qw_counts_by_slots():
    q48, q64, qother = _parse_qw_counts_by_slots(QSTAT_SLOTS_SAMPLE)
    assert q48 == 2
    assert q64 == 1
    assert qother == 1   # the 32-slot job


def test_parse_qw_counts_by_slots_empty():
    assert _parse_qw_counts_by_slots("") == (0, 0, 0)


# ── GPU / nvidia-smi parsing ───────────────────────────────────────────────

NVIDIA_SMI_SAMPLE = """\
0, NVIDIA RTX 6000 Ada Generation, 4096, 24576, 23
1, NVIDIA RTX A6000, 8192, 49152, 67
2, NVIDIA RTX A6000, 0, 49152, 0
"""

def test_parse_gpu_rows():
    rows = _parse_gpu_rows(NVIDIA_SMI_SAMPLE)
    assert rows == [
        ("0", "NVIDIA RTX 6000 Ada Generation", "4096", "24576", "23"),
        ("1", "NVIDIA RTX A6000", "8192", "49152", "67"),
        ("2", "NVIDIA RTX A6000", "0", "49152", "0"),
    ]


def test_parse_gpu_rows_ignores_header_lines():
    text = "index, name, memory.used, memory.total, utilization\n0, NVIDIA A100, 100, 200, 50\n"
    rows = _parse_gpu_rows(text)
    assert rows == [("0", "NVIDIA A100", "100", "200", "50")]


def test_parse_gpu_rows_empty():
    assert _parse_gpu_rows("") == []


# ── ascii table ────────────────────────────────────────────────────────────

def test_ascii_table_structure():
    out = _ascii_table(["Name", "Val"], [["alice", "42"], ["bob", "100"]])
    assert out.startswith("+")
    assert out.endswith("+")
    assert "Name" in out
    assert "alice" in out
    assert "100" in out


def test_ascii_table_column_widths():
    out = _ascii_table(["X"], [["short"], ["very_long_value"]])
    # All rows should be padded to the same width
    lines = out.splitlines()
    widths = {len(line) for line in lines}
    assert len(widths) == 1   # every line same length


def test_ascii_table_single_row():
    out = _ascii_table(["Col"], [["val"]])
    assert "Col" in out
    assert "val" in out
