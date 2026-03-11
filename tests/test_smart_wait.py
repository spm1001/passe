"""
Test: smart wait dispatch — one verb, three behaviors.

Covers:
  1. _classify_wait_arg correctly identifies seconds, selectors, ambiguous
  2. run_script: wait <number> sleeps
  3. run_script: wait <selector> waits for element
  4. run_script: bare wait → network idle
  5. run_script: ambiguous arg raises error
  6. wait-for and wait-idle still work as explicit aliases
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from passe.runner import _classify_wait_arg, run_script
from passe.cli import CDPClient


# ── Helpers ───────────────────────────────────────────────


def _mock_client():
    client = AsyncMock(spec=CDPClient)
    client.send = AsyncMock(
        return_value={'result': {'result': {'value': 'http://mock/'}}}
    )
    client.wait_for_event = AsyncMock(return_value={})
    client._network_enabled = True
    client._network_requests = {}
    client._inflight_count = 0
    client._network_idle_event = asyncio.Event()
    client._network_idle_event.set()
    return client


# ── 1. _classify_wait_arg ────────────────────────────────


class TestClassifyWaitArg:
    def test_float_is_seconds(self):
        assert _classify_wait_arg('3') == 'seconds'
        assert _classify_wait_arg('0.5') == 'seconds'
        assert _classify_wait_arg('10') == 'seconds'
        assert _classify_wait_arg('.5') == 'seconds'

    def test_dot_class_is_selector(self):
        assert _classify_wait_arg('.results') == 'selector'
        assert _classify_wait_arg('.foo-bar') == 'selector'

    def test_hash_id_is_selector(self):
        assert _classify_wait_arg('#main') == 'selector'

    def test_bracket_attr_is_selector(self):
        assert _classify_wait_arg('[data-loaded]') == 'selector'
        assert _classify_wait_arg('[data-loaded="true"]') == 'selector'

    def test_combinator_is_selector(self):
        assert _classify_wait_arg('div>span') == 'selector'
        assert _classify_wait_arg('ul~li') == 'selector'
        assert _classify_wait_arg('h2+p') == 'selector'

    def test_pseudo_is_selector(self):
        assert _classify_wait_arg(':has(.loaded)') == 'selector'

    def test_bare_word_is_ambiguous(self):
        assert _classify_wait_arg('results') == 'ambiguous'
        assert _classify_wait_arg('foo') == 'ambiguous'

    def test_empty_is_ambiguous(self):
        assert _classify_wait_arg('') == 'ambiguous'


# ── 2. wait <number> sleeps ──────────────────────────────


@pytest.mark.asyncio
async def test_wait_number_sleeps(capsys):
    client = _mock_client()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},
    ]

    with patch('passe.runner.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        result = await run_script(client, [('wait', ['0.5'])])

    assert result['ok'] is True
    mock_sleep.assert_awaited_once_with(0.5)


# ── 3. wait <selector> waits for element ─────────────────


@pytest.mark.asyncio
async def test_wait_selector_waits_for(capsys):
    client = _mock_client()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},
    ]

    with patch('passe.runner.do_wait_for', new_callable=AsyncMock) as mock_wf:
        result = await run_script(client, [('wait', ['.results'])])

    assert result['ok'] is True
    mock_wf.assert_awaited_once_with(client, '.results', 10)


@pytest.mark.asyncio
async def test_wait_selector_with_timeout(capsys):
    client = _mock_client()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},
    ]

    with patch('passe.runner.do_wait_for', new_callable=AsyncMock) as mock_wf:
        result = await run_script(client, [('wait', ['#loaded', '5'])])

    assert result['ok'] is True
    mock_wf.assert_awaited_once_with(client, '#loaded', 5)


# ── 4. bare wait → network idle ──────────────────────────


@pytest.mark.asyncio
async def test_bare_wait_network_idle(capsys):
    client = _mock_client()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},
    ]

    result = await run_script(client, [('wait', [])])
    assert result['ok'] is True

    stderr = capsys.readouterr().err
    lines = [json.loads(l) for l in stderr.strip().split('\n') if l.startswith('{')]
    step = lines[0]
    assert step['verb'] == 'wait'
    assert 'settled_after_ms' in step


# ── 5. ambiguous arg raises error ────────────────────────


@pytest.mark.asyncio
async def test_wait_ambiguous_arg_errors(capsys):
    client = _mock_client()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},
    ]

    result = await run_script(client, [('wait', ['results'])])
    assert result['ok'] is False

    stderr = capsys.readouterr().err
    assert 'Ambiguous wait argument' in stderr


# ── 6. explicit aliases still work ───────────────────────


@pytest.mark.asyncio
async def test_wait_for_alias(capsys):
    client = _mock_client()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},
    ]

    with patch('passe.runner.do_wait_for', new_callable=AsyncMock) as mock_wf:
        result = await run_script(client, [('wait-for', ['.thing'])])

    assert result['ok'] is True
    mock_wf.assert_awaited_once_with(client, '.thing', 10)


@pytest.mark.asyncio
async def test_wait_idle_alias(capsys):
    client = _mock_client()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},
    ]

    result = await run_script(client, [('wait-idle', [])])
    assert result['ok'] is True

    stderr = capsys.readouterr().err
    lines = [json.loads(l) for l in stderr.strip().split('\n') if l.startswith('{')]
    step = lines[0]
    assert step['verb'] == 'wait-idle'
    assert 'settled_after_ms' in step
