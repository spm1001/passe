# Passe Skill Benchmark — 2026-04-04

End-to-end benchmark of the **passe skill** vs. no skill, run via Anthropic's `skill-creator` plugin against the eval set in `tests/skill-bench/evals.json`.

## Headline result

| Metric | With Skill | Without Skill | Delta |
|---|---|---|---|
| Pass rate | 100% ± 0% | 83% ± 29% | **+17%** |
| Wall-clock time | 50.9s ± 16.3s | 134.3s ± 151.7s | **−83.4s (≈2.6× faster)** |
| Tokens | 23,740 ± 4,300 | 25,515 ± 8,784 | −1,775 |

3 evals × 3 runs × 2 configurations = 18 task executions. See `benchmark.md` for the formatted summary, `benchmark.json` for raw per-run data.

## What's here

```
2026-04-04-skill-eval/
├── README.md          # this file
├── benchmark.md       # formatted summary
├── benchmark.json     # per-run timings, tokens, assertions
├── hn-screenshot/     # eval 0: screenshot HN, identify top story
│   ├── with_skill/run-{1,2,3}/
│   └── without_skill/run-{1,2,3}/
├── spiegel-cookie/    # eval 1: get past Spiegel cookie wall
└── httpbin-verify/    # eval 2: verify httpbin.org/html contains 'Herman Melville'
```

Each `run-N/` directory contains: `transcript.md` (Claude's reasoning), `timing.json` (wall-clock + token counts), `grading.json` (assertion pass/fail with evidence), and `outputs/` (screenshots, extracted text, etc.).

## How this was generated

Anthropic's `skill-creator` Claude Code plugin. Methodology lives in that plugin's SKILL.md (see `~/.claude/plugins/cache/claude-plugins-official/skill-creator/<sha>/skills/skill-creator/`). The runner, grader subagent, and aggregation script (`aggregate_benchmark.py`) are all in the plugin — not vendored here, because they update with the plugin and we don't want maintenance drift.

To reproduce or extend: see `tests/skill-bench/README.md`.

## Notes on this iteration

- **Why pass-rate jumped 17%:** without the skill, Claude sometimes used `curl` for screenshot tasks (failing the assertion that passe verbs were used) or guessed cookie-button text without scouting (failing the anti-pattern assertion).
- **Why time dropped 2.6×:** the skill teaches `passe look` for screenshots and the scout-then-act pattern for unknowns. Without it, Claude trial-and-errors.
- **Token savings are modest** because the skill itself adds context. The win is in fewer wasted tool calls on the actual task.

## Variance

The "without skill" stddev is high (151.7s on time, 8.8k on tokens) because failed runs took longer trying to recover. The "with skill" runs are tightly clustered — the skill leads Claude down the same path each time.
