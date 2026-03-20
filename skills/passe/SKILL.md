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

# passe — fast CDP browser automation

Single Bash call, single WebSocket, arbitrary action sequences. 100x faster than MCP round-trips.

## When to use

| Need | Tool |
|------|------|
| Quick visual check of a page | **`passe look URL`** — goto + fast screenshot in one call |
| Verify a page has expected content | **`passe check URL --contains TEXT`** — deploy verification |
| See what API calls a page makes | **`passe capture URL path`** — goto + wait + network recording |
| Extract content from any web page | **`passe fetch URL`** — goto + auto-wait + read |
| Screenshot, interact, multi-step flows | **`passe run`** — full DSL scripting |
| Extract Google Workspace content (Drive, Gmail) | `mise fetch` |
| Full test suites with fixtures | Playwright directly |

**Passe owns web, mise owns Workspace — no overlap.** `passe read` uses trafilatura (Python-side) as the primary extractor for any page type, falling back to Readability.js+Turndown (browser-side) if trafilatura returns too little. Shadow DOM content is flattened before extraction. **Apple Developer Documentation** is auto-detected and fetched from the structured JSON endpoint (`source: apple-json`) — no need to use the JSON URL manually.

## When not to use

- **Complex test frameworks with fixtures and assertions** — use Playwright directly

## Common Claude mistakes

These are the most frequent errors from real passe usage across ~455 invocations. Read before writing any passe command.

| Mistake | Why it's wrong | Do this instead |
|---------|---------------|-----------------|
| `passe eval "document.title"` after `passe run` | `run` creates a tab and **closes it on success** (on failure it's kept for 30s). `eval` attaches to the first *existing* tab — which is whatever Sameer has open, not your page. | Put all verbs in one `passe run` script. Use `eval` inside the script, or use `--keep-tab` / `--flash` if you need the tab to survive. |
| `goto URL; wait 1; extract` | `extract` **auto-waits** after navigation verbs. The explicit `wait` is wasted time. | `goto URL; extract` or just `fetch URL` (one verb). |
| `goto URL; extract /tmp/out.md` instead of `fetch` | The `fetch` verb does goto + auto-wait + extract in one step and is the ergonomic default. | `passe run -c 'fetch URL /tmp/out.md'` or `passe fetch URL` (top-level subcommand). |
| Using passe for Google Drive/Gmail content | Passe opens a browser tab. Workspace content needs API access. | Use `mise fetch` for Drive docs, Gmail, Sheets. |
| `passe run -c 'goto URL; click sel; type sel text; wait 0.5; screenshot /tmp/out.png; read /tmp/content.md'` | Monster inline one-liners are unreadable and error-prone. The CLI warns at >4 verbs or >200 chars. | Use heredoc for 5+ verbs. |
| Chasing "doubled output" from passe | This is a Claude Code Bash tool quirk — non-zero exit codes replay output. Not a passe bug. | Check the exit code. If passe failed, read the error. Don't debug the duplication. |
| `scroll down 500` | Passe uses `scroll <x> <y>` (pixel coordinates), not natural language directions. | `scroll 0 500` |

## DO NOT

1. **DO NOT run `passe eval` or `passe screenshot` expecting to see your `passe run` page.** The tab is gone. Put everything in one script.
2. **DO NOT add `wait` before `extract` after a `goto`.** Auto-wait handles this. Use `fetch` for the common case.
3. **DO NOT use passe for Google Workspace content.** Use `mise fetch` for Drive, Gmail, Sheets.

## Tab lifecycle (30 words)

`passe run` creates a fresh tab, runs your script, and destroys the tab on success. **On failure, the tab is kept open** with a 30s auto-close timer — user interaction (click/keypress/scroll) cancels the timer so the page stays for debugging. Stderr shows `passe run --reuse-tab -c "..."` to resume. To keep the tab permanently: `--keep-tab`. To keep with auto-close: `--flash [secs]` (default 30s). To reuse an existing tab: `--reuse-tab`. To force cleanup on failure: `--no-keep-on-fail`.

## Chrome connection

Passe connects to Chrome on port 9222. Two modes:

| Machine | Chrome | Auth state | Use for |
|---------|--------|-----------|---------|
| **Mac** (daily driver) | Chrome Passe with `--remote-debugging-port=9222` | Full cookies, SSO | Authenticated browsing, OAuth flows |
| **Kube/remote** | Headless Chromium (systemd) on `localhost:9222` | Bare profile | Dev testing, screenshots, device emulation |

Use `--cdp http://host:9222` to target a specific Chrome instance per-invocation (overrides `PASSE_CDP` env var). Default: localhost:9222.

**Kube → Mac connection:** Mac exposes Chrome Passe via `tailscale serve --bg --tcp 9222 tcp://localhost:9222`. Kube has `PASSE_CDP=http://<mac-tailscale-ip>:9222` in `.bashrc`. Passe auto-rewrites WebSocket URLs. **If it fails:** check for stale Chrome processes on Mac (`lsof -i :9222`) — old PIDs hogging port 9222 is the most common cause.

## Invocation

```bash
# Short scripts (≤4 verbs): inline
passe run -c 'goto https://example.com; screenshot /tmp/out.png'

# Longer scripts (5+ verbs): heredoc
passe run - <<'EOF'
goto https://example.com
click "Accept Cookies"
wait 0.5
type "#search" "query"
press Enter
wait .results
screenshot /tmp/results.png
EOF

# Reusable: .passe files
passe run tests/checkout.passe

# Global flags (apply to any subcommand):
passe --cdp http://host:9222 run -c '...'              # Target specific Chrome
passe --device "iPhone 14 Pro" run -c '...'             # Device emulation preset
passe --device "iPhone 14 Pro" --dpr 1 run -c '...'     # 1x DPR (smaller screenshots)
passe run --foreground -c '...'                         # Tab starts visible (jsaction sites, OAuth)
```

Never generate long inline one-liners. Use heredoc for 5+ verbs.

## Verb reference

**Extraction (start here for content):**
- `fetch <url> [--source extractor] [path]` — **compound verb: goto + auto-wait + read**. The default for research/extraction. Path optional (auto temp file if omitted). Short content (<2000 words) is inlined in stdout JSON when no path given — no file round-trip needed. Also available as `passe fetch URL` top-level subcommand.

**Navigation:** `goto <url>` — raises on navigation failure (DNS, refused, chrome-error://). Step NDJSON: `url`, `status_code`. `back`, `forward` (step NDJSON: `url`). `scroll <x> <y>` (rarely needed — most verbs work regardless of scroll position)

**Interaction:**
- `click <selector-or-text>` — smart dispatch: CSS (`. # [ : > ~ +`) → querySelector; plain text → find by visible text content. `click "Reject"` for text, `click ".btn"` for CSS.
- `type <selector> <text>` — character-by-character via CDP. **Use for SPAs.** Auto-detects React controlled inputs and falls back to nativeInputValueSetter + synthetic events + 100ms reconciliation delay. `press Enter` after `type` works correctly on React/Streamlit.
- `fill <selector> <value>` — set value directly. Fast but may skip React/Vue reactivity.
- `select <selector> <value>` — dropdown
- `press <key>` — Enter, Tab, Escape, etc.
- `hover <selector>` — mouseover
- `tap <selector>` — touch event (touchStart + touchEnd) for mobile UI
- `swipe <selector> <direction> [distance]` — swipe gesture (left/right/up/down, default 200px)

**Observation:**
- `screenshot [--fast] [--no-fast] [--format png|jpeg|webp] [--quality 0-100] [--viewport] [path]` — full-page PNG by default (capped at 16384px). `--viewport` for viewport-only. **`--fast`** shorthand: JPEG q70 + `optimizeForSpeed` + viewport-only — 2-4x faster, 3-6x smaller. Use for inner-loop iteration. **`PASSE_SCREENSHOT_FAST` env var** defaults all screenshots to `--fast`; override with `--no-fast` when you need full-page PNG fidelity. Returns timing breakdown in step NDJSON (`capture_ms`, `decode_ms`, `write_ms`, `bytes`).
- `snapshot [path]` — list interactive elements with CSS selectors. For discovery.
- `extract [--source extractor] [--no-wait] [path]` — extract page content as markdown. (`read` still works as alias.) **Content-type sniffing**: JSON/XML/CSV/plain text pages bypass extraction and return raw content (JSON pretty-printed, `source: raw`). **Apple docs** (`developer.apple.com/documentation/*`) auto-detected → structured JSON endpoint (`source: apple-json`). HTML pages use cascade: trafilatura → Readability.js+Turndown → innerText. **Thin-read diagnostics**: if extraction is <200 chars, emits `thin_read` in step NDJSON with `possible_cause` (auth_wall/js_hydration/empty_page/unknown) and page metadata. Use `--source raw|trafilatura|readability|innertext` to force. **Auto-waits** after navigation verbs. Use `--no-wait` to skip.
- `eval <expression>` — run JS, result in NDJSON step
- `eval-to <path> <expression>` — run JS, write result to file
- `eval-file <js-path>` — read JS from a file and evaluate. **Use for multi-line JS** — avoids the minify-to-one-line dance.
- `eval-file-to <out-path> <js-path>` — read JS from file, write result to file

**Network:**
- `capture [--bodies] <path>` — record all network requests to JSONL. Place at script start; writes on exit. Step NDJSON summary: count, by_type, domains, errors. `--bodies` includes response bodies (large, opt-in).

**Emulation:**
- `device <"name"> [--dpr N]` — apply device emulation preset (viewport, DPR, UA, touch, safe area). Available: iPhone 14 Pro, iPhone SE, Pixel 7, iPad Air, iPad Pro 11, Desktop 1080p. `--dpr 1` overrides DPR for smaller screenshots.
- `viewport <width> <height>` — raw dimensions escape hatch (no UA/touch/safe-area)

**Visibility:**
- `bring-to-front` — make the tab visible and focused. Required for `jsaction` sites (Google Groups) that only bind handlers to visible elements.

**Control:**
- `wait` — **one verb, three behaviors**: `wait 3` (sleep 3s), `wait .results` (CSS selector, default 10s timeout), bare `wait` (network idle, default 30s). CSS detected by leading `. # [ :` or containing `> ~ +`. `wait-for` and `wait-idle` still work as explicit aliases.
- `watch [--fast] [--cooldown <seconds>] <path>` — **HMR-triggered auto-screenshot.** Listens for Vite `[vite] hot updated` and `[vite] page reload` console messages + DOM mutations (Tailwind CSS). Cooldown 1s default (prevents screenshot storms). Screenshots to path (overwrite each time). Stays alive until killed. Use with `Bash run_in_background`. NDJSON events: `watch_started`, `hmr`/`mutation`/`reload` (with `screenshot_ms`, `kb`), `watch_stopped`.
- `assert <expression>` — fail script if falsy. Sub-millisecond.
- `log <message>` — print to stderr

## Output protocol

**stderr:** NDJSON per step — `{"i":0,"verb":"goto","ms":342}`
**stdout:** summary — `{"ok":true,"steps":6,"total_ms":443,"files":[{"path":"/tmp/out.png","verb":"screenshot","format":"png","kb":234.5}]}`
**Exit code:** 0 success, 1 failure

`files` entries are objects with `path`, `verb`, and verb-specific metadata — read the summary to decide which files to open.

## Content extraction: `extract` vs `eval`

`extract` uses a three-stage cascade: trafilatura (Python-side, handles most page types) → Readability.js+Turndown (browser-side fallback) → innerText. Shadow DOM content is flattened before extraction, so web components (MDN code examples, etc.) are visible to both extractors. The `source` field in step output tells you which extractor was used. (`read` still works as an alias.)

**Known weaknesses:**

| Page type | `extract` produces | Fix |
|-----------|----------------|-----|
| **Cookie banner visible** | Just the banner text | Dismiss banner first (scout → click) |
| **Animated/dynamic content** | Massive garbage | Use `eval` with `innerText` |
| **Large data tables** | Quality gate auto-detects loss, falls to Readability | Rarely needed now; `eval` as escape hatch |
| **Slow-hydrating SPAs** | Incomplete content | Add adequate `wait` before `extract` |
| **JSON/XML/structured data** | Raw passthrough (auto-detected) | Content-type sniffing handles this automatically (`source: raw`) |

**Decision tree:**

1. **Any page with text content?** → try `extract` first (trafilatura handles articles, dashboards, SPAs)
2. **`extract` output missing content?** → check `source` field; try `eval` with selector chain
3. **Cookie banner present?** → scout + dismiss first, then `extract`
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
wait 0.5
screenshot /tmp/result.png
EOF
```

Two Bash calls total.

### Cookie banners: always scout

**Do NOT guess cookie button text.** Button labels vary wildly between sites, and text click fails on doubled text from icon+label combinations (e.g. `snapshot` shows `"RejectReject All Cookies"`). Always scout first:

```bash
# Scout to find the actual button
passe run -c 'goto https://site.com; snapshot /tmp/elements.txt'
# Read elements.txt, find the cookie button's CSS selector
# Then use click with the exact selector
passe run - <<'EOF'
goto https://site.com
click "div > button:nth-of-type(2)"
wait 0.5
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
click "Search"
type "#query" "parental leave"
press Enter
wait 2
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
wait 1
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

When Chrome Passe runs on a different machine (e.g., Mac) and you're on Kube/remote:

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

## Tab modes

Passe has three tab modes, controlled by run flags:

| Mode | Flag | Tab lifecycle | Use for |
|------|------|---------------|---------|
| **Default** | (none) | Creates new tab → closes on success, **kept with 30s flash on failure** | Automation, screenshots — invisible to user |
| **Keep** | `--keep-tab` | Creates new tab → leaves open permanently | Showing the user a result |
| **Flash** | `--flash [secs]` | Creates new tab → leaves open, auto-closes after timeout (default 30s) | Temporary preview — user interaction cancels timer |
| **Reuse** | `--reuse-tab` | Attaches to existing visible tab → leaves open | User handoff (login flows, OAuth) |

`--reuse-tab` attaches to the first non-chrome:// tab and implies `--keep-tab`. **Warning:** `--reuse-tab` navigates away from whatever the user is looking at — only use when explicitly co-viewing or when you've told the user what's about to happen. Flash timers are never injected into reused tabs.

`--no-keep-on-fail` reverts to old behavior (close tab on failure). `--quiet` / `-q` suppresses stderr hints (`PASSE_HINTS=0`).

**User handoff pattern** (login required):

```bash
# Navigate the user's visible tab
passe run --reuse-tab -c 'goto https://accounts.google.com/oauth/...'
# Ask user: "Log in and let me know when you're done"
# Then capture the result
passe run --reuse-tab -c 'eval document.body.innerText'
```

## Anti-patterns

- **`fill` vs `type`**: Default to `type` for SPAs. `fill` is for plain HTML forms only.
- **Guessing cookie button text**: `click "Reject"` fails more often than it works. Scout first.
- **`click` with text — multiple matches**: Clicks first visible match. Be specific.
- **Tab handling**: Default mode creates and closes its own tab on success. On failure, the tab is kept with a 30s flash timer. Use `--reuse-tab` to attach to the user's visible tab (see Tab modes).
- **Script errors are fatal** but **self-healing on interaction failures**: When `click`, `type`, `fill`, `select`, `hover`, or `tap` fail (e.g. selector not found), passe auto-runs a snapshot and includes the top 10 interactive elements in the error output. Read the error — it tells you what's on the page so you can fix the selector without a separate snapshot call.
- **DOM mutation during TreeWalker traversal**: If you use `eval` to walk the DOM with `createTreeWalker` and mutate nodes (e.g. `replaceChild`), the walker loses its position and silently stops. **Collect nodes first into an array, then mutate in a second pass.**
- **Minifying JS for `eval`**: Don't. Use `eval-file` instead.
- **`eval-file-to` arg order**: It's `eval-file-to <out-path> <js-path>` — output first, source second. Matches `eval-to` convention but opposite to Unix (source → dest). Double-check.
- **Arbitrary `wait` durations**: Don't guess (`wait 2`). `extract` auto-waits for DOM stability after navigation verbs — no explicit wait needed. Use `fetch URL /tmp/out.md` for the common case (goto + auto-wait + extract in one step). After clicks that trigger SPA route changes or XHR calls, use bare `wait` (network idle) or `wait .selector` for a specific element. Bare `wait` is the better default — it's deterministic and replaces guessed delays.
- **PNG for inner-loop iteration**: Use `screenshot --fast` for edit-and-see loops. PNG at 3x DPR produces 1179×2556 images (expensive in tokens). `--fast` gives JPEG viewport-only at the preset DPR (or `--dpr 1` for even smaller). Save PNG for final fidelity checks.

## Subcommands (no DSL needed)

Intent-level commands that handle tab lifecycle automatically — no `passe run` wrapper:

```bash
# See a page (goto + screenshot --fast, always JPEG for Claude's eyes)
passe look https://example.com                    # → /tmp/passe-look.jpg
passe look https://example.com /tmp/result.jpg    # explicit path

# Verify a page has expected content (exit 0/1)
passe check https://example.com --contains "Welcome"
passe check https://example.com --contains "Dashboard" --screenshot /tmp/proof.jpg

# Record network requests (goto + network idle + capture to JSONL)
passe capture https://spa.example.com /tmp/reqs.jsonl
passe capture --bodies https://spa.example.com /tmp/reqs.jsonl  # include response bodies

# Extract page content (goto + auto-wait + read)
passe fetch https://example.com                   # short content inlined in JSON
passe fetch https://example.com /tmp/content.md   # long content to file

# Observe current page (no navigation, attaches to existing tab)
passe screenshot /tmp/current.png
passe eval "document.title"
```

```bash
# Validate a script without executing (no Chrome needed)
passe explain -c 'goto https://example.com; screenshot /tmp/out.png'
passe explain script.passe
passe explain - <<'EOF'
...
EOF
```

`explain` checks verb names, argument counts, file existence (for eval-file), and emits warnings (goto+read → use fetch, complex inline scripts, capture not first). Exit 0 if valid, exit 1 with errors and line numbers. No Chrome connection needed.

All tab-creating subcommands create+destroy their own tab and emit the same NDJSON+JSON output protocol as `passe run`.

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
