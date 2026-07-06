#!/bin/bash
# SessionStart hook: ensure passe CLI is available. Install-if-MISSING only —
# no version-drift check here. Post single-version cutover the vendored
# plugin.json carries the stamped SUITE version, not passe's own, so any
# version comparison at session start is structurally false (bds-japoca).
# Freshness is /batterie:update's job (commit-based). Silent when fine.

# Skip for subagent invocations (fork bomb prevention)
[ -n "${CLAUDE_SUBAGENT:-}" ] && exit 0

export PATH="$HOME/.local/bin:$PATH"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
FIXED=""
ISSUES=""

# Capture auto-update output so failures are diagnosable, not silent (bon-babuse / bon-mavemi).
UPDATE_LOG="$HOME/.cache/passe/auto-update.log"
mkdir -p "$(dirname "$UPDATE_LOG")" 2>/dev/null

# Resolve install source
if [ -n "$PLUGIN_ROOT" ] && [ -f "$PLUGIN_ROOT/pyproject.toml" ]; then
    INSTALL_SRC="$PLUGIN_ROOT"
else
    # Vendored marketplace plugin ships no pyproject.toml (post-2026-06-10 cutover),
    # so install from the source repo over git — the bare name is not published on PyPI.
    INSTALL_SRC="passe @ git+https://github.com/spm1001/passe"
fi

# Check 1: CLI missing → auto-install.
# Report the version that ACTUALLY landed (re-read post-install), never an
# expected number — the old hook claimed the plugin.json version without
# checking, and misreported every session (bds-zelowe).
if ! command -v passe &>/dev/null; then
    if uv tool install "$INSTALL_SRC" --force --reinstall --no-cache >"$UPDATE_LOG" 2>&1; then
        LANDED=$(passe --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
        FIXED="${FIXED}• passe CLI installed (v${LANDED})\n"
    else
        ISSUES="${ISSUES}• passe CLI not found and auto-install failed (full error: ${UPDATE_LOG}). Run manually:\n\n  uv tool install \"$INSTALL_SRC\" --force --reinstall --no-cache\n"
    fi
fi

# Silent exit if nothing happened
[ -z "$FIXED" ] && [ -z "$ISSUES" ] && exit 0

# Report
MSG=""
[ -n "$FIXED" ] && MSG="${MSG}✓ passe auto-fixed:\n\n${FIXED}"
[ -n "$ISSUES" ] && MSG="${MSG}⚠️ passe needs attention:\n\n${ISSUES}"

# Render via json.dumps so messages containing quotes (e.g. the quoted INSTALL_SRC in
# recovery commands) produce valid JSON — a raw heredoc does not escape them (bon-mavemi).
python3 -c "import json; print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': '''${MSG}'''}}))"
