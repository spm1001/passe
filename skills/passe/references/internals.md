# Output Protocol and Internals

## Output protocol

**stderr:** NDJSON per step — `{"i":0,"verb":"goto","ms":342}`
**stdout:** summary — `{"ok":true,"steps":6,"total_ms":443,"files":[...]}`
**Exit:** 0=success, 1=failure

## Content extraction cascade

1. Content-type sniffing (JSON/XML/CSV → raw passthrough)
2. Apple docs → structured JSON endpoint
3. trafilatura (Python-side, handles most pages)
4. Readability.js + Turndown (browser-side fallback)
5. innerText (last resort)

Shadow DOM flattened before extraction. `source` field in output tells you which extractor was used.
