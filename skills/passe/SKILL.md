---
name: passe
allowed-tools: ["Bash(passe:*)", Read]
description: >
  Orchestrates browser automation — read pages, take screenshots, fill
  forms, capture network traffic, and verify deployments via Chrome CDP.
  MANDATORY BEFORE any `passe` command — 12-recipe cookbook covering
  scout-then-act pattern, verb conventions, and common pitfalls that
  prevent malformed scripts.
  Triggers on 'passe run', 'automate the browser', 'screenshot a page',
  'scrape this page', 'fetch this page', 'open this URL in Chrome',
  'what does this page look like on mobile', 'fill out this form',
  'capture network requests', 'reverse-engineer API', 'check if this
  page has', 'verify deployment', 'dismiss cookie banner',
  'monitor network traffic'. (user)
---

# Passe Cookbook

Fast CDP browser automation. One Bash call, one WebSocket, no model round-trips during execution.

## When to Use

Any task that needs a real browser: reading JavaScript-rendered pages, taking screenshots, filling forms, dismissing overlays, reverse-engineering APIs via network capture, verifying deployments, mobile device emulation.

## When NOT to Use

- **Google Workspace content** — use `mise fetch` for Drive, Gmail, Sheets
- **Static pages with no JS** — `passe fetch` tries HTTP-first automatically, but plain `curl` may suffice
- **Long-running browser sessions** — passe runs scripts, not interactive sessions

## Quick reference

| Need | Command |
|------|---------|
| Read a web page | `passe fetch URL` |
| Screenshot a page | `passe look URL` |
| Verify deployment | `passe check URL --contains TEXT` |
| See what APIs a page calls | `passe capture URL /tmp/reqs.jsonl` |
| Multi-step interaction | `passe run` with heredoc |
| Quick JS on current tab | `passe eval "expression"` |

## Anti-Patterns

1. **DO NOT run `passe eval` or `passe screenshot` expecting to see your `passe run` page.** The tab is gone. Put everything in one script.
2. **DO NOT add `wait` before `extract` after a `goto`.** Auto-wait handles this. Use `fetch` for the common case.
3. **DO NOT use passe for Google Workspace content.** Use `mise fetch` for Drive, Gmail, Sheets.
4. **DO NOT guess cookie button text.** Scout first — button labels vary wildly between sites.
5. **DO NOT write long inline one-liners.** Use heredoc for 5+ verbs.

---

## Recipes

### 1. Read a web page

The most common task. `fetch` handles goto + auto-wait + extraction in one step.

```bash
# Short content inlined in JSON output (no file round-trip)
passe fetch https://paulgraham.com/superlinear.html

# Long content to file
passe fetch https://react.dev/reference/react/useState /tmp/content.md
```

**Apple Developer docs** auto-detected — fetched from structured JSON endpoint. **Next.js** sites use `__NEXT_DATA__` fast-path. Most pages try HTTP-first before touching Chrome.

**If extraction looks thin:** check the `source` field in output. Try `--source readability` or `--source innertext` to bypass trafilatura. If a cookie banner is blocking content, dismiss it first (recipe 4).

### 2. Screenshot a page

```bash
# Quick look — always JPEG, good for Claude's eyes
passe look https://news.ycombinator.com

# Full-page PNG (large, high fidelity)
passe run -c 'goto https://example.com; screenshot /tmp/out.png'

# Fast iteration (JPEG, viewport-only, 2-4x faster)
passe run -c 'goto https://example.com; screenshot --fast /tmp/out.jpg'
```

**Mobile device emulation:**
```bash
passe --device "iPhone 14 Pro" --dpr 1 look https://example.com
```

Available presets: iPhone 14 Pro, iPhone SE, Pixel 7, iPad Air, iPad Pro 11, Desktop 1080p.

### 3. Understand page structure

Two complementary tools: `snapshot` lists interactive elements with CSS selectors. `ax-tree` shows the browser's semantic accessibility tree.

```bash
# Interactive elements (buttons, links, inputs) with CSS selectors
passe run -c 'goto https://site.com; snapshot /tmp/elements.txt'
# Shows: [0] button "Sign in" css=#sign-in

# Full semantic tree — roles, names, hierarchy
passe run -c 'goto https://site.com; ax-tree'
# Shows: RootWebArea > heading "Dashboard" > navigation > link "Settings"

# Limit tree depth on heavy pages
passe run -c 'goto https://site.com; ax-tree --depth 3'

# Semantic skeleton only — strips StaticText/InlineTextBox noise
passe run -c 'goto https://site.com; ax-tree --compact'

# Find specific elements by role or name
passe run -c 'goto https://site.com; ax-find button'
passe run -c 'goto https://site.com; ax-find --role link --name Settings'

# Inspect a specific element's accessibility subtree
passe run -c 'goto https://site.com; ax-node nav'
```

**Quick checks — no eval needed:**
```bash
# Does an element exist?
passe run --reuse-tab -c 'exists "#login-btn"'

# How many matches?
passe run --reuse-tab -c 'count ".search-result"'

# Is it visible (not hidden, has dimensions)?
passe run --reuse-tab -c 'visible ".error-banner"'

# Save page as PDF
passe run --reuse-tab -c 'pdf /tmp/page.pdf'
```

`exists`, `count`, `visible` return their result directly in the step JSON — no eval wrappers needed. `pdf` writes via `Page.printToPDF` with backgrounds and CSS page sizes.

**When to use which:** `snapshot` for CSS selectors you'll click/type into. `ax-tree` for understanding page semantics — what the page *means*, not just what's clickable. `ax-find` for targeted search (e.g. finding all buttons on a cookie banner). `exists`/`count`/`visible` for quick assertions without writing JS.

### 4. Dismiss a cookie banner

Never guess button text. Scout first.

**Step 1: Scout** — find the button:
```bash
passe run -c 'goto https://spiegel.de; ax-find button'
```

**Step 2: Act** — click it (in a separate Bash call):
```bash
passe run - <<'EOF'
goto https://spiegel.de
click "#reject-button-selector"
wait 0.5
extract /tmp/content.md
EOF
```

Alternative: `snapshot` gives CSS selectors directly:
```bash
passe run -c 'goto https://spiegel.de; snapshot /tmp/elements.txt'
```

Two Bash calls total. `ax-find button` is often faster because it returns all buttons with their accessible names — you can identify "Reject All" vs "Accept" immediately.

### 5. Fill out a form

Scout unknown pages first, then interact. Default to `type` (not `fill`) for SPAs.

```bash
passe run - <<'EOF'
goto https://example.com/signup
type "#email" "test@example.com"
type "#password" "hunter2"
press Enter
wait .dashboard
screenshot /tmp/result.png
EOF
```

**`type` vs `fill`:** `type` sends character-by-character via CDP — works with React, Vue, plain HTML. Auto-detects controlled inputs. `fill` sets the value directly — faster but may skip framework reactivity. Default to `type`.

**`click` smart dispatch:** CSS selectors (`. # [ : > ~ +`) → querySelector. Plain text → find by visible text. `click "Submit"` for text, `click ".btn-primary"` for CSS.

### 6. Reverse-engineer an API

```bash
# Record all network traffic during a flow
passe run - <<'EOF'
capture --bodies /tmp/reqs.jsonl
goto https://spa.example.com
click "Search"
type "#query" "parental leave"
press Enter
wait 2
EOF
```

Stderr summary shows request count by type and domains. Then:

```bash
# Find the API calls
passe log tail --file /tmp/reqs.jsonl --method POST
```

**The pattern:** capture → identify API endpoint → call it directly via `eval` + `fetch()` using Chrome's authenticated session. Skip the UI entirely.

### 7. Verify a deployment

```bash
# Quick check (exit 0/1)
passe check https://your-site.com --contains "Dashboard"

# With screenshot proof
passe check https://your-site.com --contains "Welcome" --screenshot /tmp/proof.jpg

# Multi-assertion smoke test
passe run - <<'EOF'
goto https://your-site.com
assert document.title.includes("Expected")
assert document.querySelectorAll("nav a").length > 0
assert !document.querySelector(".error-banner")
screenshot --fast /tmp/healthy.jpg
EOF
```

### 8. Mobile development loop

Device emulation + watch verb = Claude sees mobile UI changes live.

```bash
# One-shot mobile screenshot
passe --device "iPhone 14 Pro" --dpr 1 \
  run -c 'goto http://localhost:5173; screenshot --fast /tmp/mobile.jpg'

# Continuous: auto-screenshot on every Vite HMR update
passe --device "iPhone 14 Pro" --dpr 1 \
  run -c 'goto http://localhost:5173; watch --fast /tmp/mobile.jpg'
```

Start `watch` with `Bash run_in_background`. Read `/tmp/mobile.jpg` after each edit.

### 9. Handle auth pages

#### Manual login flow

When a page requires user login, navigate their visible tab and wait:

```bash
# Navigate the user's visible tab to the login page
passe run --reuse-tab -c 'goto https://accounts.google.com/oauth/...'
# Ask user: "Log in and let me know when you're done"
# Then capture the result
passe run --reuse-tab -c 'eval document.body.innerText'
```

**Warning:** `--reuse-tab` navigates away from whatever the user is looking at. Only use when explicitly co-viewing.

#### Authenticated API shortcut

When Chrome already has cookies, skip the login UI — use `capture` + `eval` to call APIs directly with Chrome's session. See recipe 6 for the full pattern.

### 10. Work inside an iframe

```bash
passe run - <<'EOF'
goto https://page-with-iframe.com
wait 2
frame accounts.google.com
eval document.title
ax-tree --depth 3
frame top
EOF
```

`frame` matches by URL substring. Only works with cross-origin iframes (OOPiF). Same-origin iframes: use `eval` with `querySelector('iframe').contentDocument`. `screenshot` always captures the parent page (Chrome limitation).

### 11. Connection troubleshooting

```bash
# First: check connection
passe status

# If remote Chrome unreachable, use local headless
passe --cdp localhost:9222 look https://example.com
```

When Chrome is unreachable, passe emits `[passe:connection]` diagnostics with `endpoint`, `reason`, and `alternatives`. Common causes: Mac sleeping, stale Chrome process on port 9222, wrong `PASSE_CDP` value.

### 12. Monitor Chrome network traffic

```bash
# Start background daemon (captures all tabs)
passe log start

# Query recent requests
passe log tail
passe log list --filter api.example.com --method POST

# Stop
passe log stop
```

**One-shot vs continuous:** `passe capture URL /tmp/out.jsonl` records one page visit. `passe log start` captures everything Chrome does indefinitely.

---

## Common mistakes

| Mistake | Fix |
|---------|-----|
| `passe eval "..."` after `passe run` | Tab is gone. Put everything in one `passe run` script. |
| `goto URL; wait 1; extract` | `extract` auto-waits after navigation. Just `goto; extract` or use `fetch`. |
| `scroll down 500` | Pixel coordinates: `scroll 0 500` |
| "Passe is broken" on connection refused | Run `passe status`. Diagnose the connection, not the tool. |
| Chasing "doubled output" | Claude Code bash quirk on non-zero exit. Check the error, ignore the duplication. |
| PNG for inner-loop iteration | Use `screenshot --fast` (JPEG viewport-only, 2-4x faster). |
| Monster inline one-liners | Use heredoc for 5+ verbs. |

---

## Tab lifecycle

`passe run` creates a fresh tab, runs your script, closes on success. **On failure, tab kept open** with 30s auto-close — user interaction cancels timer. Stderr shows `passe run --reuse-tab -c "..."` to resume.

| Flag | Behavior |
|------|----------|
| (default) | Create → close on success, keep on failure |
| `--keep-tab` | Create → leave open permanently |
| `--flash [secs]` | Create → auto-close after timeout |
| `--reuse-tab` | Attach to existing visible tab |
| `--no-keep-on-fail` | Force close on failure |

---

## Invocation

```bash
# Short (≤4 verbs): inline
passe run -c 'goto https://example.com; screenshot /tmp/out.png'

# Long (5+ verbs): heredoc
passe run - <<'EOF'
goto https://example.com
click "Accept"
wait 0.5
screenshot /tmp/out.png
EOF

# Reusable: .passe files
passe run tests/checkout.passe

# Global flags:
passe --cdp http://host:9222 run -c '...'
passe --device "iPhone 14 Pro" run -c '...'
passe run --foreground -c '...'
```

---

## Reference

Read when you need a verb not covered in the recipes above, or need output format details.

- Verb list: `references/verbs.md`
- Output protocol and extraction cascade: `references/internals.md`
