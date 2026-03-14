# /// script
# requires-python = ">=3.11"
# dependencies = ["trafilatura>=2.0"]
# ///
"""
Pluggable extraction functions for the bench harness.

Each extractor takes (html: str, url: str) and returns markdown string.
Register new extractors by adding to EXTRACTORS dict.
"""

from __future__ import annotations

from typing import Protocol


class Extractor(Protocol):
    """Protocol for extraction functions."""
    def __call__(self, html: str, url: str) -> str: ...


def trafilatura_default(html: str, url: str) -> str:
    """Trafilatura with passe's current settings."""
    import trafilatura
    result = trafilatura.extract(
        html, url=url,
        include_formatting=True,
        include_links=True,
        include_tables=True,
    )
    return result or ""


def trafilatura_recall(html: str, url: str) -> str:
    """Trafilatura with favor_recall — less aggressive stripping."""
    import trafilatura
    result = trafilatura.extract(
        html, url=url,
        include_formatting=True,
        include_links=True,
        include_tables=True,
        favor_recall=True,
    )
    return result or ""


def trafilatura_precision(html: str, url: str) -> str:
    """Trafilatura with favor_precision — more aggressive stripping."""
    import trafilatura
    result = trafilatura.extract(
        html, url=url,
        include_formatting=True,
        include_links=True,
        include_tables=True,
        favor_precision=True,
    )
    return result or ""


def readability_markdownify(html: str, url: str) -> str:
    """readability-lxml → markdownify chain. The proposed middle tier."""
    try:
        from readability import Document
        from markdownify import markdownify as md
    except ImportError:
        return "[readability_markdownify unavailable — install readability-lxml markdownify]"

    doc = Document(html, url=url)
    clean_html = doc.summary()
    return md(clean_html, heading_style="ATX", strip=['script', 'style'])


def html2text_default(html: str, url: str) -> str:
    """html2text — converter only, no boilerplate removal."""
    try:
        import html2text
    except ImportError:
        return "[html2text unavailable — install html2text]"

    h = html2text.HTML2Text()
    h.body_width = 0  # don't wrap
    h.ignore_images = False
    h.ignore_links = False
    return h.handle(html)


def fastpath_with_gate(html: str, url: str) -> str:
    """Trafilatura + quality gate — returns extraction only if gate passes.

    Returns empty string if gate rejects (simulates escalation to Chrome).
    This lets us measure how often the gate correctly/incorrectly rejects.
    """
    import sys
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'src'))
    from passe.fastpath import quality_gate
    import trafilatura

    result = trafilatura.extract(
        html, url=url,
        include_formatting=True,
        include_links=True,
        include_tables=True,
    )
    if not result:
        return ""  # would escalate

    score, signals = quality_gate(result, html, url)
    if score < 0.35:
        return ""  # would escalate to Chrome

    return result


# Registry — add new extractors here
EXTRACTORS: dict[str, Extractor] = {
    "trafilatura": trafilatura_default,
    "trafilatura-recall": trafilatura_recall,
    "trafilatura-precision": trafilatura_precision,
    "readability+markdownify": readability_markdownify,
    "html2text": html2text_default,
    "fastpath": fastpath_with_gate,
}
