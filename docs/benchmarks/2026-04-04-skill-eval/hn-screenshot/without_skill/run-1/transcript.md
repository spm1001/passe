# Transcript: HN Screenshot (without skill)

**Date:** 2026-04-04
**Approach:** Direct use of `passe` CLI without loading the passe skill.

## Steps

1. **Checked passe availability** — `which passe` confirmed it at `~/.local/bin/passe`.
2. **Checked Chrome connection** — `passe status` confirmed Chrome/146.0.7680.80 reachable on localhost:9222, 25 tabs open.
3. **Took screenshot** — `passe look https://news.ycombinator.com <output-path>` completed in 422ms, saved 61KB PNG.
4. **Fetched page text** — `passe fetch https://news.ycombinator.com` extracted readable content (678 words) via Readability fallback after trafilatura quality gate failed.
5. **Viewed screenshot** — Used Read tool to visually confirm the page rendered correctly.
6. **Saved top story summary** — Wrote `hn-top-story.txt` with extracted details.

## Result

The top story is:

> **Tell HN: Anthropic no longer allowing Claude Code subscriptions to use OpenClaw**
> 408 points | by firloop | 5 hours ago | 403 comments

## Tools used

- `passe status` — connection check
- `passe look` — navigate + screenshot
- `passe fetch` — navigate + extract text
- Read tool — view screenshot image

## Observations

- `passe look` is fast (422ms) and produces a clean screenshot in one command.
- `passe fetch` hit a quality gate failure on HN (trafilatura scored 0.25, 33% bare pipe lines) and fell back to Readability, which worked fine.
- No skill loading was needed for basic screenshot + text extraction.
