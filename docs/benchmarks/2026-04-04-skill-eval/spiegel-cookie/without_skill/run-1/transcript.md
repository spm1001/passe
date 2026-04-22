# Spiegel Cookie Wall Bypass -- Without Skill

## Objective

Navigate to `https://www.spiegel.de/international/`, bypass any cookie consent wall, and extract the page content.

## Approach

Used `passe` CLI (CDP browser automation on port 9222) directly, without loading the passe skill first. All commands run sequentially against a single Chrome instance.

## Steps

### 1. Check Chrome status

```
passe status
```

Chrome/146.0.7680.80 reachable on localhost:9222, 27 tabs open.

### 2. Navigate and screenshot (passe look)

```
passe look "https://www.spiegel.de/international/" outputs/01-initial-page.png
```

Page loaded (200 OK, 510ms). Screenshot showed the Spiegel International landing page with header, Substack promo text, and category tabs (Alles, World, Europe, Germany, Business, Zeitgeist, Global Societies). No cookie consent dialog visible.

### 3. Full-page screenshot

```
passe run --reuse-tab -c 'screenshot outputs/02-fullpage.png'
```

Full-page screenshot was nearly identical to viewport -- page appeared to be only ~500px tall. Article listings below the fold were not rendering in the screenshot, suggesting lazy-loaded content or the page document height being artificially constrained.

### 4. Scroll and screenshot

```
passe run --reuse-tab -c 'scroll 0 3000 ; wait 1 ; screenshot --viewport outputs/03-scrolled-down.png'
```

Scrolled to y=3000 and waited 1 second. Viewport screenshot still showed the same content -- the page didn't scroll, likely because the document height matched the viewport.

### 5. Check for cookie consent elements in DOM

```
passe eval 'document.querySelectorAll("[id*=consent], [class*=consent], [id*=cookie], [class*=cookie]").length'
# Result: 0
```

No cookie/consent elements found in the DOM. Also checked for iframes -- only one empty iframe, no consent dialog.

### 6. Extract index page content (passe read)

```
passe run --reuse-tab -c 'read outputs/04-page-content.md'
```

Trafilatura extracted 965 words from the page source. Content included:
- Substack promo text
- 14 article listings with headlines, descriptions, authors, and links
- Topics spanning Iran/Hormuz, Australia social media ban, Robert Kagan interview, Nord Stream, Gisele Pelicot, John Bolton, Sebastian Kurz, fast fashion in Italy, ICE deportations, Palestinian prisoners, Myanmar scam factories, and more

### 7. Navigate to a specific article

```
passe look "https://www.spiegel.de/international/world/u-s-military-expert-on-oil-tanker-convoys..." outputs/05-article-page.png
```

Article page loaded cleanly (200 OK). No cookie wall, no paywall interstitial. Headline, subhead, and article intro all visible.

### 8. Extract article content

```
passe run --keep-tab -c 'goto [article-url] ; read outputs/06-article-content.md'
```

Full article extracted: 1813 words. Complete DER SPIEGEL interview with retired Lt. Gen. S. Clinton Hinote about the Strait of Hormuz blockade, military options, minesweeping challenges, and geopolitical implications. Article appears to be unpaywalled SPIEGEL+ content.

### 9. Cleanup

```
passe tabs close --matching "spiegel.de"
```

Closed 1 tab.

## Findings

**No cookie wall was encountered.** Chrome Passe likely had pre-existing consent cookies from a previous session, or Spiegel doesn't show a cookie wall to this browser configuration. The `read` verb (trafilatura-based extraction) would likely bypass a DOM-level cookie overlay anyway, since it works from page source rather than rendered DOM.

The content was fully accessible -- both the index page listings and a full article were extracted without any consent interaction needed.

## Output Files

| File | Description |
|------|-------------|
| `01-initial-page.png` | First viewport screenshot of landing page |
| `02-fullpage.png` | Full-page screenshot (same as viewport -- page height limited) |
| `03-scrolled-down.png` | After scrolling to y=3000 |
| `04-page-content.md` | Extracted index page content (965 words, 14 articles listed) |
| `05-article-page.png` | Screenshot of article page |
| `06-article-content.md` | Full article text (1813 words, Hinote interview) |

## Notes

- `passe look` combines goto + screenshot in one step -- convenient for quick checks
- `passe run --reuse-tab` attaches to existing tabs at the same domain
- `scroll` takes `x y` coordinates, not a single distance value
- `wait` takes bare numbers (seconds), not suffixed like `2s`
- Trafilatura extraction via `read` pulls from page source, which may inherently bypass DOM-level overlays
- Some earlier output files (01-initial-load.png, 02-scrolled.png, etc.) exist from a prior attempt and are not part of this run
