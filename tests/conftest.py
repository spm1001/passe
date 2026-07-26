"""Shared fixtures: a genuinely-local throwaway Chrome for integration tests.

Integration tests must never assume localhost:9222 is a *local* Chrome — on
tube it's an ssh tunnel to kube's remote browser, which can't reach a test
server on this machine's 127.0.0.1 (passe-nuzege). Tests that need a real
browser request `local_chrome`: one headless Chrome per test session, on an
ephemeral port, with its own scratch profile, killed at session end.
"""

import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

from passe.connection import _find_chrome


def _launch_throwaway_chrome(user_data_dir: str):
    """Launch headless Chrome on an OS-assigned port; return (proc, endpoint).

    --remote-debugging-port=0 makes Chrome pick a free port and write it to
    <user-data-dir>/DevToolsActivePort — race-free, unlike bind-then-release
    port guessing.
    """
    chrome_path = _find_chrome()
    cmd = [
        chrome_path,
        '--headless=new',
        '--remote-debugging-port=0',
        f'--user-data-dir={user_data_dir}',
        '--no-first-run',
        '--no-default-browser-check',
        # This Chrome only ever browses this machine's own test servers from
        # a scratch profile. Without it, launch SIGABRTs on CI runners
        # (Ubuntu 24.04 AppArmor blocks unprivileged user namespaces).
        '--no-sandbox',
    ]
    stderr_path = Path(user_data_dir) / 'chrome-stderr.log'
    with open(stderr_path, 'wb') as stderr_f:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=stderr_f)

    def _stderr_tail():
        try:
            return stderr_path.read_text(errors='replace')[-800:]
        except OSError:
            return '<unreadable>'

    port_file = Path(user_data_dir) / 'DevToolsActivePort'
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f'throwaway Chrome ({chrome_path}) exited immediately '
                f'(code {proc.returncode}); stderr tail:\n{_stderr_tail()}')
        try:
            port = int(port_file.read_text().splitlines()[0])
            endpoint = f'http://127.0.0.1:{port}'
            with urllib.request.urlopen(f'{endpoint}/json/version', timeout=2) as r:
                if r.status == 200:
                    return proc, endpoint
        except Exception:
            pass
        time.sleep(0.25)
    proc.kill()
    raise RuntimeError(
        f'throwaway Chrome ({chrome_path}) never became reachable within '
        f'30s; stderr tail:\n{_stderr_tail()}')


@pytest.fixture(scope='session')
def _throwaway_chrome_endpoint():
    """One throwaway Chrome for the whole session. Skips if no binary exists."""
    if _find_chrome() is None:
        pytest.skip('No Chrome/Chromium binary on this machine')
    profile_dir = tempfile.mkdtemp(prefix='passe-test-chrome-')
    proc, endpoint = _launch_throwaway_chrome(profile_dir)
    yield endpoint
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    shutil.rmtree(profile_dir, ignore_errors=True)


@pytest.fixture
def local_chrome(_throwaway_chrome_endpoint, monkeypatch):
    """Point connect()/discover_chrome() at the throwaway Chrome; yield its endpoint.

    Clears any --cdp override so the env var is the resolved endpoint
    regardless of what earlier tests did to module state.
    """
    from passe import connection
    monkeypatch.setattr(connection, '_cdp_override', None)
    monkeypatch.setenv('PASSE_CDP', _throwaway_chrome_endpoint)
    yield _throwaway_chrome_endpoint
