"""Integration tests for log_daemon against real Chrome.

Requires headless Chrome on localhost:9222. Skipped otherwise.
Exercises the full WebSocket send/receive cycle that unit tests cannot
cover — the class of bugs where receiver/sender ordering matters.
"""

import asyncio
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen

import pytest

from passe.log_daemon import LogDaemon, DaemonState
from passe.connection import connect
from passe.verbs import do_navigate


def _chrome_available():
    try:
        with urlopen('http://localhost:9222/json/version', timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _chrome_available(),
    reason='Chrome not running on localhost:9222',
)


# ---------------------------------------------------------------------------
# HTTP test server
# ---------------------------------------------------------------------------

FETCH_PAGE = """\
<!DOCTYPE html><html><body><h1>Fetch Test</h1>
<script>fetch('/api/data').then(r => r.json());</script>
</body></html>"""


def _burst_page(n=120):
    scripts = '\n'.join(f'<script src="/res/{i}.js"></script>' for i in range(n))
    return f'<!DOCTYPE html><html><body><h1>Burst</h1>\n{scripts}\n</body></html>'


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self._send(200, 'text/html', '<html><body><h1>Test</h1></body></html>')
        elif self.path == '/fetch':
            self._send(200, 'text/html', FETCH_PAGE)
        elif self.path == '/api/data':
            self._send(200, 'application/json', '{"ok":true}')
        elif self.path == '/burst':
            self._send(200, 'text/html', _burst_page())
        elif self.path.startswith('/res/'):
            self._send(200, 'application/javascript', f'/* {self.path} */')
        else:
            self._send(404, 'text/plain', 'not found')

    def _send(self, code, ct, body):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def http_port(monkeypatch):
    """Local HTTP server; clears PASSE_CDP so connect() uses localhost:9222."""
    monkeypatch.delenv('PASSE_CDP', raising=False)
    srv = HTTPServer(('127.0.0.1', 0), _Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield port
    srv.shutdown()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _wait_state(daemon, target, timeout=10):
    """Poll until daemon reaches target state."""
    deadline = asyncio.get_running_loop().time() + timeout
    while daemon.state != target:
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError(
                f'Daemon stuck in {daemon.state.value}, wanted {target.value}')
        await asyncio.sleep(0.1)


async def _read_jsonl(path, min_lines=1, timeout=10):
    """Poll until JSONL file has at least min_lines entries."""
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if path.exists():
            text = path.read_text().strip()
            if text:
                lines = [l for l in text.split('\n') if l.strip()]
                if len(lines) >= min_lines:
                    return [json.loads(l) for l in lines]
        if asyncio.get_running_loop().time() > deadline:
            count = 0
            if path.exists():
                raw = path.read_text().strip()
                count = len([l for l in raw.split('\n') if l.strip()]) if raw else 0
            raise TimeoutError(
                f'JSONL has {count} lines, wanted >={min_lines}')
        await asyncio.sleep(0.2)


def _make_daemon(tmp_path):
    """Create a daemon with all file paths redirected to tmp_path."""
    d = LogDaemon(cdp_url='http://localhost:9222', log_dir=tmp_path)
    d.state_file = tmp_path / 'state.json'
    d.pid_file = tmp_path / '.daemon.pid'
    d._install_signals = lambda: None  # don't interfere with pytest
    return d


async def _stop_daemon(daemon, task, timeout=5):
    """Gracefully stop daemon; force-cancel if it doesn't exit in time."""
    daemon._running = False
    if daemon._ws:
        await daemon._ws.close()
    try:
        await asyncio.wait_for(task, timeout=timeout)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# 1. Lifecycle: connect → capture → disconnect
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_capture_disconnect(http_port, tmp_path):
    """Full lifecycle: connect, capture an XHR, verify JSONL, shutdown."""
    daemon = _make_daemon(tmp_path)
    task = asyncio.create_task(daemon.run())
    try:
        await _wait_state(daemon, DaemonState.CAPTURING)

        async with connect() as (client, _info):
            await client.create_tab()
            try:
                await client.send('Page.enable')
                await asyncio.sleep(0.5)  # let daemon enable network for new tab
                await do_navigate(client, f'http://127.0.0.1:{http_port}/fetch')
                await asyncio.sleep(2)  # let XHR complete
            finally:
                await client.close_tab()

        records = await _read_jsonl(tmp_path / 'requests.jsonl')
        server_recs = [r for r in records
                       if f'127.0.0.1:{http_port}' in r.get('url', '')]
        assert len(server_recs) > 0, (
            f'No test server requests. URLs: {[r["url"] for r in records]}')

        # Verify JSONL record structure
        rec = server_recs[0]
        assert 'id' in rec
        assert 'ts' in rec
        assert 'method' in rec
        assert 'tab' in rec
        # Internal meta fields must not leak into output
        assert 'session_id' not in rec
        assert 't0' not in rec
    finally:
        await _stop_daemon(daemon, task)

    assert daemon.state == DaemonState.DEAD


# ---------------------------------------------------------------------------
# 2. Reconnection: disconnect → reconnect → capture again
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconnection_resumes_capture(http_port, tmp_path):
    """Close WebSocket to simulate disconnect, verify daemon reconnects."""
    daemon = _make_daemon(tmp_path)
    task = asyncio.create_task(daemon.run())
    try:
        await _wait_state(daemon, DaemonState.CAPTURING)

        # Force disconnect
        await daemon._ws.close()

        # Daemon should reconnect after ~1s backoff
        await _wait_state(daemon, DaemonState.CAPTURING, timeout=15)

        # Verify capture works after reconnection
        async with connect() as (client, _info):
            await client.create_tab()
            try:
                await client.send('Page.enable')
                await asyncio.sleep(0.5)
                await do_navigate(client, f'http://127.0.0.1:{http_port}/fetch')
                await asyncio.sleep(2)
            finally:
                await client.close_tab()

        records = await _read_jsonl(tmp_path / 'requests.jsonl')
        server_recs = [r for r in records
                       if f'127.0.0.1:{http_port}' in r.get('url', '')]
        assert len(server_recs) > 0, 'No requests captured after reconnection'
    finally:
        await _stop_daemon(daemon, task)


# ---------------------------------------------------------------------------
# 3. Burst traffic: 120 sub-resources
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_burst_traffic(http_port, tmp_path):
    """Page with 120 script tags — daemon must capture without errors."""
    daemon = _make_daemon(tmp_path)
    task = asyncio.create_task(daemon.run())
    try:
        await _wait_state(daemon, DaemonState.CAPTURING)

        async with connect() as (client, _info):
            await client.create_tab()
            try:
                await client.send('Page.enable')
                await asyncio.sleep(0.5)
                await do_navigate(client, f'http://127.0.0.1:{http_port}/burst')
                await asyncio.sleep(5)  # 120 resources need time
            finally:
                await client.close_tab()

        records = await _read_jsonl(
            tmp_path / 'requests.jsonl', min_lines=50, timeout=15)
        server_recs = [r for r in records
                       if f'127.0.0.1:{http_port}' in r.get('url', '')]
        # 1 HTML + up to 120 JS. Allow variance but expect most captured.
        assert len(server_recs) >= 100, (
            f'Expected >=100 requests, got {len(server_recs)}')
    finally:
        await _stop_daemon(daemon, task)


# ---------------------------------------------------------------------------
# 4. Concurrent: daemon + CDPClient creating/destroying tabs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_passe_tabs(http_port, tmp_path):
    """Daemon keeps capturing while CDPClient creates and destroys tabs."""
    daemon = _make_daemon(tmp_path)
    task = asyncio.create_task(daemon.run())
    try:
        await _wait_state(daemon, DaemonState.CAPTURING)

        for _ in range(3):
            async with connect() as (client, _info):
                await client.create_tab()
                try:
                    await client.send('Page.enable')
                    await asyncio.sleep(0.3)
                    await do_navigate(client, f'http://127.0.0.1:{http_port}/')
                    await asyncio.sleep(1)
                finally:
                    await client.close_tab()

        records = await _read_jsonl(tmp_path / 'requests.jsonl')
        server_recs = [r for r in records
                       if f'127.0.0.1:{http_port}' in r.get('url', '')]
        # At least 3 page loads (one per tab)
        assert len(server_recs) >= 3, (
            f'Expected >=3 requests from 3 tabs, got {len(server_recs)}')

        # Daemon must still be alive
        assert daemon.state == DaemonState.CAPTURING
    finally:
        await _stop_daemon(daemon, task)
