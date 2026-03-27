"""
Test: Frame (OOPiF) targeting — attach_to_frame(), switch_to_parent(),
session stacking, re-entrant guard, and screenshot fallback.

Frames are cross-origin iframes exposed as separate CDP targets.
attach_to_frame() finds them by URL pattern, stashes the parent session,
and attaches. switch_to_parent() restores the original tab session.
"""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from passe.client import CDPClient


class StubWS:
    """Minimal stub — tests mock client.send() so WS is never used."""

    async def send(self, data):
        pass

    async def close(self):
        pass


def _make_client() -> CDPClient:
    return CDPClient(StubWS())


def _frame(target_id: str, parent_id: str, url: str, title: str = '') -> dict:
    return {'targetId': target_id, 'parentId': parent_id,
            'url': url, 'title': title, 'type': 'iframe'}


def _attach_result(session_id: str) -> dict:
    return {'result': {'sessionId': session_id}}


# ── attach_to_frame: basic match ──────────────────────────────────


@pytest.mark.asyncio
async def test_attach_to_frame_finds_match():
    """Single URL match attaches to that iframe."""
    client = _make_client()
    client.session_id = 'parent-sess'
    client._target_id = 'parent-tab'
    client._get_frames = AsyncMock(return_value=[
        _frame('frame-1', 'parent-tab', 'https://pivot.claude.ai/plugin'),
    ])
    client.send = AsyncMock(return_value=_attach_result('iframe-sess'))

    result = await client.attach_to_frame('pivot.claude.ai')

    assert result == 'iframe-sess'
    assert client.session_id == 'iframe-sess'
    assert client._in_frame is True
    assert client._parent_session_id == 'parent-sess'
    assert client._parent_target_id == 'parent-tab'


# ── attach_to_frame: multiple matches error ──────────────────────


@pytest.mark.asyncio
async def test_attach_to_frame_multiple_matches_errors():
    """Multiple URL matches raise RuntimeError with listing."""
    client = _make_client()
    client.session_id = 'parent-sess'
    client._get_frames = AsyncMock(return_value=[
        _frame('f1', 'p', 'https://claude.ai/a'),
        _frame('f2', 'p', 'https://claude.ai/b'),
    ])

    with pytest.raises(RuntimeError, match='matches 2 iframes'):
        await client.attach_to_frame('claude.ai')


# ── attach_to_frame: timeout ──────────────────────────────────────


@pytest.mark.asyncio
async def test_attach_to_frame_timeout():
    """No match within timeout raises RuntimeError."""
    client = _make_client()
    client.session_id = 'parent-sess'
    client._get_frames = AsyncMock(return_value=[])

    with pytest.raises(RuntimeError, match='no iframe matching'):
        await client.attach_to_frame('nonexistent.com', timeout=0.5)


# ── attach_to_frame: re-entrant guard ─────────────────────────────


@pytest.mark.asyncio
async def test_attach_to_frame_reentrant_errors():
    """Calling attach_to_frame while already in a frame raises."""
    client = _make_client()
    client._in_frame = True

    with pytest.raises(RuntimeError, match='already in an iframe context'):
        await client.attach_to_frame('anything')


# ── attach_to_frame: auto-attaches parent when session is None ────


@pytest.mark.asyncio
async def test_attach_to_frame_finds_root_page_when_no_session():
    """When session_id is None (--frame without tab), finds root page first."""
    client = _make_client()
    client.session_id = None
    client._target_id = None

    client._get_frames = AsyncMock(return_value=[
        _frame('iframe-1', 'tab-1', 'https://pivot.claude.ai/plugin'),
    ])

    # _find_root_page returns the parent page
    client._find_root_page = AsyncMock(return_value={
        'targetId': 'tab-1', 'url': 'https://excel.cloud.microsoft',
        'title': 'PowerPoint',
    })

    # send() will be called twice: once for parent attach, once for iframe
    call_count = 0
    async def mock_send(method, params=None, timeout=15.0):
        nonlocal call_count
        call_count += 1
        if method == 'Target.attachToTarget':
            if params['targetId'] == 'tab-1':
                return _attach_result('parent-sess')
            elif params['targetId'] == 'iframe-1':
                return _attach_result('iframe-sess')
        elif method == 'Page.enable':
            return {'result': {}}
        return {'result': {}}

    client.send = mock_send

    result = await client.attach_to_frame('pivot.claude.ai')

    assert result == 'iframe-sess'
    assert client._parent_session_id == 'parent-sess'
    assert client._parent_target_id == 'tab-1'
    assert client._in_frame is True


# ── switch_to_parent: restores state ──────────────────────────────


@pytest.mark.asyncio
async def test_switch_to_parent_restores_session():
    """switch_to_parent restores the stashed parent session."""
    client = _make_client()
    client.session_id = 'iframe-sess'
    client._target_id = 'iframe-1'
    client._in_frame = True
    client._parent_session_id = 'parent-sess'
    client._parent_target_id = 'parent-tab'
    client._frame_target_id = 'iframe-1'
    client.send = AsyncMock(return_value={'result': {}})

    result = await client.switch_to_parent()

    assert result == 'parent-sess'
    assert client.session_id == 'parent-sess'
    assert client._target_id == 'parent-tab'
    assert client._in_frame is False
    assert client._parent_session_id is None


# ── switch_to_parent: errors when not in frame ────────────────────


@pytest.mark.asyncio
async def test_switch_to_parent_not_in_frame_errors():
    """switch_to_parent when not in a frame raises RuntimeError."""
    client = _make_client()
    client._in_frame = False

    with pytest.raises(RuntimeError, match='not currently in an iframe'):
        await client.switch_to_parent()


# ── screenshot session swap ───────────────────────────────────────


def test_screenshot_session_swap_in_frame():
    """_switch_session_for_screenshot swaps to parent, restore brings it back."""
    client = _make_client()
    client.session_id = 'iframe-sess'
    client._in_frame = True
    client._parent_session_id = 'parent-sess'

    iframe_sess = client._switch_session_for_screenshot()

    assert iframe_sess == 'iframe-sess'
    assert client.session_id == 'parent-sess'

    client._restore_session_after_screenshot(iframe_sess)

    assert client.session_id == 'iframe-sess'


def test_screenshot_session_swap_not_in_frame():
    """_switch_session_for_screenshot returns None when not in a frame."""
    client = _make_client()
    client.session_id = 'tab-sess'
    client._in_frame = False

    result = client._switch_session_for_screenshot()

    assert result is None
    assert client.session_id == 'tab-sess'


# ── list_frames ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_frames_returns_formatted():
    """list_frames returns [{target_id, parent_id, url, title}]."""
    client = _make_client()
    client._get_frames = AsyncMock(return_value=[
        _frame('f1', 'p1', 'https://pivot.claude.ai', 'Claude Office'),
        _frame('f2', 'p1', 'https://other.example.com', ''),
    ])

    result = await client.list_frames()

    assert len(result) == 2
    assert result[0]['target_id'] == 'f1'
    assert result[0]['parent_id'] == 'p1'
    assert result[0]['url'] == 'https://pivot.claude.ai'
    assert result[0]['title'] == 'Claude Office'


# ── _find_root_page ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_root_page_walks_chain():
    """_find_root_page walks parentId chain up to a page target."""
    client = _make_client()

    # Simulate: page -> intermediate iframe -> target iframe
    all_targets = json.dumps([
        {'id': 'page-1', 'type': 'page', 'url': 'https://excel.cloud.microsoft',
         'title': 'PowerPoint'},
        {'id': 'mid-frame', 'type': 'iframe', 'url': 'https://officeapps.live.com',
         'parentId': 'page-1'},
        {'id': 'deep-frame', 'type': 'iframe', 'url': 'https://pivot.claude.ai',
         'parentId': 'mid-frame'},
    ]).encode()

    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = all_targets
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        iframe = {'parentId': 'mid-frame'}
        result = await client._find_root_page(iframe)

    assert result is not None
    assert result['targetId'] == 'page-1'
    assert result['url'] == 'https://excel.cloud.microsoft'


# ── parser: frame verb ────────────────────────────────────────────


def test_frame_in_known_verbs():
    """frame is a registered verb."""
    from passe.parser import KNOWN_VERBS, VERB_MIN_ARGS
    assert 'frame' in KNOWN_VERBS
    assert VERB_MIN_ARGS.get('frame') == 1


def test_iframe_suggests_frame():
    """iframe is a suggestion for frame."""
    from passe.parser import VERB_SUGGESTIONS
    assert 'iframe' in VERB_SUGGESTIONS
    assert VERB_SUGGESTIONS['iframe'][0] == 'frame'


def test_parse_frame_verb():
    """frame verb parses correctly."""
    from passe.parser import parse_script
    steps = parse_script('frame pivot.claude.ai\nframe top')
    assert steps == [
        ('frame', ['pivot.claude.ai']),
        ('frame', ['top']),
    ]


def test_frame_validates():
    """frame passes validate_steps with 1+ args."""
    from passe.parser import validate_steps
    good = validate_steps([('frame', ['pivot.claude.ai'])])
    assert good == []
    bad = validate_steps([('frame', [])])
    assert len(bad) == 1
    assert 'requires at least 1' in bad[0]['error']
