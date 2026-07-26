"""Empty-<pre> warning (passe-ropuze): code that was never in the DOM.

A JS component can render code via syntax-highlighter side-effects or hold
it in component state, leaving <pre><code> wrappers empty in the DOM — the
extractor is honest, but the code is silently missing (the antigravity
scrape, 2026-05-20). do_read must emit code_block_warning pointing at
`capture --bodies` for source-data discovery. Pages whose <pre> content
extracts normally must NOT warn — the false-positive case.

Runs against the throwaway local Chrome from conftest's `local_chrome`.
"""

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest

from passe.cli import connect, do_navigate, do_read


PROSE = '\n'.join(
    f'<p>Paragraph {i} of the plugin documentation, describing how the '
    f'system loads, registers and configures extensions at startup.</p>'
    for i in range(30)
)

# The antigravity shape: custom elements wrapping <pre><code> that is empty
# in the DOM at extraction time.
EMPTY_PRE_PAGE = f"""<!DOCTYPE html>
<html><head><title>Plugin Docs</title></head><body>
<article>
<h1>Plugins</h1>
{PROSE}
<app-code-snippet><pre><code></code></pre></app-code-snippet>
<app-code-snippet><pre><code></code></pre></app-code-snippet>
</article>
</body></html>"""

# Negative case: real code in the <pre> — must not warn, whichever
# extractor wins and however it renders the block.
REAL_PRE_PAGE = f"""<!DOCTYPE html>
<html><head><title>Plugin Docs</title></head><body>
<article>
<h1>Plugins</h1>
{PROSE}
<pre><code>def register(plugin):
    registry.append(plugin)
    return plugin
</code></pre>
</article>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    timeout = 2  # socket timeout — breaks keep-alive deadlock on shutdown

    def do_GET(self):
        page = EMPTY_PRE_PAGE if self.path == '/empty' else REAL_PRE_PAGE
        data = page.encode()
        self.close_connection = True
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def page_server():
    server = HTTPServer(('127.0.0.1', 0), _Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield port
    server.shutdown()


@pytest.mark.asyncio
async def test_empty_pre_wrappers_warn(local_chrome, page_server):
    """Empty <pre><code> inside custom elements → structured warning."""
    async with connect() as (client, _info):
        await client.create_tab()
        try:
            await client.send('Page.enable')
            await do_navigate(client, f'http://127.0.0.1:{page_server}/empty')
            result = await do_read(client)
        finally:
            await client.close_tab()

    cbw = result.get('code_block_warning')
    assert cbw is not None, 'expected code_block_warning on empty-<pre> page'
    assert cbw['reason'] == 'pre_present_but_no_code_extracted'
    assert cbw['pre_count'] == 2
    assert cbw['empty_pre_count'] == 2
    assert cbw['fenced_count'] == 0
    assert 'capture --bodies' in cbw['hint']
    assert 'app-code-snippet' in cbw.get('custom_elements', [])


@pytest.mark.asyncio
async def test_real_pre_content_does_not_warn(local_chrome, page_server):
    """<pre> blocks with real code must not trigger the warning."""
    async with connect() as (client, _info):
        await client.create_tab()
        try:
            await client.send('Page.enable')
            await do_navigate(client, f'http://127.0.0.1:{page_server}/real')
            result = await do_read(client)
        finally:
            await client.close_tab()

    assert 'code_block_warning' not in result, (
        f'false positive: {result.get("code_block_warning")}'
    )
