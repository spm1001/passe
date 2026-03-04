"""
Test: Watch verb cooldown prevents screenshot storms.

Verifies leading + trailing edge behaviour:
  - Leading: capture immediately on first mutation
  - Trailing: after cooldown expires, capture final state if anything was suppressed
  - Bounded: no more than ~2 captures per cooldown window (leading + trailing)
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from passe.cli import do_watch


def _console_event(text: str) -> dict:
    """Build a Runtime.consoleAPICalled CDP event."""
    return {
        'params': {
            'args': [{'value': text}],
        }
    }


def _mock_watch_client():
    """Client mock with subscribe/unsubscribe for watch tests."""
    client = AsyncMock()
    client.send = AsyncMock(return_value={'result': {'result': {}}})
    queue = asyncio.Queue()
    client.subscribe = lambda _: queue
    client.unsubscribe = lambda _: None
    return client, queue


@pytest.mark.asyncio
async def test_leading_plus_trailing_on_burst(capsys):
    """Burst of 5 mutations → leading capture + trailing capture = 2 total."""
    client, queue = _mock_watch_client()
    for _ in range(5):
        await queue.put(_console_event('[passe-watch] mutation'))

    screenshot_count = 0

    async def mock_screenshot(client, path, **kwargs):
        nonlocal screenshot_count
        screenshot_count += 1
        return {'file': path, 'kb': 10, 'format': 'jpeg', 'breakdown': {}}

    async def cancel_after_trailing():
        # Wait for queue drain + debounce + cooldown expiry + trailing capture.
        # Generous margin to avoid CI flakes on loaded machines.
        while not queue.empty():
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.6)  # cooldown(200ms) + generous margin
        task.cancel()

    with patch('passe.verbs.do_screenshot', side_effect=mock_screenshot):
        task = asyncio.create_task(
            do_watch(client, '/tmp/test.jpg', fast=True,
                     debounce_ms=10, cooldown_ms=200)
        )
        asyncio.create_task(cancel_after_trailing())
        await asyncio.gather(task, return_exceptions=True)

    # Leading (immediate) + trailing (after cooldown) = 2
    assert screenshot_count == 2


@pytest.mark.asyncio
async def test_trailing_captures_final_state(capsys):
    """The trailing capture fires after cooldown, capturing the finished state."""
    client, queue = _mock_watch_client()

    capture_times = []

    async def mock_screenshot(client, path, **kwargs):
        capture_times.append(time.monotonic())
        return {'file': path, 'kb': 10, 'format': 'jpeg', 'breakdown': {}}

    async def feed_burst():
        # 3 rapid mutations
        for _ in range(3):
            await queue.put(_console_event('[passe-watch] mutation'))
            await asyncio.sleep(0.01)
        # Wait for trailing to fire (cooldown 200ms + margin)
        await asyncio.sleep(0.5)
        task.cancel()

    with patch('passe.verbs.do_screenshot', side_effect=mock_screenshot):
        task = asyncio.create_task(
            do_watch(client, '/tmp/test.jpg', fast=True,
                     debounce_ms=10, cooldown_ms=200)
        )
        asyncio.create_task(feed_burst())
        await asyncio.gather(task, return_exceptions=True)

    assert len(capture_times) == 2
    # Gap between leading and trailing should be >= cooldown_ms.
    # Use generous lower bound (100ms for 200ms cooldown) to avoid CI flakes.
    gap_ms = (capture_times[1] - capture_times[0]) * 1000
    assert gap_ms >= 100, f'Trailing fired too soon: {gap_ms:.0f}ms (cooldown=200ms)'


@pytest.mark.asyncio
async def test_no_trailing_when_no_suppression():
    """Single mutation, no suppression → only 1 capture (no trailing needed)."""
    client, queue = _mock_watch_client()
    await queue.put(_console_event('[passe-watch] mutation'))

    screenshot_count = 0

    async def mock_screenshot(client, path, **kwargs):
        nonlocal screenshot_count
        screenshot_count += 1
        return {'file': path, 'kb': 10, 'format': 'jpeg', 'breakdown': {}}

    async def cancel_after_cooldown():
        await asyncio.sleep(0.35)  # well past cooldown
        task.cancel()

    with patch('passe.verbs.do_screenshot', side_effect=mock_screenshot):
        task = asyncio.create_task(
            do_watch(client, '/tmp/test.jpg', fast=True,
                     debounce_ms=10, cooldown_ms=200)
        )
        asyncio.create_task(cancel_after_cooldown())
        await asyncio.gather(task, return_exceptions=True)

    assert screenshot_count == 1


@pytest.mark.asyncio
async def test_cooldown_allows_spaced_captures():
    """Captures spaced beyond cooldown_ms all succeed (leading edge each time)."""
    client, queue = _mock_watch_client()

    screenshot_count = 0

    async def mock_screenshot(client, path, **kwargs):
        nonlocal screenshot_count
        screenshot_count += 1
        return {'file': path, 'kb': 10, 'format': 'jpeg', 'breakdown': {}}

    async def feed_with_spacing():
        for _ in range(3):
            await queue.put(_console_event('[passe-watch] mutation'))
            await asyncio.sleep(0.15)  # 150ms > 100ms cooldown
        await asyncio.sleep(0.1)
        task.cancel()

    with patch('passe.verbs.do_screenshot', side_effect=mock_screenshot):
        task = asyncio.create_task(
            do_watch(client, '/tmp/test.jpg', fast=True,
                     debounce_ms=10, cooldown_ms=100)
        )
        asyncio.create_task(feed_with_spacing())
        await asyncio.gather(task, return_exceptions=True)

    assert screenshot_count == 3


@pytest.mark.asyncio
async def test_trailing_reports_suppressed_count(capsys):
    """Trailing capture log includes suppressed_since_last."""
    client, queue = _mock_watch_client()

    async def mock_screenshot(client, path, **kwargs):
        return {'file': path, 'kb': 10, 'format': 'jpeg', 'breakdown': {}}

    async def feed_burst():
        for _ in range(4):
            await queue.put(_console_event('[passe-watch] mutation'))
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.35)
        task.cancel()

    with patch('passe.verbs.do_screenshot', side_effect=mock_screenshot):
        task = asyncio.create_task(
            do_watch(client, '/tmp/test.jpg', fast=True,
                     debounce_ms=10, cooldown_ms=200)
        )
        asyncio.create_task(feed_burst())
        await asyncio.gather(task, return_exceptions=True)

    captured = capsys.readouterr()
    lines = [l for l in captured.err.strip().split('\n') if l]
    mutation_lines = [json.loads(l) for l in lines
                      if '"mutation"' in l and '"event"' in l]
    # Trailing capture should have suppressed_since_last
    trailing = [m for m in mutation_lines if 'suppressed_since_last' in m]
    assert len(trailing) >= 1, f'No trailing with suppressed count: {mutation_lines}'
    assert trailing[0]['suppressed_since_last'] > 0


@pytest.mark.asyncio
async def test_watch_started_includes_cooldown(capsys):
    """watch_started event includes cooldown_ms."""
    client, queue = _mock_watch_client()

    async def cancel_immediately():
        await asyncio.sleep(0.05)
        task.cancel()

    task = asyncio.create_task(
        do_watch(client, '/tmp/test.jpg', fast=True, cooldown_ms=2000)
    )
    asyncio.create_task(cancel_immediately())
    await asyncio.gather(task, return_exceptions=True)

    captured = capsys.readouterr()
    started = json.loads(captured.err.strip().split('\n')[0])
    assert started['event'] == 'watch_started'
    assert started['cooldown_ms'] == 2000


@pytest.mark.asyncio
async def test_new_leading_cancels_pending_trailing():
    """If a new event arrives after cooldown expires (before trailing fires),
    the leading capture takes priority over the stale trailing."""
    client, queue = _mock_watch_client()

    screenshot_count = 0

    async def mock_screenshot(client, path, **kwargs):
        nonlocal screenshot_count
        screenshot_count += 1
        return {'file': path, 'kb': 10, 'format': 'jpeg', 'breakdown': {}}

    async def feed_two_waves():
        # Wave 1: burst
        for _ in range(3):
            await queue.put(_console_event('[passe-watch] mutation'))
            await asyncio.sleep(0.01)
        # Wait past cooldown so next event is a fresh leading
        await asyncio.sleep(0.25)
        # Wave 2: single event (should be a clean leading capture)
        await queue.put(_console_event('[passe-watch] mutation'))
        await asyncio.sleep(0.15)
        task.cancel()

    with patch('passe.verbs.do_screenshot', side_effect=mock_screenshot):
        task = asyncio.create_task(
            do_watch(client, '/tmp/test.jpg', fast=True,
                     debounce_ms=10, cooldown_ms=150)
        )
        asyncio.create_task(feed_two_waves())
        await asyncio.gather(task, return_exceptions=True)

    # Wave 1: leading + trailing = 2. Wave 2: leading = 1. Total = 3.
    assert screenshot_count == 3
