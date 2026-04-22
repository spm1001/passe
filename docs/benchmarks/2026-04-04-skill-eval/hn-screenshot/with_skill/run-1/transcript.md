# HN Screenshot Task — With Skill

**Date:** 2026-04-04
**Method:** passe skill (SKILL.md read first, then commands)

## Steps

1. **Read the skill file** — `/home/modha/Repos/batterie/passe/skills/passe/SKILL.md` (347 lines). Identified `passe look` as the right command for screenshots (Recipe 2) and `passe fetch` for text extraction (Recipe 1).

2. **Created output directory** — `mkdir -p .../outputs/`

3. **Took screenshot** — `passe look https://news.ycombinator.com`
   - Result: `/tmp/passe-look.jpg` (61KB JPEG), 924ms, 2 steps (goto + screenshot)
   - Chrome 146.0.7680.80 via CDP on localhost:9222

4. **Fetched page content** — `passe fetch https://news.ycombinator.com .../outputs/hn-content.md`
   - HTTP-first attempt failed quality gate (0.25) — escalated to Chrome
   - Trafilatura failed (33% bare pipe lines) — fell back to Readability
   - Result: 678 words extracted, 782ms

5. **Copied screenshot** to outputs directory.

## Commands Used

```bash
passe look https://news.ycombinator.com
passe fetch https://news.ycombinator.com .../outputs/hn-content.md
```

## Result

**Top story:** "Tell HN: Anthropic no longer allowing Claude Code subscriptions to use OpenClaw" — 407 points by firloop, 5 hours ago, 403 comments.

## Outputs

- `outputs/hn-screenshot.jpg` — viewport screenshot of HN front page
- `outputs/hn-content.md` — extracted text content of the page

## Observations

- `passe look` is the simplest path for screenshots — one command, no heredoc needed.
- `passe fetch` tried HTTP-first, failed quality gate, then used Chrome. Two extraction fallbacks (trafilatura -> readability) happened automatically. The quality gate cascade worked as designed.
- Total wall-clock time for both commands: ~1.7 seconds.
