"""Control verbs — wait_for, wait_stable, frame, device, viewport."""

import asyncio
import json
import sys
import time

from passe.client import CDPClient


async def do_wait_for(client: CDPClient, selector: str, timeout: float = 10):
    """Poll for selector until visible or timeout. timeout is in seconds."""
    js = f'''document.querySelector({json.dumps(selector)}) !== null'''
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = await client.send('Runtime.evaluate', {
            'expression': js, 'awaitPromise': False
        })
        if result['result']['result'].get('value') is True:
            return
        await asyncio.sleep(0.1)
    raise RuntimeError(f'wait-for timed out after {timeout}s: {selector}')


async def do_wait_stable(client: CDPClient, timeout_ms: int = 2000) -> bool:
    """Wait for DOM stability before extraction. Returns True if stable, False if timed out.

    Dual-signal polling: element count (structure) + text length (content).
    Both must be unchanged across two polls 100ms apart to declare stability.
    Catches both structural changes (new elements appearing) and content-only
    changes (text filling existing empty elements during hydration).
    """
    from passe.verbs_observation import do_eval

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


async def do_frame(client: CDPClient, target: str, timeout: float = 10.0):
    """Switch execution context to an iframe or back to parent.

    target='top' switches back to parent tab session.
    Otherwise, target is a URL substring to match against iframe URLs.
    Enables Page domain in the new context so subsequent verbs
    (goto, screenshot) can use Page events.
    """
    if target.lower() == 'top':
        await client.switch_to_parent()
    else:
        await client.attach_to_frame(target, timeout=timeout)
    await client.send('Page.enable')


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
