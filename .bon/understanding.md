# Passe — Project Understanding

Passe is a CDP browser automation CLI that connects Claude to Chrome via raw WebSocket. Its 100x speed advantage over MCP-based alternatives comes from eliminating model round-trips — everything happens in a single Bash call. It has become the single web content tool across all Claude sessions; mise dropped its web fetching path to end the "which tool?" confusion.

## Grammar Philosophy

The DSL was overhauled in March 2026 following a usability audit of 3,880 real invocations across 458 sessions. The governing principle: if every Claude writes it a certain way unprompted, that's the correct grammar. A naive-Claude survey (n=43) confirmed model instincts align with `goto` (81%), `wait` (100%), `click "text"` (100%), and `extract` over `read` (100%). Dead verbs with zero real usage (`click-if`, `wait-navigation`, `click-text`) were removed. `wait` collapsed three verbs into one (sleep/selector/network-idle by argument shape). All user-facing timeouts are seconds, never milliseconds.

The gap between "taught" and "used" is the kill signal for grammar decisions. `~/Taildrive/passe-usability.txt` is the ground truth. `snapshot` (25 uses) survived because scout-then-act works when taught — it's the rare case where explicit instruction changes behavior.

## Extraction Architecture

Content extraction follows a four-layer escalation: content-type sniff, framework shortcuts (Next.js `__NEXT_DATA__`, Apple docs JSON API), HTTP fetch with trafilatura + composite quality gate, then Chrome CDP as last resort. The HTTP fast-path in `cmd_fetch` fires before `connect()` — if HTTP succeeds, Chrome is never touched. This covers ~87% of pages in 300-1500ms.

Trafilatura is the benchmark leader (F1 0.958). The readability-lxml + markdownify middle tier was tested (31 fixtures, 7 categories) and scored 0.648 vs trafilatura's 0.846 — it loses on every category. Don't re-propose it; the data is in `tests/bench/`. Revisit only if a specific page type emerges where readability wins.

The quality gate uses composite scoring: word count, stop words ratio (jusText thresholds), link density (Boilerpipe's 0.33 threshold), text-to-HTML ratio, and paywall/CAPTCHA/cookie-consent detection. Thresholds (0.35 composite, 50 min words, 0.20 stop words, 0.33 link density) were tuned against the corpus once — two bugs found (CAPTCHA false positives on Wikipedia, stop words penalty on large technical docs). A systematic threshold sweep using the bench harness is possible but hasn't been done.

## Testing Landmine

When testing `cmd_fetch`, always mock `passe.fastpath.try_http_fetch` to return `None` — otherwise the test makes real HTTP calls and the fast-path may short-circuit before reaching the code under test.

## The Integration Testing Lesson

Unit tests that bypass the real transport layer give false confidence for async WebSocket code. The daemon passed 30 unit tests while deadlocking on first real use — `send()` waited for CDP responses via futures, but the receiver task that dispatches responses wasn't running yet. The tests passed because they called `_dispatch()` directly, never exercising the send-receive-future resolution cycle. The lesson isn't "unit tests are bad" — they caught real bugs in filtering, request assembly, rotation, and reconnection logic. The lesson is: for code where the architecture IS the concurrency (background tasks, message routing, lifecycle ordering), integration tests against the real dependency are the only tests that matter for "does it actually work."

## CDP Tab Discovery: Two Paths

Chrome's CDP has two tab discovery mechanisms: the `/json` HTTP endpoint (always works, returns all targets) and `Target.getTargets` via WebSocket (requires `Target.setDiscoverTargets` to be called first on the connection). On fresh connections — which is every passe invocation — `Target.getTargets` returns empty. This doesn't matter on local headless Chromium (which behaves differently), only on remote Chrome via tailscale. The daemon gets this right because it calls `setDiscoverTargets` during its persistent connection setup. For short-lived passe commands, the `/json` HTTP endpoint is the reliable path. The key names differ: HTTP uses `id`, CDP uses `targetId` — any unified helper must normalize.

## Module Ownership

`parser.py` owns verb vocabulary and aliases. `runner.py` owns the dispatch loop — aliases resolved in parser mean no runner changes needed. `commands.py` owns tab lifecycle (keep_tab, close_tab, flash timers). `cli.py` owns the entry point and `-c` flag parsing. `_libs.py` holds all JS that runs inside Chrome. `log_daemon.py` owns the continuous capture daemon — its own WebSocket handler, independent of CDPClient. `log_query.py` owns JSONL reading/formatting with zero passe imports. `connection.py` owns `discover_chrome()` (used by both `connect()` and the daemon) plus Chrome auto-launch. Dependency graph is a strict DAG with no circular imports.

## OOPiF Iframe Targeting (March 2026)

Chrome exposes cross-origin iframes (OOPiFs) as first-class CDP targets in `/json/list` with `type: "iframe"`, their own `targetId`, `parentId`, and `webSocketDebuggerUrl`. You attach via `Target.attachToTarget` on the same browser WebSocket — both parent and iframe sessions coexist, and you swap `sessionId` to toggle context. Everything works except `Page.captureScreenshot`, which Chrome restricts to top-level targets only. The parentId chain can be deeply nested (PowerPoint tab → intermediate Office iframe → Claude plugin iframe), so walking up to the root page requires iterating. Same-origin iframes never appear in `/json/list` — they share the parent's process and are reachable via `eval` with `contentDocument`. Headless Chrome with `--no-sandbox` doesn't produce OOPiFs at all, so testing iframe targeting requires a real Chrome profile with site isolation enabled.

## Chrome Log Absorption (March 2026)

skill-chrome-log (a separate repo) provides continuous background network capture across all Chrome tabs — always-on recording of HTTP traffic to JSONL, with CLI query tools and an HTML dashboard. It's been absorbed into passe as `passe log` subcommands, making passe the single Chrome tool.

The daemon (`log_daemon.py`) is architecturally distinct from CDPClient. CDPClient is single-session request-response with one-shot event waiters. The daemon is multi-session continuous streaming with `Target.setAutoAttach` (flattened sessions) routing events from all tabs through one WebSocket. These are different shapes — the daemon has its own WebSocket handler, reusing only `discover_chrome()` from `connection.py`.

The daemon is built and smoke-tested against real Chrome. Key design: `@_handles('CDP.method')` decorator for self-documenting handler registration, separate `records`/`meta` dicts in `RequestStore` to prevent internal fields leaking into JSONL, `asyncio.to_thread(discover_chrome)` to avoid blocking the event loop during reconnection, and `_log_task_error` done callbacks on all fire-and-forget tasks.

Critical pattern — receiver before send: The daemon's `_connect_and_attach()` must start the `_receive_messages` background task BEFORE sending any CDP commands. `send()` creates futures that only resolve when the receiver dispatches responses. Without the receiver running, `send()` deadlocks. This was caught by smoke testing.
