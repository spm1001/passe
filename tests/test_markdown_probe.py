"""Markdown-source probe in the HTTP fast-path (passe-nuguza).

Mintlify-class docs sites serve a pristine .md sibling of every page and
advertise it via <link rel="alternate" type="text/markdown">. The probe
returns that canonical source instead of extracting from a 1MB+ HTML shell.
Guessed URL.md probes fire only on escalation paths — healthy fetches make
exactly one request.
"""

from unittest.mock import patch

import pytest

import passe.fastpath as fastpath
from passe.fastpath import (
    _fetch_markdown_candidate,
    _markdown_source_url,
    try_http_fetch,
)


@pytest.fixture(autouse=True)
def _isolated_probe_cache(tmp_path, monkeypatch):
    """Point the host cache at a per-test file — never at ~/.passe."""
    monkeypatch.setattr(fastpath, 'PROBE_CACHE_PATH',
                        tmp_path / 'md-hosts.json')


PAGE_URL = 'https://site.test/docs/page'
MD_URL = 'https://site.test/docs/page.md'

MD_BODY = (
    '# Page title\n\n'
    'This is the canonical markdown source of the page, with enough words '
    'in it to pass the trivial word-count sanity check that guards against '
    'accepting error pages or stub responses as real content.\n'
)

ADVERTISING_HTML = (
    '<html><head>'
    '<link rel="alternate" type="text/markdown" href="/docs/page.md"/>'
    '</head><body><div>' + 'nav chrome ' * 300 + '</div></body></html>'
)

THIN_HTML = (
    '<html><head><title>t</title></head>'
    '<body><p>almost no content here</p></body></html>'
)

RICH_HTML = (
    '<html><head><title>Article</title></head><body><article>'
    '<h1>A real article</h1>'
    + ''.join(
        '<p>This is a perfectly ordinary paragraph of English text that '
        'the extractor should have no trouble with at all, because it is '
        'made of common words and it goes on for a good long while about '
        'nothing in particular so that the word count is high.</p>'
        for _ in range(8)
    )
    + '</article></body></html>'
)


class _FakeResponse:
    def __init__(self, url, status=200, text='', ctype='text/html'):
        self.url = url
        self.status_code = status
        self.text = text
        self.headers = {'content-type': ctype}


class _FakeClient:
    def __init__(self, routes, calls):
        self._routes = routes
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url):
        self._calls.append(url)
        return self._routes.get(
            url, _FakeResponse(url, status=404, text='not found',
                               ctype='text/plain'))


def _patched_httpx(routes, calls):
    return patch('httpx.Client', side_effect=lambda **kw: _FakeClient(routes, calls))


class TestMarkdownSourceUrl:
    def test_advertised_relative_href_resolved(self):
        assert _markdown_source_url(
            ADVERTISING_HTML, PAGE_URL, guess=False) == MD_URL

    def test_no_link_no_guess_returns_none(self):
        assert _markdown_source_url(THIN_HTML, PAGE_URL, guess=False) is None

    def test_guess_appends_md(self):
        assert _markdown_source_url(THIN_HTML, PAGE_URL, guess=True) == MD_URL

    def test_guess_strips_trailing_slash(self):
        assert _markdown_source_url(
            THIN_HTML, PAGE_URL + '/', guess=True) == MD_URL

    def test_no_self_probe_on_md_url(self):
        assert _markdown_source_url(THIN_HTML, MD_URL, guess=True) is None

    def test_no_guess_on_root_path(self):
        assert _markdown_source_url(
            THIN_HTML, 'https://site.test/', guess=True) is None


class TestFetchMarkdownCandidate:
    def test_rejects_html_content_type(self):
        calls = []
        routes = {MD_URL: _FakeResponse(MD_URL, text=MD_BODY, ctype='text/html')}
        with _patched_httpx(routes, calls):
            assert _fetch_markdown_candidate(MD_URL) is None

    def test_rejects_html_shell_body(self):
        calls = []
        routes = {MD_URL: _FakeResponse(
            MD_URL, text='<!DOCTYPE html><html>' + 'x ' * 100,
            ctype='text/plain')}
        with _patched_httpx(routes, calls):
            assert _fetch_markdown_candidate(MD_URL) is None

    def test_rejects_trivial_body(self):
        calls = []
        routes = {MD_URL: _FakeResponse(
            MD_URL, text='Not found', ctype='text/plain')}
        with _patched_httpx(routes, calls):
            assert _fetch_markdown_candidate(MD_URL) is None

    def test_accepts_markdown(self):
        calls = []
        routes = {MD_URL: _FakeResponse(
            MD_URL, text=MD_BODY, ctype='text/markdown; charset=utf-8')}
        # _FakeResponse stores raw header; candidate splits on ';'
        routes[MD_URL].headers = {'content-type': 'text/markdown; charset=utf-8'}
        with _patched_httpx(routes, calls):
            assert _fetch_markdown_candidate(MD_URL) == MD_BODY


class TestTryHttpFetchProbe:
    def test_advertised_link_wins(self):
        calls = []
        routes = {
            PAGE_URL: _FakeResponse(PAGE_URL, text=ADVERTISING_HTML),
            MD_URL: _FakeResponse(MD_URL, text=MD_BODY, ctype='text/markdown'),
        }
        with _patched_httpx(routes, calls):
            result = try_http_fetch(PAGE_URL)
        assert result is not None
        assert result.source == 'markdown_probe'
        assert result.markdown == MD_BODY
        assert result.quality_score == 1.0
        assert result.content_type == 'text/markdown'
        assert calls == [PAGE_URL, MD_URL]

    def test_guessed_probe_on_thin_page(self):
        calls = []
        routes = {
            PAGE_URL: _FakeResponse(PAGE_URL, text=THIN_HTML),
            MD_URL: _FakeResponse(MD_URL, text=MD_BODY, ctype='text/markdown'),
        }
        with _patched_httpx(routes, calls):
            result = try_http_fetch(PAGE_URL)
        assert result is not None
        assert result.source == 'markdown_probe'
        assert result.markdown == MD_BODY

    def test_healthy_non_docs_page_makes_single_request(self):
        """Non-docs-shaped healthy pages never pay for speculation."""
        url = 'https://site.test/article/page'
        calls = []
        routes = {url: _FakeResponse(url, text=RICH_HTML)}
        with _patched_httpx(routes, calls):
            result = try_http_fetch(url)
        assert result is not None
        assert result.source == 'trafilatura'
        assert result.escalate_reason is None
        assert calls == [url]

    def test_docs_shaped_url_probed_even_when_extraction_passes(self):
        """The platform.claude.com shape: unadvertised .md sibling, healthy
        extraction — the docs-shaped guess still finds the canonical source."""
        calls = []
        routes = {
            PAGE_URL: _FakeResponse(PAGE_URL, text=RICH_HTML),
            MD_URL: _FakeResponse(MD_URL, text=MD_BODY, ctype='text/markdown'),
        }
        with _patched_httpx(routes, calls):
            result = try_http_fetch(PAGE_URL)
        assert result is not None
        assert result.source == 'markdown_probe'
        assert result.markdown == MD_BODY

    def test_negative_host_cached_no_repeat_probe(self):
        """First docs-shaped fetch pays one wasted GET; the second doesn't."""
        calls = []
        routes = {PAGE_URL: _FakeResponse(PAGE_URL, text=RICH_HTML)}
        with _patched_httpx(routes, calls):
            first = try_http_fetch(PAGE_URL)
            second = try_http_fetch(PAGE_URL)
        assert first is not None and second is not None
        assert first.source == 'trafilatura'
        assert second.source == 'trafilatura'
        # One probe GET total (404'd, cached negative), not two
        assert calls.count(MD_URL) == 1

    def test_positive_host_cached_probes_next_fetch(self):
        """A host that served .md once gets probed on its next fetch even
        on a non-docs-shaped path."""
        other_url = 'https://site.test/guide/page'
        other_md = 'https://site.test/guide/page.md'
        calls = []
        routes = {
            PAGE_URL: _FakeResponse(PAGE_URL, text=THIN_HTML),
            MD_URL: _FakeResponse(MD_URL, text=MD_BODY, ctype='text/markdown'),
            other_url: _FakeResponse(other_url, text=RICH_HTML),
            other_md: _FakeResponse(other_md, text=MD_BODY,
                                    ctype='text/markdown'),
        }
        with _patched_httpx(routes, calls):
            first = try_http_fetch(PAGE_URL)
            second = try_http_fetch(other_url)
        assert first is not None and first.source == 'markdown_probe'
        assert second is not None and second.source == 'markdown_probe'
        assert other_md in calls

    def test_bad_md_candidate_falls_through_to_escalation(self):
        calls = []
        routes = {
            PAGE_URL: _FakeResponse(PAGE_URL, text=THIN_HTML),
            MD_URL: _FakeResponse(MD_URL, text=THIN_HTML, ctype='text/html'),
        }
        with _patched_httpx(routes, calls):
            result = try_http_fetch(PAGE_URL)
        # Probe attempted but rejected — normal escalation behaviour preserved
        assert result is None or result.escalate_reason is not None
        assert MD_URL in calls

    def test_force_source_skips_probe(self):
        calls = []
        routes = {
            PAGE_URL: _FakeResponse(PAGE_URL, text=ADVERTISING_HTML),
            MD_URL: _FakeResponse(MD_URL, text=MD_BODY, ctype='text/markdown'),
        }
        with _patched_httpx(routes, calls):
            result = try_http_fetch(PAGE_URL, force_source='trafilatura')
        assert MD_URL not in calls
        if result is not None:
            assert result.source != 'markdown_probe'
