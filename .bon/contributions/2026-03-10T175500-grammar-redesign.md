## Grammar redesign: going with the weights (Mar 2026)

Usability audit across 3,880 invocations (458 sessions, 3 machines) revealed that passe's 12 shipped DSL-layer improvements (verb hints, self-healing, explain mode) don't help when Claudes fail at the invocation layer. The invocation layer is silent when it should scream. The fundamental insight: Claudes write Playwright/Puppeteer idioms from their training weights. Instead of teaching Claudes our grammar, adopt theirs.

Key architectural notes for the implementer:
- `parser.py` owns KNOWN_VERBS, VERB_SUGGESTIONS, split_inline(), parse_script(). This is where verb aliases go.
- `runner.py` owns run_script() with the giant verb→function dispatch. Aliases resolved in parser mean no runner changes needed.
- `commands.py` owns cmd_run() — tab lifecycle lives here (keep_tab, close_tab, flash timers). The tabs-open-by-default change is here.
- `cli.py` owns main() — the -c flag parsing and file-vs-inline detection lives here.
- `wait` conversion (ms→seconds) touches runner.py line 295: `asyncio.sleep(int(args[0]) / 1000)` and also wait-for (line 297-298) and wait-idle (line 299-300) which take ms timeouts.
