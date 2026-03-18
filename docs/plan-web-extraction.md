# Plan: Passe as the single web content tool

**Outcome:** passe-baropo
**Date:** 2026-03-13
**Context:** Conversation between Sameer and Claude exploring how to unify web content
extraction across mise and passe. Includes Deep Research findings on extraction libraries
and quality gate design.

## Problem

Claudes have too many web content tools: mise fetch, passe fetch, curl, WebFetch (disabled).
They get confused. Mise's web path is a weaker copy of passe's extraction pipeline — it even
shells out to passe as a fallback. Meanwhile passe has the real muscle (Chrome CDP, shadow DOM,
4-stage extraction cascade) but no fast HTTP path.

## Decision

- **Passe fetch becomes the single web content tool.** One entry point for Claudes.
- **Mise drops web fetching entirely.** Mise is Workspace-only (Drive, Gmail).
- **Passe gets an HTTP fast-path** before Chrome, with a quality gate to decide when to escalate.

## Architecture: Two-tier escalation (revised 2026-03-14)

Bench results (31 fixtures, 7 categories) showed readability+markdownify (0.648)
doesn't outperform trafilatura (0.846) on any category. The original four-layer
design simplifies to two tiers with framework shortcuts:

```
Tier 0: Content-type sniff + shortcuts   (~0-200ms)
  JSON/XML/CSV/plain text → return raw (already in passe do_read)
  __NEXT_DATA__ → parse JSON directly (Next.js sites)
  Apple docs → structured JSON API (already in passe do_read)
  Empty SPA shell detected → skip to Tier 2 immediately

Tier 1: HTTP + trafilatura              (~300-500ms)
  httpx GET → trafilatura (F1 0.958, benchmark leader)
  composite quality gate decides: good enough? → return
  quality gate fails? → fall through to Tier 2

Tier 2: Chrome CDP                      (~3-10s)
  existing passe pipeline, unchanged
  shadow DOM flattening, Readability.js+Turndown.js, full cascade
  uses Chrome Passe's real sessions/cookies for auth
```

### Insertion point in code

The HTTP fast-path goes in `cmd_fetch` (commands.py) **before the `connect()` context
manager**. If HTTP succeeds, Chrome is never touched — no WebSocket, no tab, no overhead.

```python
async def cmd_fetch(url, path, source, device, dpr):
    # --- HTTP FAST-PATH (new) ---
    if not device and source not in ('readability', 'innertext'):
        result = try_http_fetch(url, source)
        if result and result.quality_score > THRESHOLD:
            emit and return  # never touched Chrome

    # --- CHROME FALLBACK (existing, unchanged) ---
    async with connect() as (client, conn_info):
        tab = await client.create_tab()
        ...
```

## Quality gate design

The quality gate is the novel engineering. Research (Deep Research brief, 2026-03-13)
identified these signals with concrete thresholds:

### Composite scoring

Multiply penalty factors. Reject below 0.3-0.5.

| Signal | Threshold | Penalty | Source |
|--------|-----------|---------|--------|
| Word count | < 50 words | → 0.0 (instant reject) | trafilatura internal: 250 chars |
| Word count | < 100 words | × 0.3 | research |
| Stop words ratio | < 20% | × 0.7 | jusText: content > 30%, boilerplate < 20% |
| Link density | > 0.33 | × 0.5 | Boilerpipe paper: 87.4% F1 with this alone |
| Text-to-HTML ratio | < 10% | × 0.5 | Bevendorff et al. 2023 |
| Table/code loss | Present in HTML, absent in output | × 0.5 | passe already does this in Stage 1.5 |
| Paywall detected | Keywords + short text | × 0.2 | pattern list in mise's adapter |
| CAPTCHA detected | cf-turnstile, recaptcha etc | × 0.1 | pattern list in mise's adapter |
| Cookie consent capture | Short text + cookie keywords | × 0.5 | Rasaii et al. 99% accuracy |
| High repetition | — | × 0.5 | research |

### Pattern detection

Migrate from mise's adapter (which has good pattern lists):
- Paywall: "subscribe to continue", "premium content", "members only", Schema.org isAccessibleForFree
- CAPTCHA: cf-challenge, challenge-running, g-recaptcha, hcaptcha, cf-turnstile
- Cookie consent: cookie-banner, consent-dialog, gdpr-, cc-banner
- Login redirect: /login, /signin, /auth, /sso, /oauth in redirect URL
- JS framework: empty <div id="root">, <div id="app">, <app-root>, <noscript>

## __NEXT_DATA__ shortcut

Next.js sites embed pre-rendered page data in `<script id="__NEXT_DATA__">`. This is
extractable from raw HTTP without trafilatura or Chrome. Parse the JSON, extract the
page props. Next.js is extremely common — this is a significant speed win.

Mise already detects `__NEXT_DATA__` as a JS framework signal (to escalate to browser).
The insight from the research: don't escalate — extract directly.

## readability-lxml middle tier — DEPRIORITISED

Bench results (2026-03-14) showed readability+markdownify scored 0.648 overall vs
trafilatura's 0.846. It didn't outperform trafilatura on any of the 7 tested categories.
Not worth the added complexity. Escalation goes straight from trafilatura to Chrome.

Revisit only if a specific page type is found where readability wins and trafilatura loses.

## Semantic exit codes

| Code | Meaning |
|------|---------|
| 0 | Good content (HTTP or Chrome) |
| 1 | Thin/degraded — agent should assess |
| 2 | Tool failure — Chrome down, network error, bad args |

## Test harness: WebMainBench

**Source:** OpenDataLab, 2025. 7,887 annotated pages with:
- Raw HTML (frozen, reproducible)
- Ground-truth main HTML subtrees
- Markdown ground truth
- Difficulty stratification (simple/mid/hard)

### Harness design

- Runner feeds HTML through a pluggable extraction function
- Compares output to ground truth via: ROUGE-L, word count ratio, structural metrics
  (tables preserved, code blocks preserved, heading hierarchy)
- Quick mode (~100 representative pages, <30s) for iteration
- Full mode (all 7,887) for regression
- baseline-scores.json for CI-style regression detection (fail if F1 drops > 0.05)
- Per-category breakdown (news, docs, complex, edge-cases)

### Why harness first

A Claude can: run harness → try a change → run harness → measure → iterate.
No human fingers needed. Fast autonomous iteration is the whole point.

## Mise removal

Fully mapped. See mise-kilocu for the bon item.

### Files to delete
- adapters/web.py (554 lines)
- extractors/web.py (471 lines)
- tools/fetch/web.py (285 lines)
- tests/unit/test_web.py (2200+ lines)
- field-reports/2026-02-01-url-fetch-discoverability.md

### Files to modify
- tools/fetch/router.py — remove web detection + routing (~10 lines)
- tools/fetch/__init__.py — remove web import
- models.py — remove WebData dataclass, CAPTCHA enum, possibly AUTH_REQUIRED
- pyproject.toml — drop trafilatura and httpx
- server.py — remove web references from resources and tool docstring
- cli.py — remove web URL from help text
- skills/workspace/SKILL.md — remove "Web Content" section
- CLAUDE.md — remove web.py from adapter table
- README.md — remove web URL rows from tables
- docs/decisions.md — remove/historicize 5 web decision records
- docs/test-design.md — remove web rows from coverage tables
- tests/unit/test_fetch.py — remove TestFetchWeb* classes, web routing test
- tests/unit/test_cues.py — remove WebData import, web-specific cue tests
- tests/unit/test_pdf_thumbnails.py — remove 3 web-PDF test methods
- tests/unit/test_architecture.py — remove trafilatura from allowed imports
- tests/helpers.py — remove wire_httpx_client() if no other consumer

### Shared code that stays
- html_convert.py (used by Gmail, not web)
- adapters/cdp.py (used by GenAI)
- extractors/__init__.py (never listed web)

## Research sources

- Deep Research brief (2026-03-13): "Web content extraction for LLMs: a local CLI architecture guide"
- trafilatura: F1 0.958 on ScrapingHub benchmark, 73K downloads/day
- Boilerpipe paper (Kohlschutter 2010): link density > 0.33 = 87.4% boilerplate F1
- Bevendorff et al. (SIGIR 2023): WCEB benchmark, no single extractor best on all types
- WebMainBench (OpenDataLab 2025): 7,887 pages with markdown ground truth
- jusText: stop words ratio thresholds (LOW=0.30, HIGH=0.32)
- Rasaii et al.: cookie consent detection at 99% accuracy
- Simon Willison's Rodney: confirms persistent Chrome + ephemeral CLI is the right pattern
