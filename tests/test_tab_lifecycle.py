"""
Test: Tab lifecycle — attach_to_visible_page() origin preference
and close_tab() SSE/long-lived connection handling.

attach_to_visible_page() selects a tab for --reuse-tab mode.
When origin is given, it prefers a tab whose URL matches that origin.
Falls back to first non-chrome:// tab, then any page, then RuntimeError.

close_tab() navigates to about:blank before closing to drop SSE/WS
connections. Both steps have 5s timeouts and catch TimeoutError,
ConnectionClosed, and CancelledError without re-raising.
"""

import asyncio
import io
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets

from passe.cli import CDPClient


class StubWS:
    """Minimal stub — tests mock client.send() so WS is never used."""

    async def send(self, data):
        pass

    async def close(self):
        pass


def _make_client() -> CDPClient:
    return CDPClient(StubWS())


def _page(target_id: str, url: str, title: str = '') -> dict:
    return {'type': 'page', 'targetId': target_id, 'url': url, 'title': title}


def _attach_result(session_id: str) -> dict:
    return {'result': {'sessionId': session_id}}


# ── attach_to_visible_page: origin preference ──────────────────────


@pytest.mark.asyncio
async def test_origin_match_selects_matching_tab():
    """When origin matches a tab's URL, that tab is selected."""
    client = _make_client()
    client._get_pages = AsyncMock(return_value=[
        _page('tab-1', 'https://news.example.com/front'),
        _page('tab-2', 'https://app.example.com/dashboard'),
    ])
    client.send = AsyncMock(return_value=_attach_result('sess-2'))
    await client.attach_to_visible_page(origin='https://app.example.com')

    attach_call = client.send.call_args_list[0]
    assert attach_call[0][1]['targetId'] == 'tab-2'
    assert client.session_id == 'sess-2'
    assert client._owns_tab is False


@pytest.mark.asyncio
async def test_origin_no_match_falls_back_to_first():
    """When origin doesn't match any tab, falls back to first non-chrome page."""
    client = _make_client()
    client._get_pages = AsyncMock(return_value=[
        _page('tab-1', 'https://news.example.com/front'),
        _page('tab-2', 'https://other.example.com/page'),
    ])
    client.send = AsyncMock(return_value=_attach_result('sess-1'))
    await client.attach_to_visible_page(origin='https://nope.example.com')

    attach_call = client.send.call_args_list[0]
    assert attach_call[0][1]['targetId'] == 'tab-1'


@pytest.mark.asyncio
async def test_no_origin_uses_first_non_chrome_tab():
    """Without origin, selects the first non-chrome:// page."""
    client = _make_client()
    client._get_pages = AsyncMock(return_value=[
        _page('tab-chrome', 'chrome://newtab'),
        _page('tab-real', 'https://example.com'),
    ])
    client.send = AsyncMock(return_value=_attach_result('sess-real'))
    await client.attach_to_visible_page()

    attach_call = client.send.call_args_list[0]
    assert attach_call[0][1]['targetId'] == 'tab-real'


@pytest.mark.asyncio
async def test_only_chrome_tabs_falls_back_to_any_page():
    """When all pages are chrome://, falls back to using them."""
    client = _make_client()
    client._get_pages = AsyncMock(return_value=[
        _page('tab-1', 'chrome://newtab'),
        _page('tab-2', 'chrome://settings'),
    ])
    client.send = AsyncMock(return_value=_attach_result('sess-chrome'))
    await client.attach_to_visible_page()

    attach_call = client.send.call_args_list[0]
    assert attach_call[0][1]['targetId'] == 'tab-1'


@pytest.mark.asyncio
async def test_no_pages_raises_runtime_error():
    """No page tabs at all raises RuntimeError."""
    client = _make_client()
    client._get_pages = AsyncMock(return_value=[])

    with pytest.raises(RuntimeError, match='No browser tab to reuse'):
        await client.attach_to_visible_page()


@pytest.mark.asyncio
async def test_attach_logs_tab_url_to_stderr():
    """Attached tab's URL is logged to stderr."""
    client = _make_client()
    client._get_pages = AsyncMock(return_value=[
        _page('tab-1', 'https://example.com/page'),
    ])
    client.send = AsyncMock(return_value=_attach_result('sess-1'))
    captured = io.StringIO()
    with patch('sys.stderr', captured):
        await client.attach_to_visible_page()

    assert 'reuse-tab: https://example.com/page' in captured.getvalue()


# ── close_tab: SSE/long-lived connection handling ───────────────────


# ── close_tabs_by_origin: auto-replace ─────────────────────────────


@pytest.mark.asyncio
async def test_close_tabs_by_origin_closes_matching():
    """Closes all page tabs whose URL starts with the given origin."""
    client = _make_client()
    client._get_pages = AsyncMock(return_value=[
        _page('tab-1', 'https://example.com/page1'),
        _page('tab-2', 'https://example.com/page2'),
        _page('tab-3', 'https://other.com/page'),
    ])
    client.send = AsyncMock(return_value={'result': {}})

    closed = await client.close_tabs_by_origin('https://example.com')

    assert closed == 2
    assert client.send.call_count == 2
    closed_ids = {c[0][1]['targetId'] for c in client.send.call_args_list}
    assert closed_ids == {'tab-1', 'tab-2'}


@pytest.mark.asyncio
async def test_close_tabs_by_origin_skips_non_page():
    """Non-page targets are already filtered by _get_pages()."""
    client = _make_client()
    client._get_pages = AsyncMock(return_value=[])

    closed = await client.close_tabs_by_origin('https://example.com')
    assert closed == 0


@pytest.mark.asyncio
async def test_close_tabs_by_origin_no_match():
    """Returns 0 when no tabs match the origin."""
    client = _make_client()
    client._get_pages = AsyncMock(return_value=[
        _page('tab-1', 'https://other.com/page'),
    ])

    closed = await client.close_tabs_by_origin('https://example.com')
    assert closed == 0


@pytest.mark.asyncio
async def test_close_tabs_by_origin_timeout_counted():
    """Tabs where closeTarget times out are not counted as closed."""
    client = _make_client()
    client._get_pages = AsyncMock(return_value=[
        _page('tab-1', 'https://example.com/page'),
    ])
    client.send = AsyncMock(side_effect=asyncio.TimeoutError())

    closed = await client.close_tabs_by_origin('https://example.com')
    assert closed == 0


# ── list_tabs ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tabs_returns_pages_only():
    """list_tabs returns page targets with id, url, title."""
    client = _make_client()
    client._get_pages = AsyncMock(return_value=[
        _page('t1', 'https://a.com', 'A'),
        _page('t2', 'https://b.com', 'B'),
    ])

    tabs = await client.list_tabs()

    assert len(tabs) == 2
    assert tabs[0] == {'target_id': 't1', 'url': 'https://a.com', 'title': 'A'}
    assert tabs[1] == {'target_id': 't2', 'url': 'https://b.com', 'title': 'B'}


# ── close_tab: SSE/long-lived connection handling ───────────────────

# close_tab uses _get_pages() to avoid leaving Chrome windowless.
# We don't mock _get_pages globally — close_tab tests set it per-test
# so the safety check sees multiple pages (no-op).


@pytest.mark.asyncio
async def test_close_tab_noop_when_not_owned():
    """close_tab() does nothing when we didn't create the tab."""
    client = _make_client()
    client._owns_tab = False
    client._target_id = 'some-tab'
    client.send = AsyncMock()

    await client.close_tab()

    client.send.assert_not_called()


@pytest.mark.asyncio
async def test_close_tab_noop_when_no_target_id():
    """close_tab() does nothing when _target_id is None."""
    client = _make_client()
    client._owns_tab = True
    client._target_id = None
    client.send = AsyncMock()

    await client.close_tab()

    client.send.assert_not_called()


@pytest.mark.asyncio
async def test_close_tab_navigates_then_closes():
    """Happy path: navigates to about:blank then closes the target."""
    client = _make_client()
    client._owns_tab = True
    client._target_id = 'tab-42'
    client._get_pages = AsyncMock(return_value=[
        _page('tab-42', 'https://a.com'),
        _page('tab-other', 'https://b.com'),
    ])
    client.send = AsyncMock(return_value={'result': {}})

    await client.close_tab()

    # _get_pages + Page.navigate + Target.closeTarget
    assert client.send.call_count == 2
    nav_call = client.send.call_args_list[0]
    assert nav_call[0][0] == 'Page.navigate'
    assert nav_call[0][1] == {'url': 'about:blank'}
    close_call = client.send.call_args_list[1]
    assert close_call[0][0] == 'Target.closeTarget'
    assert close_call[0][1] == {'targetId': 'tab-42'}
    assert client._owns_tab is False


@pytest.mark.asyncio
async def test_close_tab_timeout_on_navigate_still_closes():
    """TimeoutError on about:blank navigation doesn't prevent close attempt."""
    client = _make_client()
    client._owns_tab = True
    client._target_id = 'tab-sse'
    client._get_pages = AsyncMock(return_value=[
        _page('tab-sse', 'https://a.com'),
        _page('tab-other', 'https://b.com'),
    ])
    client.send = AsyncMock(side_effect=[
        asyncio.TimeoutError(),       # about:blank hangs (SSE holding connection)
        {'result': {}},               # close succeeds
    ])

    await client.close_tab()

    assert client.send.call_count == 2
    close_call = client.send.call_args_list[1]
    assert close_call[0][0] == 'Target.closeTarget'
    assert client._owns_tab is False


@pytest.mark.asyncio
async def test_close_tab_timeout_on_close_silently_passes():
    """TimeoutError on Target.closeTarget is caught — no exception raised."""
    client = _make_client()
    client._owns_tab = True
    client._target_id = 'tab-stuck'
    client._get_pages = AsyncMock(return_value=[
        _page('tab-stuck', 'https://a.com'),
        _page('tab-other', 'https://b.com'),
    ])
    client.send = AsyncMock(side_effect=[
        {'result': {}},               # navigate OK
        asyncio.TimeoutError(),       # close hangs
    ])

    await client.close_tab()  # Should not raise
    assert client._owns_tab is False


@pytest.mark.asyncio
async def test_close_tab_connection_closed_on_navigate():
    """ConnectionClosed during navigate is caught, close still attempted."""
    client = _make_client()
    client._owns_tab = True
    client._target_id = 'tab-gone'
    client._get_pages = AsyncMock(return_value=[
        _page('tab-gone', 'https://a.com'),
        _page('tab-other', 'https://b.com'),
    ])
    client.send = AsyncMock(side_effect=[
        websockets.ConnectionClosed(None, None),
        {'result': {}},
    ])

    await client.close_tab()

    assert client.send.call_count == 2
    assert client._owns_tab is False


@pytest.mark.asyncio
async def test_close_tab_connection_closed_on_close():
    """ConnectionClosed during Target.closeTarget is caught silently."""
    client = _make_client()
    client._owns_tab = True
    client._target_id = 'tab-dropped'
    client._get_pages = AsyncMock(return_value=[
        _page('tab-dropped', 'https://a.com'),
        _page('tab-other', 'https://b.com'),
    ])
    client.send = AsyncMock(side_effect=[
        {'result': {}},
        websockets.ConnectionClosed(None, None),
    ])

    await client.close_tab()
    assert client._owns_tab is False


@pytest.mark.asyncio
async def test_close_tab_disables_network_capture():
    """close_tab() always disables network capture, even if tab isn't owned."""
    client = _make_client()
    client._network_enabled = True
    client._owns_tab = False
    client._target_id = None

    await client.close_tab()

    assert client._network_enabled is False


@pytest.mark.asyncio
async def test_close_tab_both_timeout():
    """Both navigate and close timeout — no exception, ownership released."""
    client = _make_client()
    client._owns_tab = True
    client._target_id = 'tab-doomed'
    client._get_pages = AsyncMock(return_value=[
        _page('tab-doomed', 'https://a.com'),
        _page('tab-other', 'https://b.com'),
    ])
    client.send = AsyncMock(side_effect=[
        asyncio.TimeoutError(),
        asyncio.TimeoutError(),
    ])

    await client.close_tab()
    assert client._owns_tab is False


# ── _get_pages: HTTP primary, CDP fallback ────────────────────────


def _mock_urlopen(targets_json: list[dict]):
    """Return a monkeypatch-ready urlopen that returns targets_json."""
    body = json.dumps(targets_json).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return lambda *a, **kw: mock_resp


@pytest.mark.asyncio
async def test_get_pages_http_normalizes_id():
    """HTTP /json path normalizes 'id' to 'targetId' and filters to pages."""
    client = _make_client()
    http_targets = [
        {'id': 'abc', 'type': 'page', 'url': 'https://a.com', 'title': 'A'},
        {'id': 'sw1', 'type': 'service_worker', 'url': 'https://a.com/sw.js'},
        {'id': 'def', 'type': 'page', 'url': 'https://b.com', 'title': 'B'},
    ]
    with patch('urllib.request.urlopen', _mock_urlopen(http_targets)):
        pages = await client._get_pages()

    assert len(pages) == 2
    assert pages[0] == {'targetId': 'abc', 'url': 'https://a.com',
                        'title': 'A', 'type': 'page'}
    assert pages[1] == {'targetId': 'def', 'url': 'https://b.com',
                        'title': 'B', 'type': 'page'}


@pytest.mark.asyncio
async def test_get_pages_http_failure_falls_back_to_cdp():
    """When HTTP /json fails, falls back to Target.getTargets."""
    client = _make_client()
    client.send = AsyncMock(return_value={'result': {'targetInfos': [
        {'type': 'page', 'targetId': 't1', 'url': 'https://a.com', 'title': 'A'},
        {'type': 'service_worker', 'targetId': 'sw1', 'url': 'https://a.com/sw.js'},
    ]}})
    with patch('urllib.request.urlopen', side_effect=OSError('connection refused')):
        pages = await client._get_pages()

    assert len(pages) == 1
    assert pages[0]['targetId'] == 't1'
    client.send.assert_called_once_with('Target.getTargets')


@pytest.mark.asyncio
async def test_get_pages_empty_chrome():
    """HTTP returns no page targets — returns empty list."""
    client = _make_client()
    http_targets = [
        {'id': 'sw1', 'type': 'service_worker', 'url': 'https://a.com/sw.js'},
    ]
    with patch('urllib.request.urlopen', _mock_urlopen(http_targets)):
        pages = await client._get_pages()

    assert pages == []
