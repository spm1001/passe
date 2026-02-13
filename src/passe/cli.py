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

async def do_navigate(client: CDPClient, url: str):
    await client.send('Page.enable')
    load_fut = client.wait_for_event('Page.loadEventFired')
    await client.send('Page.navigate', {'url': url})
    await load_fut


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
    # Type each character via CDP Input.dispatchKeyEvent
    for char in text:
        await client.send('Input.dispatchKeyEvent', {
            'type': 'keyDown', 'text': char, 'key': char,
            'unmodifiedText': char
        })
        await client.send('Input.dispatchKeyEvent', {
            'type': 'keyUp', 'key': char
        })


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
                        full_page: bool = True, viewport_only: bool = False) -> dict:
    """Capture screenshot. Returns dict with path and size info."""
    if viewport_only:
        full_page = False

    params = {'format': 'png'}
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
    data = base64.b64decode(result['result']['data'])

    if path is None:
        path = f'/tmp/passe-{int(time.time())}.png'
    with open(path, 'wb') as f:
        f.write(data)

    return {'file': path, 'kb': round(len(data) / 1024, 1)}


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


async def do_read(client: CDPClient, path: str = None) -> dict:
    """Extract page content as markdown.

    Cascade: trafilatura (Python-side) → Readability.js+Turndown (browser-side) → innerText.
    Returns dict with 'markdown', optional 'warning', and 'source'.
    """
    # Get page HTML (with shadow DOM flattened) and metadata from Chrome.
    from ._libs import SHADOW_FLATTEN_JS
    html = await do_eval(client, SHADOW_FLATTEN_JS)
    meta_raw = await do_eval(
        client,
        'JSON.stringify({textLength: document.body.innerText.length, url: window.location.href})'
    )
    meta = json.loads(meta_raw)
    page_text_length = meta.get('textLength', 0)
    page_url = meta.get('url', '')

    markdown = None
    source = None
    warning = None

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

    if warning:
        print(f'[read] warning: {warning}', file=sys.stderr)
    print(f'[read] source: {source}', file=sys.stderr)

    if path:
        with open(path, 'w') as f:
            f.write(markdown)

    return {'markdown': markdown, 'warning': warning, 'source': source}


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
    'press', 'hover', 'scroll', 'screenshot', 'snapshot', 'read', 'viewport',
    'wait', 'wait-for', 'wait-navigation', 'back', 'forward',
    'eval', 'eval-to', 'eval-file', 'eval-file-to', 'assert', 'log',
}


async def run_script(client: CDPClient, steps: list[tuple[str, list[str]]]) -> dict:
    """Execute parsed script steps. Returns summary dict."""
    total_t0 = time.monotonic()
    files = []
    ok = True
    failed_at = None
    fail_verb = None
    fail_error = None

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
                viewport_only = '--viewport' in args
                clean_args = [a for a in args if a != '--viewport']
                path = clean_args[0] if clean_args else None
                info = await do_screenshot(client, path, viewport_only=viewport_only)
                step_info['file'] = info['file']
                step_info['kb'] = info['kb']
                files.append(info['file'])
            elif verb == 'snapshot':
                path = args[0] if args else None
                text = await do_snapshot(client, path)
                if path:
                    files.append(path)
                else:
                    step_info['result'] = text[:200]
            elif verb == 'read':
                path = args[0] if args else None
                read_result = await do_read(client, path)
                if path:
                    files.append(path)
                else:
                    step_info['result'] = read_result['markdown'][:200]
                if read_result.get('warning'):
                    step_info['warning'] = read_result['warning']
                if read_result.get('source'):
                    step_info['source'] = read_result['source']
            elif verb == 'viewport':
                await do_viewport(client, int(args[0]), int(args[1]))
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

async def cmd_run(source: str, inline: str = None):
    """Run a passe script from file, stdin, or inline."""
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
        await client.create_tab()
        await client.send('Page.enable')
        summary = await run_script(client, steps)
        print(json.dumps(summary))
        sys.exit(0 if summary['ok'] else 1)
    finally:
        await client.close_tab()
        await client.stop()
        await ws.close()


async def cmd_screenshot(output: str):
    """Atomic screenshot of current page."""
    ws, client = await connect()
    try:
        await client.attach_to_first_page()
        info = await do_screenshot(client, output)
        print(json.dumps({
            'ok': True, 'file': info['file'], 'kb': info['kb']
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


# ── Entry point ───────────────────────────────────────────

USAGE = """passe — fast CDP browser automation

Usage:
  passe run -c 'goto URL; screenshot /tmp/out.png'   Inline script
  passe run script.passe                              Script file
  passe run - <<'EOF' ... EOF                         Stdin

  passe screenshot <output.png>                       Screenshot current page
  passe eval <expression>                             Eval JS on current page

DSL verbs:
  goto, click, click-text, click-if, fill, type, select, press, hover,
  scroll, screenshot, snapshot, read, viewport, wait, wait-for,
  wait-navigation, back, forward, eval, eval-to, eval-file,
  eval-file-to, assert, log

Output: NDJSON per step on stderr, summary JSON on stdout.
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'run':
        if len(sys.argv) >= 4 and sys.argv[2] == '-c':
            # passe run -c 'inline script'
            asyncio.run(cmd_run(None, inline=' '.join(sys.argv[3:])))
        elif len(sys.argv) == 3:
            # passe run script.passe  OR  passe run -
            asyncio.run(cmd_run(sys.argv[2]))
        else:
            print(USAGE, file=sys.stderr)
            sys.exit(1)
    elif cmd == 'screenshot' and len(sys.argv) == 3:
        asyncio.run(cmd_screenshot(sys.argv[2]))
    elif cmd == 'eval' and len(sys.argv) >= 3:
        asyncio.run(cmd_eval(' '.join(sys.argv[2:])))
    else:
        print(USAGE, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
