# Transcript: httpbin.org/html verification (with skill)

**Date:** 2026-04-04
**Skill used:** passe (CDP browser automation)

## Steps

### 1. Verify page and capture screenshot

```bash
passe check https://httpbin.org/html \
  --contains "Herman Melville" \
  --screenshot .../outputs/proof.jpg
```

**Result:** `ok: true`. Page returned HTTP 200, text "Herman Melville" found. Screenshot saved as JPEG (127 KB). Total time: 539 ms.

### 2. Fetch page content

```bash
passe fetch https://httpbin.org/html .../outputs/page_content.md
```

**Result:** HTTP fast-path used (no Chrome needed). Extracted 601 words via trafilatura. Total time: 1076 ms. Content is an excerpt from Moby-Dick by Herman Melville.

### 3. Visual confirmation

Read the screenshot back. Page heading reads **"Herman Melville - Moby-Dick"** with prose text below.

## Outputs

| File | Description | Size |
|------|-------------|------|
| `outputs/proof.jpg` | Screenshot of the page | 127 KB |
| `outputs/page_content.md` | Extracted text content | 601 words |

## Verdict

The page https://httpbin.org/html exists (HTTP 200) and contains the text "Herman Melville". Screenshot saved as proof.
