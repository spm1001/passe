#!/usr/bin/env bash
# naive-survey-v2.sh — Structured instinct survey for browser automation DSL design
# Spawns Claude -p with --system-prompt (replaces default, kills global CLAUDE.md).
# Bland tool name "xt" to avoid semantic priming. JSON responses for analysis.
#
# Usage: ./scripts/naive-survey-v2.sh [runs_per_scenario]
# Default: 10 runs per scenario (60 total invocations)

set -euo pipefail

GLOBAL_MD="$HOME/.claude/CLAUDE.md"
GLOBAL_MD_BAK="$HOME/.claude/CLAUDE.md.survey-bak"

restore() {
  if [ -f "$GLOBAL_MD_BAK" ]; then
    mv "$GLOBAL_MD_BAK" "$GLOBAL_MD"
    echo "[survey] Restored ~/.claude/CLAUDE.md"
  fi
}
trap restore EXIT

if [ -f "$GLOBAL_MD" ]; then
  mv "$GLOBAL_MD" "$GLOBAL_MD_BAK"
  echo "[survey] Temporarily hidden ~/.claude/CLAUDE.md"
fi

RUNS=${1:-10}
OUTDIR="/tmp/naive-survey-v2-$(date +%Y%m%dT%H%M%S)"
mkdir -p "$OUTDIR"

echo "Survey output: $OUTDIR"
echo "Runs per scenario: $RUNS"
echo "Total invocations: $((RUNS * 6))"
echo ""

SYSPROMPT="You are a helpful assistant. You have no tools available. Respond with text only."

JSON_INSTRUCTION='Respond with ONLY a JSON object, no markdown fencing, no explanation:
{
  "invocation": "the full shell command(s) you would type, exactly as you would type them",
  "verbs_used": ["list", "of", "each", "verb", "you", "used"],
  "nav_verb": "the verb you used to go to a URL",
  "wait_verb": "the verb you used to wait/pause (if any, otherwise null)",
  "wait_value": "the argument you passed to the wait verb (if any, otherwise null)",
  "click_pattern": "how you expressed clicking by visible text label",
  "screenshot_has_path": true or false,
  "uses_run_subcommand": true or false,
  "extract_verb": "the verb you used to get page content (if any, otherwise null)"
}'

declare -A SCENARIOS

SCENARIOS[login]='You have a CLI tool called "xt" for browser automation. It connects to Chrome and lets you script browser actions using a line-based DSL — one verb per line. You have NEVER seen any documentation for this tool. You have NO access to any files or reference material.

Write the commands to:
1. Navigate to https://app.example.com/login
2. Type "user@example.com" into the email field
3. Type "password123" into the password field
4. Click the "Sign In" button
5. Wait for the dashboard to load
6. Take a screenshot'

SCENARIOS[screenshot]='You have a CLI tool called "xt" for browser automation. It connects to Chrome and lets you script browser actions using a line-based DSL. You have NEVER seen any documentation. No files, no reference.

Write a single command to open https://news.ycombinator.com and take a screenshot of it.'

SCENARIOS[streamlit]='You have a CLI tool called "xt" for browser automation. It connects to Chrome and lets you script browser actions using a line-based DSL — one verb per line. You have NEVER seen any documentation. No files, no reference.

Write the commands to:
1. Go to a Streamlit app at http://localhost:8501
2. Wait 3 seconds for it to hydrate
3. Extract the page content as text or markdown
4. Take a screenshot'

SCENARIOS[spa_nav]='You have a CLI tool called "xt" for browser automation. It connects to Chrome and lets you script browser actions using a line-based DSL — one verb per line. You have NEVER seen any documentation. No files, no reference.

Write the commands to:
1. Go to a React SPA at https://app.example.com
2. Click a navigation link that says "Settings"
3. Wait for the settings page to load (client-side route change, not full page load)
4. Fill in a form field with id "display-name" with the value "Claude"
5. Click "Save"
6. Wait a moment for the save to complete
7. Screenshot the result'

SCENARIOS[tab_reuse]='You have a CLI tool called "xt" for browser automation. It connects to Chrome and lets you script browser actions using a line-based DSL — one verb per line. You have NEVER seen any documentation. No files, no reference.

Write the commands to do this in TWO SEPARATE xt invocations (not one script):
1. First invocation: navigate to https://github.com and screenshot the page
2. Second invocation: on the SAME tab/page from step 1, click the "Sign in" link and screenshot the result'

SCENARIOS[cookie_banner]='You have a CLI tool called "xt" for browser automation. It connects to Chrome and lets you script browser actions using a line-based DSL — one verb per line. You have NEVER seen any documentation. No files, no reference.

Write the commands to:
1. Navigate to https://shop.example.com
2. Dismiss a cookie consent banner by clicking the button that says "Reject All"
3. Search for "wireless headphones" using the search box
4. Wait for results to appear
5. Screenshot the results'

TOTAL=$((RUNS * 6))
COUNT=0

for scenario in login screenshot streamlit spa_nav tab_reuse cookie_banner; do
  echo "=== $scenario ==="
  for i in $(seq 1 "$RUNS"); do
    COUNT=$((COUNT + 1))
    outfile="$OUTDIR/${scenario}_$(printf '%02d' $i).json"
    echo -n "  [$COUNT/$TOTAL] Run $i... "

    PROMPT="${SCENARIOS[$scenario]}

${JSON_INSTRUCTION}"

    echo "$PROMPT" | claude -p \
      --max-turns 1 \
      --tools "" \
      --system-prompt "$SYSPROMPT" \
      --output-format text \
      2>/dev/null \
      > "$outfile" || true

    # Quick validation — is it valid JSON?
    if python3 -c "import json; json.load(open('$outfile'))" 2>/dev/null; then
      echo "OK (valid JSON)"
    else
      echo "WARN (not valid JSON — will need manual review)"
    fi
  done
  echo ""
done

echo "=== ANALYSIS ==="
echo ""

# Aggregate analysis — extract to separate script to avoid heredoc issues
python3 "$(dirname "$0")/naive-survey-analyze.py" "$OUTDIR"

echo ""
echo "Raw responses: $OUTDIR"
