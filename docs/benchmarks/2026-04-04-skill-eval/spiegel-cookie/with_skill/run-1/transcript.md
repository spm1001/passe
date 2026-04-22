# Spiegel Cookie Wall -- Transcript (with skill)

Date: 2026-04-04

## Objective

Bypass cookie wall on `https://www.spiegel.de/international/` and extract page content.

## Steps

### 1. Read the passe skill (SKILL.md)

Loaded the passe cookbook. Recipe 4 ("Dismiss a cookie banner") was directly relevant: scout with `ax-find button`, then click the reject/accept button in a second call.

### 2. Scout -- ax-find button

```
passe run -c 'goto https://www.spiegel.de/international/; ax-find button'
```

Result: 36 buttons found, but none related to cookie consent (no "Accept", "Reject", "Alle akzeptieren", etc.). All buttons were either navigation ("Menu", "Suche offnen") or article bookmarks ("Zur Merkliste hinzufugen").

### 3. Screenshot to confirm

```
passe look https://www.spiegel.de/international/
```

Visual inspection confirmed: no cookie wall visible. The Chrome Passe profile had already accepted cookies from a prior session, so the consent banner did not appear.

### 4. Extract content

```
passe run - <<'EOF'
goto https://www.spiegel.de/international/
screenshot .../outputs/spiegel-initial.png
extract .../outputs/spiegel-content.md
EOF
```

Extraction via trafilatura returned 965 words covering the full index page: article headlines, summaries, and links.

## Outputs

| File | Description |
|------|-------------|
| `outputs/spiegel-initial.png` | Full-page PNG screenshot (1534 KB) |
| `outputs/spiegel-content.md` | Extracted text content (965 words) |

## Cookie Wall Status

**Not encountered.** The Chrome Passe profile already had cookie consent stored. The skill's scout-then-act pattern (Recipe 4) was followed but no consent buttons were found to dismiss.

## Observations

- Spiegel uses a CMP (Consent Management Platform) that likely renders in an iframe. The `ax-find button` approach would surface iframe-hosted buttons if the iframe is cross-origin (OOPiF), but since consent was already given, the iframe was not injected at all.
- For a true first-visit test, cookies would need to be cleared first (`passe eval "document.cookie.split(';').forEach(...)"`  or via CDP `Network.clearBrowserCookies`).
- The skill's two-step pattern (scout in one call, act in a second) is sound for this use case -- total wall-clock time was under 3 seconds across all steps.
