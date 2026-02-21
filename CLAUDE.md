# Passe — fast CDP browser automation

The kitchen pass (passe) between Claude and Chrome. Inspect every plate before it goes out.

## What passe is

A CLI tool that connects to Chrome via raw WebSocket (Chrome DevTools Protocol) and executes browser actions. One process, one connection, no daemon, no extension. Built because we measured the alternatives:

| Approach | Navigate + screenshot |
|---|---|
| **passe** (Bash → CDP) | **213ms** |
| Playwright MCP (8 tool calls through model) | ~12,600ms |
| claude-in-chrome (MCP extension) | ~12,600ms |

The 100x speed gap isn't the browser — it's the protocol. MCP needs a model round-trip per action (~6s each). Passe does everything in a single Bash call.

## When to use passe (and when not to)

| Need | Tool |
|------|------|
| Screenshot a page, interact with it, test it | **passe** |
| Extract content from any page (articles, SPAs, dashboards) | **passe** `read` (trafilatura primary, Readability.js fallback) |
| See what API calls a page makes | **passe** `capture` (network request recording to JSONL) |
| Extract Workspace content (Drive docs, Gmail) | `mise fetch` |
| Browse with the default Chrome profile interactively | `webctl` |
| Full Playwright test suites with fixtures and assertions | Playwright directly |

Passe is for **fast, scriptable, single-connection browser automation from the CLI**. The `read` verb extracts clean markdown from any page type — it gets the rendered HTML from Chrome, runs trafilatura Python-side for extraction, and falls back to Readability.js+Turndown if trafilatura can't handle it. Use `mise fetch` for Google Workspace content (Drive, Gmail).

## The Chrome connection model

**This is the single most important thing to understand.**

Passe connects to Chrome on port 9222. Sameer's daily driver Chrome runs with `--remote-debugging-port=9222` — so passe gets his full auth state, cookies, SSO sessions.

If Chrome isn't running, passe auto-starts one with `--user-data-dir=~/.chrome-debug`. That's a **bare profile** — no auth, no cookies, no extensions. This is fine for testing public pages but won't have any login sessions.

**Never assume you have auth unless you've confirmed Chrome is Sameer's daily driver instance.**

### Local headless Chrome on kube

Headless Chromium runs as a systemd user service (`chromium-cdp.service`) on port 9222. GPU acceleration is enabled via `--ignore-gpu-blocklist --use-angle=vulkan` — ANGLE falls through to OpenGL EGL on the GTX 1650. Without these flags, Chrome uses SwiftShader software rendering and full-page screenshots of dense pages take 60–136s instead of 2s.

```
# Service: ~/.config/systemd/user/chromium-cdp.service
ExecStart=/usr/bin/chromium --headless=new --remote-debugging-port=9222 --no-sandbox \
  --no-first-run --no-default-browser-check --user-data-dir=%h/.chromium-cdp \
  --ignore-gpu-blocklist --use-angle=vulkan
```

`PASSE_CDP` in `.bashrc` points at the Mac Chrome via tailscale, not this local instance. To use local headless: `PASSE_CDP=http://localhost:9222 passe run ...`

### Remote Chrome from kube (Mac via tailscale)

Chrome Debug on the Mac binds to `localhost:9222` only (Chrome 145 ignores `--remote-debugging-address=0.0.0.0`). Kube reaches it via `tailscale serve`:

| Where | What |
|-------|------|
| **Mac** | `tailscale serve --bg --tcp 9222 tcp://localhost:9222` (persistent, survives reboots) |
| **Kube** | `PASSE_CDP=http://100.66.153.39:9222` in `.bashrc` |
| **Passe** | WebSocket URL rewriting in `connect()` — rewrites `ws://localhost:...` to use the Tailscale IP |

**Verify:** `curl -s $PASSE_CDP/json/version` should return Chrome's version JSON.

**If connection fails but Chrome is running:** Check for stale Chrome processes hogging port 9222. `lsof -i :9222` on the Mac — if old PIDs hold the port, kill them and restart Chrome Debug. This is the most common failure mode.

### Tab isolation

`passe run` creates its own tab in the background (`background: True` in `Target.createTarget`), runs the script there, and closes it on exit. Your existing tabs are never touched and Chrome doesn't steal focus. Atomic commands (`passe screenshot`, `passe eval`) attach to the first existing tab — they observe the current page, they don't navigate.

## The DSL

Passe has a line-based scripting language. One verb per line, parsed with `shlex.split()`.

### Invocation patterns

```bash
# Short scripts (≤4 verbs): inline with -c, '; ' as separator
# Verb-aware split: '; ' only splits when followed by a known verb,
# so JS semicolons in eval/assert survive (e.g. 'eval var x = 1; x').
passe run -c 'goto https://example.com; screenshot /tmp/out.png'

# Longer scripts (5+ verbs): heredoc. ALWAYS use this for complex flows.
passe run - <<'EOF'
goto https://example.com
click-text "Accept Cookies"
wait 500
type "#search" "query"
press Enter
wait-for .results
screenshot /tmp/results.png
EOF

# Reusable scripts: .passe files
passe run tests/checkout-flow.passe
```

**Never generate 120-token inline one-liners.** Use heredoc for 5+ verbs.

**Global flags** (apply to any subcommand):
- `--cdp <url>` — CDP endpoint (overrides `PASSE_CDP` env, default `http://localhost:9222`)
- `--device <name>` — device emulation preset applied before script
- `--dpr <n>` — override device pixel ratio (e.g. `1` for smaller screenshots)

### Verb reference

**Navigation:**
- `goto <url>` — navigate and wait for load. Step NDJSON includes `url` (final URL after redirects) and `status_code` (HTTP status, e.g. 200, 301, 403). No need for `eval window.location.href` — goto tells you where you landed.
- `back` / `forward` — browser history. Step NDJSON includes `url` (page URL after navigation).
- `scroll <x> <y>` — window.scrollTo

**Interaction:**
- `click <selector>` — CSS selector click
- `click-text <"label">` — find by text content, click. Great for cookie banners: `click-text "Reject"`
- `click-if <selector>` — click if exists, silently continue if not. For optional elements.
- `type <selector> <text>` — character-by-character via `Input.insertText`. Works with React, Vue, and plain HTML. Auto-detects controlled inputs and falls back to `nativeInputValueSetter` if needed.
- `fill <selector> <value>` — set value directly. Faster but may not trigger framework reactivity. Use `type` if unsure.
- `select <selector> <value>` — dropdown
- `press <key>` — keypress (Enter, Tab, Escape, etc.)
- `hover <selector>` — mouseover event

**Observation:**
- `screenshot [--fast] [--format png|jpeg|webp] [--quality 0-100] [--viewport] [path]` — full-page PNG by default (capped at 16384px). `--viewport` for viewport-only. `--fast` = JPEG q70 + optimizeForSpeed + viewport-only (2-4x faster, 3-6x smaller). Returns timing `breakdown` in step NDJSON.
- `snapshot [path]` — list interactive elements with CSS selectors. For element discovery.
- `read [--source extractor] [--no-wait] [path]` — extract page content as markdown. **Content-type sniffing**: if the page's MIME type is structured data (application/json, text/xml, text/plain, text/csv, etc.), bypasses extraction and returns raw content (JSON is pretty-printed). Reports `source: raw` and `content_type` in step output. For HTML pages, uses the extraction cascade: trafilatura (Python-side) → Readability.js+Turndown (browser-side) → innerText. Use `--source trafilatura`, `--source readability`, `--source innertext`, or `--source raw` to force a specific extractor. Logs `source` in step output. **Auto-waits for DOM stability** when the previous verb was a navigation (`goto`, `back`, `forward`) — no explicit `wait` needed. Use `--no-wait` to skip auto-wait.
- `fetch <url> [--source extractor] [path]` — compound verb: `goto` + auto-wait + `read` in one step. The default for research/extraction workflows. Path optional — if omitted, writes to a temp file and reports the path in step output. Passes through `--source` flag to the read cascade.
- `eval <expression>` — run JS, result to stdout
- `eval-to <path> <expression>` — run JS, write result to file (for large data)
- `eval-file <js-path>` — read JS from a file and evaluate. Use for multi-line JS — avoids minification.
- `eval-file-to <out-path> <js-path>` — read JS from file, write result to file

**Network:**
- `capture [--bodies] <path>` — record all network requests during the script to a JSONL file. Place at the start of a script; writes on script exit. Each line: method, URL, status, content-type, headers, timing. `--bodies` opt-in includes response bodies (large). Step NDJSON summary shows request count, resource type breakdown, domains, and non-2xx errors — read the summary before opening the file.

**Emulation:**
- `device <"name"> [--dpr N]` — apply device preset (viewport, DPR, UA, touch, safe area). Available: iPhone 14 Pro, iPhone SE, Pixel 7, iPad Air, iPad Pro 11, Desktop 1080p. `--dpr 1` for smaller screenshots.
- `viewport <width> <height>` — raw dimensions escape hatch (no UA/touch/safe-area)

**Control:**
- `wait <ms>` — sleep
- `wait-for <selector> [timeout_ms]` — wait until selector matches visible element. Default 10s. **Critical for SPAs.**
- `wait-idle [timeout_ms]` — wait until network requests settle (in-flight count at zero for 500ms). Default 30s timeout. **The fix for SPA click-navigation**: after a click triggers a client-side route change, auto-wait doesn't fire — use `wait-idle` instead of guessed `wait` delays. Step NDJSON: `settled_after_ms`, `timed_out`. **Caveat:** sites with analytics beacons, websockets, or long-polling may never settle — use a short timeout (e.g. `wait-idle 5000`) or prefer `wait-for <selector>` when you know what content to expect.
- `wait-navigation` — wait for page load event
- `watch [--fast] [--cooldown <ms>] <path>` — HMR-triggered auto-screenshot. Listens for Vite HMR console messages + DOM mutations. Three debounce layers: JS MutationObserver (150ms clusters rapid DOM changes), Python drain (100ms batches queued events), cooldown (default 1000ms, min interval between captures). Leading + trailing edge: captures immediately on first change, then once more after cooldown to get the final state. Runs until killed. Use with `Bash run_in_background`.
- `assert <expression>` — eval JS, fail script if falsy. Error shows actual value.
- `log <message>` — print to stderr

### Output protocol

- **stderr**: NDJSON per step — `{"i":0,"verb":"goto","ms":342,"url":"https://example.com/","status_code":200}`
- **stdout**: summary — `{"ok":true,"steps":6,"total_ms":443,"files":[{"path":"/tmp/out.png","verb":"screenshot","format":"png","kb":234.5}],"final_url":"https://example.com/"}`
- **Exit code**: 0 success, 1 failure

`files` entries are objects with `path`, `verb`, and verb-specific metadata (screenshot: `format`/`kb`; read/fetch: `source`/`word_count`/`content_type`; snapshot: `element_count`; eval-to: `byte_size`; capture: `requests`/`by_type`/`domains`/`errors`). Read the summary to decide which files to open.

`final_url` is the page's `window.location.href` captured after the last step, before the tab closes. Use it for post-redirect metadata — this is the only moment the URL is available since the tab is destroyed in `cmd_run`'s finally block.

## The scout-then-act pattern

When you don't know the page's selectors:

```bash
# Pass 1: Scout — discover what's on the page
passe run -c 'goto https://unknown-site.com; snapshot /tmp/elements.txt'
```

Read `/tmp/elements.txt`. It shows something like:
```
[0] button "Sign in" css=#sign-in
[1] link "Blog" css=nav > a:nth-of-type(1) href=/blog
[2] input[email] "Email" css=input[name="email"]
[3] button "Reject" css=.cookie-banner > button:nth-of-type(1)
```

```bash
# Pass 2: Act — use discovered selectors
passe run - <<'EOF'
goto https://unknown-site.com
click ".cookie-banner > button:nth-of-type(1)"
type "input[name='email']" "test@example.com"
click "#sign-in"
screenshot /tmp/result.png
EOF
```

Two Bash calls. For simple cases (cookie banners with obvious text), skip the scout and use `click-text "Reject"` directly.

## Authenticated API pattern

Passe runs inside Chrome's authenticated session. For SPAs where `type`/`press Enter` don't trigger the UI, skip the UI and call the API directly via `eval` + `fetch()`:

```bash
passe run - <<'EOF'
goto https://intranet.example.com/search
wait 1000
eval-to /tmp/results.json (async () => { const token = document.querySelector('input[name="csrf"]').value; const resp = await fetch('/api/search', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token }, body: JSON.stringify({ query: 'parental leave' }) }); return JSON.stringify(await resp.json()); })()
EOF
```

The browser has the cookies (including HttpOnly). CSRF tokens come from the DOM. No cookie management or auth plumbing needed — Chrome *is* the authenticated session.

## Known footguns

1. **`fill` vs `type`**: Default to `type` for any SPA. `fill` is a speed optimisation for plain HTML forms only.
2. **`type` on React controlled inputs**: `type` now auto-detects when CDP key events don't take (React controlled components). After typing, it checks the element's value — if it doesn't match, it automatically falls back to `nativeInputValueSetter` + `dispatchEvent('input')`. You'll see `[type] React controlled input detected` on stderr when this happens. No manual workaround needed.
3. **`read` extraction cascade**: **Content-type sniffing runs first** — if `document.contentType` is structured data (JSON, XML, CSV, plain text, YAML), the extraction cascade is bypassed entirely and raw content is returned (JSON is pretty-printed). For HTML pages, trafilatura handles most pages well (articles, dashboards, SPAs). When trafilatura returns None or <10% of page text, it falls through to Readability.js+Turndown, then to innerText. Warnings on stderr when extraction looks incomplete (including when trafilatura import fails or throws). The `source` field in step output tells you which extractor was used (`raw`, `trafilatura`, `readability`, or `innerText`). Shadow DOM content is now flattened before serialization — web components (e.g. MDN's `<mdn-code-example>`) are inlined into the HTML so both extractors can see them. A structural quality gate detects when trafilatura drops tables or code blocks: it counts pipe-table rows and code fences in the output, compares against DOM signals (table data rows, `<pre>` blocks), and falls through to Readability if significant structure was lost (e.g. ISO country codes page: 294 data rows stripped → Readability preserves them). **Thin-read diagnostics**: when extraction returns <200 chars and the page isn't genuinely small, a `thin_read` diagnostic is emitted in step NDJSON with `word_count`, `extracted_chars`, `page_text_chars`, `html_chars`, `title`, and `possible_cause` (one of `auth_wall`, `empty_page`, `js_hydration`, `unknown`). Warning also on stderr. Suppressed for legitimately small pages (high extraction ratio with ≥100 chars of page text). Known weaknesses: (a) pages with cookie banners blocking content, (b) JS animations producing garbage HTML, (c) infinite scroll pages. Use `read --source readability` or `read --source innertext` to bypass the cascade for debugging. Use `--source raw` to force raw passthrough on any page. Use `eval` with `innerText` as a deliberate escape hatch.
3a. **Auto-wait and SPA client-side navigation**: `read` auto-waits for DOM stability after `goto`/`back`/`forward` — no explicit `wait` needed. Uses dual-signal polling (element count + text length). But auto-wait does NOT fire after `click` — SPA client-side route changes (React Router, Next.js) happen via click without a page navigation. For these, use `wait-idle` (waits for network to settle) or `wait-for .new-content-selector` between click and read. `wait-idle` is the better default — it replaces guessed `wait 500`/`wait 1000` delays with a deterministic signal. The `fetch` verb always auto-waits (no `--no-wait` option — use `goto; read --no-wait` for granular control).
4. **Full-page screenshots on infinite scroll**: Capped at 16384px height. Still potentially large.
5. **`click-text` with multiple matches**: Clicks the first visible match. Be specific.
6. **Cookie banner button text**: Don't guess — button labels vary between sites and `click-text` fails on doubled text from icon+label combinations. Always scout with `snapshot` first.
7. **Tab handling**: `passe run` creates and owns its own tab (closed on exit). Atomic commands attach to the first existing tab. If a click opens a *new* browser tab, passe stays on its own — no tab switching.
8. **Script errors are fatal**: No error recovery mid-script. Partial timing data still emitted to stderr.
9. **DOM mutation during TreeWalker**: If using `eval` with `createTreeWalker` to walk and mutate the DOM (e.g. `replaceChild`), the walker loses its position and silently stops after 1-2 nodes. Collect nodes into an array first, then mutate in a second pass.
10. **Multi-line JS in `eval`**: The DSL is line-based — `eval` takes one line. For multi-line JS, use `eval-file <path>` which reads from a file. Don't minify JS to fit on one line.
11. **`eval-file-to` arg order**: `eval-file-to <out-path> <js-path>` — output first, source second. Consistent with `eval-to <path> <expression>` but opposite to Unix `cp src dest` convention.

## Atomic commands

For one-off operations without the script runner:

```bash
passe screenshot /tmp/current-page.png    # Screenshot whatever's loaded
passe eval "document.title"                # Quick JS eval
```

These operate on the current page state — no navigation. Useful for quick checks.

## Development

```bash
# After editing code, reinstall (the --reinstall flag forces wheel rebuild)
uv tool install /Users/modha/Repos/passe --force --reinstall

# Without --reinstall, uv may use a cached wheel with old code
```

## Architecture

Single file: `src/passe/cli.py`. The `CDPClient` class handles WebSocket message routing with future-based responses. `do_*` functions are the action layer. `run_script()` is the execution engine that dispatches verbs to actions.

### Event buffering

`CDPClient.BUFFERED_EVENTS` is a frozenset whitelist of events to buffer when no waiter is registered. Currently only `Page.loadEventFired`. The buffer is `dict[str, dict]` (one entry per method name) — max size equals whitelist size.

When a `wait_for_event` waiter is active, events go directly to the waiter. When a waiter has timed out (stale cancelled future), `_receiver` falls through to the buffer instead of silently dropping the event. This matters for the `click → wait-navigation` pattern where navigation completes between the click and the wait.

`src/passe/_libs.py` holds all JS constants that run inside Chrome. Third-party vendored: Readability.js (Mozilla) and Turndown.js. Our code: `SHADOW_FLATTEN_JS` (serializes outerHTML with shadow DOM inlined) and `EXTRACT_JS` (orchestrates Readability+Turndown). The primary `read` path gets flattened outerHTML from Chrome and runs trafilatura Python-side; the browser-side libs are the fallback.

### Network capture

`CDPClient` has a non-consuming network event collector that runs in `_receiver` before waiter/queue routing. When `enable_network()` is called, `Network.requestWillBeSent`, `responseReceived`, `loadingFinished`, and `loadingFailed` events are correlated by `requestId` into `_network_requests`. The collector doesn't consume events — they still flow to waiters and queues, allowing future features (wait-idle) to coexist on the same event stream.

No external dependencies beyond `websockets`. Everything else runs in Chrome's V8.
