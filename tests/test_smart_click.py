"""
Test: smart click dispatch — click handles both CSS selectors and text.

Covers:
  1. _is_css_selector correctly classifies args
  2. click with CSS selector dispatches to do_click
  3. click with plain text dispatches to do_click_text
  4. click-text always dispatches to do_click_text (backward compat)
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from passe.runner import _is_css_selector, run_script
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


# ── 1. _is_css_selector ─────────────────────────────────


class TestIsCssSelector:
    def test_class_selector(self):
        assert _is_css_selector('.btn') is True

    def test_id_selector(self):
        assert _is_css_selector('#submit') is True

    def test_attribute_selector(self):
        assert _is_css_selector('[data-action]') is True

    def test_pseudo_selector(self):
        assert _is_css_selector(':has(.loaded)') is True

    def test_combinator(self):
        assert _is_css_selector('div > span') is True
        assert _is_css_selector('ul ~ li') is True
        assert _is_css_selector('h2 + p') is True

    def test_plain_text(self):
        assert _is_css_selector('Accept Cookies') is False
        assert _is_css_selector('Reject All') is False
        assert _is_css_selector('Sign in') is False

    def test_empty(self):
        assert _is_css_selector('') is False

    def test_single_word(self):
        assert _is_css_selector('Submit') is False


# ── 2. click with CSS → do_click ─────────────────────────


@pytest.mark.asyncio
async def test_click_css_dispatches_to_do_click():
    client = _mock_client()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},
    ]

    with patch('passe.runner.do_click', new_callable=AsyncMock) as mock_click:
        result = await run_script(client, [('click', ['.btn-primary'])])

    assert result['ok'] is True
    mock_click.assert_awaited_once_with(client, '.btn-primary')


# ── 3. click with text → do_click_text ───────────────────


@pytest.mark.asyncio
async def test_click_text_dispatches_to_do_click_text():
    client = _mock_client()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},
    ]

    with patch('passe.runner.do_click_text', new_callable=AsyncMock) as mock_ct:
        result = await run_script(client, [('click', ['Accept Cookies'])])

    assert result['ok'] is True
    mock_ct.assert_awaited_once_with(client, 'Accept Cookies')


@pytest.mark.asyncio
async def test_click_single_word_text():
    client = _mock_client()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},
    ]

    with patch('passe.runner.do_click_text', new_callable=AsyncMock) as mock_ct:
        result = await run_script(client, [('click', ['Submit'])])

    assert result['ok'] is True
    mock_ct.assert_awaited_once_with(client, 'Submit')


# ── 4. click-text alias still works ──────────────────────


@pytest.mark.asyncio
async def test_click_text_verb_always_text():
    """click-text always dispatches to do_click_text, even with CSS-like arg."""
    client = _mock_client()
    client.send.side_effect = [
        {'result': {'result': {'value': 'http://mock/'}}},
    ]

    with patch('passe.runner.do_click_text', new_callable=AsyncMock) as mock_ct:
        result = await run_script(client, [('click-text', ['.not-a-selector'])])

    assert result['ok'] is True
    mock_ct.assert_awaited_once_with(client, '.not-a-selector')
