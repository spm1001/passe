# Passe — Project Understanding

Passe is a CDP browser automation CLI that connects Claude to Chrome via raw WebSocket. Its 100x speed advantage over MCP-based alternatives comes from eliminating model round-trips — everything happens in a single Bash call. It has become the single web content tool across all Claude sessions; mise dropped its web fetching path to end the "which tool?" confusion.

**Not the browser appliance — that's `passe-partout`.** The logged-in, bot-evading *appliance* (real Chrome on kube's GPU + the `passe-kube-tunnel` user service + profiles, reached at `localhost:9222`) lives in a SEPARATE repo, `spm1001/passe-partout`. This repo is the CLI *tool* only — verbs, the DSL, extraction/`fetch`, the log daemon. Decision rule: changing how the `passe` *command* behaves → here; changing the *browser* it drives, where it runs, or what it's logged into → `passe-partout`. (A session that opened `passe` expecting the appliance burned a lot of time on 2026-06-20.)

## Grammar Philosophy

The DSL was overhauled in March 2026 following a usability audit of 3,880 real invocations across 458 sessions. The governing principle: if every Claude writes it a certain way unprompted, that's the correct grammar. A naive-Claude survey (n=43) confirmed model instincts align with `goto` (81%), `wait` (100%), `click "text"` (100%), and `extract` over `read` (100%). Dead verbs with zero real usage (`click-if`, `wait-navigation`, `click-text`) were removed. `wait` collapsed three verbs into one (sleep/selector/network-idle by argument shape). All user-facing timeouts are seconds, never milliseconds.

The gap between "taught" and "used" is the kill signal for grammar decisions. The raw audit file lived at `~/Taildrive/passe-usability.txt` — Taildrive was retired 2026-07-07 and the file's new home (if any) is unrecorded, so the audit's conclusions as written here are what survives. `snapshot` (25 uses) survived because scout-then-act works when taught — it's the rare case where explicit instruction changes behavior.

## Extraction Architecture

Content extraction follows a four-layer escalation: content-type sniff, framework shortcuts (Next.js `__NEXT_DATA__`, Apple docs JSON API), HTTP fetch with trafilatura + composite quality gate, then Chrome CDP as last resort. The HTTP fast-path in `cmd_fetch` fires before `connect()` — if HTTP succeeds, Chrome is never touched. This covers ~87% of pages in 300-1500ms.

The markdown-source probe (passe-nuguza + passe-kojimi, 2026-07-21) sits inside the fast-path: pages advertising `<link rel="alternate" type="text/markdown">` (Mintlify convention) get their `.md` sibling fetched directly — canonical source beats any extractor. On docs-shaped URLs (`docs.` host or `/docs/` in path) and escalation paths (SPA shell, empty extraction, gate failure), `_run_markdown_probe` climbs a three-rung ladder: on-disk llms.txt index lookup (exact, free), `URL.md` sibling guess, then root `/llms.txt` fetch-and-index. The index rung is what rescues `.html` pages with `.md` twins (`_page_key` strips `.html`/`.htm` when matching) — the one shape guessing can never find. State: 7-day host cache (`~/.passe/md-hosts.json`, `PROBE_CACHE_PATH` patchable in tests) plus per-host parsed indexes (`~/.passe/llms-index/<host>.json`, `LLMS_INDEX_DIR` patchable); an llms-serving host stays probe-eligible even when one page misses (only cache False on hosts with neither). Parser note: the entry regex's leading boundary must be `(?:^|[\s(<])` — a plain `\b` can't match between `(` and `/`, which silently drops all root-relative entries (caught by test, 2026-07-21). Validated against the real platform.claude.com file: 541/541 entries. Acceptance is guarded (200 + markdown/plain content-type + body not an HTML shell + ≥20 words) because SPAs serve their shell on every path. Landscape as checked live 2026-07-21: code.claude.com and mintlify.com advertise; **platform.claude.com serves siblings unadvertised** (Sameer caught this after the first advertised-only cut shipped — the docs-shaped guess exists because of it); docs.anthropic.com 301s to platform.claude.com. Why unadvertised isn't baffling: the per-page `<link rel="alternate" type="text/markdown">` tag is a *Mintlify* extra, not part of the llms.txt spec — platform.claude.com is a custom Next.js build that implements the spec as written (root `/llms.txt`, 541 .md links, 56KB; `/docs/llms.txt` 308s to it). Root llms.txt is thus a host-level discovery channel passe doesn't read yet (passe-kojimi). Known miss: guessed URLs append `.md` to the whole path, so `page.html` probes `page.html.md` not `page.md` — no observed site needs the swap yet.

Trafilatura is the benchmark leader (F1 0.958). The readability-lxml + markdownify middle tier was tested (31 fixtures, 7 categories) and scored 0.648 vs trafilatura's 0.846 — it loses on every category. Don't re-propose it; the data is in `tests/bench/`. Revisit only if a specific page type emerges where readability wins.

Known trafilatura failure mode (passe-lajesa, 2026-05-20): on pages where `<pre><code>` elements exist in the DOM but are empty (Angular `<app-code-snippet>`-style components that render code via syntax-highlighter side-effects, or hold it in component state), trafilatura silently emits nothing for those blocks — no warning. The structural quality gate counts pipe-table rows and code fences and falls back to Readability if structure is lost, but empty-`<code>` is *not* a structural drop — trafilatura "correctly" extracted nothing from empty elements. The deeper recipe for documentation SPAs is `capture --bodies` to find the source `.md`/`.json` the SPA fetches, not better DOM extraction. The Antigravity scrape took 5 seconds via `/assets/docs/<section>/<page>.md` after 30 minutes of failed DOM-based attempts.

The quality gate uses composite scoring: word count, stop words ratio (jusText thresholds), link density (Boilerpipe's 0.33 threshold), text-to-HTML ratio, and paywall/CAPTCHA/cookie-consent detection. Thresholds (0.35 composite, 50 min words, 0.20 stop words, 0.33 link density) were tuned against the corpus once — two bugs found (CAPTCHA false positives on Wikipedia, stop words penalty on large technical docs). A systematic threshold sweep using the bench harness is possible but hasn't been done.

## Testing Landmines

When testing `cmd_fetch`, always mock `passe.fastpath.try_http_fetch` to return `None` — otherwise the test makes real HTTP calls and the fast-path may short-circuit before reaching the code under test.

Integration tests using `BaseHTTPRequestHandler` will deadlock on shutdown if Chrome holds keep-alive connections. Fix: set `timeout = 2` on the handler class — `StreamRequestHandler.setup` calls `settimeout` on the socket, and `handle_one_request` catches `TimeoutError`.

## The Integration Testing Lesson

Unit tests that bypass the real transport layer give false confidence for async WebSocket code. The daemon passed 30 unit tests while deadlocking on first real use — `send()` waited for CDP responses via futures, but the receiver task that dispatches responses wasn't running yet. The tests passed because they called `_dispatch()` directly, never exercising the send-receive-future resolution cycle. The lesson: for code where the architecture IS the concurrency (background tasks, message routing, lifecycle ordering), integration tests against the real dependency are the only tests that matter for "does it actually work."

## CDP Tab Discovery: Two Paths

Chrome's CDP has two tab discovery mechanisms: the `/json` HTTP endpoint (always works, returns all targets) and `Target.getTargets` via WebSocket (requires `Target.setDiscoverTargets` to be called first on the connection). On fresh connections — which is every passe invocation — `Target.getTargets` returns empty. This doesn't matter on local headless Chromium (which behaves differently), only on remote Chrome via tailscale. The daemon gets this right because it calls `setDiscoverTargets` during its persistent connection setup. For short-lived passe commands, the `/json` HTTP endpoint is the reliable path. The key names differ: HTTP uses `id`, CDP uses `targetId` — any unified helper must normalize.

## Accessibility Tree (ax-tree)

The CDP Accessibility domain (`getFullAXTree`) returns the browser's computed semantic tree — roles, names, values — with transparent node collapsing. `queryAXTree` (server-side filtering) hangs on Chrome 146; client-side filtering of the full tree is fast enough (<100ms on GitHub, <400ms on Wikipedia). All Accessibility domain calls respect CDP session scoping in cross-origin iframes.

`ax-tree --compact` strips text-leaf nodes (27-74% reduction). The real value is signal density: actionable node proportion jumps from ~12% to 18-45%. Wikipedia goes from 12% actionable to 45%. Text-heavy pages benefit most; structure-heavy sites (Guardian, BBC) barely change. The <100 node target from the original brief was unrealistic and the wrong metric — compact makes trees useful for navigation, not small.

The ax-tree verbs complement `snapshot`: snapshot gives CSS selectors for interaction, ax-tree gives semantic understanding for page comprehension and accessibility-aware element discovery.

`--flat-refs` (passe-cosapu, 2026-07-21, the kuri absorption) filters to interactive roles, assigns e0..eN in document order, and persists {ref: backendDOMNodeId} to `~/.passe/refs/<tab_id>.json` (`refcache.py`, no passe imports — both verb modules use it without widening the DAG). click/type/hover resolve eN via DOM.resolveNode → Runtime.callFunctionOn with scrollIntoView. Design deviations from the brief, each deliberate: (1) cache invalidation lives in do_navigate/do_back/do_forward, not a Page lifecycle event — every passe navigation passes through them, no event plumbing needed; SPA client-side navigations are covered by the stale-ref error instead. (2) The runner's smart-click dispatch needed a ref guard — 'e1' has no CSS chars and would otherwise TEXT-click the literal string 'e1' (the value-carrying seam; there's a test). (3) attach_to_first_page/attach_to_visible_page now set _target_id (they never did), which the per-tab cache requires. Sharp edge discovered during live verify: `--reuse-tab` without a goto attaches to the FIRST non-chrome tab — on a shared browser (tube) that can be the human's live tab; the cross-invocation refs flow wants deterministic tab targeting (filed as a follow-up bon).

## Connection Error Architecture

The connection failure root cause was `sys.exit(1)` in `connection.py`, not inadequate error messages. When passe killed the process on connection failure, Claude had no chance to reason about alternatives. Replacing `sys.exit` with `ChromeConnectionError` (a `ConnectionError` subclass) carrying structured diagnostic fields (endpoint, reason, alternatives) lets the CLI's `_run()` catch it and print parseable output. The `[passe:connection]` and `[passe:status]` prefixed formats are now implicit API surface — Claude pattern-matches on them in SKILL.md troubleshooting guidance. Lazy imports between the four verb modules prevent circular import issues — `do_eval` is the most cross-referenced function.

## Eval Harness

The eval harness in `tests/eval/` tests whether Claudes use passe correctly — it's a Claude behaviour test, not a unit test suite. Key finding: connection_error scenarios are the weak spot. Sonnet fires `passe look` without considering connection context 80% of the time when told "Mac is closed." Improvements should focus on making errors Claude-actionable. Subtle methodology finding: putting passe context in the API system param vs in the user message produces different Sonnet behaviour, suggesting SKILL.md positioning matters as much as content.

## SKILL.md Maintenance

The skill-forge lint and CSO scorer optimise for different things and can conflict. Removing the MANDATORY gate from the description (as the Anthropic reviewer suggested) dropped CSO from 90 to 61. The gate is needed for discovery — the instruction shard only fires if passe is already installed. Keep MANDATORY BEFORE in the description; soften tone elsewhere. Lint cares about section headings (When to Use, Anti-Patterns); the cookbook's existing sections serve the same role but need the expected heading names.

## Module Ownership

`parser.py` owns verb vocabulary and aliases. `runner.py` owns the dispatch loop — aliases resolved in parser mean no runner changes needed. `commands.py` owns tab lifecycle (keep_tab, close_tab, flash timers). `cli.py` owns the entry point and `-c` flag parsing. `_libs.py` holds all JS that runs inside Chrome. `log_daemon.py` owns the continuous capture daemon — its own WebSocket handler, independent of CDPClient. `log_query.py` owns JSONL reading/formatting with zero passe imports. `connection.py` owns `discover_chrome()` (used by both `connect()` and the daemon) plus Chrome auto-launch. Dependency graph is a strict DAG with no circular imports.

## OOPiF Iframe Targeting (March 2026)

Chrome exposes cross-origin iframes (OOPiFs) as first-class CDP targets in `/json/list` with `type: "iframe"`, their own `targetId`, `parentId`, and `webSocketDebuggerUrl`. You attach via `Target.attachToTarget` on the same browser WebSocket — both parent and iframe sessions coexist, and you swap `sessionId` to toggle context. Everything works except `Page.captureScreenshot`, which Chrome restricts to top-level targets only. Same-origin iframes never appear in `/json/list` — they share the parent's process and are reachable via `eval` with `contentDocument`. Headless Chrome with `--no-sandbox` doesn't produce OOPiFs at all, so testing iframe targeting requires a real Chrome profile with site isolation enabled.

## Chrome Log Absorption (March 2026)

The daemon (`log_daemon.py`) is architecturally distinct from CDPClient. CDPClient is single-session request-response with one-shot event waiters. The daemon is multi-session continuous streaming with `Target.setAutoAttach` (flattened sessions) routing events from all tabs through one WebSocket. These are different shapes — the daemon has its own WebSocket handler, reusing only `discover_chrome()` from `connection.py`.

Critical pattern — receiver before send: The daemon's `_connect_and_attach()` must start the `_receive_messages` background task BEFORE sending any CDP commands. `send()` creates futures that only resolve when the receiver dispatches responses. Without the receiver running, `send()` deadlocks.

## Infrastructure (April 2026)

SOCKS tunnel (`socks-kube-tunnel.service`) routes headless Chrome through kube's residential IP — solves IP-based blocking. Health-check timer (5 min interval) auto-restarts on failure. But `--proxy-server` has NO fallback — if kube is down, all Chrome browsing fails. PAC files don't work in `--headless=new`. Escape hatch: restore the backup service file without proxy.

Medium, StackOverflow, Reddit still 403 even with residential IP — headless detection (not IP blocking) is the real remaining problem. Filed as passe-depeni.

## External Tool Comparisons (April 2026)

**Kuri evaluation.** Kuri (`github.com/justrach/kuri`) is a Zig CDP browser CLI in passe's exact lane. We evaluated it live on hezza. The headline HTTP server is broken on Linux (managed Chrome zombies because the binary search misses `/usr/bin/chromium`; even with `CDP_URL` set the bridge can't reach it). The released binary lags its source. Where it shines: `kuri-agent snap --interactive` returns flat `[{"ref":"e0","role":"link","name":"X"}]` JSON — a much better agent token shape than passe's nested ax-tree — and `js/stealth.js` is a tidy reference implementation for Phase 1 of `passe-depeni`.

**Decision: compete by absorption, not replacement.** Three things worth lifting: the flat-refs output shape (with a session ref-cache so `click e7` works between calls), the stealth-script injection pattern, and a bot-block detector heuristic on `goto`. Don't fork Zig; we don't write it, we don't want to maintain a CDP/WS/HTTP-server stack, and passe has months of depth (trafilatura, log daemon, frame, fast-path) that's impractical to reverse-port. The principle: passe's edge is depth in our own ecosystem; lift good shapes from peers, leave the runtime alone.

## Ergonomic Principle (April 2026)

Passe is wide and stateless-per-call. That's the right design for the speed claim — every action happens in one Bash call without model round-trips. But it pushes orchestration onto the writer, and the writer is often a Claude that reaches for `passe run -c '...'` when the right answer is a one-shot subcommand. The cost of width shows up as Claudes stumbling on which path applies.

Subcommands (`fetch`, `look`, `check`, `screenshot`, `eval`, `capture`, `tabs`) are the path of least resistance for atomic agent operations. `passe run` is for genuinely multi-step compositions. When verbs have analogous subcommand forms, the cookbook should lead with the subcommand and treat `run` as the advanced path. "Did you mean?" hints, per-verb `--help`, and SKILL.md ordering are all surfaces where this principle gets enforced or eroded.

Compared to kuri's stateful CLI (`use → go → snap → click eN`), passe's atomic-per-call model is faster but harder to think in. The mitigation isn't to abandon the model — it's to make the obvious path the right path more often.

## Portfolio status (2026-07-22)

Active again. The 2026-07-21 overnight burst shipped six items in one session — lesohu (scheme-less --cdp), nuguza (markdown probe), kojimi (llms.txt ladder), nopiku (fast-path reasons), bovunu (Python 3.14 fixes + CI matrix 3.11/3.14 + all 7 security alerts cleared), cosapu (flat-refs + eN targeting) — each committed, live-verified, and closed individually. The framing stands: passe is part of "making it easy for Claude to read stuff on my behalf, including stuff gated by Turnstile or similar hostile tech"; passe-partout (two backends since 2026-07-21: kube fingerprint specialist + tube everyday browser) is the same thread. Freshest resumable threads: ropuze (empty-pre warning, thinking done) and ketome (--reuse-tab targeting hazard).
