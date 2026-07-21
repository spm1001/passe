"""Fast-path escalation reasons are visible, never silent (passe-nopiku).

try_http_fetch always returns a FastPathResult carrying escalate_reason
when Chrome should take over; cmd_fetch surfaces it as summary
fast_path/fast_path_reason fields so callers can tell 'attempted and
failed' from 'never attempted'.
"""

import json
from io import StringIO
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import passe.fastpath as fastpath
from passe.commands import cmd_fetch
from passe.fastpath import FastPathResult, try_http_fetch


@pytest.fixture(autouse=True)
def _isolated_probe_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(fastpath, 'PROBE_CACHE_PATH',
                        tmp_path / 'md-hosts.json')
    monkeypatch.setattr(fastpath, 'LLMS_INDEX_DIR',
                        tmp_path / 'llms-index')


class _FakeResponse:
    def __init__(self, url, status=200, text='', ctype='text/html'):
        self.url = url
        self.status_code = status
        self.text = text
        self.headers = {'content-type': ctype}


class _FakeClient:
    def __init__(self, routes, raise_exc=None):
        self._routes = routes
        self._raise = raise_exc

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url):
        if self._raise:
            raise self._raise
        return self._routes.get(
            url, _FakeResponse(url, status=404, text='not found',
                               ctype='text/plain'))


def _patched_httpx(routes, raise_exc=None):
    return patch('httpx.Client',
                 side_effect=lambda **kw: _FakeClient(routes, raise_exc))


URL = 'https://site.test/thing'

SPA_HTML = '<html><body><div id="root"></div></body></html>'
THIN_HTML = '<html><body><p>tiny</p></body></html>'


class TestEscalateReasons:
    def test_http_403_carries_reason(self):
        routes = {URL: _FakeResponse(URL, status=403, text='forbidden')}
        with _patched_httpx(routes):
            result = try_http_fetch(URL)
        assert result is not None
        assert result.escalate_reason == 'http_403'

    def test_connection_error_carries_reason(self):
        with _patched_httpx({}, raise_exc=httpx.ConnectError('boom')):
            result = try_http_fetch(URL)
        assert result is not None
        assert result.escalate_reason == 'http_error: ConnectError'

    def test_spa_shell_carries_reason(self):
        routes = {URL: _FakeResponse(URL, text=SPA_HTML)}
        with _patched_httpx(routes):
            result = try_http_fetch(URL)
        assert result is not None
        assert result.escalate_reason.startswith('spa_shell:')

    def test_thin_page_carries_gate_reason(self):
        """The original example.com case: gate rejection, not silence."""
        routes = {URL: _FakeResponse(URL, text=THIN_HTML)}
        with _patched_httpx(routes):
            result = try_http_fetch(URL)
        assert result is not None
        assert result.escalate_reason is not None


def _mock_connect(client):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_connect():
        yield client, {'cdp': 'http://localhost:9222', 'browser': 'test'}

    return fake_connect


def _make_client():
    client = AsyncMock()
    client.create_tab = AsyncMock()
    client.close_tab = AsyncMock()
    client.send = AsyncMock()
    return client


def _escalate_result(reason):
    return FastPathResult(
        markdown='', url=URL, source='http', quality_score=0.0,
        word_count=0, fetch_ms=10.0, escalate_reason=reason)


class TestSummaryFields:
    @pytest.mark.asyncio
    async def test_chrome_path_summary_names_the_gate(self):
        client = _make_client()
        with patch('passe.commands.connect', _mock_connect(client)), \
             patch('passe.fastpath.try_http_fetch',
                   return_value=_escalate_result('too_few_words')), \
             patch('passe.verbs.do_fetch', AsyncMock(return_value={
                 'markdown': 'hello world', 'source': 'trafilatura'})), \
             patch('sys.stdout', new_callable=StringIO) as out, \
             patch('sys.stderr', new_callable=StringIO):
            await cmd_fetch(URL)
        summary = json.loads(out.getvalue())
        assert summary['fast_path'] is False
        assert summary['fast_path_reason'] == 'too_few_words'

    @pytest.mark.asyncio
    async def test_browser_source_skips_with_reason(self):
        client = _make_client()
        with patch('passe.commands.connect', _mock_connect(client)), \
             patch('passe.verbs.do_fetch', AsyncMock(return_value={
                 'markdown': 'hello world', 'source': 'readability'})), \
             patch('sys.stdout', new_callable=StringIO) as out, \
             patch('sys.stderr', new_callable=StringIO):
            await cmd_fetch(URL, source='readability')
        summary = json.loads(out.getvalue())
        assert summary['fast_path'] is False
        assert summary['fast_path_reason'] == (
            'skipped: --source readability is browser-side')

    @pytest.mark.asyncio
    async def test_error_summary_carries_fast_path_fields(self):
        client = _make_client()
        with patch('passe.commands.connect', _mock_connect(client)), \
             patch('passe.fastpath.try_http_fetch',
                   return_value=_escalate_result('spa_shell: React SPA shell')), \
             patch('passe.verbs.do_fetch',
                   AsyncMock(side_effect=RuntimeError('timeout'))), \
             patch('sys.stdout', new_callable=StringIO) as out, \
             patch('sys.stderr', new_callable=StringIO), \
             pytest.raises(SystemExit):
            await cmd_fetch(URL)
        summary = json.loads(out.getvalue())
        assert summary['ok'] is False
        assert summary['fast_path'] is False
        assert summary['fast_path_reason'] == 'spa_shell: React SPA shell'
