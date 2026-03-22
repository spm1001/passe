"""Post-processing utilities for extracted markdown content.

Inspired by Obsidian Clipper's filter system. Only the genuinely useful
filters for a CLI tool.
"""
import re
from urllib.parse import urljoin


def resolve_relative_urls(markdown: str, base_url: str) -> str:
    """Resolve relative URLs in markdown links/images to absolute.

    trafilatura does NOT resolve relative URLs even when passed url=.
    This fixes links like [text](schlep.html) → [text](https://example.com/schlep.html).
    """
    if not base_url:
        return markdown

    def _resolve(m):
        text = m.group(1)
        url = m.group(2)
        # Skip already-absolute URLs, anchors, mailto, data URIs
        if url.startswith(('http://', 'https://', 'mailto:', 'data:', '#', '//')):
            return m.group(0)
        return f'[{text}]({urljoin(base_url, url)})'

    # Markdown links: [text](url)
    markdown = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _resolve, markdown)

    # Markdown images: ![alt](url) — same pattern with ! prefix
    def _resolve_img(m):
        alt = m.group(1)
        url = m.group(2)
        if url.startswith(('http://', 'https://', 'data:', '//')):
            return m.group(0)
        return f'![{alt}]({urljoin(base_url, url)})'

    markdown = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _resolve_img, markdown)

    return markdown


def strip_links(markdown: str) -> str:
    """Remove markdown links, keeping the link text.

    [text](url) → text
    ![alt](url) → (removed)
    """
    # Remove images first (before links, since ![...] contains [...])
    markdown = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', markdown)
    # Remove links, keep text
    markdown = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', markdown)
    return markdown


def truncate_words(markdown: str, n: int) -> str:
    """Keep first N words of markdown content."""
    words = markdown.split()
    if len(words) <= n:
        return markdown
    return ' '.join(words[:n]) + '...'
