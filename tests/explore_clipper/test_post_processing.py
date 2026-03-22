#!/usr/bin/env python3
"""Test post-processing filters inspired by Obsidian Clipper's 56-filter system.

Obsidian has filters like: strip_md, strip_html, table, blockquote, callout,
replace, slice, split, join, map, etc.

Most are overkill for a CLI tool. But some would genuinely help passe:
- Stripping markdown formatting from extracted content
- Stripping links (keeping text)
- Truncating to N words
- Converting JSON arrays to markdown tables

Test which are useful and implement them as post-processing options for extract.
"""
import re
import json
import time
import urllib.request


def strip_markdown(text: str) -> str:
    """Remove markdown formatting, keep plain text.
    Equivalent to Obsidian's strip_md filter."""
    # Remove images
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
    # Remove links, keep text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove bold/italic
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'___(.+?)___', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    # Remove headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove code blocks (keep content)
    text = re.sub(r'^```\w*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```$', '', text, flags=re.MULTILINE)
    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove blockquotes
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    # Remove list markers
    text = re.sub(r'^[\s]*[-*+]\s', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s', '', text, flags=re.MULTILINE)
    # Collapse blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def strip_links(text: str) -> str:
    """Remove markdown links, keep text.
    [text](url) → text, ![alt](url) → (removed)"""
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text


def truncate_words(text: str, n: int) -> str:
    """Keep first N words."""
    words = text.split()
    if len(words) <= n:
        return text
    return ' '.join(words[:n]) + '...'


def json_to_table(data: str) -> str:
    """Convert JSON array of objects to markdown table.
    Inspired by Obsidian's table filter."""
    try:
        arr = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return data

    if not isinstance(arr, list) or len(arr) == 0:
        return data

    if isinstance(arr[0], dict):
        headers = list(arr[0].keys())
        lines = ['| ' + ' | '.join(headers) + ' |']
        lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        for row in arr:
            cells = [str(row.get(h, '')).replace('|', '\\|') for h in headers]
            lines.append('| ' + ' | '.join(cells) + ' |')
        return '\n'.join(lines)

    if isinstance(arr[0], list):
        lines = []
        for i, row in enumerate(arr):
            cells = [str(c).replace('|', '\\|') for c in row]
            lines.append('| ' + ' | '.join(cells) + ' |')
            if i == 0:
                lines.append('| ' + ' | '.join(['---'] * len(row)) + ' |')
        return '\n'.join(lines)

    return data


def test_filters():
    print("=" * 60)
    print("POST-PROCESSING FILTERS TEST")
    print("=" * 60)

    # Test content
    sample_md = """# How to Get Startup Ideas

The way to get startup ideas is not to try to think of startup ideas.
It's to look for **problems**, preferably [problems you have yourself](http://paulgraham.com/startupideas.html).

## The Best Ideas

> The very best startup ideas tend to have three things in common:
> they're something the founders themselves want, that they themselves
> can build, and that few others realize are worth doing.

Here's some code:

```python
def find_ideas():
    problems = get_my_problems()
    return [p for p in problems if p.is_underserved()]
```

- First point about *ideas*
- Second point about **execution**
- Third point about _timing_

For more, see [this essay](http://paulgraham.com/ds.html) and [this one](http://paulgraham.com/schlep.html).

---

Final thought: the best way to find startup ideas is to live in the future.
"""

    print("\n--- strip_markdown ---")
    stripped = strip_markdown(sample_md)
    print(stripped[:300])
    print(f"\nOriginal: {len(sample_md)} chars → Stripped: {len(stripped)} chars")
    assert '**' not in stripped, "bold markers should be removed"
    assert '[' not in stripped or '](' not in stripped, "links should be removed"
    assert '```' not in stripped, "code fences should be removed"
    print("✓ All assertions passed")

    print("\n--- strip_links ---")
    linkless = strip_links(sample_md)
    print(linkless[:300])
    link_count_before = len(re.findall(r'\[([^\]]+)\]\(', sample_md))
    link_count_after = len(re.findall(r'\[([^\]]+)\]\(', linkless))
    print(f"\nLinks: {link_count_before} → {link_count_after}")
    assert link_count_after == 0, "all links should be removed"
    assert 'problems you have yourself' in linkless, "link text should be kept"
    print("✓ All assertions passed")

    print("\n--- truncate_words ---")
    truncated = truncate_words(sample_md, 20)
    words = truncated.split()
    print(f"First 20 words: {truncated}")
    assert len(words) <= 21, f"should have ~20 words, got {len(words)}"
    assert truncated.endswith('...'), "should end with ellipsis"
    print("✓ All assertions passed")

    print("\n--- json_to_table ---")
    test_json = json.dumps([
        {"name": "Python", "type": "interpreted", "year": 1991},
        {"name": "Rust", "type": "compiled", "year": 2010},
        {"name": "Go", "type": "compiled", "year": 2009},
    ])
    table = json_to_table(test_json)
    print(table)
    assert '| name |' in table, "should have header row"
    assert '| --- |' in table, "should have separator row"
    assert '| Python |' in table, "should have data rows"
    print("✓ All assertions passed")

    # 2D array
    print("\n--- json_to_table (2D array) ---")
    test_2d = json.dumps([
        ["Language", "Type", "Year"],
        ["Python", "interpreted", 1991],
        ["Rust", "compiled", 2010],
    ])
    table_2d = json_to_table(test_2d)
    print(table_2d)
    assert '| Language |' in table_2d, "should have header from first row"
    print("✓ All assertions passed")

    print("\n" + "=" * 60)
    print("INTEGRATION PLAN")
    print("=" * 60)
    print("""
How these filters would integrate with passe extract:

1. As flags on extract/fetch verbs:
   extract --strip-md /tmp/plain.txt        # markdown → plain text
   extract --strip-links /tmp/nolinks.md    # remove hyperlinks
   extract --words 500 /tmp/summary.md      # first 500 words

2. As a pipe-friendly post-processor:
   passe fetch URL | passe filter strip-md
   passe fetch URL | passe filter words:500

3. As step-output post-processing in NDJSON:
   The step output already has word_count — adding a
   truncated preview would be free.

RECOMMENDATION:
- Add strip_markdown() and strip_links() to passe as utility functions
- Add --strip-links flag to extract (most commonly needed)
- Add --words N flag to extract for truncation
- Skip json_to_table — too niche, users can pipe through jq
- Skip strip_md as a flag — users can pipe through sed/tr
""")

    print("Performance:")
    t0 = time.monotonic()
    for _ in range(1000):
        strip_markdown(sample_md)
    ms = round((time.monotonic() - t0) * 1000, 1)
    print(f"  strip_markdown × 1000: {ms}ms ({ms/1000:.3f}ms each)")

    t0 = time.monotonic()
    for _ in range(1000):
        strip_links(sample_md)
    ms = round((time.monotonic() - t0) * 1000, 1)
    print(f"  strip_links × 1000: {ms}ms ({ms/1000:.3f}ms each)")


if __name__ == '__main__':
    test_filters()
