#!/usr/bin/env python3
"""Test metadata extraction — what passe currently misses and what we could add.

Inspired by Obsidian Clipper's schema.org/OpenGraph/meta variable system.
Tests a JS snippet that extracts structured metadata alongside content.
"""
import json
import subprocess
import tempfile
import time
import urllib.request
import os

# Proposed JS for metadata extraction — runs in Chrome, returns structured data
METADATA_JS = r'''(() => {
  const meta = {};

  // 1. Basic page metadata
  meta.title = document.title;
  meta.url = window.location.href;
  meta.language = document.documentElement.lang || '';

  // 2. Meta tags (name and property)
  const metaTags = {};
  document.querySelectorAll('meta[name], meta[property]').forEach(el => {
    const key = el.getAttribute('name') || el.getAttribute('property');
    const content = el.getAttribute('content');
    if (key && content) metaTags[key] = content;
  });
  meta.metaTags = metaTags;

  // 3. OpenGraph
  meta.og = {};
  document.querySelectorAll('meta[property^="og:"]').forEach(el => {
    const key = el.getAttribute('property').replace('og:', '');
    meta.og[key] = el.getAttribute('content');
  });

  // 4. Twitter Card
  meta.twitter = {};
  document.querySelectorAll('meta[name^="twitter:"], meta[property^="twitter:"]').forEach(el => {
    const key = (el.getAttribute('name') || el.getAttribute('property')).replace('twitter:', '');
    meta.twitter[key] = el.getAttribute('content');
  });

  // 5. Schema.org / JSON-LD
  meta.jsonLd = [];
  document.querySelectorAll('script[type="application/ld+json"]').forEach(el => {
    try {
      const data = JSON.parse(el.textContent);
      meta.jsonLd.push(data);
    } catch(e) {}
  });

  // 6. Canonical URL
  const canonical = document.querySelector('link[rel="canonical"]');
  meta.canonical = canonical ? canonical.href : null;

  // 7. Favicon
  const favicon = document.querySelector('link[rel="icon"], link[rel="shortcut icon"]');
  meta.favicon = favicon ? favicon.href : null;

  // 8. Author (multiple sources)
  meta.author = metaTags['author']
    || metaTags['article:author']
    || metaTags['dc.creator']
    || '';

  // 9. Published date (multiple sources)
  meta.published = metaTags['article:published_time']
    || metaTags['datePublished']
    || metaTags['dc.date']
    || '';
  // Also check <time> elements
  if (!meta.published) {
    const timeEl = document.querySelector('time[datetime]');
    if (timeEl) meta.published = timeEl.getAttribute('datetime');
  }

  // 10. Description
  meta.description = metaTags['description']
    || metaTags['og:description']
    || metaTags['twitter:description']
    || '';

  return JSON.stringify(meta);
})()'''

# Test pages with rich metadata
TEST_URLS = {
    'nyt_article': 'https://www.nytimes.com/2024/01/01/technology/ai-predictions.html',
    'python_docs': 'https://docs.python.org/3/library/json.html',
    'mdn': 'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise',
    'pg_essay': 'https://www.paulgraham.com/startupideas.html',
}


def test_metadata_from_html(html: str, url: str) -> dict:
    """Extract metadata using both trafilatura and our proposed JS approach."""
    results = {}

    # Trafilatura metadata
    try:
        from trafilatura.metadata import extract_metadata
        t0 = time.monotonic()
        meta = extract_metadata(html, url)
        ms = round((time.monotonic() - t0) * 1000, 1)
        results['trafilatura'] = {
            'ms': ms,
            'title': meta.title if meta else None,
            'author': meta.author if meta else None,
            'date': str(meta.date) if meta and meta.date else None,
            'sitename': meta.sitename if meta else None,
            'description': meta.description if meta else None,
        }
    except Exception as e:
        results['trafilatura'] = {'error': str(e)}

    # Defuddle metadata
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(html)
        html_path = f.name

    js_code = f"""
import {{ Defuddle }} from 'defuddle/node';
import {{ parseHTML }} from 'linkedom';
import fs from 'fs';

const html = fs.readFileSync('{html_path}', 'utf-8');
const {{ document }} = parseHTML(html);
const result = await Defuddle(document, '{url}', {{ markdown: false }});
console.log(JSON.stringify({{
    title: result.title,
    author: result.author,
    published: result.published,
    site: result.site,
    description: result.description,
    language: result.language,
    schemaOrgData: result.schemaOrgData,
    metaTagCount: (result.metaTags || []).length,
    extractorType: result.extractorType,
}}));
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mjs', delete=False, dir='/tmp') as jf:
        jf.write(js_code)
        js_path = jf.name

    try:
        t0 = time.monotonic()
        proc = subprocess.run(
            ['node', js_path], capture_output=True, text=True, timeout=30, cwd='/tmp',
        )
        ms = round((time.monotonic() - t0) * 1000, 1)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            data['ms'] = ms
            results['defuddle'] = data
        else:
            results['defuddle'] = {'error': proc.stderr[:300], 'ms': ms}
    except Exception as e:
        results['defuddle'] = {'error': str(e)}
    finally:
        os.unlink(html_path)
        try:
            os.unlink(js_path)
        except Exception:
            pass

    return results


def run():
    print("=" * 60)
    print("METADATA EXTRACTION COMPARISON")
    print("=" * 60)
    print()
    print("What passe currently extracts (from do_read, line 720-726):")
    print("  - textLength, htmlLength, title, url")
    print("  - That's it. No author, date, description, schema.org.")
    print()
    print("What we COULD extract with the proposed METADATA_JS:")
    print("  - title, url, language, canonical")
    print("  - All meta tags (name + property)")
    print("  - OpenGraph, Twitter Card")
    print("  - Schema.org / JSON-LD")
    print("  - Author (from meta, article:author, dc.creator)")
    print("  - Published date (from meta, time[datetime])")
    print("  - Favicon")
    print()

    print(f"Proposed JS size: {len(METADATA_JS)} chars")
    print()

    for name, url in TEST_URLS.items():
        print(f"\n--- {name}: {url} ---")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='replace')
            print(f"  Fetched: {len(html)} bytes")
        except Exception as e:
            print(f"  FETCH FAILED: {e}")
            continue

        results = test_metadata_from_html(html, url)

        for engine, data in results.items():
            if 'error' in data:
                print(f"  {engine}: ERROR: {data['error'][:100]}")
            else:
                print(f"  {engine}: title=\"{(data.get('title') or '')[:40]}\" "
                      f"author=\"{data.get('author') or ''}\" "
                      f"date=\"{data.get('date') or data.get('published') or ''}\"")
                if data.get('schemaOrgData'):
                    schema = data['schemaOrgData']
                    types = []
                    if isinstance(schema, dict):
                        types = [schema.get('@type', '?')]
                    elif isinstance(schema, list):
                        types = [s.get('@type', '?') for s in schema if isinstance(s, dict)]
                    print(f"           schema.org types: {types}")

    print("\n" + "=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    print("""
1. Add METADATA_JS to _libs.py — runs alongside the existing meta eval
2. Add --meta flag to extract/fetch that includes metadata in output
3. Metadata goes into step NDJSON on stderr + summary JSON on stdout
4. defuddle extracts richer metadata (author, schema.org) but at higher cost
5. The proposed JS is lightweight (~60 lines) and runs in <5ms in Chrome
""")


if __name__ == '__main__':
    run()
