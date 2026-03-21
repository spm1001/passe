"""Daemon lifecycle management — start, stop, status, pause, unpause.

Sits parallel to log_query.py in the DAG. Imports only stdlib + connection
(for discover_chrome validation). The daemon itself is log_daemon.py — this
module manages it as an external process.
"""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path.home() / '.passe'
STATE_FILE = STATE_DIR / 'state.json'
PID_FILE = STATE_DIR / '.daemon.pid'
LOG_DIR = STATE_DIR / 'logs'
PAUSE_FILE = LOG_DIR / '.paused'


def _read_state() -> dict | None:
    """Read state.json, returning None if missing or corrupt."""
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    """Check if a process is running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _clean_stale():
    """Remove state/pid files if the recorded PID is dead."""
    state = _read_state()
    if not state:
        return
    pid = state.get('pid')
    if pid and not _pid_alive(pid):
        print(f'Cleaning stale state (PID {pid} is dead)', file=sys.stderr)
        STATE_FILE.unlink(missing_ok=True)
        PID_FILE.unlink(missing_ok=True)


def cmd_log_start(args: list[str], cdp_url: str | None = None):
    """Launch the daemon as a detached subprocess.

    Usage: passe log start [--cdp URL]

    cdp_url can be passed from the global --cdp flag (cli.py strips it
    before we see args). Falls back to PASSE_CDP env.
    """
    # Local --cdp overrides global
    if '--cdp' in args:
        idx = args.index('--cdp')
        if idx + 1 < len(args):
            cdp_url = args[idx + 1]
        else:
            print('passe log start: --cdp requires a URL', file=sys.stderr)
            sys.exit(1)

    # Fall back to PASSE_CDP env
    if not cdp_url:
        cdp_url = os.environ.get('PASSE_CDP')

    # Clean stale state before checking
    _clean_stale()

    # Check if already running
    state = _read_state()
    if state:
        pid = state.get('pid')
        if pid and _pid_alive(pid):
            print(f'Daemon already running (PID {pid}, CDP {state.get("cdp")})',
                  file=sys.stderr)
            sys.exit(1)

    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Build daemon command
    cmd = [sys.executable, '-m', 'passe.log_daemon']
    if cdp_url:
        cmd += ['--cdp', cdp_url]

    # Redirect stdout/stderr to a daemon log file
    daemon_log = LOG_DIR / 'daemon.log'
    log_fh = open(daemon_log, 'a')

    proc = subprocess.Popen(
        cmd,
        start_new_session=True,
        stdout=log_fh,
        stderr=log_fh,
        stdin=subprocess.DEVNULL,
    )
    log_fh.close()

    # Wait briefly for state.json to appear (daemon writes it on startup)
    for _ in range(20):
        time.sleep(0.1)
        state = _read_state()
        if state and state.get('pid') == proc.pid:
            break
    else:
        # Check if the process died immediately
        if proc.poll() is not None:
            print(f'Daemon exited immediately (code {proc.returncode}). '
                  f'Check {daemon_log}', file=sys.stderr)
            sys.exit(1)

    cdp_display = cdp_url or 'auto-discovered'
    print(f'Daemon started (PID {proc.pid}, CDP {cdp_display})',
          file=sys.stderr)
    print(f'Log: {daemon_log}', file=sys.stderr)


def cmd_log_stop(args: list[str]):
    """Stop a running daemon.

    Usage: passe log stop
    """
    _clean_stale()

    state = _read_state()
    if not state:
        print('No daemon running', file=sys.stderr)
        sys.exit(1)

    pid = state.get('pid')
    if not pid or not _pid_alive(pid):
        print('No daemon running (stale state cleaned)', file=sys.stderr)
        STATE_FILE.unlink(missing_ok=True)
        PID_FILE.unlink(missing_ok=True)
        sys.exit(1)

    # Send SIGTERM
    os.kill(pid, signal.SIGTERM)

    # Wait up to 5s for clean exit
    for _ in range(50):
        time.sleep(0.1)
        if not _pid_alive(pid):
            print(f'Daemon stopped (PID {pid})', file=sys.stderr)
            # Daemon cleans up its own state files on exit, but
            # if they linger, clean them
            STATE_FILE.unlink(missing_ok=True)
            PID_FILE.unlink(missing_ok=True)
            return

    # Force kill
    print(f'Daemon did not exit cleanly, sending SIGKILL', file=sys.stderr)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    STATE_FILE.unlink(missing_ok=True)
    PID_FILE.unlink(missing_ok=True)
    print(f'Daemon killed (PID {pid})', file=sys.stderr)


def cmd_log_status(args: list[str]):
    """Show daemon and log status.

    Usage: passe log status
    """
    _clean_stale()

    state = _read_state()
    log_path = LOG_DIR / 'requests.jsonl'

    # Daemon status
    if state:
        pid = state.get('pid')
        alive = pid and _pid_alive(pid)
        status = 'running' if alive else 'dead'
        print(f'Daemon:    {status} (PID {pid})')
        print(f'CDP:       {state.get("cdp") or "auto-discovered"}')
        print(f'Started:   {state.get("started", "unknown")}')
    else:
        print('Daemon:    not running')

    # Pause status
    if PAUSE_FILE.exists():
        print(f'Paused:    yes')
    else:
        print(f'Paused:    no')

    # Log file stats
    if log_path.exists():
        size = log_path.stat().st_size
        if size < 1024:
            size_str = f'{size}B'
        elif size < 1024 * 1024:
            size_str = f'{size / 1024:.1f}KB'
        else:
            size_str = f'{size / (1024 * 1024):.1f}MB'
        print(f'Log file:  {log_path} ({size_str})')

        # Count lines and get timestamps without loading everything into memory
        count = 0
        first_ts = None
        last_ts = None
        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                count += 1
                try:
                    entry = json.loads(line)
                    ts = entry.get('ts', '')
                    if ts:
                        if first_ts is None:
                            first_ts = ts
                        last_ts = ts
                except json.JSONDecodeError:
                    pass

        print(f'Requests:  {count:,}')
        if first_ts:
            print(f'Oldest:    {first_ts}')
        if last_ts:
            print(f'Newest:    {last_ts}')
    else:
        print(f'Log file:  none')

    # Chrome reachable?
    if state and state.get('cdp'):
        try:
            import urllib.request
            url = state['cdp'].rstrip('/') + '/json/version'
            with urllib.request.urlopen(url, timeout=3) as resp:
                info = json.loads(resp.read())
                print(f'Chrome:    {info.get("Browser", "reachable")}')
        except Exception:
            print(f'Chrome:    unreachable')


def cmd_log_pause(args: list[str]):
    """Pause log capture (daemon keeps running, stops writing).

    Usage: passe log pause
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if PAUSE_FILE.exists():
        print('Already paused', file=sys.stderr)
        return
    PAUSE_FILE.touch()
    print('Capture paused', file=sys.stderr)


def cmd_log_unpause(args: list[str]):
    """Resume log capture.

    Usage: passe log unpause
    """
    if not PAUSE_FILE.exists():
        print('Not paused', file=sys.stderr)
        return
    PAUSE_FILE.unlink()
    print('Capture resumed', file=sys.stderr)
