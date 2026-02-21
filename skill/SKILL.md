---
name: passe
description: >
  Orchestrates fast CDP browser automation via line DSL. MANDATORY BEFORE any
  `passe` command — provides verb vocabulary, scout-then-act pattern, and invocation
  conventions that prevent malformed scripts and wasted round-trips. Triggers on
  'passe run', 'automate the browser', 'screenshot a page', 'interact with a website',
  'click a button on', 'fill a form on', 'scrape this page', 'test this page',
  'capture network requests', 'what API calls does this page make',
  'reverse-engineer API', 'record network traffic', 'inspect HTTP requests'.
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
| See what API calls a page makes | **passe** `capture` (network requests to JSONL) |
| Extract Google Workspace content (Drive, Gmail) | `mise fetch` |
| Full test suites with fixtures | Playwright directly |

**Passe owns web, mise owns Workspace — no overlap.** `passe read` uses trafilatura (Python-side) as the primary extractor for any page type, falling back to Readability.js+Turndown (browser-side) if trafilatura returns too little. Shadow DOM content is flattened before extraction.

## When not to use

- **Complex test frameworks with fixtures and assertions** — use Playwright directly

## Chrome connection

Passe connects to Chrome on port 9222. Two modes:

| Machine | Chrome | Auth state | Use for |
|---------|--------|-----------|---------|
| **Mac** (daily driver) | Chrome Debug with `--remote-debugging-port=9222` | Full cookies, SSO | Authenticated browsing, OAuth flows |
| **Kube/remote** | Headless Chromium (systemd) on `localhost:9222` | Bare profile | Dev testing, screenshots, device emulation |

Use `--cdp http://host:9222` to target a specific Chrome instance per-invocation (overrides `PASSE_CDP` env var). Default: localhost:9222.

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

# Global flags (apply to any subcommand):
passe --cdp http://host:9222 run -c '...'              # Target specific Chrome
passe --device "iPhone 14 Pro" run -c '...'             # Device emulation preset
passe --device "iPhone 14 Pro" --dpr 1 run -c '...'     # 1x DPR (smaller screenshots)
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
- `screenshot [--fast] [--format png|jpeg|webp] [--quality 0-100] [--viewport] [path]` — full-page PNG by default (capped at 16384px). `--viewport` for viewport-only. **`--fast`** shorthand: JPEG q70 + `optimizeForSpeed` + viewport-only — 2-4x faster, 3-6x smaller. Use for inner-loop iteration. Returns timing breakdown in step NDJSON (`capture_ms`, `decode_ms`, `write_ms`, `bytes`).
- `snapshot [path]` — list interactive elements with CSS selectors. For discovery.
- `read [--source extractor] [--no-wait] [path]` — extract page content. **Content-type sniffing**: JSON/XML/CSV/plain text pages bypass extraction and return raw content (JSON pretty-printed, `source: raw`). HTML pages use cascade: trafilatura → Readability.js+Turndown → innerText. **Thin-read diagnostics**: if extraction is <200 chars, emits `thin_read` in step NDJSON with `possible_cause` (auth_wall/js_hydration/empty_page/unknown) and page metadata. Use `--source raw|trafilatura|readability|innertext` to force. **Auto-waits** after navigation verbs. Use `--no-wait` to skip.
- `fetch <url> [--source extractor] [path]` — **compound verb: goto + auto-wait + read**. The default for research/extraction. Path optional (auto temp file if omitted). Reports `file`, `final_url`, `source` in step output. Prefer this over `goto; wait; read`.
- `eval <expression>` — run JS, result in NDJSON step
- `eval-to <path> <expression>` — run JS, write result to file
- `eval-file <js-path>` — read JS from a file and evaluate. **Use for multi-line JS** — avoids the minify-to-one-line dance.
- `eval-file-to <out-path> <js-path>` — read JS from file, write result to file

**Network:**
- `capture [--bodies] <path>` — record all network requests to JSONL. Place at script start; writes on exit. Step NDJSON summary: count, by_type, domains, errors. `--bodies` includes response bodies (large, opt-in).

**Emulation:**
- `device <"name"> [--dpr N]` — apply device emulation preset (viewport, DPR, UA, touch, safe area). Available: iPhone 14 Pro, iPhone SE, Pixel 7, iPad Air, iPad Pro 11, Desktop 1080p. `--dpr 1` overrides DPR for smaller screenshots.
- `viewport <width> <height>` — raw dimensions escape hatch (no UA/touch/safe-area)

**Control:**
- `wait <ms>`, `wait-for <selector> [timeout_ms]`, `wait-navigation`
- `watch [--fast] <path>` — **HMR-triggered auto-screenshot.** Listens for Vite `[vite] hot updated` and `[vite] page reload` console messages + DOM mutations (Tailwind CSS). Debounces 100ms, screenshots to path (overwrite each time). Stays alive until killed. Use with `Bash run_in_background`. NDJSON events: `watch_started`, `hmr`/`mutation`/`reload` (with `screenshot_ms`, `kb`), `watch_stopped`.
- `assert <expression>` — fail script if falsy. Sub-millisecond.
- `log <message>` — print to stderr

## Output protocol

**stderr:** NDJSON per step — `{"i":0,"verb":"goto","ms":342}`
**stdout:** summary — `{"ok":true,"steps":6,"total_ms":443,"files":[{"path":"/tmp/out.png","verb":"screenshot","format":"png","kb":234.5}]}`
**Exit code:** 0 success, 1 failure

`files` entries are objects with `path`, `verb`, and verb-specific metadata — read the summary to decide which files to open.

## Content extraction: `read` vs `eval`

`read` uses a three-stage cascade: trafilatura (Python-side, handles most page types) → Readability.js+Turndown (browser-side fallback) → innerText. Shadow DOM content is flattened before extraction, so web components (MDN code examples, etc.) are visible to both extractors. The `source` field in step output tells you which extractor was used.

**Known weaknesses:**

| Page type | `read` produces | Fix |
|-----------|----------------|-----|
| **Cookie banner visible** | Just the banner text | Dismiss banner first (scout → click) |
| **Animated/dynamic content** | Massive garbage | Use `eval` with `innerText` |
| **Large data tables** | Quality gate auto-detects loss, falls to Readability | Rarely needed now; `eval` as escape hatch |
| **Slow-hydrating SPAs** | Incomplete content | Add adequate `wait` before `read` |
| **JSON/XML/structured data** | Raw passthrough (auto-detected) | Content-type sniffing handles this automatically (`source: raw`) |

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

## Reverse-engineering APIs with `capture`

`capture` records all network requests during a script to JSONL. Place it at the start — it writes on script exit.

```bash
# Discover what API calls a page makes
passe run - <<'EOF'
capture /tmp/reqs.jsonl
goto https://spa.example.com
click-text "Search"
type "#query" "parental leave"
press Enter
wait 2000
EOF
```

The stderr summary tells you the shape without reading the file:
```json
{"verb":"capture","file":"/tmp/reqs.jsonl","requests":47,"by_type":{"XHR":3,"Script":15,"Image":27},"domains":["api.example.com","cdn.example.com"]}
```

Then grep for the API calls: `grep '"XHR"' /tmp/reqs.jsonl`. Use `--bodies` to include response payloads (large — opt-in).

**The pattern:** capture → identify the API endpoint → call it directly via `eval` + `fetch()` using the authenticated API pattern. Skip the UI entirely.

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

Passe creates and closes its own tab — the user never sees it. When you need the user to interact (e.g., log in), use `--reuse-tab` and `--keep-tab`:

```bash
# Navigate the user's visible tab
passe run --reuse-tab -c 'goto https://accounts.google.com/oauth/...'
# Ask user: "Log in and let me know when you're done"
# Then capture the result
passe run --reuse-tab -c 'eval document.body.innerText'
```

`--reuse-tab` attaches to the first non-chrome:// tab. `--keep-tab` prevents passe from closing the tab on exit. `--reuse-tab` implies `--keep-tab`.

## Anti-patterns

- **`fill` vs `type`**: Default to `type` for SPAs. `fill` is for plain HTML forms only.
- **Guessing cookie button text**: `click-text "Reject"` fails more often than it works. Scout first.
- **`click-text` with multiple matches**: Clicks first visible match. Be specific.
- **Tab handling**: Passe attaches to the first tab. No tab switching.
- **Script errors are fatal**: No mid-script recovery. Partial timing still emitted to stderr.
- **DOM mutation during TreeWalker traversal**: If you use `eval` to walk the DOM with `createTreeWalker` and mutate nodes (e.g. `replaceChild`), the walker loses its position and silently stops. **Collect nodes first into an array, then mutate in a second pass.**
- **Minifying JS for `eval`**: Don't. Use `eval-file` instead.
- **`eval-file-to` arg order**: It's `eval-file-to <out-path> <js-path>` — output first, source second. Matches `eval-to` convention but opposite to Unix (source → dest). Double-check.
- **Arbitrary `wait` durations**: Don't guess (`wait 2000`). `read` auto-waits for DOM stability after navigation verbs — no explicit wait needed. Use `fetch URL /tmp/out.md` for the common case (goto + auto-wait + read in one step). Only use explicit `wait` or `wait-for` for SPAs where you need a specific element to appear after a click.
- **PNG for inner-loop iteration**: Use `screenshot --fast` for edit-and-see loops. PNG at 3x DPR produces 1179×2556 images (expensive in tokens). `--fast` gives JPEG viewport-only at the preset DPR (or `--dpr 1` for even smaller). Save PNG for final fidelity checks.

## Atomic commands

For one-off operations without script overhead:

```bash
passe screenshot /tmp/current.png    # Screenshot whatever's loaded
passe eval "document.title"          # Quick JS eval
```

## Mobile UI development loop

Device emulation + fast screenshots + watch verb = Claude sees mobile UI without a human.

```bash
# One-shot: screenshot a page as iPhone
passe --cdp http://localhost:9222 --device "iPhone 14 Pro" --dpr 1 \
  run -c 'goto http://localhost:5173; screenshot --fast /tmp/mobile.jpg'

# Continuous: auto-screenshot on every Vite HMR update
passe --cdp http://localhost:9222 --device "iPhone 14 Pro" --dpr 1 \
  run -c 'goto http://localhost:5173; watch --fast /tmp/mobile.jpg'
```

The `watch` verb runs in the background. Start it with `Bash run_in_background`, then read `/tmp/mobile.jpg` after each edit. Use `TaskStop` to kill it when done.

**Available device presets:** iPhone 14 Pro, iPhone SE, Pixel 7, iPad Air, iPad Pro 11, Desktop 1080p.

**Fidelity caveat:** This is Chrome's Blink pretending to be Safari's WebKit. Layout, spacing, and components are pixel-close. Safari-specific bugs (`-webkit-` scroll, rubber-band, backdrop-filter) need the real device.

## Development

```bash
# After editing passe source:
uv tool install ~/Repos/passe --force --reinstall

# Run tests:
uv run --with pytest pytest tests/ -v
```
