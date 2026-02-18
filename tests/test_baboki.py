"""
Test: Baboki error handling changes.

Covers three areas added during the baboki outcome:
  1. do_navigate raises on navigation failure (errorText + chrome-error:// URL)
  2. run_script emits scroll-before-screenshot warning
  3. cmd_screenshot parses --fast, --viewport, --format, --quality flags

No browser needed: all tests mock CDP responses.
"""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, patch

import pytest

from passe.cli import CDPClient, do_navigate, run_script


# ── Helpers ───────────────────────────────────────────────


def _mock_client():
    """Create a mock CDPClient with controllable send() responses."""
    client = AsyncMock(spec=CDPClient)
    # Default return for any send() call not covered by side_effect —
    # prevents unawaited-coroutine warnings from final_url eval.
    client.send = AsyncMock(return_value=_eval_response('http://mock/'))
    client.wait_for_event = AsyncMock(return_value={})
    return client


def _nav_response(error_text=None, frame_id='F1'):
    """Build a Page.navigate CDP response."""
    result = {'frameId': frame_id}
    if error_text:
        result['errorText'] = error_text
    return {'result': result}


def _eval_response(value):
    """Build a Runtime.evaluate CDP response."""
    return {'result': {'result': {'value': value}}}


# ── 1. do_navigate raises on navigation failure ──────────


@pytest.mark.asyncio
async def test_navigate_raises_on_error_text():
    """Chrome returns errorText when DNS fails, connection refused, etc."""
    client = _mock_client()
    client.send.side_effect = [
        None,  # Page.enable
        _nav_response(error_text='net::ERR_NAME_NOT_RESOLVED'),  # Page.navigate
    ]

    with pytest.raises(RuntimeError, match='Navigation failed.*ERR_NAME_NOT_RESOLVED'):
        await do_navigate(client, 'http://nonexistent.invalid')


@pytest.mark.asyncio
async def test_navigate_raises_on_chrome_error_url():
    """Belt-and-suspenders: even without errorText, chrome-error:// URL is caught."""
    client = _mock_client()
    client.send.side_effect = [
        None,  # Page.enable
        _nav_response(),  # Page.navigate — no errorText
        _eval_response('chrome-error://chromewebdata/'),  # do_eval(window.location.href)
    ]

    with pytest.raises(RuntimeError, match='Navigation failed.*page did not load'):
        await do_navigate(client, 'http://down.example.com')


@pytest.mark.asyncio
async def test_navigate_succeeds_on_normal_url():
    """Normal navigation — no error, no exception."""
    client = _mock_client()
    client.send.side_effect = [
        None,  # Page.enable
        _nav_response(),  # Page.navigate
        _eval_response('https://example.com/'),  # do_eval(window.location.href)
    ]

    # Should not raise
    await do_navigate(client, 'https://example.com')


@pytest.mark.asyncio
async def test_navigate_error_includes_url():
    """Error message includes the URL that failed — aids debugging."""
    client = _mock_client()
    client.send.side_effect = [
        None,
        _nav_response(error_text='net::ERR_CONNECTION_REFUSED'),
    ]

    with pytest.raises(RuntimeError, match='http://localhost:9999'):
        await do_navigate(client, 'http://localhost:9999')


@pytest.mark.asyncio
async def test_navigate_redirect_no_false_positive():
    """301/302 redirects don't set errorText — do_navigate must not raise.

    Chrome follows HTTP redirects transparently. Page.navigate returns
    no errorText; the final URL is the redirect target. This verifies
    henohe's navigation check doesn't break legitimate redirects.
    (passe-riwiwo)
    """
    client = _mock_client()
    client.send.side_effect = [
        None,  # Page.enable
        _nav_response(),  # Page.navigate — no errorText (redirect followed)
        _eval_response('https://example.com/'),  # final URL after redirect
    ]

    # Should not raise — redirect is not a failure
    await do_navigate(client, 'http://example.com')


@pytest.mark.asyncio
async def test_navigate_redirect_final_url_differs():
    """After redirect, belt-and-suspenders URL check sees the target, not chrome-error://."""
    client = _mock_client()
    client.send.side_effect = [
        None,  # Page.enable
        _nav_response(),  # Page.navigate
        _eval_response('https://www.example.com/landing'),  # redirected destination
    ]

    # Should not raise even though final URL differs from requested URL
    await do_navigate(client, 'http://example.com')


# ── 2. Scroll-before-screenshot warning ──────────────────


@pytest.mark.asyncio
async def test_scroll_before_screenshot_warns(capsys):
    """run_script warns when screenshot follows scroll (full-page mode)."""
    client = _mock_client()
    # scroll does do_scroll (eval), screenshot does do_screenshot
    client.send.side_effect = [
        _eval_response(None),  # do_scroll → Runtime.evaluate
        # do_screenshot: layout metrics, then capture
        {'result': {'contentSize': {'width': 1280, 'height': 800},
                    'cssContentSize': {'width': 1280, 'height': 800},
                    'cssLayoutViewport': {'clientWidth': 1280, 'clientHeight': 720},
                    'layoutViewport': {'pageX': 0, 'pageY': 0,
                                       'clientWidth': 1280, 'clientHeight': 720}}},
        {'result': {'data': 'iVBOR'}},  # Page.captureScreenshot
    ]

    steps = [
        ('scroll', ['0', '500']),
        ('screenshot', ['/tmp/test-warn.png']),
    ]

    with patch('passe.cli.do_scroll', new_callable=AsyncMock):
        with patch('passe.cli.do_screenshot', new_callable=AsyncMock,
                   return_value={'file': '/tmp/test-warn.png', 'kb': 42,
                                 'format': 'png', 'breakdown': {}}):
            await run_script(client, steps)

    captured = capsys.readouterr()
    assert 'scroll before screenshot is usually unnecessary' in captured.err


@pytest.mark.asyncio
async def test_scroll_before_viewport_screenshot_no_warning(capsys):
    """No warning when using --viewport (scroll + viewport shot is legitimate)."""
    client = _mock_client()

    steps = [
        ('scroll', ['0', '500']),
        ('screenshot', ['--viewport', '/tmp/test-nowarn.png']),
    ]

    with patch('passe.cli.do_scroll', new_callable=AsyncMock):
        with patch('passe.cli.do_screenshot', new_callable=AsyncMock,
                   return_value={'file': '/tmp/test-nowarn.png', 'kb': 42,
                                 'format': 'png', 'breakdown': {}}):
            await run_script(client, steps)

    captured = capsys.readouterr()
    assert 'scroll before screenshot' not in captured.err


@pytest.mark.asyncio
async def test_no_warning_without_prior_scroll(capsys):
    """No warning when screenshot doesn't follow scroll."""
    client = _mock_client()

    steps = [
        ('screenshot', ['/tmp/test-noscroll.png']),
    ]

    with patch('passe.cli.do_screenshot', new_callable=AsyncMock,
               return_value={'file': '/tmp/test-noscroll.png', 'kb': 42,
                             'format': 'png', 'breakdown': {}}):
        await run_script(client, steps)

    captured = capsys.readouterr()
    assert 'scroll before screenshot' not in captured.err


# ── 3. Screenshot flag parsing (run_script inline) ───────

# These test the flag parsing logic inside run_script's screenshot branch,
# which mirrors cmd_screenshot but runs inside the script engine.


@pytest.mark.asyncio
async def test_screenshot_fast_flag():
    """--fast sets jpeg, quality 70, optimize, viewport-only."""
    calls = []

    async def mock_screenshot(client, path, **kwargs):
        calls.append(kwargs)
        return {'file': path or '/tmp/x.jpg', 'kb': 10,
                'format': kwargs.get('fmt', 'png'), 'breakdown': {}}

    client = _mock_client()
    steps = [('screenshot', ['--fast', '/tmp/fast.jpg'])]

    with patch('passe.cli.do_screenshot', side_effect=mock_screenshot):
        await run_script(client, steps)

    assert len(calls) == 1
    assert calls[0]['fmt'] == 'jpeg'
    assert calls[0]['quality'] == 70
    assert calls[0]['optimize_speed'] is True
    assert calls[0]['viewport_only'] is True


@pytest.mark.asyncio
async def test_screenshot_format_quality_flags():
    """--format webp --quality 50 passes through correctly."""
    calls = []

    async def mock_screenshot(client, path, **kwargs):
        calls.append(kwargs)
        return {'file': path or '/tmp/x.webp', 'kb': 8,
                'format': kwargs.get('fmt', 'png'), 'breakdown': {}}

    client = _mock_client()
    steps = [('screenshot', ['--format', 'webp', '--quality', '50', '/tmp/out.webp'])]

    with patch('passe.cli.do_screenshot', side_effect=mock_screenshot):
        await run_script(client, steps)

    assert len(calls) == 1
    assert calls[0]['fmt'] == 'webp'
    assert calls[0]['quality'] == 50


@pytest.mark.asyncio
async def test_screenshot_viewport_flag():
    """--viewport passes viewport_only=True."""
    calls = []

    async def mock_screenshot(client, path, **kwargs):
        calls.append(kwargs)
        return {'file': path or '/tmp/x.png', 'kb': 5,
                'format': 'png', 'breakdown': {}}

    client = _mock_client()
    steps = [('screenshot', ['--viewport', '/tmp/vp.png'])]

    with patch('passe.cli.do_screenshot', side_effect=mock_screenshot):
        await run_script(client, steps)

    assert len(calls) == 1
    assert calls[0]['viewport_only'] is True


@pytest.mark.asyncio
async def test_screenshot_fast_with_custom_quality():
    """--fast --quality 90 uses custom quality, not default 70."""
    calls = []

    async def mock_screenshot(client, path, **kwargs):
        calls.append(kwargs)
        return {'file': path or '/tmp/x.jpg', 'kb': 15,
                'format': 'jpeg', 'breakdown': {}}

    client = _mock_client()
    steps = [('screenshot', ['--fast', '--quality', '90', '/tmp/hq.jpg'])]

    with patch('passe.cli.do_screenshot', side_effect=mock_screenshot):
        await run_script(client, steps)

    assert len(calls) == 1
    assert calls[0]['fmt'] == 'jpeg'
    assert calls[0]['quality'] == 90  # custom, not 70
    assert calls[0]['viewport_only'] is True


@pytest.mark.asyncio
async def test_screenshot_no_flags_defaults():
    """No flags = png, no quality, no optimize, full-page."""
    calls = []

    async def mock_screenshot(client, path, **kwargs):
        calls.append(kwargs)
        return {'file': path or '/tmp/x.png', 'kb': 20,
                'format': 'png', 'breakdown': {}}

    client = _mock_client()
    steps = [('screenshot', ['/tmp/default.png'])]

    with patch('passe.cli.do_screenshot', side_effect=mock_screenshot):
        await run_script(client, steps)

    assert len(calls) == 1
    assert calls[0]['fmt'] == 'png'
    assert calls[0]['quality'] is None
    assert calls[0]['optimize_speed'] is False
    assert calls[0]['viewport_only'] is False
