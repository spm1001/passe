# /// script
# requires-python = ">=3.11"
# dependencies = ["anthropic[vertex]>=0.40"]
# ///
"""
Passe Claude Usability Eval.

Tests whether Claude correctly uses Passe when given browser tasks.

Two modes:
  --local   Use ardoise + local Claude (default). Free, uses CC license.
  --api     Use Anthropic API. Fast, parallel-safe, costs tokens.

Usage:
    uv run --script tests/eval/run_eval.py                    # API mode
    uv run --script tests/eval/run_eval.py --local            # ardoise mode (free)
    uv run --script tests/eval/run_eval.py --category tool_choice
    uv run --script tests/eval/run_eval.py --id tc-01
    uv run --script tests/eval/run_eval.py --model claude-sonnet-4-6
    uv run --script tests/eval/run_eval.py --verbose
    uv run --script tests/eval/run_eval.py --runs 3
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Find the Passe SKILL.md to inject as context
PASSE_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_PATH = PASSE_ROOT / "skills" / "passe" / "SKILL.md"
CLAUDE_MD_PATH = PASSE_ROOT / "CLAUDE.md"


@dataclass
class Result:
    scenario_id: str
    category: str
    passed: bool
    matched_expects: list[str] = field(default_factory=list)
    matched_rejects: list[str] = field(default_factory=list)
    missing_expects: list[str] = field(default_factory=list)
    response_text: str = ""
    duration_ms: float = 0
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0


def load_context() -> str:
    """Load Passe SKILL.md as system context."""
    parts = []

    if SKILL_PATH.exists():
        parts.append(f"# Passe Skill Reference\n\n{SKILL_PATH.read_text()}")
    else:
        print(f"WARNING: {SKILL_PATH} not found", file=sys.stderr)

    # Also inject the CLAUDE.md for full context
    if CLAUDE_MD_PATH.exists():
        parts.append(f"# Passe CLAUDE.md\n\n{CLAUDE_MD_PATH.read_text()}")

    return "\n\n---\n\n".join(parts)


SYSTEM_PROMPT_TEMPLATE = """\
You are Claude, an AI assistant helping a user with browser automation tasks.
You have access to the following tools via Bash:
- `passe` — a CDP browser automation CLI (details below)
- `mise` — for Google Workspace content (Drive, Gmail, Sheets)
- Standard Unix tools

The user is on a Linux server (hezza) with:
- Local Chromium available at localhost:9222
- A Mac reachable via Tailscale with authenticated Chrome (but it may be closed/sleeping)
- PASSE_CDP environment variable pointing to the Mac's Chrome

When the user asks you to do something, respond with the exact Bash commands
you would run. Show the commands in ```bash code blocks.
If the task requires multiple steps, show all of them.
Be specific about which tool you'd use and why.

{context}
"""


def check_pattern(text: str, pattern: str) -> bool:
    """Check if a pattern matches in the text. Supports regex."""
    try:
        return bool(re.search(pattern, text, re.IGNORECASE | re.DOTALL))
    except re.error:
        # Fall back to literal substring match
        return pattern.lower() in text.lower()


def score_response(scenario, text: str) -> tuple[bool, list, list, list]:
    """Score a response against scenario patterns. Returns (passed, matched, rejected, missing)."""
    matched_expects = [p for p in scenario.expect_any if check_pattern(text, p)]
    missing_expects = [p for p in scenario.expect_any if not check_pattern(text, p)]
    matched_rejects = [p for p in scenario.reject_any if check_pattern(text, p)]

    passed = (
        (len(matched_expects) > 0 or len(scenario.expect_any) == 0)
        and len(matched_rejects) == 0
    )
    return passed, matched_expects, matched_rejects, missing_expects


def run_scenario_api(
    client,
    scenario,
    system_prompt: str,
    model: str,
) -> Result:
    """Run a single scenario via Anthropic API."""
    import anthropic  # noqa: F811 — lazy import for --local mode

    t0 = time.monotonic()

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": scenario.prompt}],
    )

    duration_ms = (time.monotonic() - t0) * 1000
    text = "".join(
        block.text for block in response.content if block.type == "text"
    )

    passed, matched_expects, matched_rejects, missing_expects = score_response(scenario, text)

    return Result(
        scenario_id=scenario.id,
        category=scenario.category,
        passed=passed,
        matched_expects=matched_expects,
        matched_rejects=matched_rejects,
        missing_expects=missing_expects if not matched_expects else [],
        response_text=text,
        duration_ms=duration_ms,
        model=model,
        tokens_in=response.usage.input_tokens,
        tokens_out=response.usage.output_tokens,
    )


# ── Ardoise runner ─────────────────────────────────────────────────

# Find ardoise.sh relative to batterie layout
ARDOISE_CANDIDATES = [
    Path.home() / "Repos" / "batterie" / "trousse" / "scripts" / "ardoise.sh",
    Path.home() / ".claude" / "plugins" / "cache" / "batterie-de-savoir",
]


def find_ardoise() -> Path | None:
    """Find ardoise.sh."""
    for candidate in ARDOISE_CANDIDATES:
        if candidate.is_file():
            return candidate
    # Search plugin cache
    cache = Path.home() / ".claude" / "plugins" / "cache" / "batterie-de-savoir"
    if cache.is_dir():
        for ardoise in cache.rglob("ardoise.sh"):
            return ardoise
    return None


def run_scenario_local(
    scenario,
    system_prompt: str,
    model: str,
    ardoise_path: Path,
) -> Result:
    """Run a single scenario via ardoise (local Claude, free)."""
    t0 = time.monotonic()

    # Write system prompt to a temp file (too large for CLI arg)
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(system_prompt)
        sys_prompt_file = f.name

    try:
        cmd = [
            str(ardoise_path),
            "-p",
            "--max-turns", "1",
            "--tools", "",  # No tools — just text response
            "--model", model,
            "--system-prompt", f"$(cat {sys_prompt_file})",
            "--output-format", "text",
            "--",
            scenario.prompt,
        ]

        # Actually, ardoise uses env -i which complicates passing files.
        # Simpler: pipe the prompt via --stdin and put system prompt in the prompt.
        combined_prompt = (
            f"<context>\n{system_prompt}\n</context>\n\n"
            f"User request: {scenario.prompt}"
        )

        result = subprocess.run(
            [
                str(ardoise_path),
                "-p",
                "--max-turns", "1",
                "--tools", "",
                "--model", model,
                "--output-format", "text",
                "--stdin",
            ],
            input=combined_prompt,
            capture_output=True,
            text=True,
            timeout=60,
        )

        text = result.stdout.strip()
    except subprocess.TimeoutExpired:
        text = "[TIMEOUT]"
    finally:
        os.unlink(sys_prompt_file)

    duration_ms = (time.monotonic() - t0) * 1000
    passed, matched_expects, matched_rejects, missing_expects = score_response(scenario, text)

    return Result(
        scenario_id=scenario.id,
        category=scenario.category,
        passed=passed,
        matched_expects=matched_expects,
        matched_rejects=matched_rejects,
        missing_expects=missing_expects if not matched_expects else [],
        response_text=text,
        duration_ms=duration_ms,
        model=model,
    )


def main():
    parser = argparse.ArgumentParser(description="Passe Claude Usability Eval")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--api", action="store_true",
                      help="Use Anthropic API (costs tokens)")
    mode.add_argument("--local", action="store_true", default=True,
                      help="Use ardoise + local Claude (default, free)")
    parser.add_argument("--model", default="claude-sonnet-4-6",
                        help="Model to test (default: claude-sonnet-4-6)")
    parser.add_argument("--category", help="Run only scenarios in this category")
    parser.add_argument("--id", help="Run only this scenario ID")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show full responses")
    parser.add_argument("--runs", type=int, default=1,
                        help="Number of runs per scenario (for variance)")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    args = parser.parse_args()
    use_local = args.local

    # Import scenarios
    sys.path.insert(0, str(Path(__file__).parent))
    from scenarios import SCENARIOS

    # Filter scenarios
    scenarios = SCENARIOS
    if args.category:
        scenarios = [s for s in scenarios if s.category == args.category]
    if args.id:
        scenarios = [s for s in scenarios if s.id == args.id]

    if not scenarios:
        print("No matching scenarios found", file=sys.stderr)
        sys.exit(1)

    # Load context and build system prompt
    context = load_context()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context)

    # Set up runner
    ardoise_path = None
    client = None
    if use_local:
        ardoise_path = find_ardoise()
        if not ardoise_path:
            print("ERROR: ardoise.sh not found. Install trousse or use --api.",
                  file=sys.stderr)
            sys.exit(1)
        mode_label = "local (ardoise)"
    else:
        import anthropic
        if "ANTHROPIC_VERTEX_PROJECT_ID" in os.environ:
            project_id = os.environ["ANTHROPIC_VERTEX_PROJECT_ID"]
            region = os.environ.get("CLOUD_ML_REGION", "europe-west1")
            client = anthropic.AnthropicVertex(project_id=project_id, region=region)
        else:
            client = anthropic.Anthropic()
        mode_label = "API"

    all_results: list[Result] = []

    if not args.json:
        print(f"\nPasse Usability Eval — {len(scenarios)} scenarios, "
              f"{args.runs} run(s), model={args.model}, mode={mode_label}\n")
        print(f"{'ID':<8} {'Category':<18} {'Result':<6} {'ms':>6}  Detail")
        print("-" * 75)

    completed = 0
    for scenario in scenarios:
        for run_idx in range(args.runs):
            if use_local:
                result = run_scenario_local(
                    scenario, system_prompt, args.model, ardoise_path,
                )
            else:
                result = run_scenario_api(
                    client, scenario, system_prompt, args.model,
                )
            all_results.append(result)
            completed += 1

            if not args.json:
                status = "PASS" if result.passed else "FAIL"
                detail = ""
                if not result.passed:
                    if result.matched_rejects:
                        detail = f"reject: {result.matched_rejects[0][:40]}"
                    elif result.missing_expects:
                        detail = f"missing: {result.missing_expects[0][:40]}"
                run_suffix = f" (run {run_idx + 1})" if args.runs > 1 else ""
                print(f"{result.scenario_id:<8} {result.category:<18} "
                      f"{status:<6} {result.duration_ms:>5.0f}ms "
                      f"{detail}{run_suffix}")

                if args.verbose and not result.passed:
                    print(f"  Response: {result.response_text[:200]}...")
                    print()

    # Summary
    if args.json:
        output = {
            "model": args.model,
            "total": len(all_results),
            "passed": sum(1 for r in all_results if r.passed),
            "failed": sum(1 for r in all_results if not r.passed),
            "by_category": {},
            "results": [asdict(r) for r in all_results],
        }
        # Remove response text from JSON to keep it compact
        for r in output["results"]:
            r.pop("response_text", None)

        # Category breakdown
        categories = sorted(set(r.category for r in all_results))
        for cat in categories:
            cat_results = [r for r in all_results if r.category == cat]
            output["by_category"][cat] = {
                "total": len(cat_results),
                "passed": sum(1 for r in cat_results if r.passed),
            }
        print(json.dumps(output, indent=2))
    else:
        print("-" * 75)
        passed = sum(1 for r in all_results if r.passed)
        total = len(all_results)
        pct = (passed / total * 100) if total else 0

        print(f"\nTotal: {passed}/{total} ({pct:.0f}%)")

        # Category breakdown
        categories = sorted(set(r.category for r in all_results))
        print(f"\n{'Category':<18} {'Pass':>5} {'Fail':>5} {'Rate':>6}")
        print("-" * 40)
        for cat in categories:
            cat_results = [r for r in all_results if r.category == cat]
            cat_pass = sum(1 for r in cat_results if r.passed)
            cat_total = len(cat_results)
            rate = (cat_pass / cat_total * 100) if cat_total else 0
            print(f"{cat:<18} {cat_pass:>5} {cat_total - cat_pass:>5} {rate:>5.0f}%")

        # Token usage
        total_in = sum(r.tokens_in for r in all_results)
        total_out = sum(r.tokens_out for r in all_results)
        total_ms = sum(r.duration_ms for r in all_results)
        print(f"\nTokens: {total_in:,} in, {total_out:,} out")
        print(f"Time: {total_ms / 1000:.1f}s total, "
              f"{total_ms / len(all_results):.0f}ms avg")

        # List failures
        failures = [r for r in all_results if not r.passed]
        if failures:
            print(f"\n── Failures ──")
            for r in failures:
                print(f"\n{r.scenario_id} ({r.category}):")
                if r.matched_rejects:
                    print(f"  Rejected patterns found: {r.matched_rejects}")
                if r.missing_expects:
                    print(f"  Expected patterns missing: {r.missing_expects}")
                if args.verbose:
                    print(f"  Response:\n{r.response_text[:500]}")


if __name__ == "__main__":
    main()
