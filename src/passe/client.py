"""CDP WebSocket client with future-based message routing."""

import asyncio
import json
import sys
import time

import websockets


class CDPClient:
    """Minimal CDP client with future-based message routing."""

    # Only buffer events that wait_for_event callers actually consume.
    # The buffer is dict[str, dict] (one entry per method), so max size
    # equals len(BUFFERED_EVENTS). Everything else is dropped if no waiter.
    BUFFERED_EVENTS = frozenset({'Page.loadEventFired'})

    def __init__(self, ws):
        self.ws = ws
        self.msg_id = 0
        self.pending: dict[int, asyncio.Future] = {}
        self.event_waiters: dict[str, asyncio.Future] = {}
        self.event_buffer: dict[str, dict] = {}
        self.event_queues: dict[str, asyncio.Queue] = {}  # continuous event streams
        self.session_id: str | None = None
        self.receiver_task: asyncio.Task | None = None
        self._target_id: str | None = None
        self._owns_tab: bool = False
        # Network capture: requestId → merged request/response data
        self._network_requests: dict[str, dict] = {}
        self._network_enabled: bool = False
        self._inflight_count: int = 0
        self._network_idle_event: asyncio.Event = asyncio.Event()
        self._capture_t0: dict[str, float] = {}  # requestId → monotonic start

    async def start(self):
        self.receiver_task = asyncio.create_task(self._receiver())

    async def stop(self):
        if self.receiver_task and not self.receiver_task.done():
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass

    async def _receiver(self):
        """Route responses to futures, events to waiters."""
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                if 'id' in msg:
                    fut = self.pending.pop(msg['id'], None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                    continue
                method = msg.get('method', '')
                # Network capture — collect before routing (non-consuming,
                # so waiters and queues still see the event too)
                if self._network_enabled and method.startswith('Network.'):
                    self._collect_network_event(method, msg)
                if method in self.event_waiters:
                    fut = self.event_waiters.pop(method)
                    if not fut.done():
                        fut.set_result(msg)
                        continue
                # Continuous event queue (for watch verb etc.)
                if method in self.event_queues:
                    self.event_queues[method].put_nowait(msg)
                    continue
                # No active waiter (or waiter was stale/timed-out) — buffer if whitelisted
                if method in self.BUFFERED_EVENTS:
                    self.event_buffer[method] = msg
        except websockets.ConnectionClosed:
            pass
        except asyncio.CancelledError:
            pass

    async def send(self, method: str, params: dict = None,
                   timeout: float = 15.0) -> dict:
        self.msg_id += 1
        msg = {'id': self.msg_id, 'method': method, 'params': params or {}}
        if self.session_id:
            msg['sessionId'] = self.session_id
        fut = asyncio.get_event_loop().create_future()
        self.pending[self.msg_id] = fut
        await self.ws.send(json.dumps(msg))
        return await asyncio.wait_for(fut, timeout=timeout)

    async def wait_for_event(self, method: str, timeout: float = 15.0) -> dict:
        # Check buffer first — the event may have fired before we started waiting
        if method in self.event_buffer:
            return self.event_buffer.pop(method)
        fut = asyncio.get_event_loop().create_future()
        self.event_waiters[method] = fut
        return await asyncio.wait_for(fut, timeout=timeout)

    def subscribe(self, method: str) -> asyncio.Queue:
        """Subscribe to continuous events. Returns an asyncio.Queue."""
        q = asyncio.Queue()
        self.event_queues[method] = q
        return q

    def unsubscribe(self, method: str):
        """Stop receiving continuous events."""
        self.event_queues.pop(method, None)

    # ── Network capture ──────────────────────────────────

    async def ensure_network(self):
        """Enable Network domain if not already enabled. Does not clear requests."""
        if not self._network_enabled:
            self._network_enabled = True
            await self.send('Network.enable')

    async def enable_network(self, large_buffers: bool = False):
        """Enable Network domain and start a fresh capture (clears requests).

        large_buffers=True passes large buffer params to Network.enable so
        Chrome retains response bodies for getResponseBody calls. Required
        for --bodies capture and streaming responses.
        """
        self._network_requests.clear()
        self._capture_t0.clear()
        self._inflight_count = 0
        self._network_idle_event.set()
        self._network_enabled = True
        params = {}
        if large_buffers:
            params = {
                'maxTotalBufferSize': 100_000_000,
                'maxResourceBufferSize': 50_000_000,
                'maxPostDataSize': 65536,
            }
        await self.send('Network.enable', params)

    async def disable_network(self):
        """Disable Network domain and stop collecting."""
        self._network_enabled = False
        try:
            await self.send('Network.disable')
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass

    def get_network_requests(self) -> list[dict]:
        """Return collected network requests as a list, ordered by timestamp."""
        return sorted(self._network_requests.values(),
                      key=lambda r: r.get('timestamp', 0))

    def _collect_network_event(self, method: str, msg: dict):
        """Buffer a Network domain event, correlating by requestId."""
        params = msg.get('params', {})
        request_id = params.get('requestId')
        if not request_id:
            return

        if method == 'Network.requestWillBeSent':
            request = params.get('request', {})
            record = {
                'requestId': request_id,
                'method': request.get('method'),
                'url': request.get('url'),
                'request_headers': dict(request.get('headers', {})),
                'resource_type': params.get('type'),
                'timestamp': params.get('timestamp'),
                'wall_time': params.get('wallTime'),
            }
            post_data = request.get('postData')
            if post_data:
                record['request_body'] = post_data
            self._network_requests[request_id] = record
            self._capture_t0[request_id] = time.monotonic()
            self._inflight_count += 1
            self._network_idle_event.clear()
        elif method == 'Network.requestWillBeSentExtraInfo':
            if request_id in self._network_requests:
                headers = params.get('headers', {})
                self._network_requests[request_id].setdefault(
                    'request_headers', {}).update(headers)
        elif method == 'Network.responseReceived':
            response = params.get('response', {})
            if request_id in self._network_requests:
                self._network_requests[request_id].update({
                    'status': response.get('status'),
                    'status_text': response.get('statusText'),
                    'content_type': response.get('mimeType'),
                    'response_headers': dict(response.get('headers', {})),
                    'response_timestamp': params.get('timestamp'),
                })
        elif method == 'Network.responseReceivedExtraInfo':
            if request_id in self._network_requests:
                headers = params.get('headers', {})
                self._network_requests[request_id].setdefault(
                    'response_headers', {}).update(headers)
        elif method == 'Network.loadingFinished':
            if request_id in self._network_requests:
                self._network_requests[request_id]['completed'] = True
                self._network_requests[request_id]['encoded_data_length'] = params.get('encodedDataLength')
                t0 = self._capture_t0.pop(request_id, None)
                if t0 is not None:
                    self._network_requests[request_id]['timing_ms'] = round(
                        (time.monotonic() - t0) * 1000, 1)
            self._inflight_count = max(0, self._inflight_count - 1)
            if self._inflight_count == 0:
                self._network_idle_event.set()
        elif method == 'Network.loadingFailed':
            if request_id in self._network_requests:
                self._network_requests[request_id]['failed'] = True
                self._network_requests[request_id]['error_text'] = params.get('errorText')
            self._capture_t0.pop(request_id, None)
            self._inflight_count = max(0, self._inflight_count - 1)
            if self._inflight_count == 0:
                self._network_idle_event.set()

    async def attach_to_first_page(self) -> str:
        """Attach to an existing tab. Used by atomic commands (screenshot, eval)."""
        result = await self.send('Target.getTargets')
        pages = [t for t in result['result']['targetInfos'] if t['type'] == 'page']
        if not pages:
            # Chrome running with zero tabs (only service workers) — create one
            created = await self.send('Target.createTarget', {
                'url': 'about:blank', 'background': True,
            })
            target_id = created['result']['targetId']
            pages = [{'targetId': target_id}]
        result = await self.send('Target.attachToTarget', {
            'targetId': pages[0]['targetId'],
            'flatten': True
        })
        self.session_id = result['result']['sessionId']
        self._owns_tab = False
        return self.session_id

    async def attach_to_visible_page(self, origin: str = None) -> str:
        """Attach to a non-chrome:// page tab. For --reuse-tab.

        If origin is given (e.g. 'http://localhost:3333'), prefer a tab
        already on that origin. Falls back to the first non-chrome:// tab.
        Always logs the attached tab's URL to stderr.
        """
        result = await self.send('Target.getTargets')
        pages = [t for t in result['result']['targetInfos']
                 if t['type'] == 'page' and not t.get('url', '').startswith('chrome://')]
        if not pages:
            # Fall back to any page tab
            pages = [t for t in result['result']['targetInfos'] if t['type'] == 'page']
        if not pages:
            raise RuntimeError('No browser tab to reuse — open a tab first')
        # Prefer origin match when caller knows the target
        target = pages[0]
        if origin:
            for p in pages:
                if p.get('url', '').startswith(origin):
                    target = p
                    break
        tab_url = target.get('url', 'unknown')
        print(f'[passe] reuse-tab: {tab_url}', file=sys.stderr)
        result = await self.send('Target.attachToTarget', {
            'targetId': target['targetId'],
            'flatten': True
        })
        self.session_id = result['result']['sessionId']
        self._owns_tab = False
        return self.session_id

    async def close_tabs_by_origin(self, origin: str) -> int:
        """Close all page tabs matching an origin (scheme://host:port).

        Returns the number of tabs closed. Used by --keep-tab auto-replace
        to prevent tab accumulation on repeated runs to the same site.
        """
        result = await self.send('Target.getTargets')
        targets = result.get('result', {}).get('targetInfos', [])
        closed = 0
        for target in targets:
            if target.get('type') != 'page':
                continue
            url = target.get('url', '')
            if not url.startswith(origin):
                continue
            try:
                await self.send('Target.closeTarget',
                                {'targetId': target['targetId']}, timeout=5.0)
                closed += 1
            except (websockets.ConnectionClosed, asyncio.CancelledError,
                    asyncio.TimeoutError):
                pass
        return closed

    async def list_tabs(self) -> list[dict]:
        """List all page tabs. Returns [{target_id, url, title}]."""
        result = await self.send('Target.getTargets')
        targets = result.get('result', {}).get('targetInfos', [])
        return [
            {'target_id': t['targetId'], 'url': t.get('url', ''), 'title': t.get('title', '')}
            for t in targets if t.get('type') == 'page'
        ]

    async def create_tab(self, foreground: bool = False) -> str:
        """Create a fresh tab and attach to it. Caller owns the tab lifecycle.

        foreground=True creates a visible tab (background: False) and calls
        Page.bringToFront. Required for sites using Google Closure jsaction
        handlers, which silently ignore events on background tabs.
        """
        created = await self.send('Target.createTarget', {
            'url': 'about:blank', 'background': not foreground,
        })
        self._target_id = created['result']['targetId']
        result = await self.send('Target.attachToTarget', {
            'targetId': self._target_id,
            'flatten': True
        })
        self.session_id = result['result']['sessionId']
        self._owns_tab = True
        if foreground:
            await self.send('Page.bringToFront')
        return self.session_id

    async def close_tab(self):
        """Close the tab if we created it. Safe to call during teardown.

        Navigates to about:blank first to drop SSE/WebSocket connections
        that would otherwise block Target.closeTarget indefinitely.
        """
        self._network_enabled = False
        if self._owns_tab and self._target_id:
            try:
                # Drop SSE/WS connections — about:blank tears down page resources
                await self.send('Page.navigate', {'url': 'about:blank'}, timeout=5.0)
            except (websockets.ConnectionClosed, asyncio.CancelledError,
                    asyncio.TimeoutError):
                pass
            try:
                await self.send('Target.closeTarget',
                                {'targetId': self._target_id}, timeout=5.0)
            except (websockets.ConnectionClosed, asyncio.CancelledError,
                    asyncio.TimeoutError):
                pass
            self._owns_tab = False
