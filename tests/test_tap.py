"""
Test: tap verb dispatches real touch events via JS TouchEvent synthesis.

Covers:
  1. do_tap sends a single Runtime.evaluate with TouchEvent construction
  2. do_tap raises on missing selector
  3. Verb dispatch in run_script
  4. tap appears in KNOWN_VERBS

No browser needed: all tests mock CDP responses.
"""

from unittest.mock import AsyncMock

import pytest

from passe.cli import CDPClient, KNOWN_VERBS, do_tap, run_script


# ── Helpers ───────────────────────────────────────────────


def _mock_client():
    """Create a mock CDPClient with controllable send() responses."""
    client = AsyncMock(spec=CDPClient)
    client.send = AsyncMock(return_value={'result': {'result': {'value': 'http://mock/'}}})
    client.wait_for_event = AsyncMock(return_value={})
    return client


def _eval_response(value):
    """Build a Runtime.evaluate CDP response."""
    return {'result': {'result': {'value': value}}}


def _eval_ok():
    """Successful Runtime.evaluate with undefined return."""
    return {'result': {'result': {'type': 'undefined'}}}


# ── 1. do_tap sends Runtime.evaluate with TouchEvent JS ──


@pytest.mark.asyncio
async def test_tap_sends_single_evaluate():
    """tap is a single Runtime.evaluate call (JS synthesis, not CDP Input)."""
    client = _mock_client()
    client.send.return_value = _eval_ok()

    await do_tap(client, '#touch-btn')

    assert client.send.call_count == 1
    method, params = client.send.call_args[0]
    assert method == 'Runtime.evaluate'
    # JS contains TouchEvent construction
    assert 'TouchEvent' in params['expression']
    assert 'touchstart' in params['expression']
    assert 'touchend' in params['expression']


@pytest.mark.asyncio
async def test_tap_js_uses_selector():
    """The generated JS includes the selector for querySelector."""
    client = _mock_client()
    client.send.return_value = _eval_ok()

    await do_tap(client, '.my-button')

    js = client.send.call_args[0][1]['expression']
    assert '.my-button' in js


@pytest.mark.asyncio
async def test_tap_js_computes_center():
    """JS calculates element center from getBoundingClientRect."""
    client = _mock_client()
    client.send.return_value = _eval_ok()

    await do_tap(client, '#btn')

    js = client.send.call_args[0][1]['expression']
    assert 'getBoundingClientRect' in js
    assert 'width / 2' in js
    assert 'height / 2' in js


# ── 2. do_tap raises on missing selector ─────────────────


@pytest.mark.asyncio
async def test_tap_raises_on_missing_element():
    """Selector that matches nothing raises RuntimeError."""
    client = _mock_client()
    client.send.return_value = {
        'result': {
            'result': {},
            'exceptionDetails': {
                'exception': {'description': 'Error: No element matches: #missing'}
            }
        }
    }

    with pytest.raises(RuntimeError, match='tap failed.*No element matches'):
        await do_tap(client, '#missing')


# ── 3. tap in KNOWN_VERBS ────────────────────────────────


def test_tap_in_known_verbs():
    assert 'tap' in KNOWN_VERBS


# ── 4. run_script dispatches tap verb ─────────────────────


@pytest.mark.asyncio
async def test_run_script_tap_verb():
    """tap verb in a script calls do_tap correctly."""
    client = _mock_client()
    client.send.side_effect = [
        _eval_ok(),                       # do_tap Runtime.evaluate
        _eval_response('http://mock/'),   # final_url eval
    ]

    result = await run_script(client, [('tap', ['#btn'])])

    assert result['ok'] is True
    # First call is the tap JS, second is final_url
    assert client.send.call_count == 2
    assert 'TouchEvent' in client.send.call_args_list[0][0][1]['expression']
