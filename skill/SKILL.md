---
name: passe
description: >
  Orchestrates fast CDP browser automation via line DSL. Invoke BEFORE any `passe`
  command — provides verb vocabulary, scout-then-act pattern, and invocation conventions
  that prevent malformed scripts and wasted round-trips. Triggers on 'passe run',
  'automate the browser', 'screenshot a page', 'interact with a website',
  'click a button on', 'fill a form on', 'scrape this page', 'test this page'.
  Not for content fetching (use mise fetch) or authenticated browsing (use webctl). (user)
---

# passe — fast CDP browser automation

Single Bash call, single WebSocket, arbitrary action sequences. 100x faster than MCP round-trips.

## When to use

| Need | Tool |
|------|------|
| Screenshot, interact, test a page | **passe** |
| Extract article content from a URL | `mise fetch` |
| Browse with SSO/auth profile interactively | `webctl` |
| Full test suites with fixtures | Playwright directly |

## When not to use

- **Content extraction from a URL you haven't visited** — use `mise fetch` (server-side trafilatura)
- **Browsing that needs SSO/cookies from the user's profile** — use `webctl` (persistent sessions)
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
- `click-text <"label">` — find by visible text, click. Great for cookie banners.
- `click-if <selector>` — click if exists, silently continue if not
- `type <selector> <text>` — character-by-character via CDP. **Use for SPAs.**
- `fill <selector> <value>` — set value directly. Fast but may skip React/Vue reactivity.
- `select <selector> <value>` — dropdown
- `press <key>` — Enter, Tab, Escape, etc.
- `hover <selector>` — mouseover

**Observation:**
- `screenshot [path]` — full-page PNG (capped at 16384px). `--viewport` for viewport-only.
- `snapshot [path]` — list interactive elements with CSS selectors. For discovery.
- `read [path]` — extract page content as markdown (Readability.js + Turndown.js)
- `eval <expression>` — run JS, result in NDJSON step
- `eval-to <path> <expression>` — run JS, write result to file

**Control:**
- `wait <ms>`, `wait-for <selector> [timeout_ms]`, `wait-navigation`
- `viewport <width> <height>` — for responsive testing
- `assert <expression>` — fail script if falsy
- `log <message>` — print to stderr

## Output protocol

**stderr:** NDJSON per step — `{"i":0,"verb":"goto","ms":342}`
**stdout:** summary — `{"ok":true,"steps":6,"total_ms":443,"files":["/tmp/out.png"]}`
**Exit code:** 0 success, 1 failure

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

Two Bash calls total. For obvious text (cookie banners), skip the scout: `click-text "Reject"`.

## Anti-patterns

- **`fill` vs `type`**: Default to `type` for SPAs. `fill` is a speed optimisation for plain HTML forms only.
- **`read` on non-article pages**: Returns garbage on dashboards. Use `eval` or `snapshot` instead.
- **`click-text` with multiple matches**: Clicks first visible match. Be specific.
- **Tab handling**: Passe attaches to the first tab. No tab switching.
- **Script errors are fatal**: No mid-script recovery. Partial timing still emitted to stderr.

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
```
