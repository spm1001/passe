"""Continuous network capture daemon — multi-tab, reconnecting, JSONL output.

Architecturally separate from CDPClient: CDPClient is single-session
request-response with one-shot event waiters. This daemon is multi-session
continuous streaming with sessionId routing. Both open their own WebSocket
to the same Chrome — concurrent connections are fine.

Uses discover_chrome() from connection.py for Chrome discovery only.
Does NOT auto-launch Chrome — fails loudly if unreachable.

Entry point: python -m passe.log_daemon [--cdp URL] [--log-dir DIR]
"""

import argparse
import asyncio
import base64
import enum
import json
import logging
import os
import re
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets

from passe.connection import discover_chrome

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_BODY_SIZE = 100 * 1024          # 100KB per response body
MAX_LOG_SIZE = 100 * 1024 * 1024    # 100MB before rotation
MAX_ROTATED_FILES = 3
COMMAND_TIMEOUT = 10.0              # seconds for CDP command responses

# Reconnection backoff
BACKOFF_INITIAL = 1.0
BACKOFF_MAX = 60.0
BACKOFF_FACTOR = 2.0

# ---------------------------------------------------------------------------
# Filtering skip-lists
# ---------------------------------------------------------------------------

SKIP_URL_PATTERNS = [
    re.compile(p) for p in [
        r'google-analytics\.com', r'doubleclick\.net',
        r'googlesyndication\.com', r'googleadservices\.com',
        r'play\.google\.com/log', r'fonts\.googleapis\.com',
        r'fonts\.gstatic\.com', r'pagead',
        r'facebook\.com/tr', r'connect\.facebook',
        r'sentry\.io', r'hotjar', r'clarity\.ms',
        r'/analytics', r'/tracking', r'/telemetry',
        r'/beacon', r'/pixel', r'/metrics',
        r'\.ads\.', r'adservice', r'adsystem',
    ]
]

SKIP_EXTENSIONS = frozenset({'.css', '.woff', '.woff2', '.svg', '.ico'})

SKIP_MIME_PREFIXES = ('image/', 'font/', 'audio/', 'video/')
SKIP_MIME_EXACT = frozenset({
    'application/octet-stream', 'application/pdf', 'application/zip',
})

log = logging.getLogger('passe.daemon')

# Handler registry — populated by @_handles decorator, used by _dispatch.
# Lives at module level so decorators run at class definition time.
_handlers: dict[str, callable] = {}


def _handles(cdp_method: str):
    """Register a LogDaemon method as handler for a CDP event type."""
    def decorator(func):
        _handlers[cdp_method] = func
        return func
    return decorator


def should_skip_url(url: str) -> bool:
    """Check if URL should be filtered out (tracking, static assets)."""
    if any(p.search(url) for p in SKIP_URL_PATTERNS):
        return True
    path = url.split('?', 1)[0]
    return any(path.endswith(ext) for ext in SKIP_EXTENSIONS)


def should_skip_mime(mime: str | None) -> bool:
    """Check if MIME type should be filtered out (binary)."""
    if not mime:
        return False
    if mime in SKIP_MIME_EXACT:
        return True
    return any(mime.startswith(prefix) for prefix in SKIP_MIME_PREFIXES)


# ---------------------------------------------------------------------------
# Daemon state machine
# ---------------------------------------------------------------------------

class DaemonState(enum.Enum):
    CONNECTING = 'connecting'
    ATTACHING = 'attaching'
    CAPTURING = 'capturing'
    DISCONNECTED = 'disconnected'
    DEAD = 'dead'


# ---------------------------------------------------------------------------
# Request assembly store
# ---------------------------------------------------------------------------

class RequestStore:
    """In-flight request assembly — correlates CDP events by requestId.

    Maintains two parallel dicts: `records` for the JSONL output fields
    and `meta` for internal tracking (session_id, timing start). This
    separation prevents internal fields from leaking into user-visible
    output if a handler forgets to strip them.
    """

    def __init__(self):
        self.records: dict[str, dict] = {}
        self.meta: dict[str, dict] = {}

    def start(self, request_id: str, record: dict, meta: dict | None = None):
        self.records[request_id] = {
            'id': request_id,
            'ts': datetime.now(timezone.utc).isoformat(),
            **record,
        }
        self.meta[request_id] = meta or {}

    def update(self, request_id: str, data: dict):
        if request_id in self.records:
            self.records[request_id].update(data)

    def get(self, request_id: str) -> dict | None:
        return self.records.get(request_id)

    def get_meta(self, request_id: str) -> dict | None:
        return self.meta.get(request_id)

    def complete(self, request_id: str) -> dict | None:
        self.meta.pop(request_id, None)
        return self.records.pop(request_id, None)

    def clear(self):
        self.records.clear()
        self.meta.clear()


# ---------------------------------------------------------------------------
# Log file management
# ---------------------------------------------------------------------------

class LogWriter:
    """JSONL log writer with rotation and pause support."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_file = log_dir / 'requests.jsonl'
        self.pause_file = log_dir / '.paused'

    @property
    def is_paused(self) -> bool:
        return self.pause_file.exists()

    def write(self, record: dict):
        if self.is_paused:
            return
        if self.log_file.exists() and self.log_file.stat().st_size > MAX_LOG_SIZE:
            self._rotate()
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(record, default=str) + '\n')

    def _rotate(self):
        log.info('Rotating log files')
        oldest = self.log_dir / f'requests.jsonl.{MAX_ROTATED_FILES}'
        if oldest.exists():
            oldest.unlink()
        for i in range(MAX_ROTATED_FILES - 1, 0, -1):
            src = self.log_dir / f'requests.jsonl.{i}'
            dst = self.log_dir / f'requests.jsonl.{i + 1}'
            if src.exists():
                src.rename(dst)
        if self.log_file.exists():
            self.log_file.rename(self.log_dir / 'requests.jsonl.1')


# ---------------------------------------------------------------------------
# The daemon
# ---------------------------------------------------------------------------

class LogDaemon:
    """Multi-tab network capture daemon with reconnection."""

    def __init__(self, cdp_url: str | None = None,
                 log_dir: Path | None = None):
        self.cdp_url = cdp_url
        self.log_dir = log_dir or Path.home() / '.passe' / 'logs'
        self.state_file = Path.home() / '.passe' / 'state.json'
        self.pid_file = Path.home() / '.passe' / '.daemon.pid'
        self.writer = LogWriter(self.log_dir)
        self.store = RequestStore()
        self.sessions: dict[str, dict] = {}   # sessionId → targetInfo
        self.state = DaemonState.DEAD
        self._running = True
        self._msg_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._receiver_task: asyncio.Task | None = None

    # -- CDP command/response plumbing ------------------------------------

    async def send(self, method: str, params: dict | None = None,
                   session_id: str | None = None) -> dict:
        self._msg_id += 1
        msg_id = self._msg_id
        msg = {'id': msg_id, 'method': method, 'params': params or {}}
        if session_id:
            msg['sessionId'] = session_id

        future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = future
        await self._ws.send(json.dumps(msg))

        try:
            return await asyncio.wait_for(future, timeout=COMMAND_TIMEOUT)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise

    # -- Message dispatch --------------------------------------------------

    def _dispatch(self, raw: str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        # Command responses go to pending futures
        if 'id' in data:
            fut = self._pending.pop(data['id'], None)
            if fut and not fut.done():
                fut.set_result(data)
            return

        method = data.get('method', '')
        params = data.get('params', {})
        session_id = data.get('sessionId', '')

        handler = _handlers.get(method)
        if handler:
            handler(self, params, session_id)

    # -- Network event handlers --------------------------------------------

    @_handles('Network.requestWillBeSent')
    def _on_request_will_be_sent(self, params: dict, session_id: str):
        request_id = params.get('requestId')
        req = params.get('request', {})
        url = req.get('url', '')
        if should_skip_url(url):
            return
        target = self.sessions.get(session_id, {})
        self.store.start(request_id, {
            'tab': {
                'id': target.get('targetId', ''),
                'url': target.get('url', ''),
            },
            'method': req.get('method'),
            'url': url,
            'resource_type': params.get('type'),
            'request_headers': dict(req.get('headers', {})),
            'request_body': req.get('postData'),
        }, meta={
            'session_id': session_id,
            't0': time.monotonic(),
        })

    @_handles('Network.requestWillBeSentExtraInfo')
    def _on_request_extra_info(self, params: dict, session_id: str):
        request_id = params.get('requestId')
        rec = self.store.get(request_id)
        if not rec:
            return
        headers = params.get('headers', {})
        rec.setdefault('request_headers', {}).update(headers)

    @_handles('Network.responseReceived')
    def _on_response_received(self, params: dict, session_id: str):
        request_id = params.get('requestId')
        response = params.get('response', {})
        mime = response.get('mimeType', '')
        if should_skip_mime(mime):
            self.store.complete(request_id)
            return
        self.store.update(request_id, {
            'status': response.get('status'),
            'mime': mime,
            'response_headers': dict(response.get('headers', {})),
        })

    @_handles('Network.responseReceivedExtraInfo')
    def _on_response_extra_info(self, params: dict, session_id: str):
        request_id = params.get('requestId')
        rec = self.store.get(request_id)
        if not rec:
            return
        headers = params.get('headers', {})
        rec.setdefault('response_headers', {}).update(headers)

    @_handles('Network.loadingFinished')
    def _on_loading_finished(self, params: dict, session_id: str):
        request_id = params.get('requestId')
        rec = self.store.get(request_id)
        if not rec:
            return
        meta = self.store.get_meta(request_id) or {}
        t0 = meta.get('t0')
        if t0 is not None:
            rec['timing_ms'] = round(
                (time.monotonic() - t0) * 1000, 1)
        rec['size'] = params.get('encodedDataLength', 0)
        task = asyncio.create_task(self._finish_request(request_id, session_id))
        task.add_done_callback(self._log_task_error)

    @staticmethod
    def _log_task_error(task: asyncio.Task):
        """Done callback for fire-and-forget tasks — log unexpected errors."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            log.error('Background task failed: %s', exc)

    async def _finish_request(self, request_id: str, session_id: str):
        rec = self.store.get(request_id)
        if not rec:
            return
        mime = rec.get('mime', '')
        if not should_skip_mime(mime):
            body = await self._get_body(request_id, session_id)
            if body is not None:
                rec['response_body'] = body
        completed = self.store.complete(request_id)
        if completed:
            self.writer.write(completed)

    async def _get_body(self, request_id: str, session_id: str) -> str | None:
        try:
            result = await self.send(
                'Network.getResponseBody',
                {'requestId': request_id},
                session_id,
            )
            if 'error' in result:
                return None
            body_data = result.get('result', {})
            body = body_data.get('body', '')
            is_base64 = body_data.get('base64Encoded', False)
            if is_base64:
                try:
                    decoded = base64.b64decode(body)
                    if len(decoded) > MAX_BODY_SIZE:
                        return f'[truncated: {len(decoded)} bytes]'
                    return decoded.decode('utf-8', errors='replace')
                except Exception:
                    return '[binary content]'
            else:
                if len(body) > MAX_BODY_SIZE:
                    return body[:MAX_BODY_SIZE] + f'\n[truncated: {len(body)} bytes total]'
                return body
        except (asyncio.TimeoutError, Exception):
            return None

    @_handles('Network.loadingFailed')
    def _on_loading_failed(self, params: dict, session_id: str):
        self.store.complete(params.get('requestId'))

    # -- Target event handlers ---------------------------------------------

    @_handles('Target.attachedToTarget')
    def _on_attached(self, params: dict, _session_id: str):
        session_id = params.get('sessionId')
        target_info = params.get('targetInfo', {})
        if target_info.get('type') != 'page':
            return
        self.sessions[session_id] = target_info
        log.info('Attached: %s', target_info.get('url', 'unknown')[:60])
        task = asyncio.create_task(self._enable_network(session_id))
        task.add_done_callback(self._log_task_error)

    @_handles('Target.detachedFromTarget')
    def _on_detached(self, params: dict, _session_id: str):
        session_id = params.get('sessionId')
        info = self.sessions.pop(session_id, {})
        log.info('Detached: %s', info.get('url', 'unknown')[:60])

    @_handles('Target.targetInfoChanged')
    def _on_target_changed(self, params: dict, _session_id: str):
        target_info = params.get('targetInfo', {})
        target_id = target_info.get('targetId')
        for sid, info in self.sessions.items():
            if info.get('targetId') == target_id:
                self.sessions[sid] = target_info
                break

    # -- Network enable per session ----------------------------------------

    async def _enable_network(self, session_id: str):
        try:
            await self.send('Network.enable', {
                'maxTotalBufferSize': 100_000_000,
                'maxResourceBufferSize': 50_000_000,
                'maxPostDataSize': 65536,
            }, session_id)
        except Exception as exc:
            log.error('Network.enable failed for %s: %s',
                      session_id[:8], exc)

    # -- Connection lifecycle ----------------------------------------------

    async def _connect_and_attach(self):
        """Discover Chrome, open WebSocket, attach to all tabs."""
        self.state = DaemonState.CONNECTING
        ws_url, info = await asyncio.to_thread(discover_chrome, self.cdp_url)
        log.info('Connecting to %s (%s)', info['cdp'], info['browser'])

        self._ws = await websockets.connect(ws_url, max_size=50 * 1024 * 1024)

        # Start receiver BEFORE sending commands — send() needs it to
        # dispatch CDP responses to pending futures.
        self._receiver_task = asyncio.create_task(self._receive_messages())

        self.state = DaemonState.ATTACHING

        await self.send('Target.setAutoAttach', {
            'autoAttach': True,
            'waitForDebuggerOnStart': False,
            'flatten': True,
        })
        await self.send('Target.setDiscoverTargets', {'discover': True})

        result = await self.send('Target.getTargets')
        targets = result.get('result', {}).get('targetInfos', [])
        for target in targets:
            if target.get('type') != 'page':
                continue
            try:
                attach = await self.send('Target.attachToTarget', {
                    'targetId': target['targetId'],
                    'flatten': True,
                })
                sid = attach.get('result', {}).get('sessionId')
                if sid:
                    self.sessions[sid] = target
                    await self._enable_network(sid)
            except Exception as exc:
                log.warning('Attach failed: %s (%s)',
                            target.get('url', '')[:40], exc)

        log.info('Capturing %d tabs', len(self.sessions))
        self.state = DaemonState.CAPTURING

    async def _receive_messages(self):
        """Background task: receive and dispatch messages until disconnected."""
        try:
            async for raw in self._ws:
                self._dispatch(raw)
        except websockets.ConnectionClosed:
            log.warning('Chrome disconnected')
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error('Receiver error: %s', exc)

    async def _wait_for_disconnect(self):
        """Wait for the receiver task to finish (disconnect or error)."""
        if self._receiver_task:
            await self._receiver_task

    def _reset_session_state(self):
        """Discard all per-connection state on disconnect."""
        self.sessions.clear()
        self.store.clear()
        self._pending.clear()
        if self._receiver_task and not self._receiver_task.done():
            self._receiver_task.cancel()
        self._receiver_task = None
        self._ws = None

    # -- Reconnection state machine ----------------------------------------

    async def run(self):
        """Main daemon loop with reconnection."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._write_pid()
        self._install_signals()

        backoff = BACKOFF_INITIAL
        try:
            while self._running:
                try:
                    await self._connect_and_attach()
                    backoff = BACKOFF_INITIAL       # reset on success
                    await self._wait_for_disconnect()
                except ConnectionError as exc:
                    log.error('Connection failed: %s', exc)
                except Exception as exc:
                    log.error('Unexpected error: %s', exc)
                finally:
                    self._reset_session_state()

                if not self._running:
                    break

                self.state = DaemonState.DISCONNECTED
                log.info('Reconnecting in %.0fs', backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * BACKOFF_FACTOR, BACKOFF_MAX)
        finally:
            self.state = DaemonState.DEAD
            self._remove_pid()
            self._remove_state()
            log.info('Daemon stopped')

    # -- PID / state file management ---------------------------------------

    def _write_pid(self):
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()))
        self.state_file.write_text(json.dumps({
            'pid': os.getpid(),
            'cdp': self.cdp_url,
            'started': datetime.now(timezone.utc).isoformat(),
        }))

    def _remove_pid(self):
        for f in (self.pid_file, ):
            if f.exists():
                f.unlink()

    def _remove_state(self):
        if self.state_file.exists():
            self.state_file.unlink()

    # -- Signal handling ---------------------------------------------------

    def _install_signals(self):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_signal, sig)

    def _handle_signal(self, sig):
        log.info('Received %s, shutting down', signal.Signals(sig).name)
        self._running = False
        # Cancel the WebSocket to break out of _message_loop
        if self._ws:
            asyncio.create_task(self._ws.close())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='passe network capture daemon')
    parser.add_argument('--cdp', help='CDP endpoint URL')
    parser.add_argument('--log-dir', type=Path,
                        default=Path.home() / '.passe' / 'logs')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    daemon = LogDaemon(cdp_url=args.cdp, log_dir=args.log_dir)
    asyncio.run(daemon.run())


if __name__ == '__main__':
    main()
