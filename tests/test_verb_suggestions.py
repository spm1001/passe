"""Tests for friendly verb suggestions on unknown/misused verbs."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from passe.parser import parse_script, VERB_SUGGESTIONS
from passe.runner import run_script


def _mock_client():
    """Minimal mock — errors fire before any CDP call."""
    return AsyncMock()


def _run(script_text):
    """Parse and run a script, returning the summary dict."""
    steps = parse_script(script_text)
    client = _mock_client()
    return asyncio.get_event_loop().run_until_complete(run_script(client, steps))


class TestVerbSuggestions:
    def test_navigate_suggests_goto(self):
        result = _run('navigate https://example.com')
        assert not result['ok']
        assert 'did you mean "goto"' in result['error']

    def test_browse_suggests_goto(self):
        result = _run('browse https://example.com')
        assert not result['ok']
        assert 'did you mean "goto"' in result['error']

    def test_open_suggests_goto(self):
        result = _run('open https://example.com')
        assert not result['ok']
        assert 'did you mean "goto"' in result['error']

    def test_sleep_suggests_wait(self):
        result = _run('sleep 1000')
        assert not result['ok']
        assert 'did you mean "wait"' in result['error']

    def test_extract_suggests_read(self):
        result = _run('extract /tmp/out.md')
        assert not result['ok']
        assert 'did you mean "read"' in result['error']

    def test_enter_suggests_press_with_hint(self):
        result = _run('enter')
        assert not result['ok']
        assert 'did you mean "press"' in result['error']
        assert 'press Enter' in result['error']

    def test_get_suggests_with_hint(self):
        result = _run('get https://example.com')
        assert not result['ok']
        assert 'goto' in result['error'] or 'read' in result['error']

    def test_truly_unknown_verb_no_suggestion(self):
        result = _run('frobnicate something')
        assert not result['ok']
        assert 'Unknown verb: frobnicate' in result['error']
        assert 'did you mean' not in result['error']


class TestScrollDirections:
    def test_scroll_down_shows_coordinate_hint(self):
        result = _run('scroll down 500')
        assert not result['ok']
        assert 'scroll 0 500' in result['error']

    def test_scroll_up_shows_coordinate_hint(self):
        result = _run('scroll up 300')
        assert not result['ok']
        assert 'scroll 0 -300' in result['error']

    def test_scroll_left_shows_coordinate_hint(self):
        result = _run('scroll left 200')
        assert not result['ok']
        assert 'scroll -200 0' in result['error']

    def test_scroll_right_shows_coordinate_hint(self):
        result = _run('scroll right 400')
        assert not result['ok']
        assert 'scroll 400 0' in result['error']

    def test_scroll_direction_default_distance(self):
        result = _run('scroll down')
        assert not result['ok']
        assert 'scroll 0 500' in result['error']

    def test_valid_scroll_not_rejected(self):
        """scroll 0 500 should attempt execution (will fail on mock but not with suggestion error)."""
        result = _run('scroll 0 500')
        # Fails because mock client doesn't handle the call, but NOT with direction hint
        assert 'scroll uses coordinates' not in result.get('error', '')
