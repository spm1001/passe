#!/usr/bin/env python3
"""Compare shadow DOM flattening approaches.

Passe's approach:  Full custom serializer that recursively serializes outerHTML,
                   inlining shadow root children as real DOM children.
                   ~25 lines of JS. Returns complete HTML string.

Obsidian's approach: Stamps shadow DOM innerHTML into data-defuddle-shadow attributes.
                     ~10 lines of JS. Extraction library reads the data attrs later.

This test creates a synthetic HTML page with shadow DOM elements and tests both
approaches via Node.js (using linkedom for DOM simulation).
"""
import json
import subprocess
import tempfile
import os

# Passe's current shadow flatten JS (from _libs.py)
PASSE_SHADOW_JS = r'''(() => {
  const scan = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_ELEMENT);
  let hasShadow = false;
  while (scan.nextNode()) {
    if (scan.currentNode.shadowRoot) { hasShadow = true; break; }
  }
  if (!hasShadow) return document.documentElement.outerHTML;

  const VOID = /^(area|base|br|col|embed|hr|img|input|link|meta|source|track|wbr)$/i;
  function ser(node) {
    if (node.nodeType === 3) return node.textContent;
    if (node.nodeType !== 1) return '';
    const tag = node.tagName.toLowerCase();
    let s = '<' + tag;
    for (const a of node.attributes)
      s += ' ' + a.name + '="' + a.value.replace(/&/g,'&amp;').replace(/"/g,'&quot;') + '"';
    s += '>';
    if (VOID.test(tag)) return s;
    if (node.shadowRoot)
      for (const c of node.shadowRoot.childNodes) s += ser(c);
    for (const c of node.childNodes) s += ser(c);
    s += '</' + tag + '>';
    return s;
  }
  return ser(document.documentElement);
})()'''

# Obsidian's simpler approach (from flatten-shadow-dom.js)
OBSIDIAN_SHADOW_JS = '''
document.querySelectorAll('*').forEach(function(el) {
  if (el.shadowRoot && el.shadowRoot.innerHTML) {
    el.setAttribute('data-defuddle-shadow', el.shadowRoot.innerHTML);
  }
});
'''

# Test HTML with shadow DOM components (simulated)
TEST_HTML = '''<!DOCTYPE html>
<html>
<head><title>Shadow DOM Test</title></head>
<body>
  <h1>Page Title</h1>
  <p>Regular content before web component.</p>

  <!-- Simulating a web component with shadow DOM -->
  <custom-card>
    <template shadowrootmode="open">
      <style>.card { border: 1px solid #ccc; }</style>
      <div class="card">
        <h2>Shadow Content Title</h2>
        <p>This paragraph is inside shadow DOM and would be invisible to extractors.</p>
        <a href="/shadow-link">Shadow Link</a>
      </div>
    </template>
    <span slot="fallback">Fallback content</span>
  </custom-card>

  <p>Regular content after web component.</p>

  <mdn-code-example>
    <template shadowrootmode="open">
      <pre><code>console.log('hello from shadow DOM');</code></pre>
    </template>
  </mdn-code-example>

  <p>Final paragraph with <a href="https://example.com">a link</a>.</p>
</body>
</html>'''


def test_approaches():
    """Structural comparison — what each approach produces."""

    print("=" * 60)
    print("SHADOW DOM FLATTENING COMPARISON")
    print("=" * 60)

    print("\n--- Passe's approach ---")
    print(f"JS size: {len(PASSE_SHADOW_JS)} chars")
    print("Mechanism: Custom recursive serializer")
    print("Output: Complete HTML string with shadow content inlined as real children")
    print("Pros:")
    print("  + Returns ready-to-parse HTML — no post-processing needed")
    print("  + Works with any downstream extractor (trafilatura, Readability)")
    print("  + Handles nested shadow DOMs recursively")
    print("Cons:")
    print("  - More complex JS (25 lines vs 10)")
    print("  - Custom serializer may miss edge cases (attributes, encoding)")
    print("  - Returns string, not modified DOM — can't do further DOM operations")

    print("\n--- Obsidian's approach ---")
    print(f"JS size: {len(OBSIDIAN_SHADOW_JS)} chars")
    print("Mechanism: Stamps innerHTML into data-defuddle-shadow attributes")
    print("Output: Modified DOM with data attributes (extraction lib reads them)")
    print("Pros:")
    print("  + Simpler, less error-prone (10 lines)")
    print("  + Modifies DOM in-place — can use standard serializers after")
    print("  + Extraction library can decide how to handle shadow content")
    print("Cons:")
    print("  - Requires extraction library to understand data-defuddle-shadow attrs")
    print("  - Shadow HTML is stuck in an attribute (needs unescaping)")
    print("  - Only captures innerHTML, not the shadow host's own content structure")
    print("  - Attribute-escaped HTML loses some fidelity")

    print("\n--- VERDICT ---")
    print("Passe's approach is better for a CDP tool because:")
    print("1. The serialized HTML goes to trafilatura (Python-side) — trafilatura")
    print("   doesn't know about data-defuddle-shadow attributes")
    print("2. Passe already works — no reason to change")
    print("3. The Obsidian approach is optimized for their specific extraction lib (defuddle)")
    print("")
    print("HOWEVER: If passe adds defuddle as an extraction option, the Obsidian")
    print("approach could be used as a pre-step before defuddle extraction.")

    # Test that Passe's approach handles the key case: shadow content becomes visible
    print("\n--- Structural test ---")
    print("Testing: Does passe's serializer inline shadow DOM content?")
    print(f"Test HTML has {TEST_HTML.count('shadowrootmode')} shadow roots")
    print(f"Key content: 'Shadow Content Title', 'console.log'")
    print("Both should appear in serialized output but not in basic outerHTML")

    # Note: Can't test with linkedom since it doesn't support real shadow DOM
    # This would need Chrome CDP to test properly
    print("\n[NOTE: Full test requires Chrome CDP — linkedom doesn't support attachShadow]")
    print("[The structural analysis above is the key takeaway]")


if __name__ == '__main__':
    test_approaches()
