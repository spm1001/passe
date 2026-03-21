"""Tests for log_lifecycle — start, stop, status, pause, unpause."""

import json
import os
import signal
from unittest.mock import patch, MagicMock

import pytest

from passe.log_lifecycle import (
    cmd_log_start, cmd_log_stop, cmd_log_status,
    cmd_log_pause, cmd_log_unpause,
    _read_state, _pid_alive, _clean_stale,
    STATE_FILE, PID_FILE, LOG_DIR, PAUSE_FILE,
)


@pytest.fixture
def passe_home(tmp_path, monkeypatch):
    """Redirect all state/log paths to a temp directory."""
    import passe.log_lifecycle as mod
    monkeypatch.setattr(mod, 'STATE_DIR', tmp_path)
    monkeypatch.setattr(mod, 'STATE_FILE', tmp_path / 'state.json')
    monkeypatch.setattr(mod, 'PID_FILE', tmp_path / '.daemon.pid')
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()
    monkeypatch.setattr(mod, 'LOG_DIR', log_dir)
    monkeypatch.setattr(mod, 'PAUSE_FILE', log_dir / '.paused')
    return tmp_path


class TestReadState:
    def test_missing_file(self, passe_home):
        assert _read_state() is None

    def test_valid_state(self, passe_home):
        state = {'pid': 12345, 'cdp': 'http://localhost:9222',
                 'started': '2026-01-01T00:00:00Z'}
        (passe_home / 'state.json').write_text(json.dumps(state))
        assert _read_state() == state

    def test_corrupt_json(self, passe_home):
        (passe_home / 'state.json').write_text('not json')
        assert _read_state() is None


class TestPidAlive:
    def test_current_process(self):
        assert _pid_alive(os.getpid())

    def test_dead_pid(self):
        assert not _pid_alive(99999999)


class TestCleanStale:
    def test_cleans_dead_pid(self, passe_home):
        state = {'pid': 99999999, 'cdp': 'http://localhost:9222'}
        state_file = passe_home / 'state.json'
        pid_file = passe_home / '.daemon.pid'
        state_file.write_text(json.dumps(state))
        pid_file.write_text('99999999')

        _clean_stale()

        assert not state_file.exists()
        assert not pid_file.exists()

    def test_keeps_live_pid(self, passe_home):
        state = {'pid': os.getpid(), 'cdp': 'http://localhost:9222'}
        state_file = passe_home / 'state.json'
        state_file.write_text(json.dumps(state))

        _clean_stale()

        assert state_file.exists()


class TestCmdLogStart:
    def test_starts_daemon(self, passe_home, monkeypatch):
        monkeypatch.delenv('PASSE_CDP', raising=False)
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_proc.poll.return_value = None

        state_file = passe_home / 'state.json'

        def fake_popen(*args, **kwargs):
            # Simulate daemon writing state.json
            state_file.write_text(json.dumps({
                'pid': 42, 'cdp': 'http://localhost:9222',
                'started': '2026-01-01T00:00:00Z',
            }))
            return mock_proc

        with patch('passe.log_lifecycle.subprocess.Popen', side_effect=fake_popen) as mock_p:
            cmd_log_start([], cdp_url='http://localhost:9222')

        call_args = mock_p.call_args
        cmd = call_args[0][0]
        assert '-m' in cmd
        assert 'passe.log_daemon' in cmd
        assert '--cdp' in cmd
        assert 'http://localhost:9222' in cmd
        assert call_args[1]['start_new_session'] is True

    def test_refuses_double_start(self, passe_home, monkeypatch):
        state = {'pid': os.getpid(), 'cdp': 'http://localhost:9222'}
        (passe_home / 'state.json').write_text(json.dumps(state))

        with pytest.raises(SystemExit, match='1'):
            cmd_log_start([])

    def test_cleans_stale_before_start(self, passe_home, monkeypatch):
        monkeypatch.delenv('PASSE_CDP', raising=False)
        state = {'pid': 99999999, 'cdp': 'http://localhost:9222'}
        state_file = passe_home / 'state.json'
        state_file.write_text(json.dumps(state))

        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_proc.poll.return_value = None

        def fake_popen(*args, **kwargs):
            state_file.write_text(json.dumps({
                'pid': 42, 'cdp': 'http://localhost:9222',
                'started': '2026-01-01T00:00:00Z',
            }))
            return mock_proc

        with patch('passe.log_lifecycle.subprocess.Popen', side_effect=fake_popen):
            cmd_log_start([], cdp_url='http://localhost:9222')


class TestCmdLogStop:
    def test_stops_running_daemon(self, passe_home, monkeypatch):
        state_file = passe_home / 'state.json'
        pid_file = passe_home / '.daemon.pid'
        state = {'pid': 12345, 'cdp': 'http://localhost:9222'}
        state_file.write_text(json.dumps(state))
        pid_file.write_text('12345')

        kill_calls = []

        def fake_kill(pid, sig):
            kill_calls.append((pid, sig))
            if sig == 0 and len([c for c in kill_calls if c[1] == 0]) > 2:
                raise ProcessLookupError

        def fake_alive(pid):
            # Dead after first check (SIGTERM sent)
            return len(kill_calls) < 2

        with patch('passe.log_lifecycle.os.kill', side_effect=fake_kill), \
             patch('passe.log_lifecycle._pid_alive', side_effect=fake_alive):
            cmd_log_stop([])

        assert any(sig == signal.SIGTERM for _, sig in kill_calls)

    def test_no_daemon_running(self, passe_home):
        with pytest.raises(SystemExit, match='1'):
            cmd_log_stop([])


class TestCmdLogStatus:
    def test_not_running(self, passe_home, capsys):
        cmd_log_status([])
        out = capsys.readouterr().out
        assert 'not running' in out

    def test_running_with_log(self, passe_home, capsys):
        state = {'pid': os.getpid(), 'cdp': 'http://localhost:9222',
                 'started': '2026-01-01T00:00:00Z'}
        (passe_home / 'state.json').write_text(json.dumps(state))

        log_file = passe_home / 'logs' / 'requests.jsonl'
        log_file.write_text(
            json.dumps({'id': 'r1', 'ts': '2026-01-01T00:00:01Z',
                        'method': 'GET', 'url': 'https://example.com'}) + '\n'
            + json.dumps({'id': 'r2', 'ts': '2026-01-01T00:00:02Z',
                          'method': 'POST', 'url': 'https://api.example.com'}) + '\n'
        )

        with patch('urllib.request.urlopen',
                    side_effect=Exception('no chrome')):
            cmd_log_status([])

        out = capsys.readouterr().out
        assert 'running' in out
        assert '2' in out  # 2 requests
        assert 'unreachable' in out


class TestPauseUnpause:
    def test_pause_creates_file(self, passe_home):
        cmd_log_pause([])
        assert (passe_home / 'logs' / '.paused').exists()

    def test_unpause_removes_file(self, passe_home):
        (passe_home / 'logs' / '.paused').touch()
        cmd_log_unpause([])
        assert not (passe_home / 'logs' / '.paused').exists()

    def test_double_pause_harmless(self, passe_home, capsys):
        cmd_log_pause([])
        cmd_log_pause([])
        assert 'Already paused' in capsys.readouterr().err

    def test_unpause_when_not_paused(self, passe_home, capsys):
        cmd_log_unpause([])
        assert 'Not paused' in capsys.readouterr().err
