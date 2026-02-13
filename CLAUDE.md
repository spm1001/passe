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
| Extract Workspace content (Drive docs, Gmail) | `mise fetch` |
| Browse with the default Chrome profile interactively | `webctl` |
| Full Playwright test suites with fixtures and assertions | Playwright directly |

Passe is for **fast, scriptable, single-connection browser automation from the CLI**. The `read` verb extracts clean markdown from any page type — it gets the rendered HTML from Chrome, runs trafilatura Python-side for extraction, and falls back to Readability.js+Turndown if trafilatura can't handle it. Use `mise fetch` for Google Workspace content (Drive, Gmail).

## The Chrome connection model

**This is the single most important thing to understand.**

Passe connects to Chrome on port 9222. Sameer's daily driver Chrome runs with `--remote-debugging-port=9222` — so passe gets his full auth state, cookies, SSO sessions.

If Chrome isn't running, passe auto-starts one with `--user-data-dir=~/.chrome-debug`. That's a **bare profile** — no auth, no cookies, no extensions. This is fine for testing public pages but won't have any login sessions.

**Never assume you have auth unless you've confirmed Chrome is Sameer's daily driver instance.**

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

### Verb reference

**Navigation:**
- `goto <url>` — navigate and wait for load
- `back` / `forward` — browser history
- `scroll <x> <y>` — window.scrollTo

**Interaction:**
- `click <selector>` — CSS selector click
- `click-text <"label">` — find by text content, click. Great for cookie banners: `click-text "Reject"`
- `click-if <selector>` — click if exists, silently continue if not. For optional elements.
- `type <selector> <text>` — character-by-character typing. **Use this for SPAs** (React, Vue, etc.)
- `fill <selector> <value>` — set value directly. Faster but may not trigger framework reactivity. Use `type` if unsure.
- `select <selector> <value>` — dropdown
- `press <key>` — keypress (Enter, Tab, Escape, etc.)
- `hover <selector>` — mouseover event

**Observation:**
- `screenshot [path]` — full-page PNG (entire scrollable document, not just viewport). Use `--viewport` for viewport-only.
- `snapshot [path]` — list interactive elements with CSS selectors. For element discovery.
- `read [path]` — extract page content as markdown. Cascade: trafilatura (Python-side, handles any page type) → Readability.js+Turndown (browser-side) → innerText. Logs `source` in step output.
- `eval <expression>` — run JS, result to stdout
- `eval-to <path> <expression>` — run JS, write result to file (for large data)
- `eval-file <js-path>` — read JS from a file and evaluate. Use for multi-line JS — avoids minification.
- `eval-file-to <out-path> <js-path>` — read JS from file, write result to file

**Control:**
- `wait <ms>` — sleep
- `wait-for <selector> [timeout_ms]` — wait until selector matches visible element. Default 10s. **Critical for SPAs.**
- `wait-navigation` — wait for page load event
- `viewport <width> <height>` — set viewport size (for responsive testing)
- `assert <expression>` — eval JS, fail script if falsy. Error shows actual value.
- `log <message>` — print to stderr

### Output protocol

- **stderr**: NDJSON per step — `{"i":0,"verb":"goto","ms":342}`
- **stdout**: summary — `{"ok":true,"steps":6,"total_ms":443,"files":["/tmp/out.png"],"final_url":"https://example.com/"}`
- **Exit code**: 0 success, 1 failure

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
2. **`type` on React controlled inputs**: `type` dispatches CDP key events, but React controlled components may ignore them — the input stays empty. Workaround: set value via JS with the native setter to trigger React's synthetic event system: `eval var el = document.querySelector('input'); var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; setter.call(el, 'text'); el.dispatchEvent(new Event('input', { bubbles: true }));`
3. **`read` extraction cascade**: Trafilatura handles most pages well (articles, dashboards, SPAs). When trafilatura returns None or <10% of page text, it falls through to Readability.js+Turndown, then to innerText. Warnings on stderr when extraction looks incomplete (including when trafilatura import fails or throws). The `source` field in step output tells you which extractor was used (`trafilatura`, `readability`, or `innerText`). Shadow DOM content is now flattened before serialization — web components (e.g. MDN's `<mdn-code-example>`) are inlined into the HTML so both extractors can see them. Known weaknesses: (a) pages with cookie banners blocking content, (b) JS animations producing garbage HTML, (c) infinite scroll pages, (d) **large data tables may be stripped** — trafilatura's content heuristic can classify big tables as boilerplate even with `include_tables=True` (passe-bosevu tracks the fix), (e) **extraction timing matters** — the HTML captures whatever the DOM contains at that moment; slow-hydrating SPAs need adequate `wait` before `read`. Use `eval` with `innerText` as a deliberate escape hatch.
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

`src/passe/_libs.py` bundles Readability.js and Turndown.js as string constants, used as the fallback extraction path when trafilatura can't handle a page. The primary `read` path gets outerHTML from Chrome and runs trafilatura Python-side.

No external dependencies beyond `websockets`. Everything else runs in Chrome's V8.
