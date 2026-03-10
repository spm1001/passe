#!/usr/bin/env bash
# naive-survey-probe.sh — Verify Claude -p isolation before running the full survey
# Tests: no project context, no tools, no file access, bland name has no associations
# Temporarily hides ~/.claude/CLAUDE.md during run (restored on exit/Ctrl-C)

set -euo pipefail

GLOBAL_MD="$HOME/.claude/CLAUDE.md"
GLOBAL_MD_BAK="$HOME/.claude/CLAUDE.md.survey-bak"

# Restore on exit, interrupt, or error
restore() {
  if [ -f "$GLOBAL_MD_BAK" ]; then
    mv "$GLOBAL_MD_BAK" "$GLOBAL_MD"
    echo "[probe] Restored ~/.claude/CLAUDE.md"
  fi
}
trap restore EXIT

# Hide global CLAUDE.md
if [ -f "$GLOBAL_MD" ]; then
  mv "$GLOBAL_MD" "$GLOBAL_MD_BAK"
  echo "[probe] Temporarily hidden ~/.claude/CLAUDE.md"
fi

SYSPROMPT="You are a helpful assistant. You have no tools available. Respond with text only."

ask() {
  echo "$1" | claude -p \
    --max-turns 1 \
    --tools "" \
    --system-prompt "$SYSPROMPT" \
    --output-format text \
    2>/dev/null
}

echo ""
echo "=== Probe 1: Does Claude see any project context? ==="
ask 'What project are you working in? What is your current working directory? Do you see any CLAUDE.md or SKILL.md files? List everything you know about your environment. Be precise about what you can and cannot see.'
echo -e "\n"

echo "=== Probe 2: Does Claude know what passe is? ==="
ask 'Do you know what "passe" is in the context of browser automation? What verbs does it support? What is its default screenshot format? Be specific — if you are guessing, say so.'
echo -e "\n"

echo "=== Probe 3: Does the name xt prime anything? ==="
ask 'What does the tool "xt" do? Have you heard of it? What associations does the name bring to mind?'
echo -e "\n"

echo "=== Probe 4: Can Claude access files? ==="
ask 'Can you read the file /home/modha/Repos/passe/CLAUDE.md? Can you list files in /home/modha/Repos/passe/? Report exactly what you can and cannot do right now.'
echo -e "\n"

echo "=== Probe 5: Baseline instinct check (no JSON, just raw) ==="
ask 'You have a CLI tool called "xt" for browser automation. It connects to Chrome and lets you script browser actions with a line-based DSL. You have never seen docs for it. Write a command to navigate to https://example.com and take a screenshot. Just write the command.'
echo -e "\n"

echo "=== DONE ==="
