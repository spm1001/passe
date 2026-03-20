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

## Touch/Mobile Work

CDP `Input.dispatchTouchEvent` hangs through flattened sessions. The established pattern is JS `TouchEvent` synthesis — 3.7ms, reliable. `tap` and `swipe` verbs use this. Touch work (long-press, off-screen elements, PointerEvent support) is the current frontier under the mobile UI outcome.

## Module Ownership

`parser.py` owns verb vocabulary and aliases. `runner.py` owns the dispatch loop — aliases resolved in parser mean no runner changes needed. `commands.py` owns tab lifecycle (keep_tab, close_tab, flash timers). `cli.py` owns the entry point and `-c` flag parsing. `_libs.py` holds all JS that runs inside Chrome. Dependency graph is a strict DAG with no circular imports.

## Chrome Log Absorption (March 2026)

skill-chrome-log (a separate repo) provides continuous background network capture across all Chrome tabs — always-on recording of HTTP traffic to JSONL, with CLI query tools and an HTML dashboard. It's being absorbed into passe as `passe log` subcommands, making passe the single Chrome tool.

The daemon is architecturally distinct from CDPClient. CDPClient is single-session request-response with one-shot event waiters. The daemon is multi-session continuous streaming with `Target.setAutoAttach` (flattened sessions) routing events from all tabs through one WebSocket. These are different shapes — the daemon gets its own WebSocket handler in `log_daemon.py`, reusing only `discover_chrome()` from `connection.py` for Chrome discovery.

Key capability from chrome-log worth preserving: request assembly (correlating 4-5 CDP events per request into one complete record), analytics/tracking filtering, body capture with size limits, and the CLI query tools (tail/list/show/clear). The HTML dashboard is dropped — CLI covers it. launchd management is replaced by systemd (passe's primary home is now Linux/kube).

New capability not in chrome-log: reconnection with exponential backoff for tailscale resilience (chrome-log just exits on disconnect), and the daemon works on both local headless Chrome and remote Mac Chrome via tailscale. See `references/chrome-log-absorption.md` for the full design doc including JSONL schema, DAG placement, and gotchas.
