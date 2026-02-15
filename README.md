# passe

> [!CAUTION]
> Passe gives your AI agent **full control of a real Chrome browser** via the Chrome DevTools Protocol — including navigating to any URL, clicking, typing, reading page content, and executing JavaScript. Only use this if you understand and accept that your agent will have the same browser access as you do. There is no sandbox.

> **Status:** Beta — actively developed
> **Works with:** Claude Code, Amp, any agent with shell access
> **Install:** `uv tool install passe`
> **Requires:** Python 3.11+, Chrome/Chromium

Fast browser automation for Claude Code. One WebSocket, one process, no daemon.

```
Navigate + screenshot: 213ms (passe) vs ~12,600ms (MCP-based tools)
```

The speed gap isn't the browser — it's the protocol. MCP needs a model round-trip per action (~6s each). Passe does everything in a single Bash call via raw [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/).

## Install

```bash
uv tool install passe
```

Requires Chrome with `--remote-debugging-port=9222`. Passe auto-starts a debug Chrome instance if none is running.

## Quick start

```bash
# Screenshot a page
passe run -c 'goto https://example.com; screenshot /tmp/page.png'

# Extract article content as markdown
passe run -c 'goto https://example.com; read /tmp/article.md'

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

## Verbs

| | |
|---|---|
| **Navigate** | `goto` `back` `forward` `scroll` |
| **Interact** | `click` `click-text` `click-if` `type` `fill` `select` `press` `hover` |
| **Observe** | `screenshot` `snapshot` `read` `eval` `eval-to` |
| **Control** | `wait` `wait-for` `wait-navigation` `viewport` `assert` `log` |

`snapshot` lists interactive elements with CSS selectors — use it to scout unknown pages before writing interaction scripts.

`read` extracts page content as markdown via Readability.js + Turndown.js running in Chrome's V8. Warns when extraction looks incomplete.

## When to use passe (and when not to)

| Need | Tool |
|------|------|
| Screenshot, interact, test a page | **passe** |
| Extract content preserving tables/code blocks | **passe** `read` |
| Extract article/blog content (cleaner) | [mise](https://github.com/spm1001/mise-en-space) `fetch` |
| Full Playwright test suites | Playwright directly |

## The Kitchen

Passe is part of [Batterie de Savoir](https://spm1001.github.io/batterie-de-savoir/) — a suite of tools for AI-assisted knowledge work, each named for a station in a professional kitchen brigade. See the [full brigade and design principles](https://spm1001.github.io/batterie-de-savoir/) for how the tools fit together.

## License

MIT
