"""HTTP fast-path for passe fetch — try before Chrome.

Fetches a URL via httpx, runs trafilatura, and applies a composite quality
gate to decide whether the result is good enough or needs Chrome escalation.

The quality gate multiplies penalty factors for various signals. Below the
threshold, the result is rejected and Chrome takes over.
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass


# --- Quality gate thresholds (from Deep Research, 2026-03-13) ---

QUALITY_THRESHOLD = 0.35  # below this, escalate to Chrome
MIN_WORDS = 50            # instant reject
SUSPICIOUS_WORDS = 100    # penalty


# Stop words for English (top function words)
_STOP_WORDS = frozenset(
    'the be to of and a in that have i it for not on with he as you do at '
    'this but his by from they we say her she or an will my one all would '
    'there their what so up out if about who get which go me when make can '
    'like time no just him know take people into year your good some could '
    'them see other than then now look only come its over think also back '
    'after use two how our work first well way even new want because any '
    'these give day most us is are was were been has had do does did '
    'should may might must shall need'.split()
)

# Paywall / auth wall patterns
_PAYWALL_PATTERNS = [
    r'subscribe\s+to\s+(read|continue|access)',
    r'premium\s+content',
    r'members?\s+only',
    r'sign\s+in\s+to\s+(read|continue|view)',
    r'create\s+(a\s+)?free\s+account',
    r'already\s+a\s+(subscriber|member)',
    r'unlock\s+(this|full)\s+(article|story)',
]
_PAYWALL_RE = re.compile('|'.join(_PAYWALL_PATTERNS), re.IGNORECASE)

# CAPTCHA patterns
_CAPTCHA_PATTERNS = [
    'cf-challenge', 'challenge-running', 'challenge-platform',
    'g-recaptcha', 'recaptcha', 'hcaptcha', 'cf-turnstile',
    'ddos-protection',
]

# SPA shell detectors — if these match, skip trafilatura and go straight to Chrome
_SPA_SHELL_PATTERNS = [
    (r'<div\s+id=["\']root["\']\s*>\s*</div>', 'React SPA shell'),
    (r'<div\s+id=["\']app["\']\s*>\s*</div>', 'Vue SPA shell'),
    (r'<app-root[^>]*>\s*</app-root>', 'Angular SPA shell'),
    (r'<div\s+id=["\']__next["\']\s*>\s*</div>', 'Next.js SPA shell'),
]

# Framework shortcuts — extract content directly from HTML without trafilatura
_NEXT_DATA_RE = re.compile(
    r'<script\s+id=["\']__NEXT_DATA__["\']\s+type=["\']application/json["\']>\s*({.*?})\s*</script>',
    re.DOTALL,
)

# Canonical markdown source advertisement (Mintlify and the llms.txt
# convention): <link rel="alternate" type="text/markdown" href="...">
_MD_LINK_RE = re.compile(
    r'<link\b[^>]*type=["\']text/markdown["\'][^>]*>', re.IGNORECASE)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)

_MARKDOWN_CONTENT_TYPES = frozenset(
    {'text/markdown', 'text/x-markdown', 'text/plain'})

# Host-level memory of guessed-probe outcomes: serving .md siblings is a
# platform property, so one answer per host. Keeps the speculative GET off
# .md-less docs sites (MDN, docs.python.org) after first contact.
PROBE_CACHE_PATH = None  # resolved lazily; tests patch this
_PROBE_CACHE_TTL = 7 * 24 * 3600


def _probe_cache_file():
    from pathlib import Path
    return PROBE_CACHE_PATH or Path.home() / '.passe' / 'md-hosts.json'


def _probe_cache_get(host: str) -> bool | None:
    """True/False if we have a fresh answer for this host, else None."""
    import json as json_mod
    try:
        with open(_probe_cache_file()) as f:
            cache = json_mod.load(f)
        entry = cache.get(host)
        if not entry or time.time() - entry.get('ts', 0) > _PROBE_CACHE_TTL:
            return None
        return bool(entry.get('md'))
    except Exception:
        return None


def _probe_cache_set(host: str, has_md: bool):
    """Best-effort write; last writer wins, failures are silent."""
    import json as json_mod
    path = _probe_cache_file()
    try:
        try:
            with open(path) as f:
                cache = json_mod.load(f)
        except Exception:
            cache = {}
        cache[host] = {'md': has_md, 'ts': time.time()}
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json_mod.dump(cache, f)
    except Exception:
        pass


def _docs_shaped(url: str) -> bool:
    """URLs where unadvertised .md siblings are plausible enough to spend
    one GET on (platform.claude.com-style docs platforms)."""
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    return (parts.netloc.startswith('docs.')
            or '/docs/' in parts.path)


@dataclass
class FastPathResult:
    """Result from the HTTP fast-path."""
    markdown: str
    url: str                    # final URL after redirects
    source: str                 # 'trafilatura', 'next-data', 'raw'
    quality_score: float        # 0-1 composite quality
    word_count: int
    fetch_ms: float
    content_type: str | None = None
    quality_signals: dict | None = None  # for diagnostics
    escalate_reason: str | None = None   # why it was rejected


def _count_words(text: str) -> int:
    return len(re.findall(r'\w+', text))


def _stop_words_ratio(text: str) -> float:
    """Fraction of words that are stop words. Content > 0.30, boilerplate < 0.20."""
    words = re.findall(r'\w+', text.lower())
    if not words:
        return 0.0
    return sum(1 for w in words if w in _STOP_WORDS) / len(words)


def _link_density(html: str) -> float:
    """Ratio of text inside <a> tags to total text. > 0.33 suggests boilerplate."""
    # Quick approximation: count chars in anchor text vs total text
    anchor_texts = re.findall(r'<a\b[^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE)
    anchor_chars = sum(len(re.sub(r'<[^>]+>', '', t)) for t in anchor_texts)
    # Total visible text (strip all tags)
    total_chars = len(re.sub(r'<[^>]+>', '', html))
    if total_chars == 0:
        return 0.0
    return anchor_chars / total_chars


def _detect_captcha(html: str) -> bool:
    """Detect active CAPTCHA challenges — not just keyword presence.

    Looks for CAPTCHA patterns in the <body> only (not scripts/comments)
    and requires short visible text (a real CAPTCHA page has almost no content).
    """
    # Only check body content, not scripts or head
    body_match = re.search(r'<body[^>]*>(.*)</body>', html, re.DOTALL | re.IGNORECASE)
    if not body_match:
        return False
    body = body_match.group(1)
    # Strip script and style tags
    body_stripped = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', body,
                          flags=re.DOTALL | re.IGNORECASE)
    body_lower = body_stripped.lower()

    has_captcha = any(p in body_lower for p in _CAPTCHA_PATTERNS)
    if not has_captcha:
        return False

    # Real CAPTCHA pages have very little visible text
    visible_text = re.sub(r'<[^>]+>', '', body_stripped).strip()
    return len(visible_text) < 2000


def _detect_paywall(text: str) -> bool:
    return bool(_PAYWALL_RE.search(text))


def _detect_spa_shell(html: str) -> str | None:
    """Returns description if SPA shell detected, None otherwise."""
    for pattern, desc in _SPA_SHELL_PATTERNS:
        if re.search(pattern, html, re.IGNORECASE):
            # Also check body text is thin
            body_match = re.search(r'<body[^>]*>(.*)</body>', html, re.DOTALL | re.IGNORECASE)
            if body_match:
                body_text = re.sub(r'<[^>]+>', '', body_match.group(1)).strip()
                if len(body_text) < 200:
                    return desc
    return None


def _try_next_data(html: str, url: str) -> str | None:
    """Try extracting content from Next.js __NEXT_DATA__ script tag."""
    import json as json_mod

    match = _NEXT_DATA_RE.search(html)
    if not match:
        return None

    try:
        data = json_mod.loads(match.group(1))
    except (json_mod.JSONDecodeError, ValueError):
        return None

    # Navigate to page props — structure varies but commonly:
    # data.props.pageProps contains the article/page content
    props = data.get('props', {}).get('pageProps', {})
    if not props:
        return None

    # Try common content fields
    for key in ('content', 'body', 'article', 'post', 'markdownBody',
                'mdxSource', 'source', 'html', 'text'):
        content = props.get(key)
        if isinstance(content, str) and len(content) > 100:
            return content

    # If pageProps has nested objects with content, try to extract readable text
    # by JSON-dumping with some structure
    text_parts = _extract_text_from_props(props)
    if text_parts and _count_words(' '.join(text_parts)) > 50:
        return '\n\n'.join(text_parts)

    return None


def _extract_text_from_props(obj, depth=0) -> list[str]:
    """Recursively extract text strings from Next.js page props."""
    if depth > 5:
        return []
    parts = []
    if isinstance(obj, str):
        # Only keep substantial strings (not IDs, dates, etc.)
        if len(obj) > 50 and ' ' in obj:
            parts.append(obj)
    elif isinstance(obj, list):
        for item in obj:
            parts.extend(_extract_text_from_props(item, depth + 1))
    elif isinstance(obj, dict):
        for val in obj.values():
            parts.extend(_extract_text_from_props(val, depth + 1))
    return parts


def _count_html_elements(html: str, tag: str) -> int:
    """Count occurrences of an HTML tag in raw HTML."""
    return len(re.findall(rf'<{tag}\b', html, re.IGNORECASE))


def _markdown_source_url(html: str, final_url: str, guess: bool) -> str | None:
    """Find a canonical markdown URL for this page, or None.

    Advertised (authoritative): a <link rel="alternate" type="text/markdown">
    tag in the page HTML. Guessed: URL + '.md' — only when guess=True, so
    healthy fetches never pay for speculation.
    """
    from urllib.parse import urljoin, urlsplit
    link = _MD_LINK_RE.search(html)
    if link:
        href = _HREF_RE.search(link.group(0))
        if href:
            return urljoin(final_url, href.group(1))
    if not guess:
        return None
    parts = urlsplit(final_url)
    path = parts.path
    if not path or path == '/' or path.endswith('.md'):
        return None
    return f'{parts.scheme}://{parts.netloc}{path.rstrip("/")}.md'


def _fetch_markdown_candidate(md_url: str) -> str | None:
    """GET a candidate markdown URL; return text only if it's really markdown.

    Accept criteria: HTTP 200, markdown/plain content-type, body not an HTML
    shell (SPAs serve their shell on every path), non-trivial word count.
    """
    import httpx
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=15.0,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; passe/1.0)'},
        ) as client:
            resp = client.get(md_url)
    except (httpx.HTTPError, httpx.TimeoutException):
        return None
    if resp.status_code != 200:
        return None
    ctype = resp.headers.get('content-type', '').split(';')[0].strip().lower()
    if ctype not in _MARKDOWN_CONTENT_TYPES:
        return None
    text = resp.text
    head = text.lstrip()[:100].lower()
    if head.startswith('<!doctype') or head.startswith('<html'):
        return None
    if _count_words(text) < 20:
        return None
    return text


def quality_gate(markdown: str, html: str, url: str) -> tuple[float, dict]:
    """Composite quality score for extracted markdown.

    Returns (score, signals_dict). Score 0-1 where higher is better.
    Below QUALITY_THRESHOLD means escalate to Chrome.
    """
    score = 1.0
    signals = {}

    word_count = _count_words(markdown)
    signals['word_count'] = word_count

    # --- Instant reject ---
    if word_count < MIN_WORDS:
        signals['reject'] = 'too_few_words'
        return 0.0, signals

    # --- Word count penalty ---
    if word_count < SUSPICIOUS_WORDS:
        score *= 0.3
        signals['word_penalty'] = 0.3

    # --- Stop words ratio ---
    # Only penalise short extractions — large technical docs legitimately
    # have low stop words (code, table data, programming terms)
    stop_ratio = _stop_words_ratio(markdown)
    signals['stop_words_ratio'] = round(stop_ratio, 3)
    if stop_ratio < 0.20 and word_count < 500:
        score *= 0.7
        signals['stop_words_penalty'] = 0.7

    # --- Link density in source HTML ---
    ld = _link_density(html)
    signals['link_density'] = round(ld, 3)
    if ld > 0.33:
        score *= 0.5
        signals['link_density_penalty'] = 0.5

    # --- Text-to-HTML ratio ---
    html_len = len(html)
    text_len = len(markdown)
    ratio = text_len / html_len if html_len > 0 else 0
    signals['text_to_html_ratio'] = round(ratio, 4)
    if ratio < 0.02:  # less than 2% is suspicious
        score *= 0.5
        signals['text_ratio_penalty'] = 0.5

    # --- Structural preservation ---
    # Count tables and code blocks in HTML, check if they survived
    html_tables = _count_html_elements(html, 'table')
    html_pre = _count_html_elements(html, 'pre')
    md_tables = len(re.findall(r'^\|.*\|$', markdown, re.MULTILINE))
    md_code = len(re.findall(r'^```', markdown, re.MULTILINE)) // 2

    if html_tables >= 3 and md_tables == 0:
        score *= 0.5
        signals['tables_lost'] = True
    if html_pre >= 2 and md_code == 0:
        score *= 0.5
        signals['code_blocks_lost'] = True

    # --- Paywall detection ---
    if _detect_paywall(markdown):
        score *= 0.2
        signals['paywall_detected'] = True

    # --- CAPTCHA detection ---
    if _detect_captcha(html):
        score *= 0.1
        signals['captcha_detected'] = True

    signals['quality_score'] = round(score, 3)
    return score, signals


# --- Raw content type detection (mirrors verbs.py RAW_CONTENT_TYPES) ---

_RAW_CONTENT_TYPES = frozenset({
    'application/json', 'application/xml', 'text/xml',
    'text/plain', 'text/csv',
    'application/x-yaml', 'text/yaml',
})


def try_http_fetch(url: str, force_source: str | None = None) -> FastPathResult | None:
    """Attempt HTTP fetch + extraction without Chrome.

    Returns FastPathResult if successful and passes quality gate.
    Returns None if Chrome should handle this (escalation).
    """
    import httpx

    t0 = time.monotonic()

    # --- HTTP fetch ---
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; passe/1.0)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
        ) as client:
            resp = client.get(url)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        print(f'[fetch] HTTP fast-path failed: {exc}', file=sys.stderr)
        return None

    fetch_ms = round((time.monotonic() - t0) * 1000, 1)
    final_url = str(resp.url)
    content_type = resp.headers.get('content-type', '').split(';')[0].strip().lower()

    # --- Auth/error status ---
    if resp.status_code in (401, 403):
        print(f'[fetch] HTTP {resp.status_code} — escalating to Chrome', file=sys.stderr)
        return None
    if resp.status_code >= 400:
        print(f'[fetch] HTTP {resp.status_code} — not retrying', file=sys.stderr)
        return FastPathResult(
            markdown='', url=final_url, source='http',
            quality_score=0.0, word_count=0, fetch_ms=fetch_ms,
            escalate_reason=f'HTTP {resp.status_code}',
        )

    html = resp.text

    # --- Raw content passthrough ---
    if content_type in _RAW_CONTENT_TYPES or (force_source == 'raw'):
        import json as json_mod
        content = html
        if content_type == 'application/json':
            try:
                content = json_mod.dumps(json_mod.loads(html), indent=2)
            except (json_mod.JSONDecodeError, ValueError):
                pass
        return FastPathResult(
            markdown=content, url=final_url, source='raw',
            quality_score=1.0, word_count=_count_words(content),
            fetch_ms=fetch_ms, content_type=content_type,
        )

    # --- Canonical markdown source probe ---
    # The source file beats any HTML extraction. Advertised links are checked
    # on every HTML fetch (string scan, no extra request unless found);
    # guessed URL.md probes fire only on escalation paths below.
    def _probe_markdown(reason: str, guess: bool) -> FastPathResult | None:
        if force_source is not None:
            return None
        from urllib.parse import urlsplit
        host = urlsplit(final_url).netloc
        if guess and _probe_cache_get(host) is False:
            return None  # host known not to serve .md siblings
        md_url = _markdown_source_url(html, final_url, guess=guess)
        if not md_url:
            return None
        md_text = _fetch_markdown_candidate(md_url)
        if not md_text:
            if guess:
                _probe_cache_set(host, False)
                print(f'[fetch] no markdown source at {md_url}',
                      file=sys.stderr)
            return None
        if guess:
            _probe_cache_set(host, True)
        wc = _count_words(md_text)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        print(f'[fetch] markdown source ({reason}): {md_url} '
              f'({wc} words, {elapsed}ms)', file=sys.stderr)
        return FastPathResult(
            markdown=md_text, url=final_url, source='markdown_probe',
            quality_score=1.0, word_count=wc, fetch_ms=elapsed,
            content_type='text/markdown',
        )

    md_result = _probe_markdown('advertised', guess=False)
    if md_result:
        return md_result

    # Unadvertised .md siblings (platform.claude.com et al): guess on
    # docs-shaped URLs, and on any host the cache knows serves them.
    # The known-negative guard inside _probe_markdown keeps the tax off
    # .md-less docs sites after first contact.
    from urllib.parse import urlsplit as _urlsplit
    if _docs_shaped(final_url) or _probe_cache_get(
            _urlsplit(final_url).netloc) is True:
        md_result = _probe_markdown('docs-shaped guess', guess=True)
        if md_result:
            return md_result

    # --- SPA shell detection — skip trafilatura, escalate immediately ---
    spa_shell = _detect_spa_shell(html)
    if spa_shell:
        md_result = _probe_markdown('spa_shell', guess=True)
        if md_result:
            return md_result
        print(f'[fetch] {spa_shell} detected — escalating to Chrome', file=sys.stderr)
        return None

    # --- Apple Developer Documentation shortcut ---
    apple_match = re.match(
        r'https://developer\.apple\.com/documentation/(.+?)(?:\?|#|$)',
        final_url,
    )
    if apple_match and (force_source is None or force_source == 'apple'):
        doc_path = apple_match.group(1).rstrip('/')
        json_url = f'https://developer.apple.com/tutorials/data/documentation/{doc_path}.json'
        try:
            import urllib.request
            from passe.verbs import _render_apple_json
            with urllib.request.urlopen(json_url, timeout=10) as json_resp:
                import json as json_mod
                apple_data = json_mod.loads(json_resp.read())
            md = _render_apple_json(apple_data)
            wc = _count_words(md)
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            print(f'[fetch] Apple docs JSON: {json_url} ({wc} words, {elapsed}ms)',
                  file=sys.stderr)
            return FastPathResult(
                markdown=md, url=final_url, source='apple-json',
                quality_score=1.0, word_count=wc, fetch_ms=elapsed,
            )
        except Exception as exc:
            print(f'[fetch] Apple JSON failed: {exc} — continuing', file=sys.stderr)

    # --- CAPTCHA detection — escalate (Chrome may have solved challenge) ---
    if _detect_captcha(html):
        print(f'[fetch] CAPTCHA detected — escalating to Chrome', file=sys.stderr)
        return None

    # --- __NEXT_DATA__ shortcut ---
    if force_source is None or force_source == 'next-data':
        next_content = _try_next_data(html, final_url)
        if next_content:
            wc = _count_words(next_content)
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            print(f'[fetch] __NEXT_DATA__ extracted ({wc} words, {elapsed}ms)',
                  file=sys.stderr)
            return FastPathResult(
                markdown=next_content, url=final_url, source='next-data',
                quality_score=1.0, word_count=wc, fetch_ms=elapsed,
            )

    # --- Trafilatura extraction ---
    try:
        import trafilatura
        extracted = trafilatura.extract(
            html, url=final_url,
            include_formatting=True,
            include_links=True,
            include_tables=True,
        )
    except Exception as exc:
        print(f'[fetch] trafilatura failed: {exc}', file=sys.stderr)
        return None

    if not extracted:
        md_result = _probe_markdown('empty_extraction', guess=True)
        if md_result:
            return md_result
        print('[fetch] trafilatura returned empty — escalating to Chrome', file=sys.stderr)
        return None

    # --- Quality gate ---
    score, signals = quality_gate(extracted, html, final_url)
    elapsed = round((time.monotonic() - t0) * 1000, 1)

    if score < QUALITY_THRESHOLD:
        md_result = _probe_markdown('quality_gate', guess=True)
        if md_result:
            return md_result
        reason = signals.get('reject', f'quality={score:.2f}')
        print(f'[fetch] quality gate failed ({reason}) — escalating to Chrome',
              file=sys.stderr)
        return FastPathResult(
            markdown=extracted, url=final_url, source='trafilatura',
            quality_score=score, word_count=_count_words(extracted),
            fetch_ms=elapsed, quality_signals=signals,
            escalate_reason=reason,
        )

    wc = _count_words(extracted)
    print(f'[fetch] HTTP fast-path OK ({wc} words, score={score:.2f}, {elapsed}ms)',
          file=sys.stderr)

    return FastPathResult(
        markdown=extracted, url=final_url, source='trafilatura',
        quality_score=score, word_count=wc, fetch_ms=elapsed,
        quality_signals=signals,
    )
