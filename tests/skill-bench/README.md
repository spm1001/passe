# Skill Benchmark Evals

Eval prompts for benchmarking the **passe skill** (`skills/passe/SKILL.md`) end-to-end. Tests whether a Claude with the skill loaded actually completes browser-automation tasks faster, more reliably, and with fewer tokens than a Claude without the skill.

This is **separate** from `tests/eval/`, which pattern-matches Claude responses for tool-choice hygiene. This benchmark measures **task outcomes**, not response shape.

## Running

This benchmark uses Anthropic's **`skill-creator`** plugin (a Claude Code plugin from `claude-plugins-official`). It is not vendored in this repo — the methodology lives in the plugin and updates with it.

To re-run:

1. Open a Claude Code session with the `skill-creator` skill available.
2. Invoke the skill: "benchmark passe with the evals in `tests/skill-bench/evals.json`".
3. The skill follows its own workflow (see its SKILL.md for details). Output lands in `passe-workspace/iteration-N/` at the repo root.
4. When done, move the iteration's contents into `docs/benchmarks/<YYYY-MM-DD>-skill-eval/` so the historical record stays version-controlled.

## What's in `evals.json`

Three tasks chosen to exercise distinct passe paths:

| ID | Task | Tests |
|---|---|---|
| 0 | Screenshot HN, identify top story | `passe look` / `screenshot` happy path |
| 1 | Get past Spiegel cookie wall | scout-then-act pattern (snapshot before clicking) |
| 2 | Verify httpbin.org/html contains 'Herman Melville' + screenshot proof | `passe check --contains` deploy-verification path |

Each eval has typed assertions: `approach` (used the right verb?), `output` (artifact exists?), `correctness` (right answer?), `efficiency` (didn't fumble the path?), `anti-pattern` (didn't do the wrong thing?).

## When to re-run

- After significant SKILL.md changes (test the new wording actually helps Claudes).
- After major passe verb changes (test the API still produces wins through the skill).
- Before a release if the skill or core verbs changed since the last benchmark.

Compare against the most recent `docs/benchmarks/<date>-skill-eval/benchmark.md`. If pass-rate or token delta regresses meaningfully, the skill (or the verbs) drifted.
