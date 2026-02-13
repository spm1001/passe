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
| Extract content with tables/code blocks intact | **passe** `read` (Readability preserves DOM structure) |
| Extract article/blog content (cleaner, smaller) | `mise fetch` (trafilatura, better boilerplate stripping) |
| Browse with the default Chrome profile interactively | `webctl` |
| Full Playwright test suites with fixtures and assertions | Playwright directly |

Passe is for **fast, scriptable, single-connection browser automation from the CLI**. Also good for content extraction where DOM fidelity matters — `read` outperforms `mise fetch` on technical docs with tables and code examples because Readability.js works from the rendered DOM. For blog posts and articles where boilerplate stripping matters more, mise is cleaner.

## The Chrome connection model

**This is the single most important thing to understand.**

Passe connects to Chrome on port 9222. Sameer's daily driver Chrome runs with `--remote-debugging-port=9222` — so passe gets his full auth state, cookies, SSO sessions.

If Chrome isn't running, passe auto-starts one with `--user-data-dir=~/.chrome-debug`. That's a **bare profile** — no auth, no cookies, no extensions. This is fine for testing public pages but won't have any login sessions.

**Never assume you have auth unless you've confirmed Chrome is Sameer's daily driver instance.**

### Tab isolation

`passe run` creates its own tab, runs the script there, and closes it on exit. Your existing tabs are never touched. Atomic commands (`passe screenshot`, `passe eval`) attach to the first existing tab — they observe the current page, they don't navigate.

## The DSL

Passe has a line-based scripting language. One verb per line, parsed with `shlex.split()`.

### Invocation patterns

```bash
# Short scripts (≤4 verbs): inline with -c, semicolons as separators
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
- `read [path]` — extract page content as markdown (Readability.js + Turndown.js). Best for articles/blogs. Falls back to innerText on SPAs.
- `eval <expression>` — run JS, result to stdout
- `eval-to <path> <expression>` — run JS, write result to file (for large data)

**Control:**
- `wait <ms>` — sleep
- `wait-for <selector> [timeout_ms]` — wait until selector matches visible element. Default 10s. **Critical for SPAs.**
- `wait-navigation` — wait for page load event
- `viewport <width> <height>` — set viewport size (for responsive testing)
- `assert <expression>` — eval JS, fail script if falsy. Error shows actual value.
- `log <message>` — print to stderr

### Output protocol

- **stderr**: NDJSON per step — `{"i":0,"verb":"goto","ms":342}`
- **stdout**: summary — `{"ok":true,"steps":6,"total_ms":443,"files":["/tmp/out.png"]}`
- **Exit code**: 0 success, 1 failure

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

## Known footguns

1. **`fill` vs `type`**: Default to `type` for any SPA. `fill` is a speed optimisation for plain HTML forms only.
2. **`read` failure modes**: Readability.js works well on articles/blogs and technical docs with tables, but fails on: (a) pages with cookie banners (returns just the banner text), (b) pages with JS animations (saw 3.9MB of garbage from a typewriter effect), (c) SPAs with tab/panel navigation (returns nav chrome). Passe now warns on stderr when extraction looks incomplete (<10% of page text) or falls back to innerText. Use `eval` with `innerText` as the deliberate fallback when `read` warns.
3. **Full-page screenshots on infinite scroll**: Capped at 16384px height. Still potentially large.
4. **`click-text` with multiple matches**: Clicks the first visible match. Be specific.
5. **Cookie banner button text**: Don't guess — button labels vary between sites and `click-text` fails on doubled text from icon+label combinations. Always scout with `snapshot` first.
6. **Tab handling**: `passe run` creates and owns its own tab (closed on exit). Atomic commands attach to the first existing tab. If a click opens a *new* browser tab, passe stays on its own — no tab switching.
7. **Script errors are fatal**: No error recovery mid-script. Partial timing data still emitted to stderr.

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

`src/passe/_libs.py` bundles Readability.js and Turndown.js as string constants, injected into the browser via `Runtime.evaluate` for the `read` verb.

No external dependencies beyond `websockets`. Everything else runs in Chrome's V8.
