"""
Test: wait-idle verb — pauses until network requests settle.

Covers:
  1. Inflight counter increments/decrements correctly
  2. do_wait_idle returns immediately when already idle
  3. do_wait_idle waits for debounce period
  4. do_wait_idle times out when requests never settle
  5. wait-idle in KNOWN_VERBS
  6. run_script dispatch emits settled_after_ms in step NDJSON

No browser needed: all tests mock CDP and simulate network events.
"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from passe.cli import CDPClient, KNOWN_VERBS, do_wait_idle, run_script


# ── Helpers ───────────────────────────────────────────────


def _mock_client():
    client = AsyncMock(spec=CDPClient)
    client.send = AsyncMock(return_value={'result': {'result': {'value': 'http://mock/'}}})
    client.wait_for_event = AsyncMock(return_value={})
    client._network_enabled = True
    client._network_requests = {}
    client._inflight_count = 0
    client._network_idle_event = asyncio.Event()
    client._network_idle_event.set()  # starts idle
    return client


class FakeWS:
    """Minimal fake WebSocket for CDPClient tests."""

    def __init__(self, messages=None):
        self._messages = [json.dumps(m) for m in (messages or [])]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages:
            return self._messages.pop(0)
        raise StopAsyncIteration

    async def send(self, data):
        pass


# ── 1. Inflight counter ──────────────────────────────────


def test_inflight_counter_increments_on_request():
    """requestWillBeSent increments inflight count."""
    ws = FakeWS()
    client = CDPClient(ws)
    client._network_enabled = True

    client._collect_network_event('Network.requestWillBeSent', {
        'params': {'requestId': 'r1', 'request': {'url': 'http://a.com', 'method': 'GET'}}
    })

    assert client._inflight_count == 1
    assert not client._network_idle_event.is_set()


def test_inflight_counter_decrements_on_finished():
    """loadingFinished decrements inflight count."""
    ws = FakeWS()
    client = CDPClient(ws)
    client._network_enabled = True

    # Simulate request then finish
    client._collect_network_event('Network.requestWillBeSent', {
        'params': {'requestId': 'r1', 'request': {'url': 'http://a.com', 'method': 'GET'}}
    })
    client._collect_network_event('Network.loadingFinished', {
        'params': {'requestId': 'r1'}
    })

    assert client._inflight_count == 0
    assert client._network_idle_event.is_set()


def test_inflight_counter_decrements_on_failed():
    """loadingFailed also decrements inflight count."""
    ws = FakeWS()
    client = CDPClient(ws)
    client._network_enabled = True

    client._collect_network_event('Network.requestWillBeSent', {
        'params': {'requestId': 'r1', 'request': {'url': 'http://a.com', 'method': 'GET'}}
    })
    client._collect_network_event('Network.loadingFailed', {
        'params': {'requestId': 'r1', 'errorText': 'net::ERR_FAILED'}
    })

    assert client._inflight_count == 0
    assert client._network_idle_event.is_set()


def test_inflight_counter_never_goes_negative():
    """Counter stays at 0 if we receive finish without request."""
    ws = FakeWS()
    client = CDPClient(ws)
    client._network_enabled = True

    client._collect_network_event('Network.loadingFinished', {
        'params': {'requestId': 'r1'}
    })

    assert client._inflight_count == 0


def test_inflight_tracks_multiple_concurrent():
    """Multiple concurrent requests tracked correctly."""
    ws = FakeWS()
    client = CDPClient(ws)
    client._network_enabled = True

    for i in range(3):
        client._collect_network_event('Network.requestWillBeSent', {
            'params': {'requestId': f'r{i}', 'request': {'url': f'http://a.com/{i}', 'method': 'GET'}}
        })
    assert client._inflight_count == 3

    client._collect_network_event('Network.loadingFinished', {'params': {'requestId': 'r0'}})
    assert client._inflight_count == 2

    client._collect_network_event('Network.loadingFinished', {'params': {'requestId': 'r1'}})
    client._collect_network_event('Network.loadingFailed', {'params': {'requestId': 'r2', 'errorText': 'fail'}})
    assert client._inflight_count == 0
    assert client._network_idle_event.is_set()


# ── 2. do_wait_idle — already idle ───────────────────────


@pytest.mark.asyncio
async def test_wait_idle_returns_immediately_when_idle():
    """If no requests in flight, returns after debounce period."""
    client = _mock_client()
    # Already idle (inflight = 0, event set)

    result = await do_wait_idle(client, timeout=5, debounce_ms=100)

    assert result['timed_out'] is False
    # Should settle quickly (just the debounce period)
    assert result['settled_after_ms'] < 500


# ── 3. do_wait_idle — timeout ────────────────────────────


@pytest.mark.asyncio
async def test_wait_idle_times_out():
    """If requests never settle, times out."""
    client = _mock_client()
    client._inflight_count = 1
    client._network_idle_event.clear()

    result = await do_wait_idle(client, timeout=0.2, debounce_ms=100)

    assert result['timed_out'] is True


# ── 4. wait-idle in KNOWN_VERBS ──────────────────────────


def test_wait_idle_in_known_verbs():
    """wait-idle is registered as a known verb."""
    assert 'wait-idle' in KNOWN_VERBS


# ── 5. run_script dispatch ───────────────────────────────


@pytest.mark.asyncio
async def test_run_script_wait_idle_emits_settled(capsys):
    """wait-idle in a script emits settled_after_ms in step NDJSON."""
    client = _mock_client()
    # Already idle
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},  # final_url
    ]

    result = await run_script(client, [('wait-idle', [])])
    assert result['ok'] is True

    stderr = capsys.readouterr().err
    lines = [json.loads(line) for line in stderr.strip().split('\n') if line.strip()]
    step = lines[0]
    assert step['verb'] == 'wait-idle'
    assert 'settled_after_ms' in step
    assert 'ms' in step


@pytest.mark.asyncio
async def test_run_script_wait_idle_with_timeout_arg(capsys):
    """wait-idle accepts optional timeout arg."""
    client = _mock_client()
    client._inflight_count = 1
    client._network_idle_event.clear()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},  # final_url
    ]

    result = await run_script(client, [('wait-idle', ['0.2'])])
    assert result['ok'] is True

    stderr = capsys.readouterr().err
    assert '[wait] network idle timed out' in stderr
    json_lines = [json.loads(line) for line in stderr.strip().split('\n')
                  if line.strip().startswith('{')]
    step = json_lines[0]
    assert step['timed_out'] is True
