# Passe CLI Usage Analysis

Analysis of 97 passe invocations across 11 Claude Code sessions (Feb 15-20, 2026), plus 39 assistant discussion blocks describing difficulties and workarounds.

## Successful uses (sample — 25 of 70)

### 1. Basic goto + screenshot (example.com)
**Context:** Exercise 1a — verify basic headless screenshot works on kube.
```bash
passe run -c 'goto https://example.com; screenshot /tmp/ex1-desktop.png'
```
Completed in 245ms. The bread-and-butter pattern.

### 2. Device emulation + screenshot
**Context:** Exercise 1b — iPhone emulation on local headless.
```bash
passe --device "iPhone 14 Pro" --dpr 1 run -c 'goto https://example.com; screenshot /tmp/ex1-iphone.png'
```
Completed in 152ms. `--dpr 1` keeps file size small.

### 3. Heredoc with multi-verb script (HN mobile)
**Context:** Exercise 2 — full scout of Hacker News on iPhone.
```bash
passe --device "iPhone 14 Pro" --dpr 1 run - <<'EOF'
goto https://news.ycombinator.com
screenshot /tmp/ex2-hn-iphone.png
snapshot /tmp/ex2-hn-elements.txt
EOF
```
Snapshot captured interactive elements for selector discovery.

### 4. Click-text on mobile hamburger menu
**Context:** Exercise 3b — open BBC News mobile menu.
```bash
passe --device "iPhone 14 Pro" --dpr 1 run - <<'EOF'
goto https://www.bbc.co.uk/news
wait 1500
click-text "Menu"
wait 500
screenshot --viewport /tmp/ex3-menu-clicked.png
EOF
```
`click-text` found "Menu" without needing a CSS selector.

### 5. Remote CDP via Tailscale (ghost screenshot)
**Context:** Exercise 4 — screenshot Mac's current Chrome tab from kube.
```bash
passe --cdp http://100.66.153.39:9222 screenshot /tmp/ex4-mac-current.png
```
Atomic command, no script runner needed. 87KB screenshot in one call.

### 6. Ghost tab on remote Chrome
**Context:** Exercise 5 — open a tab on Mac Chrome, screenshot, close.
```bash
passe --cdp http://100.66.153.39:9222 run -c 'goto https://httpbin.org/get; screenshot --fast /tmp/ex5-mac-ghost.jpg'
```
Tab created in background, closed on exit. Mac user never saw it.

### 7. Device emulation over Tailscale
**Context:** Exercise 6 — iPhone emulation on Mac Chrome over Tailscale.
```bash
passe --cdp http://100.66.153.39:9222 --device "iPhone 14 Pro" --dpr 1 run - <<'EOF'
goto https://www.bbc.co.uk/news
wait 1500
screenshot --viewport /tmp/ex6-mac-iphone.png
EOF
```
Device emulation works remotely — same viewport/UA as local.

### 8. Touch event verification
**Context:** Exercise 7 — verify click fires mouse but not touch events.
```bash
passe --device "iPhone 14 Pro" --dpr 1 run - <<'EOF'
goto http://100.110.220.64:8765/touch-test.html
wait 500
click "#click-btn"
click "#touch-btn"
click "#swipe-area"
wait 300
screenshot --viewport /tmp/ex7-touch-result.png
eval document.getElementById('log').textContent
EOF
```
Confirmed the touch gap — click fires mouse events only, not touch events.

### 9. fetch compound verb (React SPA docs)
**Context:** Naive Claude extracting React docs.
```bash
passe run -c 'fetch https://react.dev/learn'
```
Quality gate caught trafilatura dropping 19 code blocks. Fell back to trafilatura output with a warning. Still succeeded, content was usable.

### 10. --reuse-tab for authenticated navigation
**Context:** Restoring Gmail tab after using it for testing.
```bash
passe --cdp http://100.66.153.39:9222 run --reuse-tab -c 'goto https://mail.google.com'
```
Navigated user's existing tab to Gmail. SSO session intact.

### 11. Stderr/stdout separation testing
**Context:** Debugging stderr duplication bug (passe-genazu).
```bash
passe run -c 'goto https://example.com; screenshot /tmp/genazu-test.png' 2>/tmp/genazu-stderr.txt
```
Verified NDJSON on stderr, JSON summary on stdout. Exit code 0.

### 12. fetch with JSON content-type sniffing
**Context:** Testing content-type detection on httpbin.
```bash
passe run -c 'fetch https://httpbin.org/get /tmp/httpbin.json'
```
Detected `application/json`, bypassed extraction, returned raw pretty-printed JSON. `source: raw`.

### 13. fetch with plain text content-type
**Context:** Testing raw passthrough on GPL license text.
```bash
passe run -c 'fetch https://www.gnu.org/licenses/gpl-3.0.txt /tmp/gpl.txt'
```
Detected `text/plain`, returned raw content. No extraction overhead.

### 14. Swagger JSON direct fetch
**Context:** The motivating case — Swagger UI is useless to extractors, but the JSON spec is clean.
```bash
passe run -c 'goto https://petstore.swagger.io/v2/swagger.json; read /tmp/swagger.json'
```
Content-type sniffing caught `application/json`, returned raw spec. The lesson: always fetch the `.json` spec directly.

### 15. --source raw override on HTML
**Context:** Testing forced raw passthrough on HTML page.
```bash
passe run -c 'goto https://example.com; read --source raw /tmp/example-raw.txt'
```
Forced `text/html` through raw passthrough. Returned raw HTML.

### 16. Swagger UI with forced Readability extractor
**Context:** Comparing extractors on Swagger UI.
```bash
passe run -c 'fetch https://utiq-api.com/activator/v1/docs/ --source readability /tmp/utiq-readability.md'
```
Readability gave different output from trafilatura. Neither great for Swagger — the JSON spec is always better.

### 17. Scroll + viewport screenshot
**Context:** Testing scroll-before-screenshot warning suppression.
```bash
passe run -c 'goto https://example.com; scroll 0 500; screenshot --viewport /tmp/scroll-vp.png'
```
No warning with `--viewport` (correct — viewport screenshot after scroll is intentional). Warning fires with full-page screenshot after scroll.

### 18. tap verb on touch test page
**Context:** Live test of new tap verb using JS TouchEvent synthesis.
```bash
passe run --device 'iPhone 14 Pro' - <<'EOF'
goto http://100.110.220.64:8899/touch-test.html
tap #touch-btn
wait 100
eval document.getElementById('result').textContent
screenshot /tmp/tap-result.png
EOF
```
Result: "touchend fired! changedTouches=1". Tap worked in 3.7ms.

### 19. click vs tap comparison
**Context:** Verifying click does NOT fire touch events.
```bash
passe run - <<'EOF'
goto http://100.110.220.64:8899/touch-test.html
click #touch-btn
wait 100
eval document.getElementById('result').textContent
EOF
```
Result: "click only (no touch event)". Confirms tap fills a real gap.

### 20. swipe verb — all 4 directions
**Context:** Testing swipe left/right/up/down on touch test page.
```bash
passe run --device 'iPhone 14 Pro' - <<'EOF'
goto http://100.110.220.64:8899/swipe-test.html
swipe #swipe-area left 200
wait 100
eval document.getElementById('result').textContent
screenshot /tmp/swipe-result.png
EOF
```
Result: "Swiped left! dx=-200 dy=0 moves=8". All 4 directions confirmed working.

### 21. Navigation failure detection (connection refused)
**Context:** Testing goto failure detection after passe-henohe improvements.
```bash
passe run -c 'goto http://localhost:9999; screenshot /tmp/x.png'
```
Exit code 1. Error: `Navigation failed: net::ERR_CONNECTION_REFUSED — http://localhost:9999`. Clear, immediate.

### 22. Navigation failure detection (SSL)
**Context:** Testing SSL error detection.
```bash
passe run -c 'goto https://expired.badssl.com; screenshot /tmp/x.png'
```
Exit code 1. Error: `Navigation failed: net::ERR_CERT_DATE_INVALID`. No silent continuation.

### 23. GitHub README screenshot (remote Mac Chrome)
**Context:** Screenshotting passe's own GitHub README for review.
```bash
passe run -c 'goto https://github.com/spm1001/passe; screenshot /tmp/readme-github.png'
```
Worked but slow (3.3s) — GitHub is heavy. 2.2MB screenshot.

### 24. --keep-tab for persistent tabs
**Context:** Keeping a GitHub tab open for continued work.
```bash
passe run -c 'goto https://github.com/spm1001/passe/blob/main/LANDSCAPE.md; screenshot /tmp/landscape-github.png' --keep-tab
```
Tab persisted after script exit. User could navigate to it.

### 25. devices subcommand
**Context:** Listing available device presets.
```bash
passe devices
```
Clean table output: name, size, DPR, type. Six presets listed.

---

## Difficult / failed uses (sample — 25 of 26)

### 1. file:// protocol on headless Chromium
**Context:** Touch test page loaded via `file://` protocol.
```bash
passe --device 'iPhone 14 Pro' --dpr 1 run - <<'EOF'
goto file:///tmp/touch-test.html
...
EOF
```
**What went wrong:** `goto file:///tmp/touch-test.html` hit `net::ERR_FILE_NOT_FOUND`. Headless Chromium sandboxing blocks file:// access.
**Workaround:** Served the file via `python3 -m http.server` and used HTTP URL instead. Then hit the localhost-unreachable issue (see #3-8 below).

### 2. Click on element not yet rendered
**Context:** Touch test page elements not in DOM after navigation.
```bash
click "#click-btn"
```
**What went wrong:** `click failed: Error: No element matches: #click-btn`. Navigation to chrome-error page meant the real page never loaded.
**Workaround:** Fixed navigation first (use Tailscale IP instead of localhost).

### 3-8. Headless Chromium cannot reach localhost (6 failures)
**Context:** Serving a test page on localhost, Chromium navigates to it.
```bash
passe run -c 'goto http://localhost:8765/touch-test.html; eval window.location.href'
passe run -c 'goto http://127.0.0.1:8765/touch-test.html; eval window.location.href'
passe run -c 'goto http://172.17.2.2:8765/touch-test.html; eval window.location.href'
passe run -c 'goto http://0.0.0.0:8765/touch-test.html; screenshot /tmp/debug.png'
```
**What went wrong:** All resolved to `chrome-error://chromewebdata/`. Curl could reach the server, Chromium couldn't. Confirmed as a sandbox/network-namespace issue in headless Chromium on Debian.
**Workaround:** Used Tailscale IP (`100.110.220.64`) which routes through a real network interface.

### 9. wait-for timeout on nonexistent selector
**Context:** Deliberately testing error behavior.
```bash
passe run -c 'goto https://example.com; wait-for .nonexistent-element 2000'
```
**What went wrong:** Expected failure — `wait-for timed out after 2000ms`. Exit code 1. Correct behavior, but included here because the stderr duplication (CC Bash tool quirk) made the output confusing.

### 10. Click on nonexistent element
**Context:** Deliberately testing error behavior.
```bash
passe run -c 'goto https://example.com; click "#does-not-exist"'
```
**What went wrong:** Expected failure — `click failed: Error: No element matches`. The doubled stderr output (CC quirk) made it look like the command ran twice.

### 11. Port conflict when starting HTTP server
**Context:** Starting a test server while one was already running.
```bash
python3 -m http.server 8765 --directory /tmp &
passe run -c 'goto http://127.0.0.1:8765/touch-test.html; eval window.location.href'
```
**What went wrong:** Python traceback — `Address already in use`. Not a passe bug, but the combined output was confusing.
**Workaround:** Used `fuser -k 8765/tcp` to kill existing server, then used a different port.

### 12. Silent goto failure (pre-henohe)
**Context:** Navigating to a nonexistent domain before goto failure detection was added.
```bash
passe run -c 'goto http://nonexistent.invalid; screenshot /tmp/henohe-test.png'
```
**What went wrong:** `goto` reported `ok: true` despite landing on `chrome-error://chromewebdata/`. The screenshot captured the error page. No indication of failure.
**Fix:** passe-henohe added navigation failure detection — now reports `ok: false` with Chrome's error code.

### 13-15. Stderr duplication investigation (3 failures)
**Context:** Investigating why error output appears twice in Claude Code.
```bash
passe run -c 'goto https://example.com; click "#nonexistent"' 2>&1
passe run -c 'goto https://example.com; click "#does-not-exist"' 2>&1
```
**What went wrong:** Output appeared doubled. Root cause: CC Bash tool duplicates output on non-zero exit codes. Not a passe bug.
**Resolution:** Filed as documentation note (CC Bash tool quirk). No code change needed.

### 16-19. Investigating chrome-error page content (4 invocations)
**Context:** Understanding what information is available after navigation failure.
```bash
passe run -c 'goto http://nonexistent.invalid; eval document.title'
passe run -c 'goto http://nonexistent.invalid; eval document.body.innerText'
passe run -c 'goto http://nonexistent.invalid; eval window.location.href'
```
**What went wrong:** Before henohe, these all returned `ok: true` because goto didn't check for errors. The eval results showed chrome-error content but the script didn't fail.
**Fix:** passe-henohe now checks `Page.navigate` errorText and chrome-error URL.

### 20. DNS failure detection (post-henohe)
**Context:** Testing goto failure detection after fix.
```bash
passe run -c 'goto http://nonexistent.invalid; screenshot /tmp/x.png'
```
**What went wrong:** Now correctly fails with `Navigation failed: net::ERR_NAME_NOT_RESOLVED`. Exit code 1. Script stops at goto. This is the *correct* behavior — listed here because it was a failure before the fix.

### 21. passe run --help misclassified
**Context:** Checking verb reference.
```bash
passe run --help
```
**What went wrong:** Nothing — the help text printed fine. False positive in failure classification (the word "timeout" appears in the help text description).

### 22. CDP Input.dispatchTouchEvent hangs through flattened sessions
**Context:** Implementing tap verb via CDP native touch events.
```bash
# Direct page WebSocket: works
# Browser WebSocket + sessionId: hangs for 15 seconds, then timeout
```
**What went wrong:** `Input.dispatchTouchEvent` sent through a flattened CDP session (browser-level WS + sessionId routing) never gets a response from Chrome. Works fine on direct page WebSocket. Other `Input.*` methods (like `dispatchMouseEvent` in hover) work through sessions.
**Workaround:** Used JS `TouchEvent` synthesis instead — `Runtime.evaluate` with `new Touch()` + `new TouchEvent()` + `dispatchEvent()`. 3.7ms, reliable.

### 23. thin_read false positive on example.com
**Context:** Testing thin-read diagnostics — example.com is legitimately small.
```bash
passe run -c 'fetch https://example.com /tmp/ex.md'
```
**What went wrong:** `thin_read` warning fired: "17 words extracted from 513B page — possible unknown". The page genuinely only has 17 words. Suppression logic wasn't right.
**Fix:** Adjusted suppression to check extraction ratio + absolute page text size.

### 24. tap verb hangs via CDP (pre-JS-synthesis)
**Context:** First attempt at tap verb using `Input.dispatchTouchEvent`.
```bash
passe run --device 'iPhone 14 Pro' - <<'EOF'
goto http://100.110.220.64:8899/touch-test.html
tap #touch-btn
wait 100
eval document.getElementById('result').textContent
EOF
```
**What went wrong:** tap hung for 15 seconds (`ms: 15015.8`), then returned empty error. CDP call never got a response.
**Workaround:** Reimplemented tap using JS `TouchEvent` synthesis. Works in 3.7ms.

### 25. Repeated tap hang after partial fix
**Context:** Second attempt at tap with `id` field fix — still using CDP dispatch.
```bash
passe run --device 'iPhone 14 Pro' - <<'EOF'
goto http://100.110.220.64:8899/touch-test.html
tap #touch-btn
...
EOF
```
**What went wrong:** Same 15-second hang. The issue is fundamental to `Input.dispatchTouchEvent` through flattened sessions, not a parameter problem.
**Workaround:** Same as #24 — JS synthesis.

---

## Patterns observed

### Common verb combinations
| Pattern | Count | Context |
|---------|-------|---------|
| `goto → screenshot` | 16 | The dominant pattern. Navigate, capture. |
| `goto → eval` | 13 | Mostly `eval window.location.href` or `document.title` for verification |
| `fetch` (standalone) | 11 | Content extraction — the compound verb works well |
| `goto → click → eval/screenshot` | 4+ | Interaction flows, often with wait between |
| `goto → read` | 3 | Explicit navigate-then-extract |
| `goto → scroll → screenshot` | 2 | Scroll-then-capture (triggers a "this is usually unnecessary" warning) |
| `goto → snapshot` | 2+ | Element discovery (scout pattern) |

### What eval is used for
The most revealing signal for missing verbs:
| Expression | Count | Suggests |
|------------|-------|----------|
| `window.location.href` | 7 | **URL verification** — no built-in way to check current URL |
| `document.getElementById('result').textContent` | 5 | **Text extraction from specific element** — the `text <selector>` verb would cover this |
| `document.title` | 3 | **Page title check** — minor, title is in read/fetch output |
| `document.body.innerText` | 2 | **Full page text** — covered by `read` |

### Verbs used in heredoc scripts (not captured by simple regex)
From manual inspection of the full output: `goto`, `screenshot`, `snapshot`, `wait`, `click`, `click-text`, `eval`, `read`, `scroll`, `tap`, `swipe`, `device`, `wait-for`, `type`, `fill`, `press`, `hover`, `log`, `assert`.

Most verbs that appear "never used" in the automated count are actually used inside heredocs.

### Verbs that genuinely never appeared
- `back` / `forward` — browser history navigation
- `click-if` — conditional click
- `eval-file` / `eval-file-to` — file-based JS execution
- `watch` — HMR auto-screenshot (discussed extensively but not invoked in these specific sessions)
- `wait-navigation` — explicit navigation wait
- `select` — dropdown interaction

### Recurring failure modes
1. **Headless Chromium cannot reach localhost** (6 failures) — sandbox/network namespace issue on Debian. Workaround: Tailscale IP. Well-documented in MEMORY.md now.
2. **CDP Input.dispatchTouchEvent hangs through flattened sessions** (3 failures) — Chrome doesn't respond to touch dispatch routed through browser-level WS + sessionId. Workaround: JS TouchEvent synthesis.
3. **Silent goto failure** (4 failures, pre-henohe) — goto landed on chrome-error:// but reported ok:true. Fixed by navigation failure detection.
4. **CC Bash tool stderr duplication** (3 false alarms) — non-zero exit codes cause doubled output display. Not a passe bug.
5. **file:// protocol blocked** (1 failure) — headless Chromium sandboxing. Workaround: HTTP server.
6. **thin_read false positive** (1 failure) — small pages trigger warning inappropriately.

### Workarounds that suggest missing verbs
1. **`eval window.location.href`** — used 7 times to verify navigation. Could be a property of `goto` output or an `assert` enhancement.
2. **`eval document.getElementById('result').textContent`** — used 5 times to extract element text. This is exactly what `text <selector>` would do.
3. **Manual `wait 500`/`wait 1000`/`wait 1500` before interaction** — used ~6 times. `wait-idle` would replace these with deterministic readiness detection.
4. **`goto + read` two-step** — used when `fetch` would suffice. The `fetch` compound verb already exists and handles this.
5. **No way to clear an input before typing** — not observed in these sessions but flagged in bon items (passe-tizezo).
6. **No way to check HTTP status codes** — discussed in session a21a1854. Would need `Network.enable`.

---

## Verdict on the 15 planned verbs

### 1. `reload [--hard]`
**Rating: MEDIUM**
**Reason:** Never used in these sessions, but 0 uses ≠ 0 need. Reload is a basic browser action with no current workaround short of `eval location.reload()`. It's a 5-line implementation, low risk.

### 2. `clear <selector>`
**Rating: HIGH**
**Reason:** Not observed because `type` testing was limited, but the bon items (passe-tizezo) flag complex form inputs as untested. Any form-filling workflow needs clear-before-type. Currently requires `eval` to clear a field. The pattern `clear #email; type #email "new@example.com"` is natural and common.

### 3. `focus <selector>`
**Rating: LOW**
**Reason:** No evidence of need. `click` implicitly focuses, and `type` targets by selector. The only case would be triggering focus-dependent UI (dropdowns, autocomplete), and those weren't attempted.

### 4. `submit <selector>`
**Rating: LOW**
**Reason:** No evidence of need. `press Enter` or `click` on submit button works. HTML form submission without a button is rare in SPAs.

### 5. `text <selector>`
**Rating: HIGH**
**Reason:** `eval document.getElementById('result').textContent` was used 5 times across these sessions. Every time, the intent was "give me the text of this element." `text #result` is shorter, more readable, and doesn't require knowing the JS API. This is the clearest signal in the data.

### 6. `html [selector] [path]`
**Rating: MEDIUM**
**Reason:** Not directly observed, but the extraction cascade (`read --source raw`) serves a similar purpose for full-page HTML. Element-level HTML extraction (e.g., `html .article`) would be useful for partial extraction but there's no strong signal from usage.

### 7. `attr <selector> <name>`
**Rating: LOW**
**Reason:** No evidence of need. `eval document.querySelector('a').href` works but was never used. Attribute extraction wasn't a pattern.

### 8. `screenshot-el <selector> [path]`
**Rating: MEDIUM**
**Reason:** No direct usage, but full-page screenshots were 41KB-2.2MB. Element screenshots would reduce noise for targeted verification. The GitHub README screenshot (2.2MB) would have been better as a screenshot of just the README content div.

### 9. `wait-idle [timeout_ms]`
**Rating: HIGH**
**Reason:** Manual `wait 500`/`wait 1000`/`wait 1500` appeared ~6 times, always as a guess. Discussion #39 explicitly critiqued a proposed implementation (polling `performance.getEntriesByType` is wrong — needs CDP Network domain). The correct approach (tracking in-flight requests via `Network.requestWillBeSent`/`Network.loadingFinished`) was identified. This replaces the most common guesswork in scripts.

### 10. `file <selector> <path>`
**Rating: LOW**
**Reason:** No evidence of file upload need in any session. Useful for form testing but not a pattern in these sessions.

### 11. `download <selector> [path]`
**Rating: LOW**
**Reason:** No evidence of download need. The `fetch` verb handles content extraction. Browser-initiated downloads (clicking a download link) didn't come up.

### 12. Enhanced assert (`--eq`, `--message`)
**Rating: MEDIUM**
**Reason:** `assert` was not used in these sessions, but `eval` + visual inspection was the substitute in every verification step. `assert --eq document.title "Example Domain" --message "page didn't load"` would formalize what was done manually with eval. The value is in making scripts self-documenting for CI use.

### 13. `ax-tree`
**Rating: LOW**
**Reason:** No evidence of accessibility tree need. `snapshot` serves the element discovery use case. Accessibility testing wasn't attempted.

### 14. `ax-find`
**Rating: LOW**
**Reason:** Same as ax-tree. No accessibility queries observed.

### 15. `ax-node`
**Rating: LOW**
**Reason:** Same as ax-tree. No accessibility inspection observed.

---

## Capability gaps NOT in the planned 15 verbs

### 1. `url` or URL in goto output — **HIGH priority**
`eval window.location.href` was the single most common eval pattern (7 uses). The intent is always "did I end up where I expected?" Two options: (a) `url` verb that returns current URL, or (b) include `final_url` more prominently in goto's step output (it's already in the summary JSON but not in the per-step NDJSON).

### 2. `wait-human-nav [timeout]` — **HIGH priority** (already prototyped)
Extensively discussed in sessions. The pattern: passe navigates to an OAuth page, user approves, passe detects the redirect. Prototyped in session 6cf7ca84 with CDP event listeners. Listed under passe-rulete but not in the 15 planned verbs.

### 3. `long-press <selector> [duration_ms]` — **MEDIUM priority**
The touch verb family (tap, swipe) was built and tested. Long-press is the obvious next member. Discussed in CLAUDE.md ("use JS synthesis for future touch verbs: long-press, pinch").

### 4. `cookies [--domain] [path]` — **MEDIUM priority**
No cookie inspection capability. When debugging auth issues ("is the session cookie present?"), the only option is `eval document.cookie` which misses HttpOnly cookies. CDP's `Network.getCookies` could expose these.

### 5. `network-log` or `capture` — **MEDIUM priority**
Listed as an outcome (passe-capture) but not in the 15 planned verbs. The need: "what API calls did this page make?" Currently invisible. Would need `Network.enable` + event buffering.

### 6. HTTP status code awareness — **MEDIUM priority**
Discussed in session a21a1854: passe is blind to HTTP status codes. A 403 page loads "successfully" from goto's perspective. Detection requires `Network.enable` + `Network.responseReceived`. Could be a flag (`goto --expect-status 200`) or surfaced in goto's step output.

### 7. `crawl <url> [--depth N] [--same-domain]` — **LOW priority (deferred)**
Listed as passe-wuhelu under passe-lotoco. Follow same-domain links, deposit one markdown per page. Useful for documentation sites but complex to implement well.

### 8. Tab switching — **LOW priority but notable gap**
Documented footgun: "If a click opens a new browser tab, passe stays on its own — no tab switching." No workaround exists. Rare in practice but impossible when it comes up.
