"""Observation verbs — screenshot, snapshot, read, fetch, eval, assert, watch."""

import asyncio
import base64
import json
import sys
import time

from passe.client import CDPClient


async def do_screenshot(client: CDPClient, path: str = None,
                        full_page: bool = True, viewport_only: bool = False,
                        fmt: str = 'png', quality: int = None,
                        optimize_speed: bool = False) -> dict:
    """Capture screenshot. Returns dict with path, size, and timing breakdown."""
    if viewport_only:
        full_page = False

    params = {'format': fmt if fmt != 'jpg' else 'jpeg'}
    if fmt in ('jpeg', 'jpg', 'webp') and quality is not None:
        params['quality'] = quality
    if optimize_speed:
        params['optimizeForSpeed'] = True

    t0 = time.monotonic()
    dpr = 1  # default; overwritten below
    if full_page:
        # Get full page dimensions + DPR in one round-trip
        metrics = await client.send('Runtime.evaluate', {
            'expression': 'JSON.stringify({w: document.documentElement.scrollWidth, h: Math.min(document.documentElement.scrollHeight, 16384), dpr: window.devicePixelRatio})',
            'awaitPromise': False
        })
        dims = json.loads(metrics['result']['result']['value'])
        dpr = dims.get('dpr', 1)
        params['clip'] = {
            'x': 0, 'y': 0,
            'width': dims['w'], 'height': dims['h'],
            'scale': 1
        }
        params['captureBeyondViewport'] = True

    # Page.captureScreenshot is top-level only — switch to parent if in iframe
    iframe_session = client._switch_session_for_screenshot()
    if iframe_session:
        print('[screenshot] switching to parent tab '
              '(Page.captureScreenshot is top-level only)',
              file=sys.stderr)

    # Screenshot rasterisation can be slow on software-rendered headless Chrome:
    # Wikipedia Cat (765×16384, DPR=1) takes 66s on --disable-gpu with 2 raster
    # threads.  Use a generous timeout so we only fire on a dead browser, not on
    # a page that's legitimately large.
    try:
        result = await client.send('Page.captureScreenshot', params, timeout=300.0)
    finally:
        client._restore_session_after_screenshot(iframe_session)
    capture_ms = round((time.monotonic() - t0) * 1000, 1)

    t1 = time.monotonic()
    data = base64.b64decode(result['result']['data'])
    decode_ms = round((time.monotonic() - t1) * 1000, 1)

    # For viewport-only screenshots, fetch DPR after capture (off critical path)
    if not full_page:
        dpr_result = await client.send('Runtime.evaluate', {
            'expression': 'window.devicePixelRatio',
            'awaitPromise': False,
        })
        dpr = dpr_result.get('result', {}).get('result', {}).get('value', 1)

    ext = fmt if fmt not in ('jpeg',) else 'jpg'
    if path is None:
        path = f'/tmp/passe-{int(time.time())}.{ext}'
    t2 = time.monotonic()
    with open(path, 'wb') as f:
        f.write(data)
    write_ms = round((time.monotonic() - t2) * 1000, 1)

    return {
        'file': path, 'kb': round(len(data) / 1024, 1),
        'format': params['format'],
        'breakdown': {
            'capture_ms': capture_ms, 'decode_ms': decode_ms,
            'write_ms': write_ms, 'bytes': len(data), 'dpr': dpr,
        },
    }


async def do_snapshot(client: CDPClient, path: str = None,
                      limit: int = 0) -> str:
    """List interactive elements with CSS selectors.

    limit: max elements to return (0 = unlimited). When set, the JS stops
    scanning after finding enough visible elements — avoids wasted work on
    heavy pages (used by self-healing snapshot on error).
    """
    js = r'''((limit) => {
        const results = [];
        const interactives = document.querySelectorAll(
            'a, button, input, select, textarea, [role="button"], [role="link"], ' +
            '[role="tab"], [role="menuitem"], [onclick], [tabindex]'
        );
        let idx = 0;
        for (const el of interactives) {
            if (limit > 0 && idx >= limit) break;
            // Skip invisible elements
            if (el.offsetParent === null && el.tagName !== 'BODY' &&
                getComputedStyle(el).position !== 'fixed') continue;
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 && rect.height === 0) continue;

            // Build CSS selector
            let css;
            if (el.id) {
                css = '#' + CSS.escape(el.id);
            } else if (el.name) {
                css = el.tagName.toLowerCase() + '[name=' + JSON.stringify(el.name) + ']';
            } else {
                // Positional selector
                const parent = el.parentElement;
                if (parent) {
                    const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
                    const nth = siblings.indexOf(el) + 1;
                    const parentSel = parent.id ? '#' + CSS.escape(parent.id)
                        : parent.tagName.toLowerCase();
                    css = parentSel + ' > ' + el.tagName.toLowerCase();
                    if (siblings.length > 1) css += ':nth-of-type(' + nth + ')';
                } else {
                    css = el.tagName.toLowerCase();
                }
            }

            // Element description
            const tag = el.tagName.toLowerCase();
            const type = el.type ? '[' + el.type + ']' : '';
            const name = el.getAttribute('aria-label')
                || el.getAttribute('placeholder')
                || el.textContent.trim().substring(0, 40)
                || '';

            let line = '[' + idx + '] ' + tag + type + ' "' + name + '" css=' + css;
            if (el.href) line += ' href=' + new URL(el.href, location.href).pathname;
            results.push(line);
            idx++;
        }
        return results.join('\n');
    })(''' + str(limit) + ')'
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False
    })
    text = result['result']['result'].get('value', '')

    if path:
        with open(path, 'w') as f:
            f.write(text)
    return text


THIN_READ_THRESHOLD = 200  # chars — below this, emit diagnostic
AUTH_PATTERNS = ('sign in', 'log in', 'login', 'access denied', 'forbidden', '403', 'unauthorized', '401', 'page not found', '404')

def _check_thin_read(markdown: str, html: str, page_text_length: int,
                     page_html_length: int, page_title: str, status_code: int | None = None) -> dict | None:
    """Check for suspiciously small extraction. Returns thin_read dict or None.

    Shared between forced-source and cascade paths so both emit diagnostics.
    Exempts legitimately small pages (high extraction ratio with real content).
    """
    if markdown is None:
        return None
    extraction_ratio = len(markdown) / page_text_length if page_text_length > 0 else 0
    page_is_just_small = extraction_ratio >= 0.5 and page_text_length >= 100
    if len(markdown) >= THIN_READ_THRESHOLD or page_is_just_small:
        return None

    word_count = len(markdown.split())
    html_lower = html.lower() if html else ''
    title_lower = page_title.lower() if page_title else ''

    # 1. Check HTTP Status Codes first
    if status_code == 404:
        cause = 'not_found'
    elif status_code in (401, 403):
        cause = 'auth_wall'
    # 2. Check the Title tag for strong semantic hints
    elif any(p in title_lower for p in ('sign in', 'log in', 'login', 'access denied')):
        cause = 'auth_wall'
    elif any(p in title_lower for p in ('not found', '404')):
        cause = 'not_found'
    # 3. Fallback to structural/body hints
    elif 'type="password"' in html_lower or '<form' in html_lower and 'login' in html_lower:
        cause = 'auth_wall'
    elif page_text_length < 100:
        cause = 'empty_page'
    elif page_html_length > 10 * max(len(markdown), 1):
        cause = 'js_hydration'
    else:
        cause = 'unknown'

    thin_read = {
        'word_count': word_count,
        'extracted_chars': len(markdown),
        'page_text_chars': page_text_length,
        'html_chars': page_html_length,
        'title': page_title,
        'possible_cause': cause,
    }
    size_label = f'{page_html_length // 1024}KB' if page_html_length >= 1024 else f'{page_html_length}B'
    thin_msg = f'thin-read: {word_count} words extracted from {size_label} page'
    if page_title:
        thin_msg += f' (title: "{page_title}")'
    thin_msg += f' — possible {cause.replace("_", " ")}'
    print(f'[read] {thin_msg}', file=sys.stderr)
    return thin_read


RAW_CONTENT_TYPES = frozenset({
    'application/json',
    'application/xml', 'text/xml',
    'text/plain',
    'text/csv',
    'application/x-yaml', 'text/yaml',
})


def _render_apple_json(data: dict) -> str:
    """Render Apple Developer Documentation JSON into markdown."""
    meta = data.get('metadata', {})
    refs = data.get('references', {})

    def inline(parts):
        out = []
        for p in (parts or []):
            t = p.get('type', '')
            if t == 'text':
                out.append(p.get('text', ''))
            elif t == 'codeVoice':
                out.append(f"`{p.get('code', '')}`")
            elif t == 'reference':
                ref = refs.get(p.get('identifier', ''), {})
                out.append(f"**{ref.get('title', '')}**")
        return ''.join(out)

    lines = [f"# {meta.get('title', 'Unknown')}",
             f"*{meta.get('roleHeading', '')}*\n"]
    abstract = inline(data.get('abstract', []))
    if abstract:
        lines.append(f"{abstract}\n")
    platforms = meta.get('platforms', [])
    if platforms:
        lines.append('**Availability:** '
                      + ' | '.join(f"{p['name']} {p.get('introducedAt', '')}"
                                   for p in platforms) + '\n')
    for section in data.get('primaryContentSections', []):
        kind = section.get('kind', '')
        if kind == 'declarations':
            for decl in section.get('declarations', []):
                tokens = ''.join(t.get('text', '') for t in decl.get('tokens', []))
                lines.append(f"```swift\n{tokens}\n```\n")
        elif kind == 'content':
            for item in section.get('content', []):
                itype = item.get('type', '')
                if itype == 'heading':
                    lines.append(f"{'#' * item.get('level', 2)} {item.get('text', '')}\n")
                elif itype == 'paragraph':
                    lines.append(f"{inline(item.get('inlineContent', []))}\n")
                elif itype == 'codeListing':
                    lang = item.get('syntax', '')
                    code = '\n'.join(item.get('code', []))
                    lines.append(f"```{lang}\n{code}\n```\n")
                elif itype == 'unorderedList':
                    for li in item.get('items', []):
                        for content in li.get('content', []):
                            if content.get('type') == 'paragraph':
                                lines.append(f"- {inline(content.get('inlineContent', []))}")
                    lines.append('')
    for section in data.get('topicSections', []):
        lines.append(f"## {section.get('title', '')}\n")
        for ident in section.get('identifiers', []):
            ref = refs.get(ident, {})
            title = ref.get('title', ident.split('/')[-1])
            desc = inline(ref.get('abstract', []))
            if ref.get('deprecated'):
                title = f"~~{title}~~"
            lines.append(f"- **{title}**" + (f" — {desc}" if desc else ""))
    return '\n'.join(lines)


async def do_read(client: CDPClient, path: str = None, force_source: str = None) -> dict:
    """Extract page content as markdown.

    Cascade: trafilatura (Python-side) → Readability.js+Turndown (browser-side) → innerText.
    force_source: 'trafilatura', 'readability', 'innertext', or 'raw' — skip cascade.
    Returns dict with 'markdown', optional 'warning', and 'source'.
    """
    # Content-type sniffing: bypass extraction for structured data (JSON, XML, etc.)
    content_type = await do_eval(client, 'document.contentType')
    mime = (content_type or '').split(';')[0].strip().lower()

    if force_source == 'raw' or (force_source is None and mime in RAW_CONTENT_TYPES):
        raw_text = await do_eval(client, 'document.body.innerText')
        # Pretty-print JSON
        if 'json' in mime:
            try:
                raw_text = json.dumps(json.loads(raw_text), indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass  # Return as-is if not valid JSON
        print(f'[read] content-type: {mime} — raw passthrough', file=sys.stderr)
        print(f'[read] source: raw', file=sys.stderr)
        if path:
            with open(path, 'w') as f:
                f.write(raw_text)
        return {'markdown': raw_text, 'source': 'raw', 'content_type': mime}

    # Apple Developer Documentation: use structured JSON endpoint instead of
    # extracting from the JS-rendered HTML (which times out trafilatura and
    # produces nav-chrome soup from innerText).
    if force_source is None or force_source == 'apple':
        current_url = await do_eval(client, 'window.location.href')
        import re as _re
        apple_match = _re.match(
            r'https://developer\.apple\.com/documentation/(.+?)(?:\?|#|$)',
            current_url or ''
        )
        if apple_match:
            doc_path = apple_match.group(1).rstrip('/')
            json_url = f'https://developer.apple.com/tutorials/data/documentation/{doc_path}.json'
            try:
                import urllib.request
                with urllib.request.urlopen(json_url, timeout=10) as resp:
                    apple_data = json.loads(resp.read())
                md = _render_apple_json(apple_data)
                print(f'[read] Apple docs JSON: {json_url}', file=sys.stderr)
                print(f'[read] source: apple-json', file=sys.stderr)
                if path:
                    with open(path, 'w') as f:
                        f.write(md)
                return {'markdown': md, 'source': 'apple-json',
                        'title': apple_data.get('metadata', {}).get('title', '')}
            except Exception as exc:
                if force_source == 'apple':
                    print(f'[read] Apple JSON failed: {exc}', file=sys.stderr)
                # Fall through to normal cascade

    # Get page HTML (with shadow DOM flattened) and metadata from Chrome.
    from ._libs import SHADOW_FLATTEN_JS
    html = await do_eval(client, SHADOW_FLATTEN_JS)
    meta_raw = await do_eval(
        client,
        'JSON.stringify({textLength: document.body.innerText.length,'
        ' htmlLength: document.documentElement.outerHTML.length,'
        ' title: document.title, url: window.location.href})'
    )
    meta = json.loads(meta_raw)
    page_text_length = meta.get('textLength', 0)
    page_html_length = meta.get('htmlLength', 0)
    page_title = meta.get('title', '')
    page_url = meta.get('url', '')

    markdown = None
    source = None
    warning = None

    # Find status code from network events (to help thin-read diagnostics)
    status_code = None
    for req in client._network_requests.values():
        if (req.get('resource_type') == 'Document'
                and req.get('url') == page_url
                and req.get('status') is not None):
            status_code = req['status']
            break

    # Forced source — skip cascade, use only the specified extractor
    if force_source:
        fs = force_source.lower()
        if fs == 'trafilatura':
            try:
                import trafilatura
                markdown = trafilatura.extract(
                    html, url=page_url,
                    include_formatting=True, include_links=True, include_tables=True,
                ) or ''
                source = 'trafilatura'
            except Exception as exc:
                markdown = ''
                source = 'trafilatura'
                warning = f'trafilatura failed: {exc}'
        elif fs == 'readability':
            from ._libs import READABILITY_JS, TURNDOWN_JS, EXTRACT_JS
            combined = READABILITY_JS + ';\n' + TURNDOWN_JS + ';\n' + EXTRACT_JS
            result = await client.send('Runtime.evaluate', {
                'expression': combined, 'awaitPromise': False
            })
            raw = result['result']['result'].get('value', '{}')
            data = json.loads(raw)
            markdown = data.get('markdown', '')
            source = 'readability' if not data.get('fallback') else 'innerText'
            if data.get('fallback'):
                warning = 'Readability returned no article — output is innerText'
        elif fs == 'innertext':
            text = await do_eval(client, 'document.body.innerText')
            markdown = text or ''
            source = 'innerText'
        else:
            markdown = ''
            source = 'unknown'
            warning = f'Unknown source: {force_source}. Use trafilatura, readability, or innertext.'

        # Thin-read diagnostics (shared with cascade path)
        thin_read = _check_thin_read(markdown, html, page_text_length,
                                     page_html_length, page_title, status_code)
        if thin_read and not warning:
            word_count = thin_read['word_count']
            cause = thin_read['possible_cause']
            size_label = f'{page_html_length // 1024}KB' if page_html_length >= 1024 else f'{page_html_length}B'
            warning = f'thin-read: {word_count} words extracted from {size_label} page'
            if page_title:
                warning += f' (title: "{page_title}")'
            warning += f' — possible {cause.replace("_", " ")}'

        if warning:
            print(f'[read] warning: {warning}', file=sys.stderr)
        print(f'[read] source: {source}', file=sys.stderr)
        if path:
            with open(path, 'w') as f:
                f.write(markdown)
        result = {'markdown': markdown, 'warning': warning, 'source': source,
                  'title': page_title}
        if thin_read:
            result['thin_read'] = thin_read
        return result

    # Stage 1: trafilatura — Python-side extraction from rendered HTML
    try:
        import trafilatura
        extracted = trafilatura.extract(
            html, url=page_url,
            include_formatting=True, include_links=True, include_tables=True,
        )
        if extracted and (page_text_length == 0 or len(extracted) / page_text_length >= 0.10):
            markdown = extracted
            source = 'trafilatura'
    except ImportError:
        print('[read] trafilatura not installed — falling back to Readability', file=sys.stderr)
    except Exception as exc:
        print(f'[read] trafilatura failed: {exc} — falling back to Readability', file=sys.stderr)

    gate_rejected_markdown = None  # stash if gate rejects — better than innerText
    gate_missing_code = False  # track if rejection was for code blocks

    # Stage 1.5: Structural quality gate — detect table/code-block loss.
    # Trafilatura can pass the 10% text ratio check but strip critical structure.
    # Thresholds (empirical, tested against ISO-3166-1, Python docs, Wikipedia):
    #   - Binary:        page >= 5 data rows, output has 0 table markers → reject
    #   - Proportional:  page >= 10 data rows, output < 25% of page rows → reject
    #   - Code binary:   page >= 2 long <pre> blocks, output has 0 fences → reject
    #   - Code proportional: page >= 5 long <pre> blocks, output < 25% → reject
    #   - Skip DOM eval: output has 20+ table rows AND 5+ code fences (clearly preserved)
    if source == 'trafilatura':
        import re
        # Count pipe-table data rows (exclude separator rows like |---|---|)
        output_table_rows = len(re.findall(r'^\|.*\w.*\|', markdown, re.MULTILINE))
        output_code_blocks = len(re.findall(r'^```', markdown, re.MULTILINE)) // 2

        # Pipe noise check: bare "|" lines from presentation-table artifacts
        # (HTML email templates use tables for layout, not data — trafilatura
        # leaks cell boundaries as stray pipe characters on empty lines)
        lines = markdown.split('\n')
        non_empty = [l for l in lines if l.strip()]
        bare_pipes = sum(1 for l in non_empty if l.strip() == '|')
        if len(non_empty) > 10 and bare_pipes / len(non_empty) > 0.15:
            print(
                f'[read] quality gate: trafilatura has {bare_pipes} bare pipe lines'
                f' ({bare_pipes*100//len(non_empty)}% of content)'
                ' — falling to Readability', file=sys.stderr
            )
            gate_rejected_markdown = markdown
            markdown = None
            source = None

        # Only query DOM when output might be missing structure
        if source == 'trafilatura' and (output_table_rows < 20 or output_code_blocks < 5):
            dom_raw = await do_eval(client, (
                'JSON.stringify({dataRows:[...document.querySelectorAll("tr")]'
                '.filter(r=>r.querySelectorAll("td").length>=2).length,'
                'codeBlocks:[...document.querySelectorAll("pre")]'
                '.filter(e=>e.textContent.length>50).length})'
            ))
            dom = json.loads(dom_raw)
            lost = []
            page_rows = dom.get('dataRows', 0)
            # Binary check: page has tables, output has none
            if output_table_rows == 0 and page_rows >= 5:
                lost.append(f'{page_rows} table rows')
            # Proportional check: big table mostly stripped
            elif page_rows >= 10 and output_table_rows < page_rows * 0.25:
                lost.append(f'{page_rows} table rows (got {output_table_rows})')
            page_code = dom.get('codeBlocks', 0)
            # Binary check: page has code blocks, output has none
            if output_code_blocks == 0 and page_code >= 2:
                lost.append(f'{page_code} code blocks')
                gate_missing_code = True
            # Proportional check: many code blocks mostly stripped
            elif page_code >= 5 and output_code_blocks < page_code * 0.25:
                lost.append(f'{page_code} code blocks (got {output_code_blocks})')
                gate_missing_code = True

            if lost:
                print(
                    f'[read] quality gate: trafilatura dropped {", ".join(lost)}'
                    ' — falling to Readability', file=sys.stderr
                )
                gate_rejected_markdown = markdown
                markdown = None
                source = None

    # Stage 2: Readability.js + Turndown — browser-side extraction
    if markdown is None:
        from ._libs import READABILITY_JS, TURNDOWN_JS, EXTRACT_JS
        combined = READABILITY_JS + ';\n' + TURNDOWN_JS + ';\n' + EXTRACT_JS
        result = await client.send('Runtime.evaluate', {
            'expression': combined, 'awaitPromise': False
        })
        raw = result['result']['result'].get('value', '{}')
        data = json.loads(raw)
        md = data.get('markdown', '')

        if data.get('fallback'):
            # Stage 3: Readability failed — prefer gate-rejected trafilatura over innerText
            if gate_rejected_markdown:
                markdown = gate_rejected_markdown
                source = 'trafilatura'
                warning = 'Readability also failed — kept trafilatura output (missing some structure)'
                # Supplement with DOM code blocks if that's what was lost
                if gate_missing_code:
                    code_raw = await do_eval(client, (
                        'JSON.stringify([...document.querySelectorAll("pre")]'
                        '.filter(e=>e.textContent.length>30)'
                        '.map(e=>e.textContent.trim()))'
                    ))
                    code_blocks = json.loads(code_raw)
                    if code_blocks:
                        markdown += '\n\n---\n\n## Code Examples\n\n'
                        for block in code_blocks:
                            markdown += '```\n' + block + '\n```\n\n'
                        warning = (f'Readability also failed — supplemented trafilatura prose'
                                   f' with {len(code_blocks)} code blocks from DOM')
                        print(f'[read] supplemented with {len(code_blocks)} code blocks from DOM',
                              file=sys.stderr)
            else:
                markdown = md
                source = 'innerText'
                warning = 'trafilatura and Readability both failed — fell back to innerText'
        elif md:
            markdown = md
            source = 'readability'
        else:
            markdown = ''
            source = 'innerText'
            warning = 'All extractors returned empty'

    # Ratio warning for trafilatura/readability paths
    if source in ('trafilatura', 'readability') and page_text_length > 0 and markdown:
        ratio = len(markdown) / page_text_length
        if ratio < 0.10:
            pct = round(ratio * 100, 1)
            warning = f'Extraction looks incomplete — got {pct}% of page text ({len(markdown)}/{page_text_length} chars)'

    # Thin-read diagnostics (shared helper — also used by forced-source path above)
    thin_read = _check_thin_read(markdown, html, page_text_length,
                                 page_html_length, page_title, status_code)
    if thin_read and not warning:
        word_count = thin_read['word_count']
        cause = thin_read['possible_cause']
        size_label = f'{page_html_length // 1024}KB' if page_html_length >= 1024 else f'{page_html_length}B'
        warning = f'thin-read: {word_count} words extracted from {size_label} page'
        if page_title:
            warning += f' (title: "{page_title}")'
        warning += f' — possible {cause.replace("_", " ")}'

    if warning:
        print(f'[read] warning: {warning}', file=sys.stderr)
    print(f'[read] source: {source}', file=sys.stderr)

    if path:
        with open(path, 'w') as f:
            f.write(markdown)

    result = {'markdown': markdown, 'warning': warning, 'source': source, 'title': page_title}
    if thin_read:
        result['thin_read'] = thin_read
    return result


async def do_fetch(client: CDPClient, url: str, path: str = None,
                   force_source: str = None) -> dict:
    """Compound verb: goto + auto-wait + read in one step.
    Returns read result dict with added nav_ms, wait_ms, read_ms, timed_out."""
    from passe.verbs_navigation import do_navigate
    from passe.verbs_control import do_wait_stable

    t0 = time.monotonic()
    nav = await do_navigate(client, url)
    nav_ms = round((time.monotonic() - t0) * 1000, 1)

    t1 = time.monotonic()
    stable = await do_wait_stable(client)
    wait_ms = round((time.monotonic() - t1) * 1000, 1)

    t2 = time.monotonic()
    result = await do_read(client, path, force_source=force_source)
    read_ms = round((time.monotonic() - t2) * 1000, 1)

    result['nav_ms'] = nav_ms
    result['nav_url'] = nav['url']
    result['nav_status_code'] = nav['status_code']
    result['wait_ms'] = wait_ms
    result['read_ms'] = read_ms
    if not stable:
        result['timed_out'] = True
    return result


async def do_exists(client: CDPClient, selector: str) -> bool:
    """Check whether an element matching the selector exists in the DOM."""
    result = await client.send('Runtime.evaluate', {
        'expression': f'document.querySelector({json.dumps(selector)}) !== null',
        'awaitPromise': False,
    })
    return result['result']['result'].get('value', False)


async def do_count(client: CDPClient, selector: str) -> int:
    """Count elements matching the selector."""
    result = await client.send('Runtime.evaluate', {
        'expression': f'document.querySelectorAll({json.dumps(selector)}).length',
        'awaitPromise': False,
    })
    return result['result']['result'].get('value', 0)


async def do_visible(client: CDPClient, selector: str) -> bool:
    """Check whether an element is visible (exists, has dimensions, not hidden)."""
    js = f'''(() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) return false;
        const style = getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }})()'''
    result = await client.send('Runtime.evaluate', {
        'expression': js, 'awaitPromise': False,
    })
    return result['result']['result'].get('value', False)


async def do_pdf(client: CDPClient, path: str = None) -> dict:
    """Save page as PDF via Page.printToPDF. Returns dict with path and size."""
    result = await client.send('Page.printToPDF', {
        'printBackground': True,
        'preferCSSPageSize': True,
    }, timeout=60.0)
    data = base64.b64decode(result['result']['data'])
    if path is None:
        path = f'/tmp/passe-{int(time.time())}.pdf'
    with open(path, 'wb') as f:
        f.write(data)
    return {'file': path, 'kb': round(len(data) / 1024, 1)}


async def do_eval(client: CDPClient, expression: str) -> str:
    result = await client.send('Runtime.evaluate', {
        'expression': expression, 'awaitPromise': True
    })
    r = result.get('result', {}).get('result', {})
    if 'exceptionDetails' in result.get('result', {}):
        desc = result['result']['exceptionDetails'].get('exception', {}).get('description', '')
        raise RuntimeError(f'eval failed: {desc}')
    return str(r.get('value', r.get('description', '')))


async def do_eval_to(client: CDPClient, path: str, expression: str) -> str:
    result = await do_eval(client, expression)
    with open(path, 'w') as f:
        f.write(result)
    return result


async def do_eval_file(client: CDPClient, js_path: str) -> str:
    """Read JS from a file and evaluate it. Avoids single-line minification."""
    with open(js_path) as f:
        expression = f.read()
    return await do_eval(client, expression)


async def do_eval_file_to(client: CDPClient, out_path: str, js_path: str) -> str:
    result = await do_eval_file(client, js_path)
    with open(out_path, 'w') as f:
        f.write(result)
    return result


async def do_assert(client: CDPClient, expression: str):
    result = await client.send('Runtime.evaluate', {
        'expression': expression, 'awaitPromise': True
    })
    r = result.get('result', {}).get('result', {})
    value = r.get('value', r.get('description', ''))
    if not value:
        raise RuntimeError(f'Assertion failed: {expression} (got {value!r})')


async def do_watch(client: CDPClient, path: str, fast: bool = True,
                   debounce_ms: int = 100, cooldown_ms: int = 1000):
    """Watch for HMR updates and auto-screenshot. Runs until cancelled.

    Listens for Vite's console messages:
      - '[vite] hot updated' → debounce + screenshot
      - '[vite] page reload' → wait for load event + screenshot
      - '[vite] connected'   → ignored (initial connection)

    Also catches DOM mutations (Tailwind CSS rebuild) via a MutationObserver
    fallback that fires a console.log we can detect.

    Three debounce layers prevent screenshot storms:

      1. JS MutationObserver (150ms) — clusters rapid DOM mutations into a
         single console.log('[passe-watch] mutation'). Without this, each
         DOM node added fires separately.

      2. Python debounce drain (debounce_ms, default 100ms) — after receiving
         an event, sleeps then drains any queued events. Clusters events that
         arrive in bursts (e.g. multiple HMR modules updating).

      3. Cooldown (cooldown_ms, default 1000ms) — minimum interval between
         captures, leading + trailing edge. Captures immediately on first
         event (leading), then once more after cooldown expires if anything
         was suppressed (trailing). The trailing capture gets the final page
         state, which is what matters most.
    """
    # Enable console event streaming
    await client.send('Runtime.enable')
    queue = client.subscribe('Runtime.consoleAPICalled')

    # Install MutationObserver for changes that don't trigger HMR console messages
    # (e.g. Tailwind rebuilds injected via <style> tags)
    await client.send('Runtime.evaluate', {
        'expression': '''(() => {
            let _watchTimer = null;
            new MutationObserver(() => {
                clearTimeout(_watchTimer);
                _watchTimer = setTimeout(() => console.log('[passe-watch] mutation'), 150);
            }).observe(document.documentElement, {childList: true, subtree: true, attributes: true});
        })()''',
        'awaitPromise': False,
    })

    capture_count = 0
    suppressed_count = 0
    last_capture_time = 0.0  # monotonic timestamp of last screenshot
    cooldown_sec = cooldown_ms / 1000
    _trailing_task: asyncio.Task | None = None
    print(json.dumps({'event': 'watch_started', 'path': path, 'fast': fast,
                      'cooldown_ms': cooldown_ms}),
          file=sys.stderr)

    async def _do_capture(event_type: str):
        """Actually take a screenshot and log it."""
        nonlocal capture_count, suppressed_count, last_capture_time
        t0 = time.monotonic()
        # Late-bind through passe.verbs so tests can patch do_screenshot there
        import passe.verbs as _verbs
        info = await _verbs.do_screenshot(
            client, path, viewport_only=True,
            fmt='jpeg' if fast else 'png',
            quality=70 if fast else None,
            optimize_speed=fast,
        )
        ms = round((time.monotonic() - t0) * 1000, 1)
        last_capture_time = time.monotonic()
        capture_count += 1
        log_entry = {
            'event': event_type, 'n': capture_count,
            'screenshot_ms': ms, 'kb': info['kb'],
            'file': info['file'],
        }
        if suppressed_count > 0:
            log_entry['suppressed_since_last'] = suppressed_count
            suppressed_count = 0
        print(json.dumps(log_entry), file=sys.stderr)

    async def _trailing_capture(delay: float, event_type: str):
        """Wait for remaining cooldown, then capture the final state."""
        await asyncio.sleep(delay)
        try:
            await _do_capture(event_type)
        except Exception as e:
            print(json.dumps({'event': 'trailing_error', 'error': str(e)}),
                  file=sys.stderr)

    async def _capture(event_type: str):
        """Leading + trailing: capture immediately if cooldown ok,
        otherwise schedule a trailing capture for when cooldown expires."""
        nonlocal suppressed_count, _trailing_task
        now = time.monotonic()
        elapsed = now - last_capture_time
        if elapsed < cooldown_sec:
            suppressed_count += 1
            # Schedule trailing capture if not already pending
            if _trailing_task is None or _trailing_task.done():
                remaining = cooldown_sec - elapsed
                _trailing_task = asyncio.create_task(
                    _trailing_capture(remaining, event_type))
            return

        # Cancel any pending trailing — we're capturing now
        if _trailing_task and not _trailing_task.done():
            _trailing_task.cancel()
        await _do_capture(event_type)

    try:
        while True:
            msg = await queue.get()
            # Extract console message text
            params = msg.get('params', {})
            call_args = params.get('args', [])
            if not call_args:
                continue
            text = call_args[0].get('value', '')
            if not isinstance(text, str):
                continue

            # Classify the event
            if '[vite] hot updated' in text or '[passe-watch] mutation' in text:
                # Debounce: drain any queued events within the window
                await asyncio.sleep(debounce_ms / 1000)
                drained = 0
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        drained += 1
                    except asyncio.QueueEmpty:
                        break

                event_type = 'hmr' if '[vite]' in text else 'mutation'
                await _capture(event_type)
                # Drained events mean the page was still changing — schedule
                # trailing capture to get the final state after cooldown
                if drained > 0:
                    suppressed_count += drained
                    if _trailing_task is None or _trailing_task.done():
                        _trailing_task = asyncio.create_task(
                            _trailing_capture(cooldown_sec, event_type))

            elif '[vite] page reload' in text:
                # Full reload — wait for load event first
                try:
                    await client.wait_for_event('Page.loadEventFired', timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                await asyncio.sleep(debounce_ms / 1000)
                await _capture('reload')

    except asyncio.CancelledError:
        pass
    finally:
        if _trailing_task and not _trailing_task.done():
            _trailing_task.cancel()
        client.unsubscribe('Runtime.consoleAPICalled')
        print(json.dumps({
            'event': 'watch_stopped', 'total_captures': capture_count,
        }), file=sys.stderr)


# ── Accessibility tree verbs ────────────────────────────


def _ax_node_summary(node: dict) -> dict | None:
    """Extract role/name/value from a CDP AXNode, skipping ignored nodes."""
    if node.get('ignored', False):
        return None
    role = node.get('role', {}).get('value', '')
    summary = {'role': role}
    name = node.get('name', {}).get('value', '')
    if name:
        summary['name'] = name
    value = node.get('value', {}).get('value', '')
    if value:
        summary['value'] = value
    # Expose nodeId for cross-referencing
    summary['nodeId'] = node.get('nodeId', '')
    return summary


def _is_transparent(node: dict) -> bool:
    """True for structural-only nodes that add noise (role=none, generic)."""
    role = node.get('role', {}).get('value', '')
    return role in ('none', 'generic') and not node.get('name', {}).get('value', '')


def _build_ax_tree(nodes: list[dict]) -> list[dict]:
    """Rebuild a tree from CDP's flat AXNode list.

    CDP may provide parentId, childIds, or both. We use parentId as the
    primary signal (always present in getFullAXTree output), falling back
    to childIds when parentId is absent.

    Transparent nodes (role=none/generic with no name) are collapsed: their
    children get reparented to the nearest non-transparent ancestor.
    """
    # Track which raw nodes are transparent (for reparenting)
    transparent = {n['nodeId'] for n in nodes if _is_transparent(n)}

    by_id = {}
    for node in nodes:
        summary = _ax_node_summary(node)
        if summary is None:
            continue
        summary['children'] = []
        by_id[node['nodeId']] = summary

    # Build parentId lookup
    parent_map = {}
    for node in nodes:
        pid = node.get('parentId')
        if pid is not None:
            parent_map[node['nodeId']] = pid

    def _find_visible_parent(nid):
        """Walk up parentId chain to find the nearest non-transparent ancestor."""
        pid = parent_map.get(nid)
        while pid and pid in transparent:
            pid = parent_map.get(pid)
        return pid

    roots = []
    for node in nodes:
        nid = node['nodeId']
        if nid not in by_id or nid in transparent:
            continue
        visible_parent = _find_visible_parent(nid)
        if visible_parent and visible_parent in by_id:
            by_id[visible_parent]['children'].append(by_id[nid])
        else:
            roots.append(by_id[nid])

    # Fallback: if no parentId wiring happened (e.g. getPartialAXTree),
    # try childIds instead
    if len(roots) == len(by_id) - len(transparent) and len(roots) > 1:
        for nid in by_id:
            if nid not in transparent:
                by_id[nid]['children'] = []
        roots = []
        all_children = set()
        for node in nodes:
            nid = node['nodeId']
            if nid not in by_id or nid in transparent:
                continue
            for cid in node.get('childIds', []):
                if cid in by_id and cid not in transparent:
                    by_id[nid]['children'].append(by_id[cid])
                    all_children.add(cid)
        for nid, summary in by_id.items():
            if nid not in all_children and nid not in transparent:
                roots.append(summary)

    return roots


def _prune_empty_children(tree: list[dict]) -> list[dict]:
    """Remove empty children lists for cleaner output."""
    for node in tree:
        if node.get('children'):
            node['children'] = _prune_empty_children(node['children'])
        else:
            node.pop('children', None)
    return tree


MAX_AX_NODES = 1500  # cap output to avoid blowing context on heavy pages

# Roles stripped by --compact (leaf noise that bloats context)
_COMPACT_STRIP_ROLES = {'StaticText', 'InlineTextBox'}


def _compact_tree(tree: list[dict]) -> list[dict]:
    """Strip noise leaf nodes (StaticText, InlineTextBox, unnamed generic/none).

    Only removes leaves — nodes with children are kept so structure isn't lost.
    """
    compacted = []
    for node in tree:
        children = node.get('children', [])
        if children:
            node['children'] = _compact_tree(children)
            compacted.append(node)
        else:
            role = node.get('role', '')
            if role in _COMPACT_STRIP_ROLES:
                continue
            if role in ('none', 'generic') and not node.get('name'):
                continue
            compacted.append(node)
    return compacted


# Roles that --flat-refs keeps: things an agent can act on.
_INTERACTIVE_ROLES = {
    'button', 'link', 'textbox', 'checkbox', 'menuitem', 'tab', 'option',
    'combobox', 'radio', 'searchbox', 'switch', 'slider',
}


def _flat_refs(nodes: list[dict]) -> tuple[list[dict], dict]:
    """Filter AX nodes to interactive roles, assign e0..eN in document
    order. Returns (entries, {ref: backendDOMNodeId})."""
    entries = []
    mapping = {}
    for node in nodes:
        if node.get('ignored', False):
            continue
        role = node.get('role', {}).get('value', '')
        if role not in _INTERACTIVE_ROLES:
            continue
        backend_id = node.get('backendDOMNodeId')
        if backend_id is None:
            continue
        ref = f'e{len(entries)}'
        entry = {'ref': ref, 'role': role}
        name = node.get('name', {}).get('value', '')
        if name:
            entry['name'] = name[:120]
        entries.append(entry)
        mapping[ref] = backend_id
    return entries, mapping


async def do_ax_tree(client: CDPClient, depth: int = None,
                     compact: bool = False, flat_refs: bool = False) -> str:
    """Return the full accessibility tree as structured JSON.

    depth: max tree depth to fetch (None = unlimited). Passed to CDP's
    getFullAXTree which truncates server-side — cheaper than post-filtering.
    compact: strip StaticText/InlineTextBox leaf nodes for a cleaner skeleton.
    flat_refs: emit interactive elements only, as flat one-line entries
    [{ref, role, name}], and cache {ref: backendDOMNodeId} per tab so
    'click e7' works in a later call (passe-cosapu).
    """
    params = {}
    if depth is not None:
        params['depth'] = depth
    result = await client.send('Accessibility.getFullAXTree', params,
                               timeout=30.0)
    nodes = result.get('result', {}).get('nodes', [])
    truncated = len(nodes) > MAX_AX_NODES
    if truncated:
        nodes = nodes[:MAX_AX_NODES]

    if flat_refs:
        from passe.refcache import save_refs
        entries, mapping = _flat_refs(nodes)
        save_refs(client._target_id or '', mapping)
        if truncated:
            print(f'[ax-tree] truncated to {MAX_AX_NODES} nodes '
                  f'(use --depth N to limit)', file=sys.stderr)
        if not entries:
            return '[]'
        return '[\n' + ',\n'.join(json.dumps(e) for e in entries) + '\n]'

    tree = _build_ax_tree(nodes)
    if compact:
        tree = _compact_tree(tree)
    tree = _prune_empty_children(tree)
    out = json.dumps(tree, indent=2)
    if truncated:
        print(f'[ax-tree] truncated to {MAX_AX_NODES} nodes '
              f'(use --depth N to limit)', file=sys.stderr)
    return out


async def do_ax_find(client: CDPClient, role: str = None,
                     name: str = None) -> str:
    """Find accessibility nodes matching role and/or name filters.

    Fetches the full tree and filters client-side. CDP's queryAXTree
    is unreliable (hangs/times out on some Chrome versions).
    At least one of role or name must be provided.
    """
    if not role and not name:
        return json.dumps({'error': 'ax-find requires --role and/or --name'})

    result = await client.send('Accessibility.getFullAXTree', {},
                               timeout=30.0)
    nodes = result.get('result', {}).get('nodes', [])
    matches = []
    for node in nodes:
        if _is_transparent(node) or node.get('ignored', False):
            continue
        node_role = node.get('role', {}).get('value', '')
        node_name = node.get('name', {}).get('value', '')
        if role and role.lower() != node_role.lower():
            continue
        if name and name.lower() not in node_name.lower():
            continue
        summary = _ax_node_summary(node)
        if summary:
            backend_id = node.get('backendDOMNodeId')
            if backend_id:
                summary['backendDOMNodeId'] = backend_id
            matches.append(summary)
    return json.dumps(matches, indent=2)


async def do_ax_node(client: CDPClient, selector: str) -> str:
    """Return the accessibility subtree for a DOM element found by CSS selector."""
    # Resolve selector to DOM nodeId
    doc = await client.send('DOM.getDocument')
    root_id = doc['result']['root']['nodeId']
    found = await client.send('DOM.querySelector', {
        'nodeId': root_id,
        'selector': selector,
    })
    node_id = found.get('result', {}).get('nodeId', 0)
    if not node_id:
        return json.dumps({'error': f'No element matches selector: {selector}'})

    # Resolve to backendNodeId for the Accessibility domain
    attrs = await client.send('DOM.describeNode', {'nodeId': node_id})
    backend_id = attrs['result']['node']['backendNodeId']

    result = await client.send('Accessibility.getPartialAXTree', {
        'backendNodeId': backend_id,
        'fetchRelatives': True,
    })
    nodes = result.get('result', {}).get('nodes', [])
    tree = _build_ax_tree(nodes)
    tree = _prune_empty_children(tree)
    return json.dumps(tree, indent=2)
