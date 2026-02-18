"""
Passe — fast CDP browser automation via line DSL.

The kitchen pass: inspect everything before it goes out.

Commands:
  passe run -c 'goto URL; screenshot /tmp/out.png'
  passe run script.passe
  passe run - <<'EOF'
  passe screenshot <output.png>
  passe eval <expression>
"""

import asyncio
import base64
import json
import os
import shlex
import sys
import time
import urllib.request

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

    async def attach_to_visible_page(self) -> str:
        """Attach to the first non-chrome:// page tab. For --reuse-tab."""
        result = await self.send('Target.getTargets')
        pages = [t for t in result['result']['targetInfos']
                 if t['type'] == 'page' and not t.get('url', '').startswith('chrome://')]
        if not pages:
            # Fall back to any page tab
            pages = [t for t in result['result']['targetInfos'] if t['type'] == 'page']
        if not pages:
            raise RuntimeError('No browser tab to reuse — open a tab first')
        result = await self.send('Target.attachToTarget', {
            'targetId': pages[0]['targetId'],
            'flatten': True
        })
        self.session_id = result['result']['sessionId']
        self._owns_tab = False
        return self.session_id

    async def create_tab(self) -> str:
        """Create a fresh tab and attach to it. Caller owns the tab lifecycle."""
        created = await self.send('Target.createTarget', {
            'url': 'about:blank', 'background': True,
        })
        self._target_id = created['result']['targetId']
        result = await self.send('Target.attachToTarget', {
            'targetId': self._target_id,
            'flatten': True
        })
        self.session_id = result['result']['sessionId']
        self._owns_tab = True
        return self.session_id

    async def close_tab(self):
        """Close the tab if we created it. Safe to call during teardown."""
        if self._owns_tab and self._target_id:
            try:
                await self.send('Target.closeTarget', {'targetId': self._target_id})
            except (websockets.ConnectionClosed, asyncio.CancelledError):
                pass
            self._owns_tab = False


_cdp_override: str | None = None


def _extract_flag(args: list[str], flag: str) -> tuple[str | None, list[str]]:
    """Extract --flag value from args, return (value, remaining_args).

    Raises SystemExit if flag is present but has no value.
    """
    if flag in args:
        idx = args.index(flag)
        if idx + 1 < len(args):
            val = args[idx + 1]
            return val, args[:idx] + args[idx + 2:]
        print(f'{flag} requires an argument', file=sys.stderr)
        sys.exit(1)
    return None, args


def _cdp_base_url():
    """Get CDP base URL from --cdp flag, PASSE_CDP env var, or default to localhost:9222."""
    return _cdp_override or os.environ.get('PASSE_CDP', 'http://localhost:9222')


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


def _start_chrome(port=9222):
    """Launch Chrome with debug profile if not running. Only works locally."""
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
    print(f"Starting Chrome Debug ({os.path.basename(chrome_path)})...", file=sys.stderr)
    try:
        subprocess.Popen(
            [chrome_path,
             f'--remote-debugging-port={port}',
             '--user-data-dir=' + str(Path.home() / '.chrome-debug'),
             '--no-default-browser-check'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
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
            print("Chrome Debug started.", file=sys.stderr)
            return
        time.sleep(0.5)
    print("Failed to start Chrome Debug.", file=sys.stderr)
    sys.exit(1)


async def connect(port=9222):
    """Connect to Chrome, starting it if needed. Return (websocket, CDPClient)."""
    base_url = _cdp_base_url()
    is_remote = 'localhost' not in base_url and '127.0.0.1' not in base_url
    if not _chrome_running():
        if is_remote:
            print(
                f"Cannot connect to Chrome at {base_url}\n"
                f"Check that Chrome is running with --remote-debugging-port "
                f"or set PASSE_CDP to the correct endpoint.",
                file=sys.stderr,
            )
            sys.exit(1)
        _start_chrome(port)
    with urllib.request.urlopen(f'{base_url}/json/version', timeout=5) as resp:
        ws_url = json.loads(resp.read())['webSocketDebuggerUrl']
    # When connecting remotely, Chrome returns ws://localhost:... which won't work.
    # Rewrite the WebSocket URL to match the actual CDP endpoint.
    if is_remote:
        from urllib.parse import urlparse
        parsed_base = urlparse(base_url)
        parsed_ws = urlparse(ws_url)
        ws_url = f'ws://{parsed_base.netloc}{parsed_ws.path}'
    ws = await websockets.connect(ws_url, max_size=50 * 1024 * 1024)
    client = CDPClient(ws)
    await client.start()
    return ws, client


# ── Actions ───────────────────────────────────────────────

async def do_navigate(client: CDPClient, url: str):
    await client.send('Page.enable')
    load_fut = client.wait_for_event('Page.loadEventFired')
    nav_result = await client.send('Page.navigate', {'url': url})
    await load_fut
    # Detect navigation failure — Chrome loads chrome-error:// silently
    error_text = nav_result.get('result', {}).get('errorText')
    if error_text:
        raise RuntimeError(f'Navigation failed: {error_text} — {url}')
    # Belt-and-suspenders: check URL in case errorText wasn't set
    current_url = await do_eval(client, 'window.location.href')
    if current_url.startswith('chrome-error://'):
        raise RuntimeError(f'Navigation failed: page did not load — {url}')


async def do_back(client: CDPClient):
    result = await client.send('Page.getNavigationHistory')
    entries = result['result']['entries']
    idx = result['result']['currentIndex']
    if idx > 0:
        await client.send('Page.navigateToHistoryEntry', {'entryId': entries[idx - 1]['id']})
        await asyncio.sleep(0.1)


async def do_forward(client: CDPClient):
    result = await client.send('Page.getNavigationHistory')
    entries = result['result']['entries']
    idx = result['result']['currentIndex']
    if idx < len(entries) - 1:
        await client.send('Page.navigateToHistoryEntry', {'entryId': entries[idx + 1]['id']})
        await asyncio.sleep(0.1)


async def do_click(client: CDPClient, selector: str):
    js = f'''(() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) throw new Error('No element matches: ' + {json.dumps(selector)});
        el.click();
    }})()'''
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    if 'exceptionDetails' in result.get('result', {}):
        desc = result['result']['exceptionDetails'].get('exception', {}).get('description', '')
        raise RuntimeError(f'click failed: {desc}')


async def do_click_text(client: CDPClient, label: str):
    js = f'''(() => {{
        const label = {json.dumps(label)};
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {{
            const node = walker.currentNode;
            if (node.textContent.trim() === label) {{
                const el = node.parentElement;
                if (el && el.offsetParent !== null) {{
                    el.click();
                    return 'clicked';
                }}
            }}
        }}
        // Partial match fallback
        const walker2 = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (walker2.nextNode()) {{
            const node = walker2.currentNode;
            if (node.textContent.trim().includes(label)) {{
                const el = node.parentElement;
                if (el && el.offsetParent !== null) {{
                    el.click();
                    return 'clicked-partial';
                }}
            }}
        }}
        throw new Error('No visible element with text: ' + label);
    }})()'''
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    if 'exceptionDetails' in result.get('result', {}):
        desc = result['result']['exceptionDetails'].get('exception', {}).get('description', '')
        raise RuntimeError(f'click-text failed: {desc}')


async def do_click_if(client: CDPClient, selector: str):
    js = f'''(() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (el) {{ el.click(); return 'clicked'; }}
        return 'not-found';
    }})()'''
    await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })


async def do_fill(client: CDPClient, selector: str, value: str):
    js = f'''(() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) throw new Error('No element matches: ' + {json.dumps(selector)});
        el.value = {json.dumps(value)};
        el.dispatchEvent(new Event("input", {{bubbles: true}}));
        el.dispatchEvent(new Event("change", {{bubbles: true}}));
    }})()'''
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    if 'exceptionDetails' in result.get('result', {}):
        desc = result['result']['exceptionDetails'].get('exception', {}).get('description', '')
        raise RuntimeError(f'fill failed: {desc}')


async def do_type(client: CDPClient, selector: str, text: str):
    # Focus the element first
    js = f'''(() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) throw new Error('No element matches: ' + {json.dumps(selector)});
        el.focus();
        return true;
    }})()'''
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    if 'exceptionDetails' in result.get('result', {}):
        desc = result['result']['exceptionDetails'].get('exception', {}).get('description', '')
        raise RuntimeError(f'type focus failed: {desc}')
    # Type each character via CDP Input.insertText (matches Puppeteer).
    # dispatchKeyEvent rawKeyDown/char/keyUp dispatches events but doesn't
    # reliably insert characters. insertText triggers beforeinput + input
    # events which frameworks (React, Vue) pick up correctly.
    for char in text:
        await client.send('Input.insertText', {'text': char})
    # Auto-detect React controlled inputs: if value didn't take, use nativeInputValueSetter
    check_js = f'document.querySelector({json.dumps(selector)}).value'
    actual = await do_eval(client, check_js)
    if actual != text:
        fallback_js = f'''(() => {{
            const el = document.querySelector({json.dumps(selector)});
            const proto = el.tagName === 'TEXTAREA'
                ? window.HTMLTextAreaElement.prototype
                : window.HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
            setter.call(el, {json.dumps(text)});
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }})()'''
        await client.send('Runtime.evaluate', {
            'expression': fallback_js, 'awaitPromise': False
        })
        print(f'[type] React controlled input detected — used nativeInputValueSetter', file=sys.stderr)


async def do_select(client: CDPClient, selector: str, value: str):
    js = f'''(() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) throw new Error('No element matches: ' + {json.dumps(selector)});
        el.value = {json.dumps(value)};
        el.dispatchEvent(new Event("change", {{bubbles: true}}));
    }})()'''
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    if 'exceptionDetails' in result.get('result', {}):
        desc = result['result']['exceptionDetails'].get('exception', {}).get('description', '')
        raise RuntimeError(f'select failed: {desc}')


async def do_press(client: CDPClient, key: str):
    # Map common key names to CDP key values
    key_map = {
        'enter': ('Enter', '\r', 13),
        'tab': ('Tab', '\t', 9),
        'escape': ('Escape', '', 27),
        'backspace': ('Backspace', '', 8),
        'delete': ('Delete', '', 46),
        'arrowup': ('ArrowUp', '', 38),
        'arrowdown': ('ArrowDown', '', 40),
        'arrowleft': ('ArrowLeft', '', 37),
        'arrowright': ('ArrowRight', '', 39),
        'space': (' ', ' ', 32),
    }
    lower = key.lower()
    if lower in key_map:
        key_name, text, code = key_map[lower]
    else:
        key_name, text, code = key, key, ord(key) if len(key) == 1 else 0

    params = {'type': 'keyDown', 'key': key_name, 'windowsVirtualKeyCode': code}
    if text:
        params['text'] = text
    await client.send('Input.dispatchKeyEvent', params)
    await client.send('Input.dispatchKeyEvent', {
        'type': 'keyUp', 'key': key_name, 'windowsVirtualKeyCode': code
    })


async def do_hover(client: CDPClient, selector: str):
    js = f'''(() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) throw new Error('No element matches: ' + {json.dumps(selector)});
        const rect = el.getBoundingClientRect();
        return JSON.stringify({{x: rect.x + rect.width/2, y: rect.y + rect.height/2}});
    }})()'''
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    if 'exceptionDetails' in result.get('result', {}):
        desc = result['result']['exceptionDetails'].get('exception', {}).get('description', '')
        raise RuntimeError(f'hover failed: {desc}')
    coords = json.loads(result['result']['result']['value'])
    await client.send('Input.dispatchMouseEvent', {
        'type': 'mouseMoved', 'x': coords['x'], 'y': coords['y']
    })


async def do_scroll(client: CDPClient, x: int, y: int):
    await client.send('Runtime.evaluate', {
        'expression': f'window.scrollTo({x}, {y})',
        'awaitPromise': False
    })


async def do_screenshot(client: CDPClient, path: str = None,
                        full_page: bool = True, viewport_only: bool = False,
                        fmt: str = 'png', quality: int = None,
                        optimize_speed: bool = False) -> dict:
    """Capture screenshot. Returns dict with path, size, and timing breakdown."""
    if viewport_only:
        full_page = False

    params = {'format': fmt if fmt != 'jpg' else 'jpeg'}
    if fmt in ('jpeg', 'jpg', 'webp') and quality is not None:
        params['quality'] = quality
    if optimize_speed:
        params['optimizeForSpeed'] = True

    t0 = time.monotonic()
    if full_page:
        # Get full page dimensions
        metrics = await client.send('Runtime.evaluate', {
            'expression': 'JSON.stringify({w: document.documentElement.scrollWidth, h: Math.min(document.documentElement.scrollHeight, 16384)})',
            'awaitPromise': False
        })
        dims = json.loads(metrics['result']['result']['value'])
        params['clip'] = {
            'x': 0, 'y': 0,
            'width': dims['w'], 'height': dims['h'],
            'scale': 1
        }
        params['captureBeyondViewport'] = True

    result = await client.send('Page.captureScreenshot', params)
    capture_ms = round((time.monotonic() - t0) * 1000, 1)

    t1 = time.monotonic()
    data = base64.b64decode(result['result']['data'])
    decode_ms = round((time.monotonic() - t1) * 1000, 1)

    ext = fmt if fmt not in ('jpeg',) else 'jpg'
    if path is None:
        path = f'/tmp/passe-{int(time.time())}.{ext}'
    t2 = time.monotonic()
    with open(path, 'wb') as f:
        f.write(data)
    write_ms = round((time.monotonic() - t2) * 1000, 1)

    return {
        'file': path, 'kb': round(len(data) / 1024, 1),
        'format': params['format'],
        'breakdown': {
            'capture_ms': capture_ms, 'decode_ms': decode_ms,
            'write_ms': write_ms, 'bytes': len(data),
        },
    }


async def do_snapshot(client: CDPClient, path: str = None) -> str:
    """List interactive elements with CSS selectors."""
    js = r'''(() => {
        const results = [];
        const interactives = document.querySelectorAll(
            'a, button, input, select, textarea, [role="button"], [role="link"], ' +
            '[role="tab"], [role="menuitem"], [onclick], [tabindex]'
        );
        let idx = 0;
        for (const el of interactives) {
            // Skip invisible elements
            if (el.offsetParent === null && el.tagName !== 'BODY' &&
                getComputedStyle(el).position !== 'fixed') continue;
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 && rect.height === 0) continue;

            // Build CSS selector
            let css;
            if (el.id) {
                css = '#' + CSS.escape(el.id);
            } else if (el.name) {
                css = el.tagName.toLowerCase() + '[name=' + JSON.stringify(el.name) + ']';
            } else {
                // Positional selector
                const parent = el.parentElement;
                if (parent) {
                    const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
                    const nth = siblings.indexOf(el) + 1;
                    const parentSel = parent.id ? '#' + CSS.escape(parent.id)
                        : parent.tagName.toLowerCase();
                    css = parentSel + ' > ' + el.tagName.toLowerCase();
                    if (siblings.length > 1) css += ':nth-of-type(' + nth + ')';
                } else {
                    css = el.tagName.toLowerCase();
                }
            }

            // Element description
            const tag = el.tagName.toLowerCase();
            const type = el.type ? '[' + el.type + ']' : '';
            const name = el.getAttribute('aria-label')
                || el.getAttribute('placeholder')
                || el.textContent.trim().substring(0, 40)
                || '';

            let line = '[' + idx + '] ' + tag + type + ' "' + name + '" css=' + css;
            if (el.href) line += ' href=' + new URL(el.href, location.href).pathname;
            results.push(line);
            idx++;
        }
        return results.join('\n');
    })()'''
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    text = result['result']['result'].get('value', '')

    if path:
        with open(path, 'w') as f:
            f.write(text)
    return text


THIN_READ_THRESHOLD = 200  # chars — below this, emit diagnostic
AUTH_PATTERNS = ('sign in', 'log in', 'login', 'access denied', 'forbidden', '403', 'unauthorized', '401')


def _check_thin_read(markdown: str, html: str, page_text_length: int,
                     page_html_length: int, page_title: str) -> dict | None:
    """Check for suspiciously small extraction. Returns thin_read dict or None.

    Shared between forced-source and cascade paths so both emit diagnostics.
    Exempts legitimately small pages (high extraction ratio with real content).
    """
    if markdown is None:
        return None
    extraction_ratio = len(markdown) / page_text_length if page_text_length > 0 else 0
    page_is_just_small = extraction_ratio >= 0.5 and page_text_length >= 100
    if len(markdown) >= THIN_READ_THRESHOLD or page_is_just_small:
        return None

    word_count = len(markdown.split())
    html_lower = html.lower() if html else ''
    if any(p in html_lower for p in AUTH_PATTERNS) and 'type="password"' in html_lower:
        cause = 'auth_wall'
    elif page_text_length < 100:
        cause = 'empty_page'
    elif page_html_length > 10 * max(len(markdown), 1):
        cause = 'js_hydration'
    else:
        cause = 'unknown'

    thin_read = {
        'word_count': word_count,
        'extracted_chars': len(markdown),
        'page_text_chars': page_text_length,
        'html_chars': page_html_length,
        'title': page_title,
        'possible_cause': cause,
    }
    size_label = f'{page_html_length // 1024}KB' if page_html_length >= 1024 else f'{page_html_length}B'
    thin_msg = f'thin-read: {word_count} words extracted from {size_label} page'
    if page_title:
        thin_msg += f' (title: "{page_title}")'
    thin_msg += f' — possible {cause.replace("_", " ")}'
    print(f'[read] {thin_msg}', file=sys.stderr)
    return thin_read


RAW_CONTENT_TYPES = frozenset({
    'application/json',
    'application/xml', 'text/xml',
    'text/plain',
    'text/csv',
    'application/x-yaml', 'text/yaml',
})


async def do_read(client: CDPClient, path: str = None, force_source: str = None) -> dict:
    """Extract page content as markdown.

    Cascade: trafilatura (Python-side) → Readability.js+Turndown (browser-side) → innerText.
    force_source: 'trafilatura', 'readability', 'innertext', or 'raw' — skip cascade.
    Returns dict with 'markdown', optional 'warning', and 'source'.
    """
    # Content-type sniffing: bypass extraction for structured data (JSON, XML, etc.)
    content_type = await do_eval(client, 'document.contentType')
    mime = (content_type or '').split(';')[0].strip().lower()

    if force_source == 'raw' or (force_source is None and mime in RAW_CONTENT_TYPES):
        raw_text = await do_eval(client, 'document.body.innerText')
        # Pretty-print JSON
        if 'json' in mime:
            try:
                raw_text = json.dumps(json.loads(raw_text), indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass  # Return as-is if not valid JSON
        print(f'[read] content-type: {mime} — raw passthrough', file=sys.stderr)
        print(f'[read] source: raw', file=sys.stderr)
        if path:
            with open(path, 'w') as f:
                f.write(raw_text)
        return {'markdown': raw_text, 'source': 'raw', 'content_type': mime}

    # Get page HTML (with shadow DOM flattened) and metadata from Chrome.
    from ._libs import SHADOW_FLATTEN_JS
    html = await do_eval(client, SHADOW_FLATTEN_JS)
    meta_raw = await do_eval(
        client,
        'JSON.stringify({textLength: document.body.innerText.length,'
        ' htmlLength: document.documentElement.outerHTML.length,'
        ' title: document.title, url: window.location.href})'
    )
    meta = json.loads(meta_raw)
    page_text_length = meta.get('textLength', 0)
    page_html_length = meta.get('htmlLength', 0)
    page_title = meta.get('title', '')
    page_url = meta.get('url', '')

    markdown = None
    source = None
    warning = None

    # Forced source — skip cascade, use only the specified extractor
    if force_source:
        fs = force_source.lower()
        if fs == 'trafilatura':
            try:
                import trafilatura
                markdown = trafilatura.extract(
                    html, url=page_url,
                    include_formatting=True, include_links=True, include_tables=True,
                ) or ''
                source = 'trafilatura'
            except Exception as exc:
                markdown = ''
                source = 'trafilatura'
                warning = f'trafilatura failed: {exc}'
        elif fs == 'readability':
            from ._libs import READABILITY_JS, TURNDOWN_JS, EXTRACT_JS
            combined = READABILITY_JS + ';\n' + TURNDOWN_JS + ';\n' + EXTRACT_JS
            result = await client.send('Runtime.evaluate', {
                'expression': combined, 'awaitPromise': False
            })
            raw = result['result']['result'].get('value', '{}')
            data = json.loads(raw)
            markdown = data.get('markdown', '')
            source = 'readability' if not data.get('fallback') else 'innerText'
            if data.get('fallback'):
                warning = 'Readability returned no article — output is innerText'
        elif fs == 'innertext':
            text = await do_eval(client, 'document.body.innerText')
            markdown = text or ''
            source = 'innerText'
        else:
            markdown = ''
            source = 'unknown'
            warning = f'Unknown source: {force_source}. Use trafilatura, readability, or innertext.'

        # Thin-read diagnostics (shared with cascade path)
        thin_read = _check_thin_read(markdown, html, page_text_length,
                                     page_html_length, page_title)
        if thin_read and not warning:
            word_count = thin_read['word_count']
            cause = thin_read['possible_cause']
            size_label = f'{page_html_length // 1024}KB' if page_html_length >= 1024 else f'{page_html_length}B'
            warning = f'thin-read: {word_count} words extracted from {size_label} page'
            if page_title:
                warning += f' (title: "{page_title}")'
            warning += f' — possible {cause.replace("_", " ")}'

        if warning:
            print(f'[read] warning: {warning}', file=sys.stderr)
        print(f'[read] source: {source}', file=sys.stderr)
        if path:
            with open(path, 'w') as f:
                f.write(markdown)
        result = {'markdown': markdown, 'warning': warning, 'source': source,
                  'title': page_title}
        if thin_read:
            result['thin_read'] = thin_read
        return result

    # Stage 1: trafilatura — Python-side extraction from rendered HTML
    try:
        import trafilatura
        extracted = trafilatura.extract(
            html, url=page_url,
            include_formatting=True, include_links=True, include_tables=True,
        )
        if extracted and (page_text_length == 0 or len(extracted) / page_text_length >= 0.10):
            markdown = extracted
            source = 'trafilatura'
    except ImportError:
        print('[read] trafilatura not installed — falling back to Readability', file=sys.stderr)
    except Exception as exc:
        print(f'[read] trafilatura failed: {exc} — falling back to Readability', file=sys.stderr)

    gate_rejected_markdown = None  # stash if gate rejects — better than innerText

    # Stage 1.5: Structural quality gate — detect table/code-block loss.
    # Trafilatura can pass the 10% text ratio check but strip critical structure.
    # Thresholds (empirical, tested against ISO-3166-1, Python docs, Wikipedia):
    #   - Binary:        page >= 5 data rows, output has 0 table markers → reject
    #   - Proportional:  page >= 10 data rows, output < 25% of page rows → reject
    #   - Code binary:   page >= 2 long <pre> blocks, output has 0 fences → reject
    #   - Code proportional: page >= 5 long <pre> blocks, output < 25% → reject
    #   - Skip DOM eval: output has 20+ table rows AND 5+ code fences (clearly preserved)
    if source == 'trafilatura':
        import re
        # Count pipe-table data rows (exclude separator rows like |---|---|)
        output_table_rows = len(re.findall(r'^\|.*\w.*\|', markdown, re.MULTILINE))
        output_code_blocks = len(re.findall(r'^```', markdown, re.MULTILINE)) // 2

        # Only query DOM when output might be missing structure
        if output_table_rows < 20 or output_code_blocks < 5:
            dom_raw = await do_eval(client, (
                'JSON.stringify({dataRows:[...document.querySelectorAll("tr")]'
                '.filter(r=>r.querySelectorAll("td").length>=2).length,'
                'codeBlocks:[...document.querySelectorAll("pre")]'
                '.filter(e=>e.textContent.length>50).length})'
            ))
            dom = json.loads(dom_raw)
            lost = []
            page_rows = dom.get('dataRows', 0)
            # Binary check: page has tables, output has none
            if output_table_rows == 0 and page_rows >= 5:
                lost.append(f'{page_rows} table rows')
            # Proportional check: big table mostly stripped
            elif page_rows >= 10 and output_table_rows < page_rows * 0.25:
                lost.append(f'{page_rows} table rows (got {output_table_rows})')
            page_code = dom.get('codeBlocks', 0)
            # Binary check: page has code blocks, output has none
            if output_code_blocks == 0 and page_code >= 2:
                lost.append(f'{page_code} code blocks')
            # Proportional check: many code blocks mostly stripped
            elif page_code >= 5 and output_code_blocks < page_code * 0.25:
                lost.append(f'{page_code} code blocks (got {output_code_blocks})')

            if lost:
                print(
                    f'[read] quality gate: trafilatura dropped {", ".join(lost)}'
                    ' — falling to Readability', file=sys.stderr
                )
                gate_rejected_markdown = markdown
                markdown = None
                source = None

    # Stage 2: Readability.js + Turndown — browser-side extraction
    if markdown is None:
        from ._libs import READABILITY_JS, TURNDOWN_JS, EXTRACT_JS
        combined = READABILITY_JS + ';\n' + TURNDOWN_JS + ';\n' + EXTRACT_JS
        result = await client.send('Runtime.evaluate', {
            'expression': combined, 'awaitPromise': False
        })
        raw = result['result']['result'].get('value', '{}')
        data = json.loads(raw)
        md = data.get('markdown', '')

        if data.get('fallback'):
            # Stage 3: Readability failed — prefer gate-rejected trafilatura over innerText
            if gate_rejected_markdown:
                markdown = gate_rejected_markdown
                source = 'trafilatura'
                warning = 'Readability also failed — kept trafilatura output (missing some structure)'
            else:
                markdown = md
                source = 'innerText'
                warning = 'trafilatura and Readability both failed — fell back to innerText'
        elif md:
            markdown = md
            source = 'readability'
        else:
            markdown = ''
            source = 'innerText'
            warning = 'All extractors returned empty'

    # Ratio warning for trafilatura/readability paths
    if source in ('trafilatura', 'readability') and page_text_length > 0 and markdown:
        ratio = len(markdown) / page_text_length
        if ratio < 0.10:
            pct = round(ratio * 100, 1)
            warning = f'Extraction looks incomplete — got {pct}% of page text ({len(markdown)}/{page_text_length} chars)'

    # Thin-read diagnostics (shared helper — also used by forced-source path above)
    thin_read = _check_thin_read(markdown, html, page_text_length,
                                 page_html_length, page_title)
    if thin_read and not warning:
        word_count = thin_read['word_count']
        cause = thin_read['possible_cause']
        size_label = f'{page_html_length // 1024}KB' if page_html_length >= 1024 else f'{page_html_length}B'
        warning = f'thin-read: {word_count} words extracted from {size_label} page'
        if page_title:
            warning += f' (title: "{page_title}")'
        warning += f' — possible {cause.replace("_", " ")}'

    if warning:
        print(f'[read] warning: {warning}', file=sys.stderr)
    print(f'[read] source: {source}', file=sys.stderr)

    if path:
        with open(path, 'w') as f:
            f.write(markdown)

    result = {'markdown': markdown, 'warning': warning, 'source': source, 'title': page_title}
    if thin_read:
        result['thin_read'] = thin_read
    return result


async def do_fetch(client: CDPClient, url: str, path: str = None,
                   force_source: str = None) -> dict:
    """Compound verb: goto + auto-wait + read in one step.
    Returns read result dict with added nav_ms, wait_ms, read_ms, timed_out."""
    t0 = time.monotonic()
    await do_navigate(client, url)
    nav_ms = round((time.monotonic() - t0) * 1000, 1)

    t1 = time.monotonic()
    stable = await do_wait_stable(client)
    wait_ms = round((time.monotonic() - t1) * 1000, 1)

    t2 = time.monotonic()
    result = await do_read(client, path, force_source=force_source)
    read_ms = round((time.monotonic() - t2) * 1000, 1)

    result['nav_ms'] = nav_ms
    result['wait_ms'] = wait_ms
    result['read_ms'] = read_ms
    if not stable:
        result['timed_out'] = True
    return result


async def do_device(client: CDPClient, name: str, dpr_override: float = None):
    """Apply device emulation preset. Fires 3-4 CDP calls."""
    from ._devices import get_device
    dev = get_device(name)
    dpr = dpr_override if dpr_override is not None else dev['deviceScaleFactor']

    # Viewport + DPR + mobile flag
    metrics = {
        'width': dev['width'], 'height': dev['height'],
        'deviceScaleFactor': dpr, 'mobile': dev['mobile'],
    }
    if dev.get('orientation'):
        metrics['screenOrientation'] = dev['orientation']
    await client.send('Emulation.setDeviceMetricsOverride', metrics)

    # User agent + platform
    ua_params = {}
    if dev['userAgent']:
        ua_params['userAgent'] = dev['userAgent']
    if dev['platform']:
        ua_params['platform'] = dev['platform']
    if ua_params:
        await client.send('Emulation.setUserAgentOverride', ua_params)

    # Touch emulation
    await client.send('Emulation.setTouchEmulationEnabled', {
        'enabled': dev['touch'],
        'maxTouchPoints': dev['maxTouchPoints'],
    })

    # Safe area insets (notch, dynamic island) — requires Chrome 108+
    if dev.get('safeArea'):
        try:
            await client.send('Emulation.setSafeAreaInsetsOverride', {
                'insets': dev['safeArea'],
            })
        except Exception:
            pass  # Older Chrome — safe area emulation unavailable

    print(f'[device] {name}: {dev["width"]}x{dev["height"]}@{dpr}x', file=sys.stderr)


async def do_viewport(client: CDPClient, width: int, height: int):
    await client.send('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': height,
        'deviceScaleFactor': 1, 'mobile': width < 768
    })


async def do_wait_for(client: CDPClient, selector: str, timeout_ms: int = 10000):
    """Poll for selector until visible or timeout."""
    js = f'''document.querySelector({json.dumps(selector)}) !== null'''
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        result = await client.send('Runtime.evaluate', {
            'expression': js, 'awaitPromise': False
        })
        if result['result']['result'].get('value') is True:
            return
        await asyncio.sleep(0.1)
    raise RuntimeError(f'wait-for timed out after {timeout_ms}ms: {selector}')


async def do_wait_navigation(client: CDPClient):
    await client.send('Page.enable')
    await client.wait_for_event('Page.loadEventFired', timeout=15.0)


async def do_wait_stable(client: CDPClient, timeout_ms: int = 2000) -> bool:
    """Wait for DOM stability before extraction. Returns True if stable, False if timed out.

    Dual-signal polling: element count (structure) + text length (content).
    Both must be unchanged across two polls 100ms apart to declare stability.
    Catches both structural changes (new elements appearing) and content-only
    changes (text filling existing empty elements during hydration).
    """
    probe_js = ('JSON.stringify([document.getElementsByTagName("*").length,'
                'document.body.textContent.length])')
    prev = None
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            raw = await do_eval(client, probe_js)
            cur = json.loads(raw)
        except (ValueError, RuntimeError):
            cur = None
        if prev is not None and cur == prev:
            return True
        prev = cur
        await asyncio.sleep(0.1)
    print(
        f'[read] auto-wait: timed out after {timeout_ms}ms'
        ' (page may have continuous mutations)', file=sys.stderr
    )
    return False


async def do_eval(client: CDPClient, expression: str) -> str:
    result = await client.send('Runtime.evaluate', {
        'expression': expression, 'awaitPromise': True
    })
    r = result.get('result', {}).get('result', {})
    if 'exceptionDetails' in result.get('result', {}):
        desc = result['result']['exceptionDetails'].get('exception', {}).get('description', '')
        raise RuntimeError(f'eval failed: {desc}')
    return str(r.get('value', r.get('description', '')))


async def do_eval_to(client: CDPClient, path: str, expression: str) -> str:
    result = await do_eval(client, expression)
    with open(path, 'w') as f:
        f.write(result)
    return result


async def do_eval_file(client: CDPClient, js_path: str) -> str:
    """Read JS from a file and evaluate it. Avoids single-line minification."""
    with open(js_path) as f:
        expression = f.read()
    return await do_eval(client, expression)


async def do_eval_file_to(client: CDPClient, out_path: str, js_path: str) -> str:
    result = await do_eval_file(client, js_path)
    with open(out_path, 'w') as f:
        f.write(result)
    return result


async def do_assert(client: CDPClient, expression: str):
    result = await client.send('Runtime.evaluate', {
        'expression': expression, 'awaitPromise': True
    })
    r = result.get('result', {}).get('result', {})
    value = r.get('value', r.get('description', ''))
    if not value:
        raise RuntimeError(f'Assertion failed: {expression} (got {value!r})')


async def do_watch(client: CDPClient, path: str, fast: bool = True,
                   debounce_ms: int = 100, cooldown_ms: int = 1000):
    """Watch for HMR updates and auto-screenshot. Runs until cancelled.

    Listens for Vite's console messages:
      - '[vite] hot updated' → debounce + screenshot
      - '[vite] page reload' → wait for load event + screenshot
      - '[vite] connected'   → ignored (initial connection)

    Also catches DOM mutations (Tailwind CSS rebuild) via a MutationObserver
    fallback that fires a console.log we can detect.

    cooldown_ms is the minimum interval between captures, independent of debounce.
    Prevents screenshot storms on pages with animations or continuous updates.
    """
    # Enable console event streaming
    await client.send('Runtime.enable')
    queue = client.subscribe('Runtime.consoleAPICalled')

    # Install MutationObserver for changes that don't trigger HMR console messages
    # (e.g. Tailwind rebuilds injected via <style> tags)
    await client.send('Runtime.evaluate', {
        'expression': '''(() => {
            let _watchTimer = null;
            new MutationObserver(() => {
                clearTimeout(_watchTimer);
                _watchTimer = setTimeout(() => console.log('[passe-watch] mutation'), 150);
            }).observe(document.documentElement, {childList: true, subtree: true, attributes: true});
        })()''',
        'awaitPromise': False,
    })

    capture_count = 0
    suppressed_count = 0
    last_capture_time = 0.0  # monotonic timestamp of last screenshot
    cooldown_sec = cooldown_ms / 1000
    _trailing_task: asyncio.Task | None = None
    print(json.dumps({'event': 'watch_started', 'path': path, 'fast': fast,
                      'cooldown_ms': cooldown_ms}),
          file=sys.stderr)

    async def _do_capture(event_type: str):
        """Actually take a screenshot and log it."""
        nonlocal capture_count, suppressed_count, last_capture_time
        t0 = time.monotonic()
        info = await do_screenshot(
            client, path, viewport_only=True,
            fmt='jpeg' if fast else 'png',
            quality=70 if fast else None,
            optimize_speed=fast,
        )
        ms = round((time.monotonic() - t0) * 1000, 1)
        last_capture_time = time.monotonic()
        capture_count += 1
        log_entry = {
            'event': event_type, 'n': capture_count,
            'screenshot_ms': ms, 'kb': info['kb'],
            'file': info['file'],
        }
        if suppressed_count > 0:
            log_entry['suppressed_since_last'] = suppressed_count
            suppressed_count = 0
        print(json.dumps(log_entry), file=sys.stderr)

    async def _trailing_capture(delay: float, event_type: str):
        """Wait for remaining cooldown, then capture the final state."""
        await asyncio.sleep(delay)
        await _do_capture(event_type)

    async def _capture(event_type: str):
        """Leading + trailing: capture immediately if cooldown ok,
        otherwise schedule a trailing capture for when cooldown expires."""
        nonlocal suppressed_count, _trailing_task
        now = time.monotonic()
        elapsed = now - last_capture_time
        if elapsed < cooldown_sec:
            suppressed_count += 1
            # Schedule trailing capture if not already pending
            if _trailing_task is None or _trailing_task.done():
                remaining = cooldown_sec - elapsed
                _trailing_task = asyncio.create_task(
                    _trailing_capture(remaining, event_type))
            return

        # Cancel any pending trailing — we're capturing now
        if _trailing_task and not _trailing_task.done():
            _trailing_task.cancel()
        await _do_capture(event_type)

    try:
        while True:
            msg = await queue.get()
            # Extract console message text
            params = msg.get('params', {})
            call_args = params.get('args', [])
            if not call_args:
                continue
            text = call_args[0].get('value', '')
            if not isinstance(text, str):
                continue

            # Classify the event
            if '[vite] hot updated' in text or '[passe-watch] mutation' in text:
                # Debounce: drain any queued events within the window
                await asyncio.sleep(debounce_ms / 1000)
                drained = 0
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        drained += 1
                    except asyncio.QueueEmpty:
                        break

                event_type = 'hmr' if '[vite]' in text else 'mutation'
                await _capture(event_type)
                # Drained events mean the page was still changing — schedule
                # trailing capture to get the final state after cooldown
                if drained > 0:
                    suppressed_count += drained
                    if _trailing_task is None or _trailing_task.done():
                        _trailing_task = asyncio.create_task(
                            _trailing_capture(cooldown_sec, event_type))

            elif '[vite] page reload' in text:
                # Full reload — wait for load event first
                try:
                    await client.wait_for_event('Page.loadEventFired', timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                await asyncio.sleep(debounce_ms / 1000)
                await _capture('reload')

    except asyncio.CancelledError:
        pass
    finally:
        if _trailing_task and not _trailing_task.done():
            _trailing_task.cancel()
        client.unsubscribe('Runtime.consoleAPICalled')
        print(json.dumps({
            'event': 'watch_stopped', 'total_captures': capture_count,
        }), file=sys.stderr)


# ── Script engine ─────────────────────────────────────────

# eval/assert/log take the raw rest-of-line as a single argument — no shlex
# quote stripping. This is intentional: `eval document.querySelector("h1")`
# must preserve the JS quotes. shlex would strip them, turning "h1" into h1
# which V8 interprets as a variable reference, not a string literal.
RAW_REST_VERBS = {'eval', 'assert', 'log'}
RAW_REST_AFTER_PATH_VERBS = {'eval-to'}


def split_inline(text: str) -> str:
    """Split inline -c text on '; ' but only when followed by a known verb.

    Plain replace(';', newline) destroys semicolons inside JS expressions.
    This verb-aware split keeps JS intact:
      'goto URL; eval var x = 1; x'  →  two lines, not three
    """
    parts = text.split('; ')
    if len(parts) <= 1:
        return text

    lines = [parts[0]]
    for part in parts[1:]:
        first_word = part.split(None, 1)[0].lower() if part.strip() else ''
        if first_word in KNOWN_VERBS:
            lines.append(part)
        else:
            # Not a verb — this semicolon was inside an expression, rejoin
            lines[-1] += '; ' + part
    return '\n'.join(lines)


def parse_script(text: str) -> list[tuple[str, list[str]]]:
    """Parse script text into list of (verb, args) tuples."""
    steps = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Split verb from rest, preserving raw text for expression verbs
        parts = line.split(None, 1)
        if not parts:
            continue
        verb = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ''

        if verb in RAW_REST_VERBS:
            # eval, assert, log: entire rest is a single raw argument
            args = [rest] if rest else []
        elif verb in RAW_REST_AFTER_PATH_VERBS:
            # eval-to: first arg is path (shlex), rest is raw expression
            sub_parts = rest.split(None, 1)
            if len(sub_parts) >= 2:
                args = [sub_parts[0], sub_parts[1]]
            elif sub_parts:
                args = [sub_parts[0]]
            else:
                args = []
        else:
            # Standard verbs: full shlex parsing
            try:
                all_parts = shlex.split(line)
            except ValueError:
                all_parts = line.split()
            args = all_parts[1:] if len(all_parts) > 1 else []

        steps.append((verb, args))
    return steps


KNOWN_VERBS = {
    'goto', 'click', 'click-text', 'click-if', 'fill', 'type', 'select',
    'press', 'hover', 'scroll', 'screenshot', 'snapshot', 'read', 'fetch',
    'viewport', 'device', 'watch', 'wait', 'wait-for', 'wait-navigation',
    'back', 'forward', 'eval', 'eval-to', 'eval-file', 'eval-file-to',
    'assert', 'log',
}

# Verbs that trigger auto-wait in the next read/fetch step.
# Keep near KNOWN_VERBS so new navigation verbs don't get forgotten.
NAV_VERBS = {'goto', 'back', 'forward'}


async def run_script(client: CDPClient, steps: list[tuple[str, list[str]]]) -> dict:
    """Execute parsed script steps. Returns summary dict."""
    total_t0 = time.monotonic()
    files = []
    ok = True
    failed_at = None
    fail_verb = None
    fail_error = None

    prev_verb = None

    for i, (verb, args) in enumerate(steps):
        if verb not in KNOWN_VERBS:
            ok = False
            failed_at = i
            fail_verb = verb
            fail_error = f'Unknown verb: {verb}'
            step_info = {'i': i, 'verb': verb, 'error': fail_error}
            print(json.dumps(step_info), file=sys.stderr)
            break

        t0 = time.monotonic()
        step_info = {'i': i, 'verb': verb}

        try:
            if verb == 'goto':
                await do_navigate(client, args[0])
            elif verb == 'click':
                await do_click(client, args[0])
            elif verb == 'click-text':
                await do_click_text(client, args[0])
            elif verb == 'click-if':
                await do_click_if(client, args[0])
            elif verb == 'fill':
                await do_fill(client, args[0], args[1])
            elif verb == 'type':
                await do_type(client, args[0], args[1])
            elif verb == 'select':
                await do_select(client, args[0], args[1])
            elif verb == 'press':
                await do_press(client, args[0])
            elif verb == 'hover':
                await do_hover(client, args[0])
            elif verb == 'scroll':
                await do_scroll(client, int(args[0]), int(args[1]))
            elif verb == 'screenshot':
                ss_args = list(args)
                # Parse screenshot flags
                viewport_only = '--viewport' in ss_args
                fast = '--fast' in ss_args
                ss_args = [a for a in ss_args if a not in ('--viewport', '--fast')]
                ss_fmt = 'png'
                ss_quality = None
                ss_optimize = False
                if '--format' in ss_args:
                    idx = ss_args.index('--format')
                    if idx + 1 < len(ss_args):
                        ss_fmt = ss_args[idx + 1]
                        del ss_args[idx:idx + 2]
                if '--quality' in ss_args:
                    idx = ss_args.index('--quality')
                    if idx + 1 < len(ss_args):
                        ss_quality = int(ss_args[idx + 1])
                        del ss_args[idx:idx + 2]
                if fast:
                    ss_fmt = 'jpeg'
                    ss_quality = ss_quality or 70
                    ss_optimize = True
                    viewport_only = True
                if prev_verb == 'scroll' and not viewport_only:
                    print(
                        '[screenshot] hint: screenshot is full-page by default'
                        ' (max 16384px) — scroll before screenshot is usually'
                        ' unnecessary', file=sys.stderr,
                    )
                path = ss_args[0] if ss_args else None
                info = await do_screenshot(
                    client, path, viewport_only=viewport_only,
                    fmt=ss_fmt, quality=ss_quality, optimize_speed=ss_optimize,
                )
                step_info['file'] = info['file']
                step_info['kb'] = info['kb']
                step_info['format'] = info['format']
                step_info['breakdown'] = info['breakdown']
                files.append(info['file'])
            elif verb == 'snapshot':
                path = args[0] if args else None
                text = await do_snapshot(client, path)
                if path:
                    files.append(path)
                else:
                    step_info['result'] = text[:200]
            elif verb == 'read':
                read_args = list(args)
                force_source = None
                no_wait = '--no-wait' in read_args
                if no_wait:
                    read_args.remove('--no-wait')
                if '--source' in read_args:
                    idx = read_args.index('--source')
                    if idx + 1 < len(read_args):
                        force_source = read_args[idx + 1]
                        del read_args[idx:idx + 2]
                    else:
                        del read_args[idx]
                # Auto-wait: if previous verb was navigation, wait for DOM stability
                if not no_wait and prev_verb in NAV_VERBS:
                    t_wait = time.monotonic()
                    stable = await do_wait_stable(client)
                    wait_ms = round((time.monotonic() - t_wait) * 1000, 1)
                    step_info['auto_wait_ms'] = wait_ms
                    if not stable:
                        step_info['auto_wait_timed_out'] = True
                    print(f'[read] auto-wait: {wait_ms}ms', file=sys.stderr)
                path = read_args[0] if read_args else None
                read_result = await do_read(client, path, force_source=force_source)
                if path:
                    files.append(path)
                else:
                    step_info['result'] = read_result['markdown'][:200]
                if read_result.get('warning'):
                    step_info['warning'] = read_result['warning']
                if read_result.get('source'):
                    step_info['source'] = read_result['source']
                if read_result.get('content_type'):
                    step_info['content_type'] = read_result['content_type']
                if read_result.get('thin_read'):
                    step_info['thin_read'] = read_result['thin_read']
                if read_result.get('title'):
                    step_info['title'] = read_result['title']
            elif verb == 'fetch':
                fetch_args = list(args)
                force_source = None
                if '--source' in fetch_args:
                    idx = fetch_args.index('--source')
                    if idx + 1 < len(fetch_args):
                        force_source = fetch_args[idx + 1]
                        del fetch_args[idx:idx + 2]
                    else:
                        del fetch_args[idx]
                url = fetch_args[0]
                path = fetch_args[1] if len(fetch_args) > 1 else None
                if path is None:
                    import tempfile
                    fd, path = tempfile.mkstemp(suffix='.md', prefix='passe-fetch-')
                    os.close(fd)
                read_result = await do_fetch(client, url, path, force_source=force_source)
                files.append(path)
                step_info['file'] = path
                step_info['final_url'] = await do_eval(client, 'window.location.href')
                step_info['nav_ms'] = read_result.get('nav_ms')
                step_info['wait_ms'] = read_result.get('wait_ms')
                step_info['read_ms'] = read_result.get('read_ms')
                if read_result.get('timed_out'):
                    step_info['auto_wait_timed_out'] = True
                if read_result.get('warning'):
                    step_info['warning'] = read_result['warning']
                if read_result.get('source'):
                    step_info['source'] = read_result['source']
                if read_result.get('content_type'):
                    step_info['content_type'] = read_result['content_type']
                if read_result.get('thin_read'):
                    step_info['thin_read'] = read_result['thin_read']
                if read_result.get('title'):
                    step_info['title'] = read_result['title']
            elif verb == 'viewport':
                await do_viewport(client, int(args[0]), int(args[1]))
            elif verb == 'device':
                dev_args = list(args)
                dpr_override = None
                if '--dpr' in dev_args:
                    idx = dev_args.index('--dpr')
                    if idx + 1 < len(dev_args):
                        dpr_override = float(dev_args[idx + 1])
                        del dev_args[idx:idx + 2]
                await do_device(client, dev_args[0], dpr_override=dpr_override)
            elif verb == 'watch':
                # watch is a blocking verb — runs until killed. Must be last.
                w_args = list(args)
                w_fast = '--fast' in w_args
                w_args = [a for a in w_args if a != '--fast']
                w_cooldown = 1000
                if '--cooldown' in w_args:
                    idx = w_args.index('--cooldown')
                    if idx + 1 < len(w_args):
                        w_cooldown = int(w_args[idx + 1])
                        del w_args[idx:idx + 2]
                w_path = w_args[0] if w_args else '/tmp/passe-watch.jpg'
                await do_watch(client, w_path, fast=w_fast, cooldown_ms=w_cooldown)
                # do_watch only returns on cancellation — skip remaining steps
                break
            elif verb == 'wait':
                await asyncio.sleep(int(args[0]) / 1000)
            elif verb == 'wait-for':
                timeout = int(args[1]) if len(args) > 1 else 10000
                await do_wait_for(client, args[0], timeout)
            elif verb == 'wait-navigation':
                await do_wait_navigation(client)
            elif verb == 'back':
                await do_back(client)
            elif verb == 'forward':
                await do_forward(client)
            elif verb == 'eval':
                result = await do_eval(client, args[0])
                step_info['result'] = str(result)
            elif verb == 'eval-to':
                await do_eval_to(client, args[0], args[1])
                files.append(args[0])
            elif verb == 'eval-file':
                result = await do_eval_file(client, args[0])
                step_info['result'] = str(result)[:200]
            elif verb == 'eval-file-to':
                await do_eval_file_to(client, args[0], args[1])
                files.append(args[0])
            elif verb == 'assert':
                await do_assert(client, args[0])
            elif verb == 'log':
                print(f'[log] {args[0]}', file=sys.stderr)

            step_info['ms'] = round((time.monotonic() - t0) * 1000, 1)
            prev_verb = verb

        except Exception as e:
            step_info['ms'] = round((time.monotonic() - t0) * 1000, 1)
            step_info['error'] = str(e)
            ok = False
            failed_at = i
            fail_verb = verb
            fail_error = str(e)
            print(json.dumps(step_info), file=sys.stderr)
            break

        print(json.dumps(step_info), file=sys.stderr)

    total_ms = round((time.monotonic() - total_t0) * 1000, 1)
    summary = {
        'ok': ok,
        'steps': (failed_at + 1) if failed_at is not None else len(steps),
        'total_ms': total_ms,
    }
    if files:
        summary['files'] = files
    if not ok:
        summary['failed_at'] = failed_at
        summary['verb'] = fail_verb
        summary['error'] = fail_error

    # Capture final URL (post-redirect) before the tab is closed.
    # Best effort — don't fail the run for this.
    try:
        summary['final_url'] = await do_eval(client, 'window.location.href')
    except Exception:
        pass

    return summary


# ── CLI commands ──────────────────────────────────────────

async def cmd_run(source: str, inline: str = None,
                  keep_tab: bool = False, reuse_tab: bool = False,
                  device: str = None, dpr: float = None):
    """Run a passe script from file, stdin, or inline."""
    # --reuse-tab implies --keep-tab (don't close someone else's tab)
    if reuse_tab:
        keep_tab = True

    # Parse the script text
    if inline:
        # -c 'verb arg; verb arg' — verb-aware split preserves JS semicolons
        text = split_inline(inline)
    elif source == '-':
        text = sys.stdin.read()
    else:
        with open(source) as f:
            text = f.read()

    steps = parse_script(text)
    if not steps:
        print(json.dumps({'ok': True, 'steps': 0, 'total_ms': 0}))
        return

    ws, client = await connect()
    try:
        if reuse_tab:
            await client.attach_to_visible_page()
        else:
            await client.create_tab()
        await client.send('Page.enable')
        # Apply device preset before script if --device flag used
        if device:
            await do_device(client, device, dpr_override=dpr)
        summary = await run_script(client, steps)
        print(json.dumps(summary))
        sys.exit(0 if summary['ok'] else 1)
    finally:
        if not keep_tab:
            await client.close_tab()
        await client.stop()
        await ws.close()


async def cmd_screenshot(args: list[str], device: str = None, dpr: float = None):
    """Atomic screenshot of current page. Parses --fast, --viewport, --format, --quality."""
    fast = '--fast' in args
    viewport_only = '--viewport' in args
    args = [a for a in args if a not in ('--fast', '--viewport')]
    fmt = 'png'
    quality = None
    optimize = False
    if '--format' in args:
        idx = args.index('--format')
        if idx + 1 < len(args):
            fmt = args[idx + 1]
            del args[idx:idx + 2]
    if '--quality' in args:
        idx = args.index('--quality')
        if idx + 1 < len(args):
            quality = int(args[idx + 1])
            del args[idx:idx + 2]
    if fast:
        fmt = 'jpeg'
        quality = quality or 70
        optimize = True
        viewport_only = True
    output = args[0] if args else None
    ws, client = await connect()
    try:
        await client.attach_to_first_page()
        if device:
            await do_device(client, device, dpr_override=dpr)
        info = await do_screenshot(client, output, viewport_only=viewport_only,
                                   fmt=fmt, quality=quality, optimize_speed=optimize)
        print(json.dumps({
            'ok': True, 'file': info['file'], 'kb': info['kb'],
            'format': info['format'],
        }))
    finally:
        await client.stop()
        await ws.close()


async def cmd_eval(expression: str):
    """Atomic JS eval on current page."""
    ws, client = await connect()
    try:
        await client.attach_to_first_page()
        result = await do_eval(client, expression)
        print(result)
    finally:
        await client.stop()
        await ws.close()


def cmd_devices():
    """Print available device presets as a table."""
    from ._devices import DEVICES
    print(f'{"Name":<16} {"Size":>11}  {"DPR":>6}  {"Type":<7}')
    print(f'{"─" * 16} {"─" * 11}  {"─" * 6}  {"─" * 7}')
    for name, dev in DEVICES.items():
        size = f'{dev["width"]}×{dev["height"]}'
        dpr_num = dev["deviceScaleFactor"]
        dpr = f'{int(dpr_num)}x' if dpr_num == int(dpr_num) else f'{dpr_num}x'
        kind = 'mobile' if dev['mobile'] else 'desktop'
        print(f'{name:<16} {size:>11}  {dpr:>6}  {kind:<7}')


# ── Entry point ───────────────────────────────────────────

USAGE = """\
passe — fast CDP browser automation

Commands:
  passe run -c 'verbs...'         Run inline script
  passe run script.passe          Run script file
  passe run - <<'EOF' ... EOF     Run from stdin
  passe screenshot [flags] <out>  Screenshot current page
  passe eval <expression>         Eval JS on current page
  passe devices                   List available device presets

Global flags:
  --cdp <url>       CDP endpoint (default: PASSE_CDP env or http://localhost:9222)
  --device <name>   Device emulation preset (e.g. "iPhone 14 Pro")
  --dpr <n>         Override device pixel ratio

Run flags:
  --keep-tab        Keep tab open after script
  --reuse-tab       Attach to existing visible tab (implies --keep-tab)

Screenshot flags:
  --fast            JPEG q70, viewport-only, optimizeForSpeed
  --viewport        Viewport only (default is full-page)
  --format <fmt>    png, jpeg, or webp (default: png)
  --quality <n>     0-100, for jpeg/webp

Use 'passe run --help' for the verb reference.
"""

RUN_HELP = """\
passe run — DSL verb reference

Navigation:
  goto <url>                Navigate and wait for load
  back / forward            Browser history

Interaction:
  click <selector>          CSS selector click
  click-text <"label">      Find by visible text, click
  click-if <selector>       Click if exists, silently skip if not
  type <selector> <text>    Character-by-character input (works with React)
  fill <selector> <value>   Set value directly (plain HTML forms only)
  select <selector> <value> Dropdown selection
  press <key>               Keypress (Enter, Tab, Escape, etc.)
  hover <selector>          Mouseover event

Observation:
  screenshot [flags] [path] Full-page by default (entire document, max 16384px — no need to scroll).
                            --viewport for visible area only. Flags: --fast, --viewport, --format, --quality
  snapshot [path]           List interactive elements with CSS selectors
  read [flags] [path]       Extract page content as markdown (flags: --source, --no-wait)
  fetch <url> [flags] [path] goto + auto-wait + read in one step (flags: --source)
  eval <expression>         Run JS, result to stdout
  eval-to <path> <expr>     Run JS, write result to file
  eval-file <js-path>       Run JS from file
  eval-file-to <out> <js>   Run JS from file, write to file

Emulation:
  device <"name"> [--dpr N] Apply device preset (iPhone 14 Pro, Pixel 7, etc.)
  viewport <w> <h>          Set raw viewport dimensions

Control:
  wait <ms>                 Sleep
  wait-for <sel> [timeout]  Wait for selector (default 10s)
  wait-navigation           Wait for page load event
  watch [flags] <path>      Auto-screenshot on HMR/DOM changes. --fast, --cooldown <ms> (default 1000)
  assert <expression>       Fail script if JS expression is falsy
  log <message>             Print to stderr

Rarely needed:
  scroll <x> <y>            Position viewport (for lazy-load triggers or --viewport shots).
                            Most verbs work regardless of scroll position.
"""


def _run(coro):
    """Run an async command, catching unexpected exceptions as one-line errors."""
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as exc:
        print(f'passe: {exc}', file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    # Global flags: extract before subcommand processing
    global _cdp_override
    all_args = sys.argv[1:]

    cdp_url, all_args = _extract_flag(all_args, '--cdp')
    if cdp_url:
        _cdp_override = cdp_url
    device_name, all_args = _extract_flag(all_args, '--device')
    dpr_str, all_args = _extract_flag(all_args, '--dpr')
    dpr_val = float(dpr_str) if dpr_str else None

    # Re-derive cmd after extracting global flags
    if not all_args:
        print(USAGE, file=sys.stderr)
        sys.exit(1)
    cmd = all_args[0]

    if cmd in ('--help', '-h'):
        print(USAGE)
        sys.exit(0)
    elif cmd in ('--version', '-V'):
        from importlib.metadata import version
        print(f"passe {version('passe')}")
        sys.exit(0)
    elif cmd == 'run':
        # Extract flags before positional args
        run_args = all_args[1:]
        if '--help' in run_args or '-h' in run_args:
            print(RUN_HELP)
            sys.exit(0)
        keep_tab = '--keep-tab' in run_args
        reuse_tab = '--reuse-tab' in run_args
        run_args = [a for a in run_args if a not in ('--keep-tab', '--reuse-tab')]

        if len(run_args) >= 2 and run_args[0] == '-c':
            # passe run [-flags] -c 'inline script'
            _run(cmd_run(None, inline=' '.join(run_args[1:]),
                                keep_tab=keep_tab, reuse_tab=reuse_tab,
                                device=device_name, dpr=dpr_val))
        elif len(run_args) == 1:
            # passe run [-flags] script.passe  OR  passe run [-flags] -
            _run(cmd_run(run_args[0],
                                keep_tab=keep_tab, reuse_tab=reuse_tab,
                                device=device_name, dpr=dpr_val))
        else:
            print(USAGE, file=sys.stderr)
            sys.exit(1)
    elif cmd == 'screenshot' and len(all_args) >= 2:
        _run(cmd_screenshot(all_args[1:], device=device_name, dpr=dpr_val))
    elif cmd == 'eval' and len(all_args) >= 2:
        _run(cmd_eval(' '.join(all_args[1:])))
    elif cmd == 'devices':
        cmd_devices()
    else:
        print(USAGE, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
