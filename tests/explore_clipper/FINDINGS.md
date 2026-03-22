# Obsidian Clipper Exploration — Findings for Passe

## What we tested

Cloned [obsidian-clipper](https://github.com/obsidianmd/obsidian-clipper) and
explored its extraction, metadata, template, and DOM handling systems. Compared
against passe's existing extraction cascade (trafilatura → Readability.js →
innerText).

## Key findings

### 1. Defuddle extraction engine — WORTH ADDING

Defuddle (`defuddle@0.14.0`, MIT, by Steph Ango/kepano) is a standalone
extraction library that wraps Readability.js + Turndown but adds:

- **Site-specific extractors**: YouTube (transcripts), Reddit, GitHub, Hacker
  News, ChatGPT/Claude/Gemini/Grok (conversation extractors), X/Twitter
- **Richer metadata**: author, published date, schema.org/JSON-LD, all meta
  tags, language, word count — in a single parse
- **Better HTML normalization**: standardizes footnotes, code blocks, math
  (MathML → LaTeX), callouts before conversion
- **Mobile CSS inspection**: applies mobile media queries to remove clutter
- **React SSR handling**: resolves streaming suspense boundaries
- **Shadow DOM awareness**: reads `data-defuddle-shadow` attributes

**Test results** (HTTP-only, no Chrome):

| Page | trafilatura words | defuddle words | defuddle extras |
|------|-------------------|----------------|-----------------|
| PG essay | 7206 | 7293 | title |
| Python docs | 3338 | 4625 | title, author ("Python documentation"), 16 meta tags |
| MDN Promise | 3781 | 4633 | title, 19 meta tags, published date |

Defuddle consistently extracts ~20-35% more content (keeps nav context,
related links, etc. that trafilatura strips). It also extracts metadata that
passe currently throws away.

**Trade-off**: Node.js dependency (ESM-only via `defuddle/node` + `linkedom`).
Adds ~400ms cold start. Could be used as a fallback or alternative to
Readability.js in the browser-side cascade.

**Recommendation**: Add as `--source defuddle` option. Use browser-side (not
Node.js) since passe already has Chrome. The browser bundle
(`defuddle/full`) can run directly via `Runtime.evaluate`.

### 2. Shadow DOM flattening — KEEP CURRENT APPROACH

Obsidian's approach: 10 lines, stamps `innerHTML` into `data-defuddle-shadow`
attributes. Passe's approach: 25 lines, custom recursive serializer that
inlines shadow content as real DOM children.

**Verdict**: Passe's approach is correct for a CDP tool. The serialized HTML
goes to trafilatura (Python-side), which doesn't know about data attributes.
Obsidian's approach only works because defuddle reads those attrs.

No change needed.

### 3. Metadata extraction — WORTH ADDING

Passe currently extracts: `textLength`, `htmlLength`, `title`, `url`. That's it.

Proposed `METADATA_JS` (~60 lines) would extract in one Chrome eval:
- All meta tags (name + property)
- OpenGraph (`og:*`)
- Twitter Card (`twitter:*`)
- Schema.org / JSON-LD
- Author (from meta, article:author, dc.creator, time[datetime])
- Published date, canonical URL, favicon, language

This runs in <5ms in Chrome. Cost is negligible.

**Recommendation**: Add `METADATA_JS` to `_libs.py`. Add `--meta` flag to
`extract`/`fetch` that includes metadata in step output and summary JSON.

### 4. Selection clipping — LOW PRIORITY

Obsidian uses `window.getSelection()` → `Range.cloneContents()` for selection
extraction. This is valuable for interactive extensions but less useful for
a CLI tool that can already target specific content via `eval` + CSS selectors.

Prototyped `SELECTION_EXTRACT_JS` (~35 lines) but the use case is narrow.

**Recommendation**: Not worth a dedicated verb. The JS snippet is available in
`test_selection_clipping.py` if ever needed.

### 5. Post-processing filters — PARTIALLY USEFUL

Tested 4 filters from Obsidian's 56-filter system:

| Filter | Speed | Useful for passe? |
|--------|-------|-------------------|
| `strip_markdown` | 0.06ms | Maybe — as utility function |
| `strip_links` | 0.004ms | Yes — `--strip-links` on extract |
| `truncate_words` | trivial | Yes — `--words N` on extract |
| `json_to_table` | trivial | No — too niche, use jq |

**Recommendation**: Add `strip_links()` and `truncate_words()` as utility
functions. Add `--strip-links` and `--words N` flags to `extract`/`fetch`.

### 6. URL normalization — CONFIRMED BUG

trafilatura does NOT normalize relative URLs to absolute. Test on
paulgraham.com:

```
Links: 19 total, 0 absolute, 2 relative
Relative samples: ['schlep.html', 'marginal.html']
```

These should be `https://paulgraham.com/schlep.html` etc. Passe passes
`url=page_url` to `trafilatura.extract()` but trafilatura doesn't use it for
link resolution.

**Recommendation**: Post-process trafilatura output to resolve relative URLs:
```python
import re
from urllib.parse import urljoin
markdown = re.sub(
    r'\[([^\]]+)\]\((/[^)]+|[^)]+\.html?)\)',
    lambda m: f'[{m.group(1)}]({urljoin(page_url, m.group(2))})',
    markdown
)
```

## What's NOT worth stealing

- **Template AST system** — We have shell pipes
- **Highlight/XPath re-application** — Interactive extension feature
- **56-filter library** — Over-engineered for CLI
- **Browser extension architecture** — CDP-native is better
- **DOMPurify** — No XSS risk in CLI output

## Files in this exploration

- `test_extraction_comparison.py` — Defuddle vs trafilatura comparison
- `test_shadow_dom.py` — Shadow DOM approach analysis
- `test_metadata_extraction.py` — Metadata extraction prototype
- `test_selection_clipping.py` — Selection clipping prototype
- `test_post_processing.py` — Filter functions with tests
