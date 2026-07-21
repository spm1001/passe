"""
Test: Event buffer behaviour and edge cases.

CDPClient.event_buffer is dict[str, dict] — one entry per event method.
Only events in BUFFERED_EVENTS are stored; everything else is dropped
when no waiter is registered. Also tests race conditions between
waiters, timeouts, and unsolicited events.
"""

import asyncio
import json

import pytest

from passe.cli import CDPClient


class FakeWS:
    """Minimal fake WebSocket that feeds canned messages."""

    def __init__(self, messages: list[dict]):
        self._messages = [json.dumps(m) for m in messages]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def send(self, data):
        pass

    async def close(self):
        pass


def _make_event(method: str, seq: int = 0) -> dict:
    return {'method': method, 'params': {'seq': seq}}


@pytest.mark.asyncio
async def test_only_whitelisted_events_buffered():
    """Non-whitelisted events are dropped when no waiter is registered."""
    events = [
        _make_event('Page.loadEventFired'),
        _make_event('Page.frameNavigated'),
        _make_event('Page.domContentEventFired'),
        _make_event('Network.requestWillBeSent'),
        _make_event('Runtime.consoleAPICalled'),
    ]
    ws = FakeWS(events)
    client = CDPClient(ws)
    await client.start()
    # Let receiver process all messages
    await asyncio.sleep(0.05)

    assert set(client.event_buffer.keys()) == {'Page.loadEventFired'}
    assert len(client.event_buffer) == 1


@pytest.mark.asyncio
async def test_buffer_size_constant_after_many_events():
    """100 repeated events produce at most len(BUFFERED_EVENTS) entries."""
    events = []
    for i in range(100):
        events.append(_make_event('Page.loadEventFired', seq=i))
        events.append(_make_event('Page.frameNavigated', seq=i))
        events.append(_make_event('Page.lifecycleEvent', seq=i))
    ws = FakeWS(events)
    client = CDPClient(ws)
    await client.start()
    await asyncio.sleep(0.05)

    # Only whitelisted events stored, each overwritten to latest
    assert len(client.event_buffer) == 1
    assert client.event_buffer['Page.loadEventFired']['params']['seq'] == 99


@pytest.mark.asyncio
async def test_waiter_consumes_before_buffer():
    """When a waiter is registered, the event goes to the waiter, not the buffer."""
    events = [_make_event('Page.loadEventFired', seq=42)]
    ws = FakeWS(events)
    client = CDPClient(ws)

    # Register waiter before events arrive
    fut = asyncio.get_running_loop().create_future()
    client.event_waiters['Page.loadEventFired'] = fut

    await client.start()
    result = await asyncio.wait_for(fut, timeout=1.0)

    assert result['params']['seq'] == 42
    assert 'Page.loadEventFired' not in client.event_buffer


@pytest.mark.asyncio
async def test_wait_for_event_checks_buffer_first():
    """If event is already buffered, wait_for_event returns immediately."""
    ws = FakeWS([])
    client = CDPClient(ws)

    # Pre-populate buffer
    client.event_buffer['Page.loadEventFired'] = _make_event('Page.loadEventFired', seq=7)

    result = await client.wait_for_event('Page.loadEventFired')
    assert result['params']['seq'] == 7
    assert 'Page.loadEventFired' not in client.event_buffer  # consumed


# ── Edge cases ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stale_waiter_does_not_drop_event():
    """Timed-out waiter must not prevent the event from being buffered.

    Regression: wait_for_event timeout leaves a cancelled future in
    event_waiters. When the event fires, _receiver pops the stale future,
    sees fut.done() == True, and — before the fix — skipped the buffer
    branch (elif). The event was silently dropped. A subsequent
    wait_for_event would hang forever.
    """
    # FakeWS that waits before delivering — gives time for the timeout
    class SlowWS(FakeWS):
        async def __anext__(self):
            if not self._messages:
                # Keep the receiver alive (block until cancelled)
                await asyncio.get_running_loop().create_future()
            await asyncio.sleep(0.15)  # Delay delivery past the timeout
            return self._messages.pop(0)

    events = [_make_event('Page.loadEventFired', seq=99)]
    ws = SlowWS(events)
    client = CDPClient(ws)
    await client.start()

    # Register a waiter that will time out before the event arrives
    with pytest.raises(asyncio.TimeoutError):
        await client.wait_for_event('Page.loadEventFired', timeout=0.05)

    # Stale future is still in event_waiters
    assert 'Page.loadEventFired' in client.event_waiters

    # Let the event arrive (SlowWS delivers after 0.15s)
    await asyncio.sleep(0.2)

    # The event must be buffered despite the stale waiter
    assert 'Page.loadEventFired' in client.event_buffer, (
        'Event was silently dropped by stale waiter — the bug is back'
    )
    assert client.event_buffer['Page.loadEventFired']['params']['seq'] == 99

    # A new wait_for_event must find it immediately
    result = await client.wait_for_event('Page.loadEventFired', timeout=0.1)
    assert result['params']['seq'] == 99


@pytest.mark.asyncio
async def test_unsolicited_event_consumed_by_next_waiter():
    """Unsolicited load event (e.g. meta-refresh) gets buffered, then
    consumed by the next wait_for_event — which may be waiting for a
    different navigation entirely.

    This is documented behaviour, not a bug: the buffer stores the latest
    event per method. A meta-refresh overwrites the buffer entry, and the
    next goto's wait_for_event finds it immediately. The consequence is
    that goto returns before its own navigation completes.
    """
    events = [
        _make_event('Page.loadEventFired', seq=1),  # First goto's event
        _make_event('Page.loadEventFired', seq=2),  # Unsolicited (meta-refresh)
    ]
    ws = FakeWS(events)
    client = CDPClient(ws)

    # Register waiter for first event (simulating first goto)
    fut = asyncio.get_running_loop().create_future()
    client.event_waiters['Page.loadEventFired'] = fut

    await client.start()

    # First event delivered to waiter
    result1 = await asyncio.wait_for(fut, timeout=1.0)
    assert result1['params']['seq'] == 1

    # Second event goes to buffer (no waiter registered)
    await asyncio.sleep(0.05)
    assert 'Page.loadEventFired' in client.event_buffer
    assert client.event_buffer['Page.loadEventFired']['params']['seq'] == 2

    # Next wait_for_event gets the stale buffered event immediately —
    # it doesn't know (or care) that this was from a meta-refresh
    result2 = await client.wait_for_event('Page.loadEventFired', timeout=0.1)
    assert result2['params']['seq'] == 2
