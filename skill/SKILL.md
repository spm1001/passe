---
name: passe
description: >
  Orchestrates fast CDP browser automation via line DSL. MANDATORY BEFORE any
  `passe` command — provides verb vocabulary, scout-then-act pattern, and invocation
  conventions that prevent malformed scripts and wasted round-trips. Triggers on
  'passe run', 'automate the browser', 'screenshot a page', 'interact with a website',
  'click a button on', 'fill a form on', 'scrape this page', 'test this page'.
  For clean article/blog extraction use mise fetch; for DOM-faithful extraction
  (tables, code blocks, technical docs) use passe read. (user)
requires:
  - cli: passe
    check: "passe --version"
---

# passe — fast CDP browser automation

Single Bash call, single WebSocket, arbitrary action sequences. 100x faster than MCP round-trips.

## When to use

| Need | Tool |
|------|------|
| Screenshot, interact, test a page | **passe** |
| Extract content from any web page | **passe** `read` (trafilatura primary, Readability fallback, shadow DOM flattened) |
| Extract Google Workspace content (Drive, Gmail) | `mise fetch` |
| Full test suites with fixtures | Playwright directly |

**Passe owns web, mise owns Workspace — no overlap.** `passe read` uses trafilatura (Python-side) as the primary extractor for any page type, falling back to Readability.js+Turndown (browser-side) if trafilatura returns too little. Shadow DOM content is flattened before extraction.

## When not to use

- **Complex test frameworks with fixtures and assertions** — use Playwright directly

## Chrome connection

Passe connects to Chrome on port 9222. If the user's daily driver Chrome runs with `--remote-debugging-port=9222`, passe gets full auth state. If Chrome isn't running, passe auto-starts one with `--user-data-dir=~/.chrome-debug` — a bare profile with no auth. Never assume auth unless confirmed.

## Invocation

```bash
# Short scripts (≤4 verbs): inline
passe run -c 'goto https://example.com; screenshot /tmp/out.png'

# Longer scripts (5+ verbs): heredoc
passe run - <<'EOF'
goto https://example.com
click-text "Accept Cookies"
wait 500
type "#search" "query"
press Enter
wait-for .results
screenshot /tmp/results.png
EOF

# Reusable: .passe files
passe run tests/checkout.passe
```

Never generate long inline one-liners. Use heredoc for 5+ verbs.

## Verb reference

**Navigation:** `goto <url>`, `back`, `forward`, `scroll <x> <y>`

**Interaction:**
- `click <selector>` — CSS selector
- `click-text <"label">` — find by visible text, click
- `click-if <selector>` — click if exists, silently continue if not
- `type <selector> <text>` — character-by-character via CDP. **Use for SPAs.** Auto-detects React controlled inputs and falls back to nativeInputValueSetter if key events don't take.
- `fill <selector> <value>` — set value directly. Fast but may skip React/Vue reactivity.
- `select <selector> <value>` — dropdown
- `press <key>` — Enter, Tab, Escape, etc.
- `hover <selector>` — mouseover

**Observation:**
- `screenshot [path]` — full-page PNG (capped at 16384px). `--viewport` for viewport-only.
- `snapshot [path]` — list interactive elements with CSS selectors. For discovery.
- `read [--source extractor] [--no-wait] [path]` — extract page as markdown. Three-stage cascade: trafilatura → Readability.js+Turndown → innerText. Use `--source` to bypass cascade. **Auto-waits for DOM stability** when previous verb was navigation (`goto`/`back`/`forward`) — no explicit `wait` needed. Use `--no-wait` to skip.
- `fetch <url> [--source extractor] [path]` — **compound verb: goto + auto-wait + read**. The default for research/extraction. Path optional (auto temp file if omitted). Reports `file`, `final_url`, `source` in step output. Prefer this over `goto; wait; read`.
- `eval <expression>` — run JS, result in NDJSON step
- `eval-to <path> <expression>` — run JS, write result to file
- `eval-file <js-path>` — read JS from a file and evaluate. **Use for multi-line JS** — avoids the minify-to-one-line dance.
- `eval-file-to <out-path> <js-path>` — read JS from file, write result to file

**Control:**
- `wait <ms>`, `wait-for <selector> [timeout_ms]`, `wait-navigation`
- `viewport <width> <height>` — for responsive testing
- `assert <expression>` — fail script if falsy. Sub-millisecond.
- `log <message>` — print to stderr

## Output protocol

**stderr:** NDJSON per step — `{"i":0,"verb":"goto","ms":342}`
**stdout:** summary — `{"ok":true,"steps":6,"total_ms":443,"files":["/tmp/out.png"]}`
**Exit code:** 0 success, 1 failure

## Content extraction: `read` vs `eval`

`read` uses a three-stage cascade: trafilatura (Python-side, handles most page types) → Readability.js+Turndown (browser-side fallback) → innerText. Shadow DOM content is flattened before extraction, so web components (MDN code examples, etc.) are visible to both extractors. The `source` field in step output tells you which extractor was used.

**Known weaknesses:**

| Page type | `read` produces | Fix |
|-----------|----------------|-----|
| **Cookie banner visible** | Just the banner text | Dismiss banner first (scout → click) |
| **Animated/dynamic content** | Massive garbage | Use `eval` with `innerText` |
| **Large data tables** | Quality gate auto-detects loss, falls to Readability | Rarely needed now; `eval` as escape hatch |
| **Slow-hydrating SPAs** | Incomplete content | Add adequate `wait` before `read` |
| **JSON/XML/structured data** | Mangled prose extraction | Use `curl` or `eval-to` — trafilatura treats structured data as text |

**Decision tree:**

1. **Any page with text content?** → try `read` first (trafilatura handles articles, dashboards, SPAs)
2. **`read` output missing content?** → check `source` field; try `eval` with selector chain
3. **Cookie banner present?** → scout + dismiss first, then `read`
4. **Huge or garbled output?** → page has animations or dynamic content; switch to `eval`

**The `eval` fallback pattern** — chain selectors with `||` for resilience:

```bash
eval-to /tmp/content.txt document.querySelector('article')?.innerText || document.querySelector('[class*="content"]')?.innerText || document.querySelector('main')?.innerText || 'NO_CONTENT'
```

**For structured data**, use `eval-to` with `JSON.stringify`:

```bash
eval-to /tmp/links.json JSON.stringify(Array.from(document.querySelectorAll('a[href*="/blog/"]')).map(a => ({title: a.textContent.trim(), href: a.href})))
```

## The scout-then-act pattern

When you don't know the page's selectors:

```bash
# Pass 1: Scout
passe run -c 'goto https://site.com; snapshot /tmp/elements.txt'
```

Read `/tmp/elements.txt` — shows `[0] button "Sign in" css=#sign-in` etc.

```bash
# Pass 2: Act with discovered selectors
passe run - <<'EOF'
goto https://site.com
click "#sign-in"
wait 500
screenshot /tmp/result.png
EOF
```

Two Bash calls total.

### Cookie banners: always scout

**Do NOT guess cookie button text.** Button labels vary wildly between sites, and `click-text` fails on doubled text from icon+label combinations (e.g. `snapshot` shows `"RejectReject All Cookies"`). Always scout first:

```bash
# Scout to find the actual button
passe run -c 'goto https://site.com; snapshot /tmp/elements.txt'
# Read elements.txt, find the cookie button's CSS selector
# Then use click with the exact selector
passe run - <<'EOF'
goto https://site.com
click "div > button:nth-of-type(2)"
wait 500
read /tmp/content.md
EOF
```

## Smoke tests with `assert`

`assert` evaluates JS and fails the script if falsy. Each assertion takes <1ms. Use for quick health checks:

```bash
passe run - <<'EOF'
goto https://your-site.com
assert document.title.includes("Expected")
assert document.querySelectorAll("nav a").length > 0
assert !document.querySelector(".error-banner")
log All checks passed
screenshot /tmp/healthy.png --viewport
EOF
```

This pattern works as a `.passe` file for reusable site verification.

## Multi-line JS: use `eval-file`

The DSL is line-based — `eval` and `eval-to` take a single line of JS. For anything beyond a one-liner, write the JS to a file and use `eval-file`:

```bash
# Write multi-line JS (use Write tool, not heredoc-into-eval)
# Then reference it in the script:
passe run - <<'EOF'
goto https://example.com
wait 1000
eval-file /tmp/my-analysis.js
screenshot /tmp/result.png
EOF

# Or with output capture:
passe run - <<'EOF'
goto https://example.com
eval-file-to /tmp/data.json /tmp/extract-data.js
EOF
```

This replaces the painful minify → bash variable → unquoted heredoc dance.

## Remote Chrome (cross-machine)

When Chrome Debug runs on a different machine (e.g., Mac) and you're on Kube/remote:

1. Set `PASSE_CDP=http://<host>:9222` — find the host via `tailscale status | grep macOS`
2. Verify: `curl -s $PASSE_CDP/json/list` should show open tabs
3. All passe commands respect `PASSE_CDP`

**Common issue:** If passe attaches to `chrome://newtab-footer` or similar internal pages, close them first:
````bash
# List real tabs
curl -s $PASSE_CDP/json/list | python3 -c "import json,sys; [print(f\"{t['title'][:50]} — {t['url'][:60]}\") for t in json.load(sys.stdin) if t['type']=='page']"

# Close internal pages so real tab is first
ID=$(curl -s $PASSE_CDP/json/list | python3 -c "import json,sys; [print(t['id']) for t in json.load(sys.stdin) if 'newtab' in t.get('url','')]" | head -1)
curl -s "$PASSE_CDP/json/close/$ID"
````

## User handoff (login required)

Passe creates and closes its own tab — the user never sees it. When you need the user to interact (e.g., log in):

**Current workaround** (until `--keep-tab` and `--reuse-tab` land):
````bash
# Navigate the user's visible tab via raw CDP (no tab create/close)
uv run --with websockets python3 -c "
import asyncio, json, websockets
async def nav():
    ws = await websockets.connect('WS_URL_FROM_JSON_LIST')
    await ws.send(json.dumps({'id':1,'method':'Page.navigate','params':{'url':'TARGET_URL'}}))
    await ws.recv(); await ws.close()
asyncio.run(nav())
"
# Then wait for user: "Log in and let me know when you're done"
# Screenshot to verify: use the same websocket pattern with Page.captureScreenshot
````

**Future** (tracked in bon): `passe run --reuse-tab --keep-tab` will handle this natively.

## Anti-patterns

- **`fill` vs `type`**: Default to `type` for SPAs. `fill` is for plain HTML forms only.
- **Guessing cookie button text**: `click-text "Reject"` fails more often than it works. Scout first.
- **`click-text` with multiple matches**: Clicks first visible match. Be specific.
- **Tab handling**: Passe attaches to the first tab. No tab switching.
- **Script errors are fatal**: No mid-script recovery. Partial timing still emitted to stderr.
- **DOM mutation during TreeWalker traversal**: If you use `eval` to walk the DOM with `createTreeWalker` and mutate nodes (e.g. `replaceChild`), the walker loses its position and silently stops. **Collect nodes first into an array, then mutate in a second pass.**
- **Minifying JS for `eval`**: Don't. Use `eval-file` instead.
- **`eval-file-to` arg order**: It's `eval-file-to <out-path> <js-path>` — output first, source second. Matches `eval-to` convention but opposite to Unix (source → dest). Double-check.
- **Arbitrary `wait` durations**: Don't guess (`wait 2000`). Use `wait-for <selector>` with a specific element, or omit the wait entirely on server-rendered pages — most complete in <300ms. Only add `wait` for known-slow SPAs with measured timing.

## Atomic commands

For one-off operations without script overhead:

```bash
passe screenshot /tmp/current.png    # Screenshot whatever's loaded
passe eval "document.title"          # Quick JS eval
```

## Development

```bash
# After editing passe source:
uv tool install /Users/modha/Repos/passe --force --reinstall

# Run tests:
uv run --with pytest pytest tests/ -v
```
