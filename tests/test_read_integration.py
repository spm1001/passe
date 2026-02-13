"""
Browser integration test: read ratio warning on real SPA.

Tests that the <10% ratio warning fires when passe reads a
client-rendered SPA where Readability extracts a small article
while the total page text is dominated by navigation chrome.

Requires Chrome running on port 9222. Skipped otherwise.
"""

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen

import pytest

from passe.cli import connect, do_navigate, do_read


def _chrome_available():
    try:
        with urlopen('http://localhost:9222/json/version', timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _chrome_available(),
    reason='Chrome not running on port 9222',
)


# SPA fixture: client-side rendered dashboard.
# ~30K chars of nav/sidebar/footer chrome, ~1K chars of article.
# Readability strips the chrome → ratio ≈ 3%, well below 10% threshold.
SPA_FIXTURE = """\
<!DOCTYPE html>
<html><head><title>Dashboard App</title></head>
<body>
<div id="app"></div>
<script>
var app = document.getElementById('app');
var html = '';

// Navigation chrome (~10K chars visible text)
html += '<nav class="navigation">';
for (var i = 0; i < 200; i++) {
  html += '<a href="/p/' + i + '">Navigation Menu Item ' + i + ' - Dashboard Category</a> ';
}
html += '</nav>';

// Sidebar chrome (~18K chars visible text)
html += '<div class="sidebar">';
for (var i = 0; i < 200; i++) {
  html += '<div class="widget">Sidebar Widget Panel ' + i +
    ': Displaying current system metrics and real-time status indicators</div>';
}
html += '</div>';

// Small article content (~1K chars, above Readability 500-char threshold)
html += '<article><h1>Dashboard Overview</h1>';
for (var i = 0; i < 8; i++) {
  html += '<p>This is paragraph ' + i +
    ' of the main content section providing an overview of the application ' +
    'dashboard and its monitoring capabilities for the entire system.</p>';
}
html += '</article>';

// Footer chrome (~3K chars visible text)
html += '<footer class="footer">';
for (var i = 0; i < 150; i++) {
  html += '<a href="/legal/' + i + '">Legal Policy Document ' + i + '</a> ';
}
html += '</footer>';

app.innerHTML = html;
</script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(SPA_FIXTURE.encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def spa_server():
    """Start a local HTTP server serving the SPA fixture."""
    server = HTTPServer(('127.0.0.1', 0), _Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield port
    server.shutdown()


@pytest.mark.asyncio
async def test_ratio_warning_fires_on_spa(spa_server):
    """Read a client-rendered SPA — ratio warning should fire."""
    ws, client = await connect()
    try:
        await client.create_tab()
        await client.send('Page.enable')
        await do_navigate(client, f'http://127.0.0.1:{spa_server}')
        result = await do_read(client)

        assert result['warning'] is not None, (
            f'Expected ratio warning but got none. '
            f'Markdown length: {len(result["markdown"])}'
        )
        # Ratio warning says "incomplete"; fallback warning says "fell back".
        # We specifically want the ratio path, not the fallback path.
        assert 'incomplete' in result['warning'], (
            f'Expected ratio warning but got: {result["warning"]}'
        )
    finally:
        await client.close_tab()
        await client.stop()
        await ws.close()
