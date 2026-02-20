# Rodney vs Passe: A Comparison

Both tools automate Chrome from the command line via the Chrome DevTools Protocol. They share a goal — make browser automation fast and scriptable from a terminal — but take fundamentally different architectural approaches.

## At a Glance

| Dimension | Rodney | Passe |
|-----------|--------|-------|
| **Author** | Simon Willison | Sameer Modha |
| **Language** | Go (single binary) | Python (`uv tool install`) |
| **CDP layer** | [rod](https://github.com/go-rod/rod) Go library | Raw WebSocket (`websockets` only) |
| **Chrome lifecycle** | Managed: `rodney start` / `rodney stop` | Unmanaged: connects to port 9222 or auto-starts |
| **Execution model** | One CLI invocation per action | One invocation runs a full script |
| **Scripting** | Shell composition (`&&`, pipes, loops) | Built-in DSL (one verb per line) |
| **State** | Persistent (`~/.rodney/state.json`) | Stateless (tab created and destroyed per run) |
| **Tab model** | Full multi-tab: list, switch, open, close | Isolated: owns one tab, closes on exit |
| **Content extraction** | `text`, `html`, `attr` (raw DOM) | `read` with 4-stage cascade (trafilatura → Readability.js → innerText) |
| **Device emulation** | Not documented | 6 presets (iPhone, Pixel, iPad, Desktop) |
| **Auth model** | Own headless Chrome (bare profile) | Connects to user's daily-driver Chrome (full auth) |
| **Version** | 0.1.0 (Feb 2026) | Pre-1.0 |
| **License** | Apache 2.0 | — |

## Architecture: Daemon vs Single-Shot

This is the core difference.

**Rodney** runs Chrome as a persistent daemon. `rodney start` launches headless Chrome and writes the WebSocket debug URL to `~/.rodney/state.json`. Every subsequent command (`rodney open`, `rodney click`, `rodney text`) is a separate process that reads the state file, connects via WebSocket, performs one action, prints output, and exits. Browser state (tabs, cookies, navigation history) persists between invocations.

```bash
# Rodney: 5 separate processes, 5 WebSocket connections
rodney start
rodney open https://example.com
rodney click "#login"
rodney input "#email" "user@example.com"
rodney screenshot /tmp/out.png
```

**Passe** is single-shot. `passe run` opens one WebSocket connection, creates a background tab, runs all verbs sequentially, then closes the tab and disconnects. No state file, no daemon. Chrome must already be running (or passe auto-starts a bare instance).

```bash
# Passe: 1 process, 1 WebSocket connection
passe run - <<'EOF'
goto https://example.com
click "#login"
type "#email" "user@example.com"
screenshot /tmp/out.png
EOF
```

**Trade-offs:**

| | Rodney (daemon) | Passe (single-shot) |
|---|---|---|
| Connection overhead | Per command (~50ms each) | Once per script |
| Shell composability | Native (`&&`, pipes, `if`) | Requires wrapping in Bash |
| Error recovery | Natural (next command is independent) | Fatal (script aborts on first error) |
| Tab persistence | Yes — tabs survive between commands | No — tab destroyed on exit |
| State management | Explicit (state file, PID tracking) | None needed |

## Scripting Philosophy

**Rodney** embraces Unix philosophy: each command is a small tool that does one thing. You compose workflows with the shell. Exit codes drive conditionals:

```bash
rodney exists "#cookie-banner" && rodney click "#cookie-banner .reject"
rodney open https://example.com
for sel in h1 h2 h3; do
  rodney text "$sel" 2>/dev/null
done
rodney screenshot /tmp/out.png
```

**Passe** has its own DSL. Verbs are parsed line-by-line with `shlex.split()`. The DSL is purpose-built for browser automation, with verbs like `click-text`, `wait-for`, `click-if`, and `fetch` that encode common patterns:

```bash
passe run - <<'EOF'
goto https://example.com
click-if "#cookie-banner .reject"
wait-for .main-content
read /tmp/content.md
screenshot /tmp/out.png
EOF
```

**Key DSL differences:**

| Pattern | Rodney | Passe |
|---------|--------|-------|
| Click if exists | `rodney exists sel && rodney click sel` | `click-if sel` |
| Click by text | Not available | `click-text "Accept"` |
| Wait for element | `rodney wait sel` | `wait-for sel` |
| Wait for load | `rodney waitload` | `wait-navigation` |
| Wait for stability | `rodney waitstable` | Auto (after `goto`) |
| Extract content | `rodney text sel` | `read` (full markdown extraction) |
| JS execution | `rodney js "expr"` | `eval expr` |
| JS to file | Not available | `eval-to /tmp/out.json expr` |
| JS from file | Not available | `eval-file script.js` |
| Device emulation | Not available | `device "iPhone 14 Pro"` |
| Navigate + extract | `rodney open URL && rodney text body` | `fetch URL` |

## Content Extraction

This is where the tools diverge most.

**Rodney** gives you raw DOM access: `text` returns `textContent`, `html` returns `outerHTML`, `attr` reads attributes. You get exactly what the DOM has. For structured extraction, you'd use `rodney js` with custom JavaScript.

**Passe** has a multi-stage extraction pipeline via `read`:

1. **Content-type sniffing** — JSON, XML, CSV returned raw
2. **Trafilatura** (Python-side) — article/content extraction with structural quality gates
3. **Readability.js + Turndown** (browser-side) — Mozilla's reader mode, converted to markdown
4. **innerText fallback** — raw text as last resort

Passe also handles shadow DOM (flattening web components before extraction), detects thin reads (auth walls, empty pages), and includes diagnostics when extraction fails.

This reflects the tools' different audiences: Rodney is for developers who know what selector to query; Passe is optimized for AI agents that need clean markdown from arbitrary pages.

## Performance Model

**Rodney** pays connection overhead per command. Each invocation: read state file → WebSocket connect → send CDP command → receive result → disconnect. For a 10-step workflow, that's 10 connection round-trips.

**Passe** pays connection overhead once. One WebSocket connection serves all steps. The CLAUDE.md claims 213ms for navigate+screenshot — the speed comes from eliminating per-action overhead.

Neither tool has the MCP tax (no model round-trips per action), so both are dramatically faster than MCP-based browser tools. But passe's single-connection model has an edge for multi-step scripts, while Rodney's per-command model has constant overhead regardless of script length.

## Tab and Session Management

**Rodney** has explicit multi-tab support: `pages` lists tabs, `newpage` opens one, `page N` switches, `closepage N` closes. Tabs persist between commands. The active page index is tracked in state.json.

**Passe** creates one ephemeral tab per `passe run` invocation. It never touches existing tabs. There's no tab switching — if a click opens a new browser tab, passe stays on its own. This is simpler but means you can't orchestrate multi-tab workflows.

## Auth Model

**Rodney** launches its own headless Chrome with `rodney start`. This is a clean browser instance with no cookies or login sessions. To authenticate, you'd need to script the login flow or use `rodney connect` to attach to an existing Chrome.

**Passe** connects to an already-running Chrome on port 9222. If that's the user's daily-driver Chrome (started with `--remote-debugging-port=9222`), passe inherits all cookies, SSO sessions, and login state. This makes authenticated workflows trivial — Chrome *is* the auth layer.

## Feature Matrix

| Feature | Rodney | Passe |
|---------|:------:|:-----:|
| Navigate (goto/open) | Yes | Yes |
| Click (CSS selector) | Yes | Yes |
| Click by visible text | — | Yes |
| Click if exists | Via shell | Yes (verb) |
| Type/input | Yes | Yes (with React detection) |
| Select dropdown | Yes | Yes |
| Hover | Yes | Yes |
| Focus | Yes | — |
| File upload | Yes | — |
| Clear input | Yes | — |
| Screenshot (full page) | Yes | Yes |
| Screenshot (element) | Yes | — |
| Screenshot (fast mode) | — | Yes (JPEG q70) |
| PDF export | Yes | — |
| JS execution | Yes | Yes |
| JS from file | — | Yes |
| JS result to file | — | Yes |
| Content extraction | DOM only | 4-stage cascade |
| Device emulation | — | 6 presets |
| Tab management | Full | Isolated |
| History (back/forward) | Yes | Yes |
| Wait for element | Yes | Yes |
| Wait for load | Yes | Yes |
| Wait for DOM stable | Yes | Yes (auto) |
| Wait for network idle | Yes | — |
| Sleep | Yes | Yes |
| Assertions | Yes (`assert`) | Yes (`assert`) |
| Accessibility tree | Yes | — |
| HMR watch mode | — | Yes |
| Scroll | — | Yes |
| Snapshot (element discovery) | — | Yes |
| Shadow DOM handling | — | Yes (flattening) |
| NDJSON step timing | — | Yes (stderr) |

## When to Use Which

**Choose Rodney when:**
- You want Unix-native composability (pipes, loops, conditionals)
- You need multi-tab orchestration
- You want element screenshots or PDF export
- You need accessibility tree inspection
- You prefer a single Go binary with no Python dependency
- You want to explore pages interactively (command by command)

**Choose Passe when:**
- You're running multi-step workflows and need speed (single connection)
- You need content extraction from arbitrary pages (the `read` cascade)
- You want to leverage an existing authenticated Chrome session
- An AI agent is driving the browser (markdown output, snapshot for discovery)
- You need device emulation
- You're doing HMR-triggered screenshot workflows during development

## Summary

Rodney and Passe occupy the same niche — fast CLI browser automation without MCP overhead — but embody different philosophies. Rodney is a Unix toolkit: small commands, shell composition, persistent state. Passe is a scripting engine: one connection, purpose-built DSL, rich extraction. Rodney is broader (tabs, a11y, PDF); Passe is deeper (extraction cascade, device emulation, shadow DOM, auto-wait intelligence). Both are dramatically faster than MCP-based alternatives for the same reason: they skip the model round-trip per action.
