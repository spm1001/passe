# passe

> [!CAUTION]
> Passe gives your AI agent **full control of a real Chrome browser** via the Chrome DevTools Protocol — including navigating to any URL, clicking, typing, reading page content, and executing JavaScript. Only use this if you understand and accept that your agent will have the same browser access as you do. There is no sandbox.

Fast browser automation for AI agents. One WebSocket, one process, no daemon.

The browser was never slow — the agentic loop was. Every MCP tool call costs a model round-trip (1.5–6 seconds depending on the model). A 20-step workflow through an agentic loop means 20 round-trips: 60–120 seconds of waiting for the model, not the browser. Passe takes a different approach: your AI writes a complete script in a line-based DSL, then a single Bash call executes every step via raw [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) at wire speed. Per-action latency is ~20ms.

## The landscape

There are dozens of browser automation tools now. This 2×2 captures where they all sit:

```
                The AI scripts it        AI feels it out
            ┌──────────────────────┬───────────────────────────┐
  Your      │                      │  Browser-Use (78K ★)      │
  Chrome    │   ★ passe            │  BrowserMCP extension     │
  (real     │                      │  Chrome DevTools MCP      │
  session)  │                      │  Claude in Chrome         │
            ├──────────────────────┼───────────────────────────┤
  Managed   │  Playwright          │  Stagehand / Browserbase  │
  browser   │  Selenium            │  CUA / Operator           │
  (clean)   │                      │  Computer Use / Mariner   │
            └──────────────────────┴───────────────────────────┘
```

**Bottom-left** is what we've always had — Playwright, Selenium. Scripted automation against clean browser instances. Test automation.

**Bottom-right** is the current gold rush — autonomous AI agents driving cloud or sandboxed browsers. Browserbase ($67.5M raised), Browser-Use (78K stars, $17M seed), OpenAI's CUA, Google's Mariner.

**Top-right** is the extension and open-source wave — autonomous agents riding *your* real browser session. Claude in Chrome proved the value: your SSO, your cookies, your logins, no credential management. But every action still costs a model round-trip.

**Top-left** is passe. Same authenticated session access as the top-right tools, but the AI thinks once and the script runs at wire speed. This quadrant is empty except for passe.

See [docs/landscape.md](docs/landscape.md) for the full competitive analysis with hard numbers.

## The numbers

```
Navigate + screenshot:   213ms (passe)  vs  ~12,600ms (MCP-based tools)
```

That's a ~60× speed gap — and it's not the browser. MCP tool schemas alone consume 10,000–15,000 tokens of context before any page content. Each round-trip adds 1.5–6 seconds of model inference. Multiply by 20 steps and you're waiting two minutes for work that takes a few seconds at the wire.

| Scenario | Agentic loop (20 steps) | Passe |
|---|---|---|
| Fast model (GPT-4o, ~1.5s/step) | ~30s model time | ~1–5s execution + one model call |
| Mid model (Claude Sonnet, ~3s/step) | ~60s model time | Same |
| Reasoning model (o3, ~6s/step) | ~120s model time | Same |

The model call to *write* the script is the same cost regardless. The difference is paying it once vs. twenty times.

## Install

```bash
uv tool install 'passe @ git+https://github.com/spm1001/passe'
```

(Or `uv tool install ~/repos/spm1001/passe` from a local clone. Passe is not published to PyPI, so a bare `uv tool install passe` won't resolve.)

Requires Python 3.11+ and Chrome/Chromium with `--remote-debugging-port=9222`. Passe auto-starts a debug Chrome instance if none is running.

## Quick start

```bash
# Screenshot a page
passe run -c 'goto https://example.com; screenshot /tmp/page.png'

# Extract page content as markdown
passe run -c 'fetch https://example.com /tmp/article.md'

# Multi-step scripts use heredoc
passe run - <<'EOF'
goto https://example.com
click-text "Accept Cookies"
wait 500
type "#search" "query"
press Enter
wait-for .results
screenshot /tmp/results.png
EOF
```

Output is structured JSON — NDJSON per step on stderr, summary on stdout:

```json
{"ok": true, "steps": 2, "total_ms": 213.4, "files": ["/tmp/page.png"], "final_url": "https://example.com/"}
```

## The DSL

One verb per line. Short scripts inline with `-c` (`;` as separator), longer scripts as heredoc or `.passe` files.

| | |
|---|---|
| **Navigate** | `goto` `back` `forward` `scroll` |
| **Interact** | `click` `click-text` `click-if` `type` `fill` `select` `press` `hover` |
| **Observe** | `screenshot` `snapshot` `read` `fetch` `eval` `eval-to` `eval-file` `eval-file-to` |
| **Control** | `wait` `wait-for` `wait-navigation` `viewport` `assert` `log` |

### Scout-then-act

When you don't know the page's selectors, scout first:

```bash
# Pass 1: discover interactive elements
passe run -c 'goto https://unknown-site.com; snapshot /tmp/elements.txt'
```

`snapshot` returns something like:

```
[0] button "Sign in" css=#sign-in
[1] link "Blog" css=nav > a:nth-of-type(1) href=/blog
[2] input[email] "Email" css=input[name="email"]
[3] button "Reject" css=.cookie-banner > button:nth-of-type(1)
```

```bash
# Pass 2: act on discovered selectors
passe run - <<'EOF'
goto https://unknown-site.com
click ".cookie-banner > button:nth-of-type(1)"
type "input[name='email']" "test@example.com"
click "#sign-in"
screenshot /tmp/result.png
EOF
```

Two Bash calls. For simple cases, skip the scout — `click-text "Reject"` works when the button text is unambiguous.

## Content extraction

Most browser automation tools stop at screenshots and clicks. If you want page content, you need a separate tool. Passe has extraction built in.

`read` and `fetch` extract page content as clean markdown through a 4-stage cascade:

1. **Content-type sniffing** — if the response is JSON, XML, CSV, or plain text, bypass extraction entirely and return raw content (JSON is pretty-printed). Handles API endpoints and structured data without configuration.
2. **Trafilatura** (Python-side) — the primary extractor. Handles articles, dashboards, SPAs. A structural quality gate detects when tables or code blocks are dropped and falls through automatically.
3. **Readability.js + Turndown** (browser-side) — Mozilla's extraction library as fallback. Better at preserving tabular data and code blocks.
4. **innerText** — last resort. Raw text content.

Shadow DOM content is flattened before extraction — web components are inlined so both extractors can see them.

**Thin-read diagnostics**: when extraction returns suspiciously little content, passe emits a diagnostic with word count, page size, and a probable cause (`auth_wall`, `empty_page`, `js_hydration`). Helps debug extraction failures without guessing.

`fetch` is the compound verb for research workflows — `goto` + auto-wait + `read` in one step:

```bash
passe run -c 'fetch https://example.com/article /tmp/content.md'
```

Force a specific extractor with `--source`:

```bash
passe run -c 'goto https://example.com; read --source readability /tmp/out.md'
```

## Your browser, your session

Passe connects to Chrome on port 9222. If you run Chrome with `--remote-debugging-port=9222`, passe gets your full session — SSO, HttpOnly cookies, saved logins. No credential management, no token juggling. Chrome *is* the authenticated session.

This is the same insight that made tools like Claude in Chrome and BrowserMCP valuable: riding the user's real browser session eliminates the hardest part of web automation. Passe keeps that property while removing the per-step model tax.

**The security model**: the debug port binds to localhost only. Since Chrome 136 (March 2025), `--remote-debugging-port` requires a separate `--user-data-dir` — Chrome won't expose your main profile's data directory over the debug protocol. This was a response to malware campaigns that relaunched Chrome with debug flags to dump cookies. The separate data directory gets its own encryption key, protecting main profile credentials.

If Chrome isn't running when you invoke passe, it auto-starts one with `--user-data-dir=~/.chrome-passe` — a bare profile with no logins. Fine for public pages, but it won't have your sessions.

## When to use passe (and when not to)

| Need | Tool |
|------|------|
| Scripted browser workflows (navigate, click, type, screenshot) | **passe** |
| Extract content from any page (articles, SPAs, dashboards) | **passe** `read` / `fetch` |
| Reactive navigation of unknown pages where the AI needs to decide each step | Agentic tools (Browser-Use, Stagehand, CUA) |
| Full test suites with fixtures and assertions | Playwright directly |
| Google Workspace content (Drive, Gmail) | [mise](https://github.com/spm1001/mise-en-space) `fetch` |

Passe is for workflows where the AI can plan the steps upfront. When the page is genuinely unknown and each step depends on what the AI sees, agentic tools earn their round-trips. Both approaches have their place — and they compose well: use an agentic tool to explore, then write a passe script for the repeatable workflow you discovered.

## Works with

Claude Code, Amp, Cursor, Codex, Gemini CLI — any AI agent or coding assistant with shell access. Passe is a CLI tool, not an extension or MCP server. If it can run `bash`, it can run passe.

## The Kitchen

Passe is part of [Batterie de Savoir](https://spm1001.github.io/batterie-de-savoir/) — tools for AI-assisted knowledge work, named for stations in a professional kitchen brigade. Passe is the pass — the inspection window where every plate is checked before it goes out.

## License

MIT
