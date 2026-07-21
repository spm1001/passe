"""Daemon lifecycle management — start, stop, status, pause, unpause.

Sits parallel to log_query.py in the DAG. Imports only stdlib.
The daemon itself is log_daemon.py — this module manages it as an
external process.

CDP flag forwarding: cli.py's global flag parser strips --cdp before
subcommands see their args. For lifecycle commands that spawn a
subprocess (where set_cdp_override doesn't carry over), the resolved
cdp_url is passed as a kwarg. See cli.py dispatch comment.
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

STATE_DIR = Path.home() / '.passe'
STATE_FILE = STATE_DIR / 'state.json'
PID_FILE = STATE_DIR / '.daemon.pid'
LOG_DIR = STATE_DIR / 'logs'
PAUSE_FILE = LOG_DIR / '.paused'

DAEMON_LOG_MAX = 1024 * 1024  # 1MB before rotation


# -- Helpers ---------------------------------------------------------------

def _read_state() -> dict | None:
    """Read state.json, returning None if missing or corrupt."""
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    """Check if a process is running.

    Returns True on PermissionError — the process exists, we just
    can't signal it (different user). Only ProcessLookupError means
    the PID is genuinely dead.
    """
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _remove_state_files():
    """Remove state.json and .daemon.pid. Single cleanup site."""
    STATE_FILE.unlink(missing_ok=True)
    PID_FILE.unlink(missing_ok=True)


def _clean_stale():
    """Remove state/pid files if the recorded PID is dead."""
    state = _read_state()
    if not state:
        return
    pid = state.get('pid')
    if pid and not _pid_alive(pid):
        print(f'Cleaning stale state (PID {pid} is dead)', file=sys.stderr)
        _remove_state_files()


def _check_chrome(cdp_url: str) -> dict | None:
    """Check Chrome is reachable at cdp_url. Returns version info or None."""
    try:
        url = cdp_url.rstrip('/') + '/json/version'
        with urllib.request.urlopen(url, timeout=3) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _rotate_daemon_log():
    """Rotate daemon.log if it exceeds DAEMON_LOG_MAX."""
    daemon_log = LOG_DIR / 'daemon.log'
    if daemon_log.exists() and daemon_log.stat().st_size > DAEMON_LOG_MAX:
        rotated = LOG_DIR / 'daemon.log.1'
        daemon_log.rename(rotated)


def _wait_for_startup(pid: int, timeout: float = 2.0) -> bool:
    """Wait for daemon to write state.json with matching PID."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.1)
        state = _read_state()
        if state and state.get('pid') == pid:
            return True
    return False


# -- Commands --------------------------------------------------------------

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

    # Scheme-less host:port → http:// (mirror of connection._normalize_endpoint;
    # this module stays stdlib-only, so no passe import)
    if cdp_url and '://' not in cdp_url:
        cdp_url = f'http://{cdp_url}'

    # Pre-flight: verify Chrome is reachable before spawning
    if cdp_url:
        info = _check_chrome(cdp_url)
        if not info:
            print(f'Chrome not reachable at {cdp_url}', file=sys.stderr)
            sys.exit(1)

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

    # Ensure log directory exists and rotate daemon.log if large
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _rotate_daemon_log()

    # Build daemon command
    cmd = [sys.executable, '-m', 'passe.log_daemon']
    if cdp_url:
        cmd += ['--cdp', cdp_url]

    # Redirect stdout/stderr to a daemon log file
    daemon_log = LOG_DIR / 'daemon.log'
    with open(daemon_log, 'a') as log_fh:
        proc = subprocess.Popen(
            cmd,
            start_new_session=True,
            stdout=log_fh,
            stderr=log_fh,
            stdin=subprocess.DEVNULL,
        )

    # Wait for state.json to confirm daemon started
    if not _wait_for_startup(proc.pid):
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

    pid = state['pid']

    # Send SIGTERM
    os.kill(pid, signal.SIGTERM)

    # Wait up to 5s for clean exit
    for _ in range(50):
        time.sleep(0.1)
        if not _pid_alive(pid):
            print(f'Daemon stopped (PID {pid})', file=sys.stderr)
            _remove_state_files()
            return

    # Force kill
    print(f'Daemon did not exit cleanly, sending SIGKILL', file=sys.stderr)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    _remove_state_files()
    print(f'Daemon killed (PID {pid})', file=sys.stderr)


def cmd_log_status(args: list[str]):
    """Show daemon and log status.

    Usage: passe log status [--json]
    """
    as_json = '--json' in args
    _clean_stale()

    state = _read_state()
    log_path = LOG_DIR / 'requests.jsonl'

    result = {}

    # Daemon status
    if state:
        pid = state.get('pid')
        alive = pid and _pid_alive(pid)
        result['daemon'] = 'running' if alive else 'dead'
        result['pid'] = pid
        result['cdp'] = state.get('cdp') or 'auto-discovered'
        result['started'] = state.get('started', 'unknown')
    else:
        result['daemon'] = 'not running'

    # Pause status
    result['paused'] = PAUSE_FILE.exists()

    # Log file stats
    if log_path.exists():
        size = log_path.stat().st_size
        result['log_file'] = str(log_path)
        result['log_size'] = size

        # Count lines, parse JSON only for first and last
        count = 0
        first_ts = None
        last_line = None
        with open(log_path) as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                count += 1
                if first_ts is None:
                    try:
                        first_ts = json.loads(stripped).get('ts', '')
                    except json.JSONDecodeError:
                        pass
                last_line = stripped

        result['requests'] = count
        if first_ts:
            result['oldest'] = first_ts
        if last_line:
            try:
                last_ts = json.loads(last_line).get('ts', '')
                if last_ts:
                    result['newest'] = last_ts
            except json.JSONDecodeError:
                pass
    else:
        result['requests'] = 0

    # Chrome reachable?
    if state and state.get('cdp'):
        info = _check_chrome(state['cdp'])
        result['chrome'] = info.get('Browser', 'reachable') if info else 'unreachable'

    if as_json:
        print(json.dumps(result))
        return

    # Human-readable output
    if 'pid' in result:
        print(f'Daemon:    {result["daemon"]} (PID {result["pid"]})')
        print(f'CDP:       {result["cdp"]}')
        print(f'Started:   {result["started"]}')
    else:
        print(f'Daemon:    {result["daemon"]}')

    print(f'Paused:    {"yes" if result["paused"] else "no"}')

    if 'log_file' in result:
        size = result['log_size']
        if size < 1024:
            size_str = f'{size}B'
        elif size < 1024 * 1024:
            size_str = f'{size / 1024:.1f}KB'
        else:
            size_str = f'{size / (1024 * 1024):.1f}MB'
        print(f'Log file:  {result["log_file"]} ({size_str})')
        print(f'Requests:  {result["requests"]:,}')
        if 'oldest' in result:
            print(f'Oldest:    {result["oldest"]}')
        if 'newest' in result:
            print(f'Newest:    {result["newest"]}')
    else:
        print(f'Log file:  none')

    if 'chrome' in result:
        print(f'Chrome:    {result["chrome"]}')


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
