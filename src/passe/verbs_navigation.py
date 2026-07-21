"""Navigation verbs — navigate, back, forward, wait_idle."""

import asyncio
import time

from passe.client import CDPClient


async def do_navigate(client: CDPClient, url: str) -> dict:
    """Navigate to url. Returns {'url': final_url, 'status_code': int|None}."""
    from passe.verbs_observation import do_eval

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
    # backendDOMNodeIds never survive a page load — drop this tab's refs
    from passe.refcache import clear_refs, tab_id_of
    clear_refs(tab_id_of(client))
    return {'url': current_url, 'status_code': status_code}


async def do_back(client: CDPClient) -> str:
    """Go back in history. Returns the URL after navigation."""
    from passe.verbs_observation import do_eval

    result = await client.send('Page.getNavigationHistory')
    entries = result['result']['entries']
    idx = result['result']['currentIndex']
    if idx > 0:
        await client.send('Page.navigateToHistoryEntry', {'entryId': entries[idx - 1]['id']})
        await asyncio.sleep(0.1)
        from passe.refcache import clear_refs, tab_id_of
        clear_refs(tab_id_of(client))
    return await do_eval(client, 'window.location.href')


async def do_forward(client: CDPClient) -> str:
    """Go forward in history. Returns the URL after navigation."""
    from passe.verbs_observation import do_eval

    result = await client.send('Page.getNavigationHistory')
    entries = result['result']['entries']
    idx = result['result']['currentIndex']
    if idx < len(entries) - 1:
        await client.send('Page.navigateToHistoryEntry', {'entryId': entries[idx + 1]['id']})
        await asyncio.sleep(0.1)
        from passe.refcache import clear_refs, tab_id_of
        clear_refs(tab_id_of(client))
    return await do_eval(client, 'window.location.href')


async def do_wait_idle(client: CDPClient, timeout: float = 30,
                       debounce_ms: int = 500) -> dict:
    """Wait until network requests settle (in-flight count at zero for debounce_ms).

    timeout is in seconds. Returns {'settled_after_ms': N, 'timed_out': bool}.
    """
    await client.ensure_network()
    start = time.monotonic()
    deadline = start + timeout
    settled_start = None

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {'settled_after_ms': round(timeout * 1000), 'timed_out': True}

        if client._inflight_count == 0:
            if settled_start is None:
                settled_start = time.monotonic()
            elapsed_idle = (time.monotonic() - settled_start) * 1000
            if elapsed_idle >= debounce_ms:
                return {
                    'settled_after_ms': round(
                        (time.monotonic() - start) * 1000, 1
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
