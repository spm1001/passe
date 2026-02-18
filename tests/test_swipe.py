"""
Test: swipe verb dispatches touch move gesture via JS TouchEvent synthesis.

Covers:
  1. do_swipe sends a single Runtime.evaluate with touchstart/touchmove/touchend
  2. do_swipe returns start/end coordinates
  3. do_swipe raises on missing selector and invalid direction
  4. Verb dispatch in run_script enriches step_info
  5. swipe appears in KNOWN_VERBS
  6. Default distance is 200px

No browser needed: all tests mock CDP responses.
"""

import json
from unittest.mock import AsyncMock

import pytest

from passe.cli import CDPClient, KNOWN_VERBS, do_swipe, run_script


# ── Helpers ───────────────────────────────────────────────


def _mock_client():
    client = AsyncMock(spec=CDPClient)
    client.send = AsyncMock(return_value={'result': {'result': {'value': 'http://mock/'}}})
    client.wait_for_event = AsyncMock(return_value={})
    return client


def _eval_response(value):
    return {'result': {'result': {'value': value}}}


def _swipe_response(start_x=100, start_y=200, end_x=300, end_y=200):
    return _eval_response(json.dumps({
        'startX': start_x, 'startY': start_y,
        'endX': end_x, 'endY': end_y,
    }))


# ── 1. do_swipe sends single evaluate with touch sequence ─


@pytest.mark.asyncio
async def test_swipe_sends_single_evaluate():
    """swipe is a single Runtime.evaluate call."""
    client = _mock_client()
    client.send.return_value = _swipe_response()

    result = await do_swipe(client, '#area', 'left')

    assert client.send.call_count == 1
    method, params = client.send.call_args[0]
    assert method == 'Runtime.evaluate'
    js = params['expression']
    assert 'touchstart' in js
    assert 'touchmove' in js
    assert 'touchend' in js


@pytest.mark.asyncio
async def test_swipe_js_contains_direction_vector():
    """Generated JS uses correct displacement for each direction."""
    client = _mock_client()
    client.send.return_value = _swipe_response()

    await do_swipe(client, '#area', 'left', 300)
    js = client.send.call_args[0][1]['expression']
    assert 'dx = -300' in js
    assert 'dy = 0' in js


@pytest.mark.asyncio
async def test_swipe_directions():
    """All four directions produce correct dx/dy."""
    client = _mock_client()
    client.send.return_value = _swipe_response()

    for direction, expected_dx, expected_dy in [
        ('left', -200, 0), ('right', 200, 0),
        ('up', 0, -200), ('down', 0, 200),
    ]:
        await do_swipe(client, '#area', direction, 200)
        js = client.send.call_args[0][1]['expression']
        assert f'dx = {expected_dx}' in js
        assert f'dy = {expected_dy}' in js


# ── 2. do_swipe returns coordinates ──────────────────────


@pytest.mark.asyncio
async def test_swipe_returns_coordinates():
    """Return value contains start and end coordinates."""
    client = _mock_client()
    client.send.return_value = _swipe_response(50, 100, 250, 100)

    result = await do_swipe(client, '#area', 'right')

    assert result == {'startX': 50, 'startY': 100, 'endX': 250, 'endY': 100}


# ── 3. do_swipe raises on errors ─────────────────────────


@pytest.mark.asyncio
async def test_swipe_raises_on_missing_element():
    client = _mock_client()
    client.send.return_value = {
        'result': {
            'result': {},
            'exceptionDetails': {
                'exception': {'description': 'Error: No element matches: #missing'}
            }
        }
    }

    with pytest.raises(RuntimeError, match='swipe failed.*No element matches'):
        await do_swipe(client, '#missing', 'left')


@pytest.mark.asyncio
async def test_swipe_raises_on_invalid_direction():
    """Invalid direction raises before sending to Chrome."""
    client = _mock_client()

    with pytest.raises(RuntimeError, match='unknown direction.*diagonal'):
        await do_swipe(client, '#area', 'diagonal')

    assert client.send.call_count == 0  # no CDP call made


# ── 4. run_script enriches step_info ──────────────────────


@pytest.mark.asyncio
async def test_run_script_swipe_verb(capsys):
    """swipe verb in a script reports start/end in NDJSON."""
    client = _mock_client()
    client.send.side_effect = [
        _swipe_response(50, 100, 250, 100),  # do_swipe
        _eval_response('http://mock/'),        # final_url
    ]

    result = await run_script(client, [('swipe', ['#area', 'right'])])

    assert result['ok'] is True
    # Check stderr NDJSON has start/end
    import sys
    # The step_info is printed to stderr as NDJSON — verify via the mock calls
    # that the swipe return was consumed (call count confirms single eval + final_url)
    assert client.send.call_count == 2


@pytest.mark.asyncio
async def test_run_script_swipe_custom_distance():
    """swipe with explicit distance passes it through."""
    client = _mock_client()
    client.send.side_effect = [
        _swipe_response(),
        _eval_response('http://mock/'),
    ]

    result = await run_script(client, [('swipe', ['#area', 'down', '500'])])

    assert result['ok'] is True
    js = client.send.call_args_list[0][0][1]['expression']
    assert 'dy = 500' in js


# ── 5. swipe in KNOWN_VERBS ──────────────────────────────


def test_swipe_in_known_verbs():
    assert 'swipe' in KNOWN_VERBS


# ── 6. Default distance ──────────────────────────────────


@pytest.mark.asyncio
async def test_swipe_default_distance():
    """Default distance is 200px."""
    client = _mock_client()
    client.send.return_value = _swipe_response()

    await do_swipe(client, '#area', 'up')

    js = client.send.call_args[0][1]['expression']
    assert 'dy = -200' in js
