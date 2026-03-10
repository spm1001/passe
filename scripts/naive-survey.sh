#!/usr/bin/env bash
# naive-survey.sh — Ask clean Claudes what browser automation DSL they'd write
# Run from anywhere. Spawns Claude -p in /tmp so no project CLAUDE.md loads.
# No tools allowed — pure text response from training weights.
#
# Usage: ./scripts/naive-survey.sh [runs_per_scenario]
# Default: 3 runs per scenario (18 total invocations)

set -euo pipefail

RUNS=${1:-3}
OUTDIR="/tmp/naive-survey-$(date +%Y%m%dT%H%M%S)"
mkdir -p "$OUTDIR"

echo "Survey output: $OUTDIR"
echo "Runs per scenario: $RUNS"
echo ""

# Scenarios — each is a prompt
declare -A SCENARIOS

SCENARIOS[login]='You have a CLI tool called "webbot" for browser automation. It connects to Chrome via CDP and lets you script browser actions using a line-based DSL — one verb per line. That is ALL you know. You have NEVER read documentation for this tool. You have NO access to any files or tools.

Write the exact shell commands you would use to:
1. Navigate to https://app.example.com/login
2. Type "user@example.com" into the email field
3. Type "password123" into the password field
4. Click the "Sign In" button
5. Wait for the dashboard to load
6. Take a screenshot

Write ONLY the commands — what you would TRY FIRST based on pure intuition. No explanation, no caveats.'

SCENARIOS[screenshot]='You have a CLI tool called "webbot" for browser automation. It connects to Chrome via CDP and lets you script browser actions using a line-based DSL. That is ALL you know. No docs, no files.

Write the exact shell command to open https://news.ycombinator.com and take a screenshot. One command. No explanation.'

SCENARIOS[streamlit]='You have a CLI tool called "webbot" for browser automation. It connects to Chrome via CDP and lets you script browser actions using a line-based DSL — one verb per line. That is ALL you know. No docs, no files.

Write the exact shell commands to:
1. Go to a Streamlit app at http://localhost:8501
2. Wait 3 seconds for it to hydrate
3. Extract the page content as text/markdown
4. Take a screenshot

Write ONLY the commands. No explanation.'

SCENARIOS[spa_nav]='You have a CLI tool called "webbot" for browser automation. It connects to Chrome via CDP and lets you script browser actions using a line-based DSL — one verb per line. That is ALL you know. No docs, no files.

Write the exact shell commands to:
1. Go to a React SPA at https://app.example.com
2. Click a navigation link that says "Settings"
3. Wait for the settings page to load (client-side route change, not full page load)
4. Fill in a form field with id "display-name" with the value "Claude"
5. Click "Save"
6. Wait a moment for the save to complete
7. Screenshot the result

Write ONLY the commands. No explanation.'

SCENARIOS[tab_reuse]='You have a CLI tool called "webbot" for browser automation. It connects to Chrome via CDP and lets you script browser actions using a line-based DSL — one verb per line. That is ALL you know. No docs, no files.

Write the exact shell commands to do this in TWO separate webbot invocations (not one script):
1. First: navigate to https://github.com and screenshot the page
2. Then: on the SAME tab/page, click the "Sign in" link and screenshot the login page

Write ONLY the commands. No explanation.'

SCENARIOS[cookie_banner]='You have a CLI tool called "webbot" for browser automation. It connects to Chrome via CDP and lets you script browser actions using a line-based DSL — one verb per line. That is ALL you know. No docs, no files.

Write the exact shell commands to:
1. Navigate to https://shop.example.com
2. Dismiss a cookie consent banner (click "Reject All")
3. Search for "wireless headphones" using the search box
4. Wait for results to appear
5. Screenshot the results

Write ONLY the commands. No explanation.'

# Run each scenario N times
for scenario in login screenshot streamlit spa_nav tab_reuse cookie_banner; do
  echo "=== $scenario ==="
  for i in $(seq 1 "$RUNS"); do
    outfile="$OUTDIR/${scenario}_${i}.txt"
    echo "  Run $i..."

    # Claude -p in /tmp: no project context, no tools, single turn
    echo "${SCENARIOS[$scenario]}" | claude -p \
      --max-turns 1 \
      --allowed-tools "" \
      --output-format text \
      2>/dev/null \
      > "$outfile" || true

    # Brief preview
    head -3 "$outfile" | sed 's/^/    /'
    echo "    ..."
    echo ""
  done
done

echo ""
echo "=== DONE ==="
echo "All responses in: $OUTDIR"
echo ""
echo "Quick diff check (are responses identical or varied?):"
for scenario in login screenshot streamlit spa_nav tab_reuse cookie_banner; do
  unique=$(md5sum "$OUTDIR/${scenario}_"*.txt | awk '{print $1}' | sort -u | wc -l)
  echo "  $scenario: $unique unique responses out of $RUNS"
done
