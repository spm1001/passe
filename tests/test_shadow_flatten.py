"""
Test: Shadow DOM flattener JS (SHADOW_FLATTEN_JS)
=================================================

Runs the actual JS against a mock DOM via Node.js + jsdom.
No Chrome needed — jsdom provides the DOM environment.

Tests both paths:
  - Fast path: no shadow roots → returns outerHTML directly
  - Shadow path: shadow roots → recursive serializer inlines shadow content
"""

import json
import os
import subprocess
import textwrap

import pytest

from passe._libs import SHADOW_FLATTEN_JS


def _run_js_with_dom(html: str, setup_js: str = "") -> str:
    """Run SHADOW_FLATTEN_JS against an HTML string using jsdom.

    Args:
        html: The HTML to parse into a jsdom document.
        setup_js: Extra JS to run after DOM creation but before the flattener
                  (e.g., to attach shadow roots — jsdom can't parse declarative ones).

    Returns:
        The string result of evaluating SHADOW_FLATTEN_JS.
    """
    import tempfile

    # Write the test script to a temp file — avoids shell escaping issues
    # and handles the multi-line JS cleanly.
    script = (
        f'const {{ JSDOM }} = require("jsdom");\n'
        f'const dom = new JSDOM({json.dumps(html)});\n'
        f'const document = dom.window.document;\n'
        f'const NodeFilter = dom.window.NodeFilter;\n'
        f'{setup_js}\n'
        f'const result = {SHADOW_FLATTEN_JS};\n'
        f'process.stdout.write(result);\n'
    )

    # Write temp file in project root so Node can find node_modules/jsdom
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fd, path = tempfile.mkstemp(suffix=".js", dir=project_root)
    try:
        os.write(fd, script.encode())
        os.close(fd)
        result = subprocess.run(
            ["node", path],
            capture_output=True, text=True, timeout=10,
            cwd=project_root,
        )
    finally:
        os.unlink(path)

    if result.returncode != 0:
        pytest.fail(f"Node.js failed:\n{result.stderr}")
    return result.stdout


# ── Structural tests (pure Python, no Node needed) ───────

def test_shadow_flatten_js_importable():
    """SHADOW_FLATTEN_JS is importable from _libs."""
    assert isinstance(SHADOW_FLATTEN_JS, str)
    assert len(SHADOW_FLATTEN_JS) > 100


def test_shadow_flatten_js_contains_key_patterns():
    """JS contains the expected fast-path check and serializer."""
    assert "shadowRoot" in SHADOW_FLATTEN_JS
    assert "outerHTML" in SHADOW_FLATTEN_JS
    assert "VOID" in SHADOW_FLATTEN_JS
    assert "ser(" in SHADOW_FLATTEN_JS  # recursive serializer function
    assert "hasShadow" in SHADOW_FLATTEN_JS


# ── Fast path: no shadow DOM ─────────────────────────────

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@pytest.mark.skipif(
    subprocess.run(
        ["node", "-e", "require('jsdom')"],
        capture_output=True, cwd=_PROJECT_ROOT,
    ).returncode != 0,
    reason="jsdom not installed (npm install jsdom in project root)",
)
class TestWithJsdom:
    """Tests that run SHADOW_FLATTEN_JS in jsdom."""

    def test_fast_path_no_shadow_dom(self):
        """No shadow roots → returns outerHTML directly."""
        html = "<html><head></head><body><p>Hello world</p></body></html>"
        result = _run_js_with_dom(html)
        assert "<p>Hello world</p>" in result
        assert "<body>" in result

    def test_fast_path_preserves_attributes(self):
        """Fast path preserves element attributes."""
        html = '<html><head></head><body><div id="main" class="container">Content</div></body></html>'
        result = _run_js_with_dom(html)
        assert 'id="main"' in result
        assert 'class="container"' in result

    def test_shadow_dom_content_inlined(self):
        """Shadow root content appears in serialized output."""
        html = "<html><head></head><body><my-widget></my-widget></body></html>"
        setup = textwrap.dedent("""\
            const widget = document.querySelector("my-widget");
            const shadow = widget.attachShadow({ mode: "open" });
            const p = document.createElement("p");
            p.textContent = "Shadow content here";
            shadow.appendChild(p);
        """)
        result = _run_js_with_dom(html, setup)
        assert "Shadow content here" in result
        assert "<my-widget>" in result

    def test_shadow_dom_with_light_dom_children(self):
        """Both shadow root content AND light DOM children appear."""
        html = "<html><head></head><body><my-widget><span>Light child</span></my-widget></body></html>"
        setup = textwrap.dedent("""\
            const widget = document.querySelector("my-widget");
            const shadow = widget.attachShadow({ mode: "open" });
            const p = document.createElement("p");
            p.textContent = "Shadow content";
            shadow.appendChild(p);
        """)
        result = _run_js_with_dom(html, setup)
        assert "Shadow content" in result
        assert "Light child" in result

    def test_nested_shadow_dom(self):
        """Nested shadow roots (shadow within shadow) are flattened."""
        html = "<html><head></head><body><outer-el></outer-el></body></html>"
        setup = textwrap.dedent("""\
            const outer = document.querySelector("outer-el");
            const outerShadow = outer.attachShadow({ mode: "open" });
            const inner = document.createElement("inner-el");
            outerShadow.appendChild(inner);
            const innerShadow = inner.attachShadow({ mode: "open" });
            const span = document.createElement("span");
            span.textContent = "Deep nested content";
            innerShadow.appendChild(span);
        """)
        result = _run_js_with_dom(html, setup)
        assert "Deep nested content" in result

    def test_void_elements_self_close(self):
        """Void elements (img, br, etc.) don't get closing tags."""
        html = '<html><head></head><body><img src="test.png"><br></body></html>'
        result = _run_js_with_dom(html)
        assert "</img>" not in result
        assert "</br>" not in result
        assert 'src="test.png"' in result

    def test_attribute_escaping(self):
        """Attributes with special characters are escaped."""
        html = '<html><head></head><body><div data-value="a&amp;b&quot;c">Text</div></body></html>'
        result = _run_js_with_dom(html)
        # The serializer should escape & and " in attribute values
        assert "Text" in result

    def test_multiple_shadow_hosts(self):
        """Multiple shadow hosts on the same page all get inlined."""
        html = "<html><head></head><body><widget-a></widget-a><widget-b></widget-b></body></html>"
        setup = textwrap.dedent("""\
            const a = document.querySelector("widget-a");
            const shadowA = a.attachShadow({ mode: "open" });
            shadowA.innerHTML = "<p>Content A</p>";

            const b = document.querySelector("widget-b");
            const shadowB = b.attachShadow({ mode: "open" });
            shadowB.innerHTML = "<p>Content B</p>";
        """)
        result = _run_js_with_dom(html, setup)
        assert "Content A" in result
        assert "Content B" in result
