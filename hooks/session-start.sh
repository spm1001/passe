#!/bin/bash
# SessionStart hook: symlink instruction shard + probe Chrome connection
# set -euo pipefail  # removed: races with plugin autoUpdate cache swap
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$HOOK_DIR")"
if [ -f "$PLUGIN_ROOT/instructions.md" ]; then
    mkdir -p "$HOME/.claude/rules"
    ln -sf "$PLUGIN_ROOT/instructions.md" "$HOME/.claude/rules/passe.md"
fi

# Probe Chrome connection (2s timeout, best-effort)
# Skip for subagents — they inherit parent's connection knowledge
CONN_STATUS=""
if [ -z "${CLAUDE_SUBAGENT:-}" ] && command -v passe &>/dev/null; then
    CONN_STATUS=$(timeout 2 passe status 2>/dev/null || true)
fi

# Surface connection state if probe returned results
if [ -n "$CONN_STATUS" ]; then
    if echo "$CONN_STATUS" | grep -q "reachable=True"; then
        CHROME_VER=$(echo "$CONN_STATUS" | grep chrome_version | sed 's/.*=//')
        TABS=$(echo "$CONN_STATUS" | grep tabs_open | sed 's/.*=//')
        DETAIL="Chrome connected: ${CHROME_VER}, ${TABS} tab(s)"
    else
        DETAIL="Chrome unreachable — use --cdp localhost:9222 for headless or check Mac is awake"
    fi
    cat <<EOF
{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "${DETAIL}"}}
EOF
fi

# Consume stdin (hook protocol)
cat > /dev/null
exit 0
