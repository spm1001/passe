---
name: passe
allowed-tools: ["Bash(passe:*)", Read]
description: >
  Orchestrates fast CDP browser automation via line DSL. MANDATORY BEFORE any
  `passe` command — provides verb vocabulary, scout-then-act pattern, and invocation
  conventions that prevent malformed scripts. Triggers on 'passe run',
  'automate the browser', 'screenshot a page', 'interact with a website',
  'scrape this page', 'capture network requests', 'reverse-engineer API',
  'fetch this page', 'check if this page has', 'verify deployment'. (user)
---

# Passe Cookbook

Fast CDP browser automation. One Bash call, one WebSocket, no model round-trips during execution.

## Quick reference

| Need | Command |
|------|---------|
| Read a web page | `passe fetch URL` |
| Screenshot a page | `passe look URL` |
| Verify deployment | `passe check URL --contains TEXT` |
| See what APIs a page calls | `passe capture URL /tmp/reqs.jsonl` |
| Multi-step interaction | `passe run` with heredoc |
| Quick JS on current tab | `passe eval "expression"` |

## DO NOT

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

**Apple Developer docs** auto-detected — fetched from structured JSON endpoint. **Next.js** sites use `__NEXT_DATA__` fast-path. Most pages try HTTP-first before touching Chrome (~87% succeed without a browser).

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

**When to use which:** `snapshot` for CSS selectors you'll click/type into. `ax-tree` for understanding page semantics — what the page *means*, not just what's clickable. `ax-find` for targeted search (e.g. finding all buttons on a cookie banner).

### 4. Dismiss a cookie banner

Never guess button text. Scout first.

```bash
# Option A: ax-find (fastest — finds buttons by role)
passe run - <<'EOF'
goto https://spiegel.de
ax-find button
EOF
# Read output, find the reject/accept button, then:
passe run - <<'EOF'
goto https://spiegel.de
click "#reject-button-selector"
wait 0.5
read /tmp/content.md
EOF

# Option B: snapshot (shows CSS selectors directly)
passe run -c 'goto https://spiegel.de; snapshot /tmp/elements.txt'
# Read elements.txt, find the cookie button's CSS selector, then act
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

```bash
# Navigate the user's visible tab to the login page
passe run --reuse-tab -c 'goto https://accounts.google.com/oauth/...'
# Ask user: "Log in and let me know when you're done"
# Then capture the result
passe run --reuse-tab -c 'eval document.body.innerText'
```

**Warning:** `--reuse-tab` navigates away from whatever the user is looking at. Only use when explicitly co-viewing.

For authenticated APIs, skip the UI — Chrome has the cookies:
```bash
passe run -c 'goto https://intranet.example.com; eval-to /tmp/data.json (async()=>{const r=await fetch("/api/data");return JSON.stringify(await r.json())})()'
```

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

## Verb reference

**Extraction:**
`fetch <url> [--source S] [path]` — goto + auto-wait + read (compound). `extract [--source S] [--no-wait] [path]` — extract current page (`read` is alias). Sources: `trafilatura` (default), `readability`, `innertext`, `raw`.

**Navigation:**
`goto <url>`, `back`, `forward`, `scroll <x> <y>`

**Interaction:**
`click <sel-or-text>`, `type <sel> <text>`, `fill <sel> <val>`, `select <sel> <val>`, `press <key>`, `hover <sel>`, `tap <sel>`, `swipe <sel> <dir> [dist]`

**Observation:**
`screenshot [--fast] [--viewport] [--format F] [--quality N] [path]`, `snapshot [path]`, `eval <expr>`, `eval-to <path> <expr>`, `eval-file <js>`, `eval-file-to <out> <js>`, `ax-tree [--depth N] [--compact]`, `ax-find [--role R] [--name N]`, `ax-node <selector>`

**Network:**
`capture [--bodies] [--filter] <path>`

**Control:**
`wait` (bare=network idle, `<n>`=sleep, `<sel>`=element), `wait-for <sel>`, `wait-idle`, `watch [--fast] [--cooldown N] <path>`, `assert <expr>`, `log <msg>`, `frame <url-pattern>`, `frame top`, `bring-to-front`

**Emulation:**
`device <name> [--dpr N]`, `viewport <w> <h>`

## Output protocol

**stderr:** NDJSON per step — `{"i":0,"verb":"goto","ms":342}`
**stdout:** summary — `{"ok":true,"steps":6,"total_ms":443,"files":[...]}`
**Exit:** 0=success, 1=failure

## Content extraction cascade

1. Content-type sniffing (JSON/XML/CSV → raw passthrough)
2. Apple docs → structured JSON endpoint
3. trafilatura (Python-side, handles most pages)
4. Readability.js + Turndown (browser-side fallback)
5. innerText (last resort)

Shadow DOM flattened before extraction. `source` field in output tells you which extractor was used.

## Development

```bash
uv tool install ~/Repos/batterie/passe --force --reinstall   # --reinstall forces wheel rebuild
uv run --with pytest --with pytest-asyncio python -m pytest tests/ -v
```
