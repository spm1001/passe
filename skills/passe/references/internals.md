# Output Protocol and Internals

## Output protocol

**stderr:** NDJSON per step — `{"i":0,"verb":"goto","ms":342,"url":"...","status_code":200}`
**stdout:** summary — `{"ok":true,"steps":6,"total_ms":443,"files":[...],"final_url":"..."}`
**Exit:** `passe fetch`: 0 = success, 1 = thin/degraded extraction (content returned, assess usability), 2 = tool failure (Chrome down, network error, bad args). Scripts (`passe run`): 0/1.

## HTTP fast-path (fetch only)

`passe fetch` tries HTTP before touching Chrome (~87% of pages, 300-1500ms):

1. Markdown-source probe — advertised `.md` alternates, `.md` siblings, llms.txt indexes (`source: markdown_probe`)
2. Framework shortcuts — Apple docs JSON API, Next.js `__NEXT_DATA__`
3. httpx GET → trafilatura → composite quality gate

Escalation is never silent: `fast_path: false` carries `fast_path_reason` (`spa_shell`, `quality=0.25`, `http_403`, `skipped: ...`).

## Content extraction cascade (Chrome path)

1. Content-type sniffing (JSON/XML/CSV → raw passthrough)
2. Apple docs → structured JSON endpoint
3. trafilatura (Python-side, handles most pages)
4. Readability.js + Turndown (browser-side fallback)
5. innerText (last resort)

Shadow DOM flattened before extraction. `source` field in output tells you which extractor was used. A structural quality gate rejects trafilatura output that dropped tables or code blocks.

## Diagnostics

- `thin_read` — suspiciously small extraction: word counts plus probable cause (`auth_wall`, `empty_page`, `js_hydration`, `unknown`)
- `code_block_warning` — the page's `<pre>` blocks were empty in the DOM (component-rendered code that never landed); hint points at `capture --bodies` for source-data discovery
