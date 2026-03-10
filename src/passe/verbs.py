"""Verb implementations — the action layer of the passe DSL."""

import asyncio
import base64
import json
import os
import sys
import time

from passe.client import CDPClient


async def do_navigate(client: CDPClient, url: str) -> dict:
    """Navigate to url. Returns {'url': final_url, 'status_code': int|None}."""
    await client.send('Page.enable')
    await client.ensure_network()
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
    # Find status code from network events — match Document request for final URL
    status_code = None
    for req in client._network_requests.values():
        if (req.get('resource_type') == 'Document'
                and req.get('url') == current_url
                and req.get('status') is not None):
            status_code = req['status']
            break
    return {'url': current_url, 'status_code': status_code}


async def do_back(client: CDPClient) -> str:
    """Go back in history. Returns the URL after navigation."""
    result = await client.send('Page.getNavigationHistory')
    entries = result['result']['entries']
    idx = result['result']['currentIndex']
    if idx > 0:
        await client.send('Page.navigateToHistoryEntry', {'entryId': entries[idx - 1]['id']})
        await asyncio.sleep(0.1)
    return await do_eval(client, 'window.location.href')


async def do_forward(client: CDPClient) -> str:
    """Go forward in history. Returns the URL after navigation."""
    result = await client.send('Page.getNavigationHistory')
    entries = result['result']['entries']
    idx = result['result']['currentIndex']
    if idx < len(entries) - 1:
        await client.send('Page.navigateToHistoryEntry', {'entryId': entries[idx + 1]['id']})
        await asyncio.sleep(0.1)
    return await do_eval(client, 'window.location.href')


async def do_wait_idle(client: CDPClient, timeout_ms: int = 30000,
                       debounce_ms: int = 500) -> dict:
    """Wait until network requests settle (in-flight count at zero for debounce_ms).

    Returns {'settled_after_ms': N, 'timed_out': bool}.
    """
    await client.ensure_network()
    deadline = time.monotonic() + timeout_ms / 1000
    settled_start = None

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {'settled_after_ms': timeout_ms, 'timed_out': True}

        if client._inflight_count == 0:
            if settled_start is None:
                settled_start = time.monotonic()
            elapsed_idle = (time.monotonic() - settled_start) * 1000
            if elapsed_idle >= debounce_ms:
                return {
                    'settled_after_ms': round(
                        (time.monotonic() - (deadline - timeout_ms / 1000)) * 1000, 1
                    ),
                    'timed_out': False,
                }
            # Sleep a short interval, then re-check
            wait_time = min((debounce_ms - elapsed_idle) / 1000, remaining)
            client._network_idle_event.clear()
            client._network_idle_event.set()  # Already idle, just need to sleep
            await asyncio.sleep(min(wait_time, 0.05))
        else:
            # Requests in flight — wait for idle event or timeout
            settled_start = None
            try:
                client._network_idle_event.clear()
                await asyncio.wait_for(
                    client._network_idle_event.wait(),
                    timeout=min(remaining, 1.0)
                )
            except asyncio.TimeoutError:
                pass


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
            el.focus();
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
        # Give React time to reconcile after the synthetic input/change events.
        # Without this, the next verb (e.g. press Enter) fires via CDP before
        # React has updated its internal state from the dispatched events.
        await asyncio.sleep(0.1)
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


async def do_tap(client: CDPClient, selector: str):
    """Dispatch real touch events (touchstart + touchend) on element center.

    Uses JS TouchEvent synthesis rather than CDP Input.dispatchTouchEvent
    because the CDP method doesn't respond through flattened sessions
    (browser-level WS + sessionId).  JS synthesis is reliable, portable,
    and fires the same events real touches do.
    """
    js = f'''(() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) throw new Error('No element matches: ' + {json.dumps(selector)});
        const rect = el.getBoundingClientRect();
        const x = rect.x + rect.width / 2;
        const y = rect.y + rect.height / 2;
        const touch = new Touch({{
            identifier: 1, target: el,
            clientX: x, clientY: y, pageX: x, pageY: y
        }});
        el.dispatchEvent(new TouchEvent('touchstart', {{
            touches: [touch], targetTouches: [touch], changedTouches: [touch],
            bubbles: true, cancelable: true
        }}));
        el.dispatchEvent(new TouchEvent('touchend', {{
            touches: [], targetTouches: [], changedTouches: [touch],
            bubbles: true, cancelable: true
        }}));
    }})()'''
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    if 'exceptionDetails' in result.get('result', {}):
        desc = result['result']['exceptionDetails'].get('exception', {}).get('description', '')
        raise RuntimeError(f'tap failed: {desc}')


async def do_swipe(client: CDPClient, selector: str, direction: str, distance: int = 200) -> dict:
    """Dispatch a touch swipe gesture (touchstart + touchmove sequence + touchend).

    Same JS synthesis approach as do_tap — CDP Input.dispatchTouchEvent
    doesn't work through flattened sessions.

    Returns dict with start/end coordinates for step NDJSON reporting.
    """
    # Direction → (dx, dy) unit vector
    vectors = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}
    if direction not in vectors:
        raise RuntimeError(f'swipe: unknown direction {direction!r} — use left, right, up, down')
    dx, dy = vectors[direction]
    steps = 8  # intermediate touchmove points for realism
    js = f'''(() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) throw new Error('No element matches: ' + {json.dumps(selector)});
        const rect = el.getBoundingClientRect();
        const cx = rect.x + rect.width / 2;
        const cy = rect.y + rect.height / 2;
        const dx = {dx * distance};
        const dy = {dy * distance};
        const steps = {steps};
        const startX = cx - dx / 2;
        const startY = cy - dy / 2;

        function mkTouch(x, y) {{
            return new Touch({{
                identifier: 1, target: el,
                clientX: x, clientY: y, pageX: x, pageY: y
            }});
        }}

        // touchstart
        const t0 = mkTouch(startX, startY);
        el.dispatchEvent(new TouchEvent('touchstart', {{
            touches: [t0], targetTouches: [t0], changedTouches: [t0],
            bubbles: true, cancelable: true
        }}));

        // touchmove sequence
        for (let i = 1; i <= steps; i++) {{
            const frac = i / steps;
            const t = mkTouch(startX + dx * frac, startY + dy * frac);
            el.dispatchEvent(new TouchEvent('touchmove', {{
                touches: [t], targetTouches: [t], changedTouches: [t],
                bubbles: true, cancelable: true
            }}));
        }}

        // touchend at final position
        const tEnd = mkTouch(startX + dx, startY + dy);
        el.dispatchEvent(new TouchEvent('touchend', {{
            touches: [], targetTouches: [], changedTouches: [tEnd],
            bubbles: true, cancelable: true
        }}));

        return JSON.stringify({{
            startX: Math.round(startX), startY: Math.round(startY),
            endX: Math.round(startX + dx), endY: Math.round(startY + dy)
        }});
    }})()'''
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    if 'exceptionDetails' in result.get('result', {}):
        desc = result['result']['exceptionDetails'].get('exception', {}).get('description', '')
        raise RuntimeError(f'swipe failed: {desc}')
    return json.loads(result['result']['result']['value'])


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
    dpr = 1  # default; overwritten below
    if full_page:
        # Get full page dimensions + DPR in one round-trip
        metrics = await client.send('Runtime.evaluate', {
            'expression': 'JSON.stringify({w: document.documentElement.scrollWidth, h: Math.min(document.documentElement.scrollHeight, 16384), dpr: window.devicePixelRatio})',
            'awaitPromise': False
        })
        dims = json.loads(metrics['result']['result']['value'])
        dpr = dims.get('dpr', 1)
        params['clip'] = {
            'x': 0, 'y': 0,
            'width': dims['w'], 'height': dims['h'],
            'scale': 1
        }
        params['captureBeyondViewport'] = True

    # Screenshot rasterisation can be slow on software-rendered headless Chrome:
    # Wikipedia Cat (765×16384, DPR=1) takes 66s on --disable-gpu with 2 raster
    # threads.  Use a generous timeout so we only fire on a dead browser, not on
    # a page that's legitimately large.
    result = await client.send('Page.captureScreenshot', params, timeout=300.0)
    capture_ms = round((time.monotonic() - t0) * 1000, 1)

    t1 = time.monotonic()
    data = base64.b64decode(result['result']['data'])
    decode_ms = round((time.monotonic() - t1) * 1000, 1)

    # For viewport-only screenshots, fetch DPR after capture (off critical path)
    if not full_page:
        dpr_result = await client.send('Runtime.evaluate', {
            'expression': 'window.devicePixelRatio',
            'awaitPromise': False,
        })
        dpr = dpr_result.get('result', {}).get('result', {}).get('value', 1)

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
            'write_ms': write_ms, 'bytes': len(data), 'dpr': dpr,
        },
    }


async def do_snapshot(client: CDPClient, path: str = None,
                      limit: int = 0) -> str:
    """List interactive elements with CSS selectors.

    limit: max elements to return (0 = unlimited). When set, the JS stops
    scanning after finding enough visible elements — avoids wasted work on
    heavy pages (used by self-healing snapshot on error).
    """
    js = r'''((limit) => {
        const results = [];
        const interactives = document.querySelectorAll(
            'a, button, input, select, textarea, [role="button"], [role="link"], ' +
            '[role="tab"], [role="menuitem"], [onclick], [tabindex]'
        );
        let idx = 0;
        for (const el of interactives) {
            if (limit > 0 && idx >= limit) break;
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
    })(''' + str(limit) + ')'
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    text = result['result']['result'].get('value', '')

    if path:
        with open(path, 'w') as f:
            f.write(text)
    return text


THIN_READ_THRESHOLD = 200  # chars — below this, emit diagnostic
AUTH_PATTERNS = ('sign in', 'log in', 'login', 'access denied', 'forbidden', '403', 'unauthorized', '401', 'page not found', '404')

def _check_thin_read(markdown: str, html: str, page_text_length: int,
                     page_html_length: int, page_title: str, status_code: int | None = None) -> dict | None:
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
    title_lower = page_title.lower() if page_title else ''

    # 1. Check HTTP Status Codes first
    if status_code == 404:
        cause = 'not_found'
    elif status_code in (401, 403):
        cause = 'auth_wall'
    # 2. Check the Title tag for strong semantic hints
    elif any(p in title_lower for p in ('sign in', 'log in', 'login', 'access denied')):
        cause = 'auth_wall'
    elif any(p in title_lower for p in ('not found', '404')):
        cause = 'not_found'
    # 3. Fallback to structural/body hints
    elif 'type="password"' in html_lower or '<form' in html_lower and 'login' in html_lower:
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


def _render_apple_json(data: dict) -> str:
    """Render Apple Developer Documentation JSON into markdown."""
    meta = data.get('metadata', {})
    refs = data.get('references', {})

    def inline(parts):
        out = []
        for p in (parts or []):
            t = p.get('type', '')
            if t == 'text':
                out.append(p.get('text', ''))
            elif t == 'codeVoice':
                out.append(f"`{p.get('code', '')}`")
            elif t == 'reference':
                ref = refs.get(p.get('identifier', ''), {})
                out.append(f"**{ref.get('title', '')}**")
        return ''.join(out)

    lines = [f"# {meta.get('title', 'Unknown')}",
             f"*{meta.get('roleHeading', '')}*\n"]
    abstract = inline(data.get('abstract', []))
    if abstract:
        lines.append(f"{abstract}\n")
    platforms = meta.get('platforms', [])
    if platforms:
        lines.append('**Availability:** '
                      + ' | '.join(f"{p['name']} {p.get('introducedAt', '')}"
                                   for p in platforms) + '\n')
    for section in data.get('primaryContentSections', []):
        kind = section.get('kind', '')
        if kind == 'declarations':
            for decl in section.get('declarations', []):
                tokens = ''.join(t.get('text', '') for t in decl.get('tokens', []))
                lines.append(f"```swift\n{tokens}\n```\n")
        elif kind == 'content':
            for item in section.get('content', []):
                itype = item.get('type', '')
                if itype == 'heading':
                    lines.append(f"{'#' * item.get('level', 2)} {item.get('text', '')}\n")
                elif itype == 'paragraph':
                    lines.append(f"{inline(item.get('inlineContent', []))}\n")
                elif itype == 'codeListing':
                    lang = item.get('syntax', '')
                    code = '\n'.join(item.get('code', []))
                    lines.append(f"```{lang}\n{code}\n```\n")
                elif itype == 'unorderedList':
                    for li in item.get('items', []):
                        for content in li.get('content', []):
                            if content.get('type') == 'paragraph':
                                lines.append(f"- {inline(content.get('inlineContent', []))}")
                    lines.append('')
    for section in data.get('topicSections', []):
        lines.append(f"## {section.get('title', '')}\n")
        for ident in section.get('identifiers', []):
            ref = refs.get(ident, {})
            title = ref.get('title', ident.split('/')[-1])
            desc = inline(ref.get('abstract', []))
            if ref.get('deprecated'):
                title = f"~~{title}~~"
            lines.append(f"- **{title}**" + (f" — {desc}" if desc else ""))
    return '\n'.join(lines)


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

    # Apple Developer Documentation: use structured JSON endpoint instead of
    # extracting from the JS-rendered HTML (which times out trafilatura and
    # produces nav-chrome soup from innerText).
    if force_source is None or force_source == 'apple':
        current_url = await do_eval(client, 'window.location.href')
        import re as _re
        apple_match = _re.match(
            r'https://developer\.apple\.com/documentation/(.+?)(?:\?|#|$)',
            current_url or ''
        )
        if apple_match:
            doc_path = apple_match.group(1).rstrip('/')
            json_url = f'https://developer.apple.com/tutorials/data/documentation/{doc_path}.json'
            try:
                import urllib.request
                with urllib.request.urlopen(json_url, timeout=10) as resp:
                    apple_data = json.loads(resp.read())
                md = _render_apple_json(apple_data)
                print(f'[read] Apple docs JSON: {json_url}', file=sys.stderr)
                print(f'[read] source: apple-json', file=sys.stderr)
                if path:
                    with open(path, 'w') as f:
                        f.write(md)
                return {'markdown': md, 'source': 'apple-json',
                        'title': apple_data.get('metadata', {}).get('title', '')}
            except Exception as exc:
                if force_source == 'apple':
                    print(f'[read] Apple JSON failed: {exc}', file=sys.stderr)
                # Fall through to normal cascade

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

    # Find status code from network events (to help thin-read diagnostics)
    status_code = None
    for req in client._network_requests.values():
        if (req.get('resource_type') == 'Document'
                and req.get('url') == page_url
                and req.get('status') is not None):
            status_code = req['status']
            break

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
                                     page_html_length, page_title, status_code)
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
    gate_missing_code = False  # track if rejection was for code blocks

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

        # Pipe noise check: bare "|" lines from presentation-table artifacts
        # (HTML email templates use tables for layout, not data — trafilatura
        # leaks cell boundaries as stray pipe characters on empty lines)
        lines = markdown.split('\n')
        non_empty = [l for l in lines if l.strip()]
        bare_pipes = sum(1 for l in non_empty if l.strip() == '|')
        if len(non_empty) > 10 and bare_pipes / len(non_empty) > 0.15:
            print(
                f'[read] quality gate: trafilatura has {bare_pipes} bare pipe lines'
                f' ({bare_pipes*100//len(non_empty)}% of content)'
                ' — falling to Readability', file=sys.stderr
            )
            gate_rejected_markdown = markdown
            markdown = None
            source = None

        # Only query DOM when output might be missing structure
        if source == 'trafilatura' and (output_table_rows < 20 or output_code_blocks < 5):
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
                gate_missing_code = True
            # Proportional check: many code blocks mostly stripped
            elif page_code >= 5 and output_code_blocks < page_code * 0.25:
                lost.append(f'{page_code} code blocks (got {output_code_blocks})')
                gate_missing_code = True

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
                # Supplement with DOM code blocks if that's what was lost
                if gate_missing_code:
                    code_raw = await do_eval(client, (
                        'JSON.stringify([...document.querySelectorAll("pre")]'
                        '.filter(e=>e.textContent.length>30)'
                        '.map(e=>e.textContent.trim()))'
                    ))
                    code_blocks = json.loads(code_raw)
                    if code_blocks:
                        markdown += '\n\n---\n\n## Code Examples\n\n'
                        for block in code_blocks:
                            markdown += '```\n' + block + '\n```\n\n'
                        warning = (f'Readability also failed — supplemented trafilatura prose'
                                   f' with {len(code_blocks)} code blocks from DOM')
                        print(f'[read] supplemented with {len(code_blocks)} code blocks from DOM',
                              file=sys.stderr)
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
                                 page_html_length, page_title, status_code)
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
    nav = await do_navigate(client, url)
    nav_ms = round((time.monotonic() - t0) * 1000, 1)

    t1 = time.monotonic()
    stable = await do_wait_stable(client)
    wait_ms = round((time.monotonic() - t1) * 1000, 1)

    t2 = time.monotonic()
    result = await do_read(client, path, force_source=force_source)
    read_ms = round((time.monotonic() - t2) * 1000, 1)

    result['nav_ms'] = nav_ms
    result['nav_url'] = nav['url']
    result['nav_status_code'] = nav['status_code']
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

    Three debounce layers prevent screenshot storms:

      1. JS MutationObserver (150ms) — clusters rapid DOM mutations into a
         single console.log('[passe-watch] mutation'). Without this, each
         DOM node added fires separately.

      2. Python debounce drain (debounce_ms, default 100ms) — after receiving
         an event, sleeps then drains any queued events. Clusters events that
         arrive in bursts (e.g. multiple HMR modules updating).

      3. Cooldown (cooldown_ms, default 1000ms) — minimum interval between
         captures, leading + trailing edge. Captures immediately on first
         event (leading), then once more after cooldown expires if anything
         was suppressed (trailing). The trailing capture gets the final page
         state, which is what matters most.
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
        try:
            await _do_capture(event_type)
        except Exception as e:
            print(json.dumps({'event': 'trailing_error', 'error': str(e)}),
                  file=sys.stderr)

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

