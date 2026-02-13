---
name: passe
description: >
  Orchestrates fast CDP browser automation via line DSL. Invoke BEFORE any `passe`
  command — provides verb vocabulary, scout-then-act pattern, and invocation conventions
  that prevent malformed scripts and wasted round-trips. Triggers on 'passe run',
  'automate the browser', 'screenshot a page', 'interact with a website',
  'click a button on', 'fill a form on', 'scrape this page', 'test this page'.
  Not for content fetching (use mise fetch). (user)
---

# passe — fast CDP browser automation

Single Bash call, single WebSocket, arbitrary action sequences. 100x faster than MCP round-trips.

## When to use

| Need | Tool |
|------|------|
| Screenshot, interact, test a page | **passe** |
| Extract content with tables/code blocks intact | **passe** `read` (Readability preserves DOM structure) |
| Extract article/blog content (cleaner, smaller) | `mise fetch` (trafilatura, better boilerplate stripping) |
| Full test suites with fixtures | Playwright directly |

**`read` vs `mise fetch` for content extraction:** `mise fetch` is faster and produces cleaner output for articles and blog posts. But `passe read` preserves tables and code blocks more faithfully because Readability.js works from the rendered DOM. For technical docs, `passe read` is more reliable.

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
- `type <selector> <text>` — character-by-character via CDP. **Use for SPAs.**
- `fill <selector> <value>` — set value directly. Fast but may skip React/Vue reactivity.
- `select <selector> <value>` — dropdown
- `press <key>` — Enter, Tab, Escape, etc.
- `hover <selector>` — mouseover

**Observation:**
- `screenshot [path]` — full-page PNG (capped at 16384px). `--viewport` for viewport-only.
- `snapshot [path]` — list interactive elements with CSS selectors. For discovery.
- `read [path]` — extract page as markdown (Readability.js + Turndown.js). **Articles/blogs only** — see Content Extraction below.
- `eval <expression>` — run JS, result in NDJSON step
- `eval-to <path> <expression>` — run JS, write result to file

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

`read` uses Readability.js — designed for articles. It **fails silently** on three page types:

| Page type | `read` produces | Fix |
|-----------|----------------|-----|
| **Cookie banner visible** | Just the banner text | Dismiss banner first (scout → click) |
| **Animated/dynamic content** | Massive garbage (saw 3.9MB from a typewriter animation) | Use `eval` with `innerText` |
| **SPAs with tabs/panels** | Nav chrome, not content | Click the right tab, then `eval` the panel |

**Decision tree:**

1. **Article or blog post?** → `read` (Readability's sweet spot)
2. **SPA, dashboard, or interactive page?** → `eval` with selector chain
3. **Cookie banner present?** → scout + dismiss first, then decide read vs eval
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

## Anti-patterns

- **`fill` vs `type`**: Default to `type` for SPAs. `fill` is for plain HTML forms only.
- **`read` on everything**: `read` is for articles. SPAs, dashboards, animated pages → `eval`.
- **Guessing cookie button text**: `click-text "Reject"` fails more often than it works. Scout first.
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

# Run tests:
uv run --with pytest pytest tests/ -v
```
