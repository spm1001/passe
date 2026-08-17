"""Invocation-log adoption tests (erg-cilasa).

passe vendors the estate invocation-log shim as src/passe/_invlog.py —
canonical copy and the cross-estate conformance test live in
spm1001/harness-ergonomics (shim/invocation_log.py, tests/test_conformance.py).
These tests pin the adoption facts locally: every invocation appends exactly
one caller-stamped JSONL line — success and failure alike — and a broken log
path never breaks the CLI. All cases use Chrome-free subcommands.
"""
import json
import os
import subprocess
import sys


def _run_passe(*args, env):
    return subprocess.run(
        [sys.executable, "-m", "passe.cli", *args],
        capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL,
    )


def _env(tmp_path, **overrides):
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env["XDG_DATA_HOME"] = str(tmp_path / "xdg")
    env.update(overrides)
    return env


def _log_lines(tmp_path):
    log = tmp_path / "xdg" / "passe" / "invocations.jsonl"
    assert log.exists(), f"no invocation log at {log}"
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


def test_ok_invocation_logs_one_line(tmp_path):
    env = _env(tmp_path, CLAUDECODE="1", CLAUDE_CODE_ENTRYPOINT="cli")
    result = _run_passe("devices", env=env)
    assert result.returncode == 0, result.stderr
    (line,) = _log_lines(tmp_path)
    assert line["tool"] == "passe"
    assert line["subcommand"] == "devices"
    assert line["argv"] == ["devices"]
    assert line["parsed"]["rest"] == []
    assert line["outcome"] == "ok" and line["exit_code"] == 0
    assert line["caller"] == "model" and line["caller_detail"] == "cli"
    assert line["duration_ms"] >= 0
    assert line["version"]


def test_global_flags_land_in_parsed(tmp_path):
    """--cdp is extracted pre-dispatch and recorded; explain needs no Chrome."""
    env = _env(tmp_path, CLAUDECODE="1")
    result = _run_passe("--cdp", "http://localhost:9999", "explain",
                        "-c", "goto https://example.com", env=env)
    assert result.returncode == 0, result.stderr
    (line,) = _log_lines(tmp_path)
    assert line["subcommand"] == "explain"
    assert line["parsed"]["cdp"] == "http://localhost:9999"
    assert line["argv"][0] == "--cdp"  # raw argv keeps the pre-extraction shape


def test_unknown_subcommand_logged_as_error(tmp_path):
    env = _env(tmp_path, CLAUDECODE="1")
    result = _run_passe("definitely-not-a-subcommand", env=env)
    assert result.returncode == 1
    (line,) = _log_lines(tmp_path)
    assert line["outcome"] == "error" and line["exit_code"] == 1
    assert line["subcommand"] == "definitely-not-a-subcommand"
    assert line["argv"] == ["definitely-not-a-subcommand"]


def test_no_args_usage_failure_still_logged(tmp_path):
    """Dies before any parsing — subcommand/parsed null, raw argv the evidence."""
    env = _env(tmp_path, CLAUDECODE="1")
    result = _run_passe(env=env)
    assert result.returncode == 1
    (line,) = _log_lines(tmp_path)
    assert line["outcome"] == "error"
    assert line["subcommand"] is None and line["parsed"] is None
    assert line["argv"] == []


def test_robot_stamp_without_cc_env_or_tty(tmp_path):
    env = _env(tmp_path)
    result = _run_passe("devices", env=env)
    assert result.returncode == 0
    (line,) = _log_lines(tmp_path)
    assert line["caller"] == "robot"
    assert line["caller_detail"]


def test_unwritable_log_path_never_breaks_cli(tmp_path):
    blocker = tmp_path / "xdg"
    blocker.write_text("occupied")
    env = dict(os.environ, XDG_DATA_HOME=str(blocker), CLAUDECODE="1")
    result = _run_passe("devices", env=env)
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
