# Changelog

## [0.3.0] - 2026-03-18

Batterie-wide consistency pass: docs consolidation, CI, versioning.

## 2026-03-14 — HTTP Fast-Path

### Added
- HTTP fast-path for `passe fetch`: ~87% of pages extracted without Chrome (300-1500ms)
- Semantic exit codes (0 success, 1 thin/degraded, 2 tool failure)

## 2026-03-10–11 — Grammar Redesign

### Changed
- Renamed `read` to `extract` (read still works as alias), dropped `-c` flag requirement
- Smart wait, smart click, removed dead verbs
- `wait`/`wait-for`/`wait-idle` all take seconds, not milliseconds

### Fixed
- `type` verb: re-focus element before React fallback setter
- `type` verb: add React reconciliation delay after fallback

## 2026-03-06 — Content Extraction Quality

### Added
- Apple Developer Documentation: auto-detect and use JSON endpoint
- Code block supplementation for framework docs pages
- Quality gate: detect pipe-noise from HTML email table layouts
- SSR+RPC extraction pipeline for Google Groups

### Fixed
- Catastrophic regex backtracking in multiline signature pattern

## 2026-03-05 — Intent-Level Subcommands & Self-Healing

### Added
- Intent-level subcommands: `look`, `check`, `capture`, `fetch`
- Dry-run validation: `passe explain` subcommand
- Self-healing: snapshot on click/type failure
- Flash tabs: auto-cleanup kept tabs after idle timeout
- `PASSE_SCREENSHOT_FAST` env var for default fast screenshots
- Short extraction content inlined to stdout
- Friendly errors for natural-language verb variants
- Stderr hints for common anti-patterns
- Human-readable summary line on stderr after every run
- `passe fetch` as top-level subcommand

### Fixed
- Issues from titans review
- Flash tab guard against reuse-tab

## 2026-03-04 — Modular Package

### Changed
- Broke monolithic `cli.py` into modular package: parser, client, connection, verbs, runner, commands

## 2026-03-02–03 — Async Context Manager & Tab Attach

### Changed
- Converted `connect()` to async context manager with origin-preference tab attach
- Tab lifecycle tests added

## 2026-02-27 — Plugin System

### Added
- Plugin manifest for Claude Code plugin system
- Skill directory moved from `skill/` to `skills/browser/`

## 2026-02-22–23 — Chrome Passe & Auto-Launch

### Added
- Auto-launch headless Chrome when no CDP endpoint available
- Native macOS handler for Chrome Debug Apple Events
- Chrome debug log output (which Chrome, CDP/browser/DPR)

### Changed
- Renamed Chrome Debug to Chrome Passe
- Fixed TCC crash via NSWorkspace launch
- Platform-aware Chrome auto-launch (find chromium/chrome on Linux)

## 2026-02-21 — Network Capture & Remote Chrome

### Added
- `capture` verb: network request recording to JSONL
- `wait-idle` verb: pause until network requests settle
- `goto` reports URL and HTTP status code in step NDJSON
- Document kube-to-Mac Chrome connection via tailscale serve
- Per-call timeout parameter on `CDPClient.send`

## 2026-02-18 — Mobile Touch & Error Handling

### Added
- `tap` verb: touch events for mobile UI via JS TouchEvent synthesis
- `swipe` verb: touch move gestures for mobile UI
- `watch` verb: HMR-triggered auto-screenshot with leading+trailing cooldown
- `devices` subcommand listing available presets
- Unit tests for CLI flag parsing and error handling

### Changed
- Fail loudly: goto detection, connection errors, help, screenshot flags, scroll warning

## 2026-02-16–17 — Device Emulation

### Added
- Device emulation, fast JPEG screenshots, HMR watch verb
- Competitive landscape analysis (LANDSCAPE.md)

## 2026-02-15 — Content Extraction & Tab Management

### Added
- Thin-read diagnostics for minimal extraction content
- Content-type sniffing: bypass extraction for structured data (JSON, XML, CSV)
- `--keep-tab` and `--reuse-tab` flags for user-handoff workflows
- Auto-wait, `fetch` verb, dual-signal DOM stability polling

## 2026-02-13 — Extraction Cascade & Remote CDP

### Added
- Remote CDP support via `PASSE_CDP` environment variable
- Trafilatura extraction cascade (primary), Readability.js+Turndown (fallback)
- Shadow DOM flattener for web components
- Structural quality gate (code blocks, tables)
- `eval-file` verb for multi-line JS
- `type` verb uses `Input.insertText`, auto-detects controlled inputs

## 2026-02-12–13 — Initial Release

### Added
- CDP browser automation CLI with composable line DSL
- Verb set: goto, click, type, fill, select, press, hover, scroll, screenshot, read, eval, wait, assert, log
- Tab isolation (background tabs, kept on failure)
- NDJSON step output on stderr, JSON summary on stdout
