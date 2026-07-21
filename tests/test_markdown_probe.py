"""Markdown-source probe in the HTTP fast-path (passe-nuguza).

Mintlify-class docs sites serve a pristine .md sibling of every page and
advertise it via <link rel="alternate" type="text/markdown">. The probe
returns that canonical source instead of extracting from a 1MB+ HTML shell.
Guessed URL.md probes fire only on escalation paths — healthy fetches make
exactly one request.
"""

from unittest.mock import patch

from passe.fastpath import (
    _fetch_markdown_candidate,
    _markdown_source_url,
    try_http_fetch,
)


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

    def test_healthy_page_makes_single_request(self):
        calls = []
        routes = {PAGE_URL: _FakeResponse(PAGE_URL, text=RICH_HTML)}
        with _patched_httpx(routes, calls):
            result = try_http_fetch(PAGE_URL)
        assert result is not None
        assert result.source == 'trafilatura'
        assert result.escalate_reason is None
        assert calls == [PAGE_URL]

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
