#!/usr/bin/env python3
"""Test selection clipping via Range API.

Obsidian Clipper captures page selections using:
  window.getSelection() → Range.cloneContents() → XMLSerializer

This test prototypes the JS and the passe verb that would use it.
"""

# Proposed JS for selection extraction (would run in Chrome via eval)
SELECTION_EXTRACT_JS = r'''(() => {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
    return JSON.stringify({ hasSelection: false });
  }

  const range = sel.getRangeAt(0);
  const fragment = range.cloneContents();

  // Serialize to HTML
  const div = document.createElement('div');
  div.appendChild(fragment);
  const html = div.innerHTML;

  // Also get plain text
  const text = sel.toString();

  // Get bounding rect for context
  const rect = range.getBoundingClientRect();

  return JSON.stringify({
    hasSelection: true,
    html: html,
    text: text,
    charCount: text.length,
    wordCount: text.split(/\s+/).filter(Boolean).length,
    rect: {
      top: Math.round(rect.top),
      left: Math.round(rect.left),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
    }
  });
})()'''

# How it would be used in a passe script
USAGE_EXAMPLE = """
# Example: Select text programmatically and extract it
passe run - <<'EOF'
goto https://example.com/article
eval (() => {
  const range = document.createRange();
  const article = document.querySelector('article');
  range.selectNodeContents(article.querySelector('p:first-of-type'));
  window.getSelection().removeAllRanges();
  window.getSelection().addRange(range);
})()
extract --selection /tmp/selected.md
EOF
"""

# How it would integrate with do_extract
INTEGRATION_SKETCH = """
# In verbs.py, add to do_read:

async def do_read(client, path=None, force_source=None, selection_only=False):
    if selection_only:
        result = await do_eval(client, SELECTION_EXTRACT_JS)
        data = json.loads(result)
        if not data['hasSelection']:
            return {'markdown': '', 'warning': 'no selection', 'source': 'selection'}

        # Convert selection HTML to markdown using Turndown
        # (or just use the plain text for simple cases)
        html = data['html']
        # ... run through Readability/Turndown or trafilatura ...
        return {'markdown': ..., 'source': 'selection', 'word_count': data['wordCount']}
"""


def run():
    print("=" * 60)
    print("SELECTION CLIPPING VIA RANGE API")
    print("=" * 60)
    print()
    print("What Obsidian Clipper does:")
    print("  1. Captures window.getSelection() when clip button pressed")
    print("  2. Uses Range.cloneContents() to get DOM fragment")
    print("  3. Serializes with XMLSerializer (they use innerHTML instead)")
    print("  4. Stores as selectedHtml and converts to selectedMarkdown")
    print()
    print("What this would look like in passe:")
    print()
    print(f"JS snippet ({len(SELECTION_EXTRACT_JS)} chars):")
    print(SELECTION_EXTRACT_JS[:200] + "...")
    print()
    print("Usage:")
    print(USAGE_EXAMPLE)
    print()
    print("Integration with do_read:")
    print("  - Add --selection flag to extract verb")
    print("  - eval SELECTION_EXTRACT_JS to get selected HTML")
    print("  - Run selection HTML through Turndown (browser-side) for markdown")
    print("  - Return as {markdown, source: 'selection', word_count}")
    print()
    print("Key insight: Selection clipping is useful when combined with")
    print("programmatic selection via eval. Examples:")
    print("  1. Select first 3 paragraphs of an article")
    print("  2. Select a specific table")
    print("  3. Select code examples only")
    print("  4. Select the visible viewport content")
    print()
    print("VERDICT: Low priority. The eval + extract pattern already works")
    print("for targeted extraction. Selection adds a layer of indirection")
    print("that's mainly useful for interactive (extension) use cases.")
    print("But the JS snippet is worth keeping as a utility.")


if __name__ == '__main__':
    run()
