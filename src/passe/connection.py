"""Chrome connection management — discovery, launch, and CDP WebSocket setup."""

import contextlib
import json
import os
import sys
import time
import urllib.request

import websockets

from passe.client import CDPClient


_cdp_override: str | None = None


def set_cdp_override(url: str | None):
    """Set an explicit CDP base URL (from --cdp flag). Called by main()."""
    global _cdp_override
    _cdp_override = url



def _cdp_base_url():
    """Get CDP base URL from --cdp flag, PASSE_CDP env var, or default to localhost:9222."""
    return _cdp_override or os.environ.get('PASSE_CDP', '').strip() or 'http://localhost:9222'


def _chrome_running() -> bool:
    try:
        with urllib.request.urlopen(f'{_cdp_base_url()}/json/version', timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _find_chrome() -> str:
    """Find a Chrome/Chromium executable for the current platform."""
    import shutil
    if sys.platform == 'darwin':
        candidates = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
    else:
        # Linux: try common names in PATH order
        candidates = ['chromium-browser', 'chromium', 'google-chrome-stable', 'google-chrome']
    for candidate in candidates:
        if '/' in candidate:
            # Absolute path — check directly
            if os.path.isfile(candidate):
                return candidate
        else:
            found = shutil.which(candidate)
            if found:
                return found
    return None


def _start_chrome(port=9222, headless=False):
    """Launch Chrome with debug profile if not running. Only works locally.

    Returns the Popen process if headless (caller owns teardown), else None.
    """
    import subprocess
    from pathlib import Path
    chrome_path = _find_chrome()
    if not chrome_path:
        print(
            "No Chrome/Chromium found.\n"
            f"Install Chrome or set PASSE_CDP to an existing instance.",
            file=sys.stderr,
        )
        sys.exit(1)
    cmd = [
        chrome_path,
        f'--remote-debugging-port={port}',
        '--user-data-dir=' + str(Path.home() / '.chrome-passe'),
        '--no-default-browser-check',
    ]
    if headless:
        cmd.append('--headless=new')
    label = 'headless Chrome' if headless else 'Chrome Passe'
    print(f"[passe] starting {label} ({os.path.basename(chrome_path)})...", file=sys.stderr)
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        print(
            f"Chrome not found at {chrome_path}\n"
            f"Start Chrome manually with --remote-debugging-port={port} "
            f"or set PASSE_CDP to an existing Chrome instance.",
            file=sys.stderr,
        )
        sys.exit(1)
    for _ in range(30):
        if _chrome_running():
            print(f"[passe] {label} started (pid {proc.pid}).", file=sys.stderr)
            return proc if headless else None
        time.sleep(0.5)
    print(f"[passe] failed to start {label}.", file=sys.stderr)
    sys.exit(1)


def _is_loopback(url: str) -> bool:
    """Check if a CDP URL points to a loopback address."""
    from urllib.parse import urlparse
    import socket
    hostname = urlparse(url).hostname or ''
    if hostname in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
        return True
    try:
        addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        return all(
            ai[4][0].startswith('127.') or ai[4][0] == '::1'
            for ai in addr_info
        )
    except socket.gaierror:
        return False


def discover_chrome(cdp_url: str | None = None) -> tuple[str, dict]:
    """Find Chrome and return (ws_url, browser_info).

    Checks cdp_url arg → --cdp override → PASSE_CDP env → localhost:9222.
    Rewrites ws://localhost WebSocket URLs for remote Chrome.
    Does NOT auto-launch Chrome — raises ConnectionError if unreachable.

    Returns:
        ws_url: WebSocket URL for the browser-level debugger endpoint.
        info: dict with 'cdp' (base URL), 'browser' (version string),
              'remote' (bool).
    """
    base_url = cdp_url or _cdp_base_url()
    is_remote = not _is_loopback(base_url)

    try:
        with urllib.request.urlopen(f'{base_url}/json/version', timeout=5) as resp:
            version_info = json.loads(resp.read())
    except Exception as exc:
        raise ConnectionError(
            f"Cannot connect to Chrome at {base_url}: {exc}"
        ) from exc

    ws_url = version_info['webSocketDebuggerUrl']
    browser_str = version_info.get('Browser', 'unknown')

    # Rewrite WS URL for remote Chrome — Chrome returns ws://localhost:...
    if is_remote:
        from urllib.parse import urlparse
        parsed_base = urlparse(base_url)
        parsed_ws = urlparse(ws_url)
        ws_url = f'ws://{parsed_base.netloc}{parsed_ws.path}'

    info = {'cdp': base_url, 'browser': browser_str, 'remote': is_remote}
    return ws_url, info


@contextlib.asynccontextmanager
async def connect(port=9222):
    """Connect to Chrome, yield (CDPClient, info), clean up on exit.

    info dict contains: cdp (base URL), browser (version string), remote (bool),
    and optionally _process (Popen) if we auto-launched headless Chrome.
    """
    base_url = _cdp_base_url()
    is_remote = not _is_loopback(base_url)
    cdp_explicit = _cdp_override is not None or bool(os.environ.get('PASSE_CDP', '').strip())
    chrome_proc = None
    if not _chrome_running():
        if is_remote:
            print(
                f"Cannot connect to Chrome at {base_url}\n"
                f"Check that Chrome is running with --remote-debugging-port "
                f"or set PASSE_CDP to the correct endpoint.",
                file=sys.stderr,
            )
            sys.exit(1)
        # Auto-launch: headless when no explicit CDP target (passe owns it),
        # GUI when user explicitly pointed at localhost (they want Chrome Passe)
        headless = not cdp_explicit
        chrome_proc = _start_chrome(port, headless=headless)

    ws_url, disc_info = discover_chrome()
    browser_str = disc_info['browser']

    # Log which Chrome we connected to
    if is_remote:
        from urllib.parse import urlparse
        parsed_base = urlparse(base_url)
        # Prominent note for remote Chrome — impossible to miss
        print(f'[passe] remote Chrome: {parsed_base.hostname}:{parsed_base.port} ({browser_str})',
              file=sys.stderr)
    elif chrome_proc is not None:
        print(f'[passe] Chrome: {browser_str} (bare profile — no auth cookies)',
              file=sys.stderr)
        print('[passe] hint: for authenticated browsing, start Chrome with '
              'your profile first', file=sys.stderr)
    else:
        print(f'[passe] Chrome: {browser_str}', file=sys.stderr)

    ws = await websockets.connect(ws_url, max_size=50 * 1024 * 1024)
    client = CDPClient(ws)
    client._cdp_http = base_url
    await client.start()
    conn_info = {
        'cdp': base_url, 'browser': browser_str, 'remote': is_remote,
        '_process': chrome_proc,
    }
    try:
        yield client, conn_info
    finally:
        await client.stop()
        await ws.close()
        _teardown_chrome(conn_info)


def _teardown_chrome(conn_info: dict):
    """Kill auto-launched headless Chrome if we own it."""
    proc = conn_info.get('_process')
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
