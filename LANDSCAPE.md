# Browser Automation Landscape

A reference for developers comparing browser automation tools in the age of AI agents. Last updated: February 2026.

## The framework

Two axes define the space: **who decides what to do** (you script it vs. the AI figures it out) and **whose browser runs it** (your real Chrome session vs. a managed/sandboxed instance).

```
                You script it              AI figures it out
            ┌──────────────────────┬───────────────────────────┐
  Your      │                      │  Browser-Use              │
  Chrome    │   ★ passe            │  BrowserMCP extension     │
  (real     │                      │  Chrome DevTools MCP      │
  session)  │                      │  Claude in Chrome         │
            ├──────────────────────┼───────────────────────────┤
  Managed   │  Playwright          │  Stagehand / Browserbase  │
  browser   │  Selenium            │  CUA / Operator           │
  (clean)   │                      │  Computer Use / Mariner   │
            └──────────────────────┴───────────────────────────┘
```

**"Your Chrome"** means the browser you use daily — your SSO, your cookies, your logins. No credential management needed. The debug port (9222) binds to localhost only; Chrome 136+ requires a separate user-data-dir to protect main profile credentials.

**"Managed browser"** means a fresh instance — Docker container, cloud VM, sandboxed profile. Clean slate every time. Great for testing and scraping; useless for anything behind a login unless you handle auth separately.

**"You script it"** means the AI (or human) writes the full script upfront. One planning step, then execution at wire speed.

**"AI figures it out"** means the AI decides each action after seeing the result of the previous one. Flexible, but every decision costs a model round-trip.

## The Playwright exodus

Three of the four leading browser-agent frameworks independently dropped Playwright in 2025. The pattern is worth understanding.

**Browser-Use** (August 2025) — published "Closer to the Metal" detailing why:
- Playwright interposes a Node.js relay between the Python client and Chrome, creating a double-RPC hop
- State drifts across three processes (browser, Playwright's Node relay, Python client)
- Specific failures: crashes on `fullPage=True` screenshots exceeding 16,000px, broken cross-origin iframe support, ten distinct tab-crash scenarios hidden by Playwright's abstractions
- Lightpanda benchmark: Playwright generates **326KB of WebSocket messages** for the same scraping task that Puppeteer handles in **11KB** — a 30× wire overhead
- Puppeteer runs **15–20% faster** than Playwright on identical Chromium tasks
- Browser-Use built `cdp-use`, their own typed Python CDP client (223 stars)

**Stagehand v3 / Browserbase** (October 2025):
- "A testing-first framework brings a long tail of APIs and behaviors we don't lean on"
- Memory growth in long-running sessions
- iframe handling demanded direct CDP access
- Migration yielded a **44% speed improvement** on iframe and shadow-root interactions

**Vercel Agent-Browser** — kept Playwright internally but wrapped it in a Rust CLI communicating over Unix sockets:
- ~50ms CLI startup
- Claims **93% context reduction** vs. Playwright MCP's verbose accessibility trees

Microsoft acknowledged the shift: Playwright MCP's README now concedes that "modern coding agents increasingly favor CLI-based workflows" over MCP, and added a CLI+SKILLS mode alongside their MCP server.

The common thread: Playwright was built for test automation. Agents need a thinner, more direct connection to the browser. CDP is that connection.

## CDP-based tools

### Agentic (AI decides each step)

| Tool | Stars | Approach | Key numbers |
|------|-------|----------|-------------|
| **Browser-Use** | ~78,400 | Async Python agent loop, raw CDP via cdp-use | $17M seed (Felicis, YC). 2.3M+ monthly PyPI downloads. 89.1% WebVoyager (GPT-4o). ~3s/step, 68s average task completion (OnlineMind2Web). 6× faster than CUA/Mariner/Claude on same benchmark. |
| **Stagehand v3** | ~20,000 | Four primitives: `act()`, `extract()`, `observe()`, `agent()`. Auto-caching eliminates redundant LLM calls. | Part of Browserbase ($67.5M raised, $300M valuation). Self-healing execution. Server mode supports TypeScript, Python, Go, Java, Ruby, Rust. |
| **Playwright MCP** | ~24,000 | Accessibility tree serialized as YAML, elements get ref IDs (e.g. `e150`). 22 tools exposed. | ~1.1M weekly npm installs, most-installed MCP server. Supports `--cdp-endpoint` for existing sessions (with documented issues). |
| **Chrome DevTools MCP** | ~23,900 | Direct CDP, launched by Addy Osmani (Google). 26 tools exposed. | Unique: performance tracing tools for Core Web Vitals and CrUX data. Chrome 144+ supports auto-connection to running Chrome. |
| **BrowserMCP** | ~5,800 | Chrome extension — runs inside user's browser process. MCP bridge. | No separate browser needed. Extension-based approach. |
| **Agent-Browser** (Vercel) | ~14,000 | Rust CLI wrapping Playwright, Unix socket to Node.js daemon. | ~50ms startup. 93% context reduction vs. Playwright MCP. |
| **NoDriver** | ~3,300 | Minimal CDP, successor to Undetected-Chromedriver. AGPL. | Designed to avoid WebDriver detection vectors. |
| **AgentQL** (TinyFish) | — | Semantic query layer: natural-language selectors like `{ products[] { name, price } }`. | $47M Series A (ICONIQ Capital, August 2025). |
| **Pydoll** | ~6,500 | Python-first CDP client. | Recommended by Browser-Use as Playwright replacement. |
| **Amazon Nova Act** | — | Composable atomic commands. Prioritizes determinism over autonomy. | GA December 2025. >90% reliability on common UI interactions. |

### Scripted (human or AI writes script upfront)

| Tool | Stars | Approach | Key numbers |
|------|-------|----------|-------------|
| **passe** | — | Line-based DSL, single WebSocket, one Bash call. Content extraction built in. | ~20ms/action. 213ms for navigate+screenshot. Zero model round-trips during execution. |

## Pixel-based approaches

These tools work from screenshots rather than the DOM. More general (work on any UI, not just browsers) but slower and less precise.

| Tool | Approach | Key numbers |
|------|----------|-------------|
| **Anthropic Computer Use** | XGA resolution (1024×768), Docker + VNC. October 2024. | 14.9% OSWorld (SOTA at launch). |
| **Claude Cowork** | Desktop agent in Apple Virtualization Framework sandbox. Browser control via Chrome extension. January 2026. | Powered by Opus 4.5. |
| **OpenAI CUA / Operator** | o3-based vision model. January 2025. By July 2025, integrated into ChatGPT as "agent mode". | 58.1% WebArena. 87% WebVoyager. 38.1% OSWorld. |
| **Google Project Mariner** | Started as Chrome extension, moved to cloud VMs. Up to 10 parallel tasks. "Teach & Repeat" workflow. | 83.5% WebVoyager. Available on AI Ultra plan ($249.99/month). |
| **Skyvern** | "Explore then Replay": LLM reasoning on first run, generates deterministic Playwright code for replay. YC S23. | 64.4% WebBench (SOTA for form-filling). Replay is 2.7× cheaper and 2.3× faster. $2.7M seed. |

## AI browsers

Full browser products with AI built in, aimed at end users rather than developers.

| Product | Details |
|---------|---------|
| **ChatGPT Atlas** | Launched October 2025. Full Chromium with custom "OWL" architecture by Ben Goodger (former Chrome engineering lead). Agent mode controls cursor directly. |
| **Perplexity Comet** | July 2025, free October 2025. AI search + background task assistants. |
| **Dia** (The Browser Company) | Raised $128M. Acquired by Atlassian for $610M. |
| **Fellou** | Claims 80% on Online-Mind2Web (self-reported, unverified). Uses Browser-Use under the hood. |

## Cloud browser platforms

Infrastructure for running browsers at scale — the hosting layer beneath many of the tools above.

| Platform | Details |
|----------|---------|
| **Browserbase** | $67.5M raised across 3 rounds (Kleiner Perkins, CRV, Notable Capital). $300M valuation. Serverless containers, 4 vCPUs each, spin up in <3s. 50M sessions in first half of 2025. Contexts API persists cookies across sessions. Angels include Patrick Collison (Stripe) and Guillermo Rauch (Vercel). Pricing: free (1 hr/month), $99/month (500 hrs), custom enterprise. |
| **Steel.dev** | ~6,300 stars. Open source (Apache 2.0). Docker or cloud on Fly.io. Puppeteer + CDP. Sub-second startup, sessions up to 24 hours. |
| **Hyperbrowser** | 10,000+ simultaneous browsers with sub-second launch. Built-in CAPTCHA solving. |

## The MCP browser server ecosystem

At least 12 MCP server implementations for browser control, using four distinct approaches:

| Approach | Examples |
|----------|---------|
| Accessibility tree serialization | Playwright MCP |
| Direct CDP via Puppeteer/custom | Chrome DevTools MCP, executeautomation/mcp-playwright (~5,200 ★), eyalzh/browser-control-mcp (~500 ★), hangwin/mcp-chrome |
| Chrome extension bridge | BrowserMCP |
| Cloud browser API | Browserbase MCP (~3,100 ★), Hyperbrowser MCP (734 ★) |

## The latency math

This is why passe exists. The bottleneck in browser automation is never the browser — it's the model.

### Per-layer latency

| Layer | Typical latency |
|-------|----------------|
| MCP server processing | <10ms |
| Browser action via CDP | 50–500ms |
| Model TTFT (GPT-4o) | ~500ms |
| Model TTFT (Claude Sonnet) | ~1.3–2.0s |
| Model TTFT (reasoning models) | 3–7s+ |
| Processing 100K tokens of context | +500–1,500ms |
| **Per-step cost in agentic loop** | **1.5–6s** |

### Token overhead

- Tool schemas for 15–20 browser tools consume **10,000–15,000 tokens** of context before any page content
- arXiv paper (2511.07426) measured **2×–30× token inflation** vs. baseline chat when using MCP tools
- Playwright MCP exposes 22 tools; Chrome DevTools MCP exposes 26

### End-to-end

| Approach | Navigate + screenshot | 20-step workflow (model time only) |
|----------|----------------------|-----------------------------------|
| Passe | 213ms | One model call (~3–6s) + ~1–5s execution |
| MCP-based (3s/step) | ~12,600ms | ~60s |
| MCP-based (6s/step) | ~12,600ms | ~120s |

Tasks on benchmarks like OnlineMind2Web average 8.5–36 steps. The model time dominates at every scale.

### What passe trades away

Passe's speed comes from a constraint: the AI must plan the full script upfront. When the workflow is known or discoverable (scout-then-act), this is strictly better. When each step genuinely depends on AI interpretation of the result (visual reasoning, unknown page structure, error recovery), agentic tools earn their round-trips.

## The authenticated session question

Using your real Chrome session is powerful — SSO, HttpOnly cookies, saved passwords, extensions — but it has security implications.

**Chrome 136** (March 2025): `--remote-debugging-port` now requires a separate `--user-data-dir`. The separate directory gets its own encryption key. This was a direct response to malware campaigns (WhiteChocolateMacademiaNut, RemoteChromiumPwn) that relaunched Chrome with debug flags to dump cookies via `Network.getAllCookies()`.

**The security model**: the debug port binds to localhost. The risk is local privilege escalation, not remote attack. Chrome classifies remote debugging as a feature, not a vulnerability — no CVEs exist for it.

**How tools handle it**:
- Passe, BrowserMCP, Chrome DevTools MCP: connect to existing Chrome on port 9222
- Browser-Use, Stagehand: support `user_data_dir` / `cdpUrl` parameters
- Playwright MCP: supports `--cdp-endpoint` (documented issues in GitHub #921, #1319)
- Cloud platforms (Browserbase, Steel): Browserbase's Contexts API persists cookies across sessions; Steel uses standard Puppeteer `connect()`

---

*Numbers sourced from GitHub, PyPI, npm, official announcements, and benchmark papers as of February 2026. Star counts and funding figures go stale — check the sources.*
