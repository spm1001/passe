"""Interaction verbs — click, fill, type, select, press, hover, tap, swipe, scroll."""

import asyncio
import json
import sys

from passe.client import CDPClient


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
    from passe.verbs_observation import do_eval

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
