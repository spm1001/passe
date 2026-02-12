"""
Passe — fast CDP browser automation for Chrome Debug.

The kitchen pass: inspect everything before it goes out.

Commands:
  passe screenshot <output.png>
  passe navigate-screenshot <url> <output.png>
  passe navigate-click-screenshot <url> <selector> <output.png>
  passe navigate-fill-click-screenshot <url> <input-sel> <value> <submit-sel> <output.png>

Connects to Chrome on port 9222 via raw WebSocket.
Outputs timing JSON to stdout, saves screenshot to file.
"""

import asyncio
import base64
import json
import sys
import time
import urllib.request

import websockets


class CDPClient:
    """Minimal CDP client with future-based message routing."""

    def __init__(self, ws):
        self.ws = ws
        self.msg_id = 0
        self.pending: dict[int, asyncio.Future] = {}
        self.event_waiters: dict[str, asyncio.Future] = {}
        self.session_id: str | None = None
        self.receiver_task: asyncio.Task | None = None

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
                if method in self.event_waiters:
                    fut = self.event_waiters.pop(method)
                    if not fut.done():
                        fut.set_result(msg)
        except websockets.ConnectionClosed:
            pass
        except asyncio.CancelledError:
            pass

    async def send(self, method: str, params: dict = None) -> dict:
        self.msg_id += 1
        msg = {'id': self.msg_id, 'method': method, 'params': params or {}}
        if self.session_id:
            msg['sessionId'] = self.session_id
        fut = asyncio.get_event_loop().create_future()
        self.pending[self.msg_id] = fut
        await self.ws.send(json.dumps(msg))
        return await asyncio.wait_for(fut, timeout=15.0)

    async def wait_for_event(self, method: str, timeout: float = 15.0) -> dict:
        fut = asyncio.get_event_loop().create_future()
        self.event_waiters[method] = fut
        return await asyncio.wait_for(fut, timeout=timeout)

    async def attach_to_first_page(self) -> str:
        result = await self.send('Target.getTargets')
        pages = [t for t in result['result']['targetInfos'] if t['type'] == 'page']
        if not pages:
            raise RuntimeError('No pages found')
        result = await self.send('Target.attachToTarget', {
            'targetId': pages[0]['targetId'],
            'flatten': True
        })
        self.session_id = result['result']['sessionId']
        return self.session_id


def _chrome_running(port=9222) -> bool:
    try:
        with urllib.request.urlopen(f'http://localhost:{port}/json/version', timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _start_chrome(port=9222):
    """Launch Chrome with debug profile if not running."""
    import subprocess
    from pathlib import Path
    print("Starting Chrome Debug...", file=sys.stderr)
    subprocess.Popen(
        ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
         f'--remote-debugging-port={port}',
         '--user-data-dir=' + str(Path.home() / '.chrome-debug'),
         '--no-default-browser-check'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    for _ in range(30):
        if _chrome_running(port):
            print("Chrome Debug started.", file=sys.stderr)
            return
        time.sleep(0.5)
    print("Failed to start Chrome Debug.", file=sys.stderr)
    sys.exit(1)


async def connect(port=9222):
    """Connect to Chrome, starting it if needed. Return (websocket, CDPClient)."""
    if not _chrome_running(port):
        _start_chrome(port)
    with urllib.request.urlopen(f'http://localhost:{port}/json/version', timeout=5) as resp:
        ws_url = json.loads(resp.read())['webSocketDebuggerUrl']
    ws = await websockets.connect(ws_url, max_size=50 * 1024 * 1024)
    client = CDPClient(ws)
    await client.start()
    return ws, client


# ── Actions ───────────────────────────────────────────────

async def do_screenshot(client: CDPClient, full_page: bool = False) -> bytes:
    params = {'format': 'png'}
    if full_page:
        params['captureBeyondViewport'] = True
    result = await client.send('Page.captureScreenshot', params)
    return base64.b64decode(result['result']['data'])


async def do_navigate(client: CDPClient, url: str):
    await client.send('Page.enable')
    load_fut = client.wait_for_event('Page.loadEventFired')
    await client.send('Page.navigate', {'url': url})
    await load_fut


async def do_click(client: CDPClient, selector: str):
    result = await client.send('Runtime.evaluate', {
        'expression': f'document.querySelector("{selector}").click()',
        'awaitPromise': False
    })
    if 'exceptionDetails' in result.get('result', {}):
        raise RuntimeError(f'Click failed on "{selector}"')


async def do_fill(client: CDPClient, selector: str, value: str):
    js = f'''(() => {{
        const el = document.querySelector("{selector}");
        el.value = {json.dumps(value)};
        el.dispatchEvent(new Event("input", {{bubbles: true}}));
    }})()'''
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    if 'exceptionDetails' in result.get('result', {}):
        raise RuntimeError(f'Fill failed on "{selector}"')


async def do_eval(client: CDPClient, expression: str) -> str:
    result = await client.send('Runtime.evaluate', {
        'expression': expression, 'awaitPromise': True
    })
    r = result.get('result', {}).get('result', {})
    return r.get('value', r.get('description', ''))


def save_screenshot(data: bytes, path: str):
    with open(path, 'wb') as f:
        f.write(data)


# ── Compound commands ─────────────────────────────────────

async def cmd_screenshot(output: str):
    timings = {}
    t0 = time.monotonic()
    ws, client = await connect()
    timings['connect_ms'] = round((time.monotonic() - t0) * 1000, 1)
    try:
        t1 = time.monotonic()
        await client.attach_to_first_page()
        timings['attach_ms'] = round((time.monotonic() - t1) * 1000, 1)
        t2 = time.monotonic()
        img = await do_screenshot(client)
        timings['capture_ms'] = round((time.monotonic() - t2) * 1000, 1)
        save_screenshot(img, output)
        timings['total_ms'] = round((time.monotonic() - t0) * 1000, 1)
        timings['size_kb'] = round(len(img) / 1024, 1)
        print(json.dumps(timings))
    finally:
        await client.stop()
        await ws.close()


async def cmd_navigate_screenshot(url: str, output: str):
    timings = {}
    t0 = time.monotonic()
    ws, client = await connect()
    timings['connect_ms'] = round((time.monotonic() - t0) * 1000, 1)
    try:
        t1 = time.monotonic()
        await client.attach_to_first_page()
        timings['attach_ms'] = round((time.monotonic() - t1) * 1000, 1)
        t2 = time.monotonic()
        await do_navigate(client, url)
        timings['navigate_ms'] = round((time.monotonic() - t2) * 1000, 1)
        t3 = time.monotonic()
        img = await do_screenshot(client)
        timings['capture_ms'] = round((time.monotonic() - t3) * 1000, 1)
        save_screenshot(img, output)
        timings['total_ms'] = round((time.monotonic() - t0) * 1000, 1)
        timings['size_kb'] = round(len(img) / 1024, 1)
        print(json.dumps(timings))
    finally:
        await client.stop()
        await ws.close()


async def cmd_navigate_click_screenshot(url: str, selector: str, output: str):
    timings = {}
    t0 = time.monotonic()
    ws, client = await connect()
    timings['connect_ms'] = round((time.monotonic() - t0) * 1000, 1)
    try:
        t1 = time.monotonic()
        await client.attach_to_first_page()
        timings['attach_ms'] = round((time.monotonic() - t1) * 1000, 1)
        t2 = time.monotonic()
        await do_navigate(client, url)
        timings['navigate_ms'] = round((time.monotonic() - t2) * 1000, 1)
        t3 = time.monotonic()
        await do_click(client, selector)
        timings['click_ms'] = round((time.monotonic() - t3) * 1000, 1)
        t4 = time.monotonic()
        img = await do_screenshot(client)
        timings['capture_ms'] = round((time.monotonic() - t4) * 1000, 1)
        save_screenshot(img, output)
        timings['total_ms'] = round((time.monotonic() - t0) * 1000, 1)
        timings['size_kb'] = round(len(img) / 1024, 1)
        print(json.dumps(timings))
    finally:
        await client.stop()
        await ws.close()


async def cmd_navigate_fill_click_screenshot(url: str, input_sel: str, value: str, submit_sel: str, output: str):
    timings = {}
    t0 = time.monotonic()
    ws, client = await connect()
    timings['connect_ms'] = round((time.monotonic() - t0) * 1000, 1)
    try:
        t1 = time.monotonic()
        await client.attach_to_first_page()
        timings['attach_ms'] = round((time.monotonic() - t1) * 1000, 1)
        t2 = time.monotonic()
        await do_navigate(client, url)
        timings['navigate_ms'] = round((time.monotonic() - t2) * 1000, 1)
        t3 = time.monotonic()
        await do_fill(client, input_sel, value)
        timings['fill_ms'] = round((time.monotonic() - t3) * 1000, 1)
        t4 = time.monotonic()
        await do_click(client, submit_sel)
        timings['click_ms'] = round((time.monotonic() - t4) * 1000, 1)
        await asyncio.sleep(0.05)
        t5 = time.monotonic()
        img = await do_screenshot(client)
        timings['capture_ms'] = round((time.monotonic() - t5) * 1000, 1)
        save_screenshot(img, output)
        timings['total_ms'] = round((time.monotonic() - t0) * 1000, 1)
        timings['size_kb'] = round(len(img) / 1024, 1)
        print(json.dumps(timings))
    finally:
        await client.stop()
        await ws.close()


async def cmd_eval(expression: str):
    ws, client = await connect()
    try:
        await client.attach_to_first_page()
        result = await do_eval(client, expression)
        print(result)
    finally:
        await client.stop()
        await ws.close()


# ── CLI ───────────────────────────────────────────────────

def usage():
    print("""passe — fast CDP browser automation

Usage:
  passe screenshot <output.png>
  passe navigate-screenshot <url> <output.png>
  passe navigate-click-screenshot <url> <selector> <output.png>
  passe navigate-fill-click-screenshot <url> <input-sel> <value> <submit-sel> <output.png>
  passe eval <javascript-expression>

Connects to Chrome on port 9222 via raw WebSocket.
Outputs timing JSON to stdout, saves screenshot to file.
""", file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        usage()

    cmd = sys.argv[1]

    if cmd == 'screenshot' and len(sys.argv) == 3:
        asyncio.run(cmd_screenshot(sys.argv[2]))
    elif cmd == 'navigate-screenshot' and len(sys.argv) == 4:
        asyncio.run(cmd_navigate_screenshot(sys.argv[2], sys.argv[3]))
    elif cmd == 'navigate-click-screenshot' and len(sys.argv) == 5:
        asyncio.run(cmd_navigate_click_screenshot(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == 'navigate-fill-click-screenshot' and len(sys.argv) == 7:
        asyncio.run(cmd_navigate_fill_click_screenshot(
            sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]))
    elif cmd == 'eval' and len(sys.argv) == 3:
        asyncio.run(cmd_eval(sys.argv[2]))
    else:
        usage()


if __name__ == '__main__':
    main()
