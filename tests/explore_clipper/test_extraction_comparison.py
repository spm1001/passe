#!/usr/bin/env python3
"""Compare extraction engines: trafilatura vs defuddle vs Readability.

Fetches real pages via HTTP and runs each extractor, comparing:
- Word count, extraction time, source quality
- Metadata extraction (author, date, schema.org)
- Structural preservation (tables, code blocks, math)
"""
import json
import subprocess
import sys
import time
import urllib.request

# Test URLs covering different page types
TEST_PAGES = {
    'article': 'https://www.paulgraham.com/startupideas.html',
    'docs_tables': 'https://httpbin.org/html',  # simple HTML page
    'code_heavy': 'https://docs.python.org/3/library/json.html',
    'spa_content': 'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise',
    'github_readme': 'https://raw.githubusercontent.com/kepano/defuddle/main/README.md',
}

def fetch_html(url: str) -> str:
    """Fetch page HTML via HTTP."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='replace')


def test_trafilatura(html: str, url: str) -> dict:
    """Run trafilatura extraction."""
    import trafilatura
    t0 = time.monotonic()
    result = trafilatura.extract(
        html, url=url,
        include_formatting=True, include_links=True, include_tables=True,
    )
    ms = round((time.monotonic() - t0) * 1000, 1)
    if result is None:
        return {'source': 'trafilatura', 'ms': ms, 'words': 0, 'chars': 0, 'text': ''}

    words = len(result.split())
    # Count structural elements
    import re
    tables = len(re.findall(r'^\|.*\w.*\|', result, re.MULTILINE))
    code_blocks = len(re.findall(r'^```', result, re.MULTILINE)) // 2

    return {
        'source': 'trafilatura',
        'ms': ms,
        'words': words,
        'chars': len(result),
        'tables': tables,
        'code_blocks': code_blocks,
        'text': result,
    }


def test_defuddle(html: str, url: str) -> dict:
    """Run defuddle extraction via Node.js subprocess."""
    # Write HTML to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(html)
        html_path = f.name

    # Write ESM script to temp file (defuddle/node is ESM-only)
    import tempfile
    js_code = f"""
import {{ Defuddle }} from 'defuddle/node';
import {{ parseHTML }} from 'linkedom';
import fs from 'fs';

const html = fs.readFileSync('{html_path}', 'utf-8');
const {{ document }} = parseHTML(html);

const t0 = Date.now();
const result = await Defuddle(document, '{url}', {{ markdown: true }});
const ms = Date.now() - t0;
console.log(JSON.stringify({{
    source: 'defuddle',
    ms,
    title: result.title,
    author: result.author,
    description: result.description,
    published: result.published,
    site: result.site,
    language: result.language,
    wordCount: result.wordCount,
    extractorType: result.extractorType,
    schemaOrgData: result.schemaOrgData,
    metaTags: result.metaTags,
    contentLength: (result.contentMarkdown || '').length,
    contentMarkdown: (result.contentMarkdown || '').slice(0, 500),
    variables: result.variables,
}}));
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mjs', delete=False, dir='/tmp') as jf:
        jf.write(js_code)
        js_path = jf.name

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            ['node', js_path],
            capture_output=True, text=True, timeout=30,
            cwd='/tmp',
        )
        total_ms = round((time.monotonic() - t0) * 1000, 1)
        if proc.returncode != 0:
            return {'source': 'defuddle', 'error': proc.stderr[:500], 'ms': total_ms}

        data = json.loads(proc.stdout)
        data['total_ms'] = total_ms
        return data
    except Exception as e:
        return {'source': 'defuddle', 'error': str(e), 'ms': round((time.monotonic() - t0) * 1000, 1)}
    finally:
        import os
        os.unlink(html_path)
        try:
            os.unlink(js_path)
        except Exception:
            pass


def test_trafilatura_metadata(html: str, url: str) -> dict:
    """Test trafilatura's metadata extraction specifically."""
    import trafilatura
    from trafilatura.metadata import extract_metadata

    t0 = time.monotonic()
    meta = extract_metadata(html, url)
    ms = round((time.monotonic() - t0) * 1000, 1)

    if meta is None:
        return {'source': 'trafilatura-meta', 'ms': ms, 'error': 'no metadata'}

    return {
        'source': 'trafilatura-meta',
        'ms': ms,
        'title': meta.title,
        'author': meta.author,
        'date': str(meta.date) if meta.date else None,
        'sitename': meta.sitename,
        'description': meta.description,
        'categories': meta.categories if hasattr(meta, 'categories') else None,
        'tags': meta.tags if hasattr(meta, 'tags') else None,
        'license': meta.license if hasattr(meta, 'license') else None,
    }


def test_url_normalization(html: str, url: str) -> dict:
    """Test whether trafilatura preserves/normalizes relative URLs."""
    import trafilatura
    result = trafilatura.extract(
        html, url=url,
        include_formatting=True, include_links=True, include_tables=True,
    )
    if not result:
        return {'relative_urls': False, 'note': 'no extraction'}

    import re
    # Find all markdown links
    links = re.findall(r'\[([^\]]*)\]\(([^)]+)\)', result)
    relative = [l for l in links if not l[1].startswith(('http://', 'https://', 'mailto:', '#'))]
    absolute = [l for l in links if l[1].startswith(('http://', 'https://'))]

    return {
        'total_links': len(links),
        'absolute': len(absolute),
        'relative': len(relative),
        'relative_samples': [l[1] for l in relative[:5]],
        'absolute_samples': [l[1] for l in absolute[:3]],
    }


def run_tests():
    results = {}

    for name, url in TEST_PAGES.items():
        print(f'\n{"="*60}')
        print(f'Testing: {name} ({url})')
        print(f'{"="*60}')

        try:
            html = fetch_html(url)
            print(f'  Fetched: {len(html)} bytes')
        except Exception as e:
            print(f'  FETCH FAILED: {e}')
            results[name] = {'error': str(e)}
            continue

        page_results = {'url': url, 'html_bytes': len(html)}

        # Test trafilatura
        traf = test_trafilatura(html, url)
        print(f'  trafilatura: {traf["words"]} words, {traf.get("tables", 0)} table rows, '
              f'{traf.get("code_blocks", 0)} code blocks, {traf["ms"]}ms')
        page_results['trafilatura'] = {k: v for k, v in traf.items() if k != 'text'}

        # Test defuddle
        defu = test_defuddle(html, url)
        if 'error' in defu:
            print(f'  defuddle: ERROR: {defu["error"][:200]}')
        else:
            print(f'  defuddle: {defu.get("wordCount", "?")} words, '
                  f'title="{defu.get("title", "")[:50]}", '
                  f'author="{defu.get("author", "")}", '
                  f'{defu.get("ms", "?")}ms (node: {defu.get("total_ms", "?")}ms)')
            if defu.get('schemaOrgData'):
                print(f'  defuddle schema.org: {json.dumps(defu["schemaOrgData"])[:200]}')
            if defu.get('metaTags'):
                print(f'  defuddle metaTags: {len(defu["metaTags"])} tags')
        page_results['defuddle'] = defu

        # Test trafilatura metadata
        meta = test_trafilatura_metadata(html, url)
        title = (meta.get("title") or "")[:50]
        author = meta.get("author") or ""
        date = meta.get("date") or ""
        print(f'  trafilatura-meta: title="{title}", '
              f'author="{author}", date="{date}", '
              f'{meta["ms"]}ms')
        page_results['trafilatura_meta'] = meta

        # Test URL normalization
        urls = test_url_normalization(html, url)
        if 'total_links' in urls:
            print(f'  URL normalization: {urls["total_links"]} links, '
                  f'{urls["absolute"]} absolute, {urls["relative"]} relative')
            if urls.get('relative_samples'):
                print(f'    relative samples: {urls["relative_samples"]}')
        else:
            print(f'  URL normalization: {urls.get("note", "skipped")}')
        page_results['url_normalization'] = urls

        results[name] = page_results

    return results


if __name__ == '__main__':
    results = run_tests()

    # Write full results
    out_path = '/tmp/extraction_comparison.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f'\n\nFull results: {out_path}')
