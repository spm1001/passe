#!/usr/bin/env python3
"""Analyze naive survey results. Usage: python3 naive-survey-analyze.py <outdir>"""

import json, re, sys
from collections import Counter
from pathlib import Path


def try_parse_json(text: str):
    """Try to extract JSON from text that may have markdown fencing or preamble."""
    text = text.strip()
    # Strip markdown fencing
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def analyze(outdir: str):
    outdir = Path(outdir)
    scenarios = ["login", "screenshot", "streamlit", "spa_nav", "tab_reuse", "cookie_banner"]

    for scenario in scenarios:
        files = sorted(outdir.glob(f"{scenario}_*.json"))
        results = []
        parse_errors = 0
        for f in files:
            with open(f) as fh:
                parsed = try_parse_json(fh.read())
            if parsed:
                results.append(parsed)
            else:
                parse_errors += 1

        if not results:
            print(f"\n{'='*60}")
            print(f"  {scenario}: NO VALID RESPONSES ({parse_errors} parse errors)")
            continue

        n = len(results)
        print(f"\n{'='*60}")
        print(f"  {scenario} (n={n}, {parse_errors} parse errors)")
        print(f"{'='*60}")

        # Navigation verb
        nav = Counter(r.get("nav_verb", "???") for r in results)
        print(f"\n  Navigation verb:")
        for verb, count in nav.most_common():
            pct = count / n * 100
            bar = "\u2588" * int(pct / 5)
            print(f"    {verb:<15} {count:>2}/{n}  {pct:>5.1f}%  {bar}")

        # Wait verb
        wait = Counter(r.get("wait_verb") or "???" for r in results)
        print(f"\n  Wait verb:")
        for verb, count in wait.most_common():
            pct = count / n * 100
            bar = "\u2588" * int(pct / 5)
            print(f"    {verb:<15} {count:>2}/{n}  {pct:>5.1f}%  {bar}")

        # Wait value (seconds vs ms)
        wait_vals = [r.get("wait_value") for r in results if r.get("wait_value")]
        if wait_vals:
            print(f"\n  Wait values: {wait_vals}")
            numeric = []
            for v in wait_vals:
                try:
                    numeric.append(float(str(v).rstrip("ms").rstrip("s")))
                except (ValueError, TypeError):
                    pass
            if numeric:
                gt_100 = sum(1 for v in numeric if v >= 100)
                lt_100 = sum(1 for v in numeric if v < 100)
                print(f"    Likely milliseconds (>=100): {gt_100}/{len(numeric)}")
                print(f"    Likely seconds (<100):       {lt_100}/{len(numeric)}")

        # Click pattern
        click = Counter(r.get("click_pattern") or "???" for r in results)
        print(f"\n  Click-by-text pattern:")
        for pattern, count in click.most_common():
            pct = count / n * 100
            print(f"    {str(pattern):<45} {count:>2}/{n}  {pct:>5.1f}%")

        # Screenshot path
        has_path = Counter(r.get("screenshot_has_path", "???") for r in results)
        print(f"\n  Screenshot has path:")
        for val, count in has_path.most_common():
            print(f"    {str(val):<15} {count:>2}/{n}")

        # Uses run subcommand
        uses_run = Counter(r.get("uses_run_subcommand", "???") for r in results)
        print(f"\n  Uses 'run' subcommand:")
        for val, count in uses_run.most_common():
            print(f"    {str(val):<15} {count:>2}/{n}")

        # Extract verb (where applicable)
        extract = [r.get("extract_verb") for r in results if r.get("extract_verb")]
        if extract:
            ec = Counter(extract)
            print(f"\n  Extract/read verb:")
            for verb, count in ec.most_common():
                print(f"    {verb:<15} {count:>2}/{len(extract)}")

        # All verbs used (flattened)
        all_verbs = Counter()
        for r in results:
            for v in r.get("verbs_used", []):
                all_verbs[v] += 1
        print(f"\n  All verbs (frequency across {n} responses):")
        for verb, count in all_verbs.most_common(15):
            print(f"    {verb:<15} {count:>2}")

    print(f"\n{'='*60}")
    print("  DONE")
    print(f"{'='*60}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Find latest
        outdir = max(
            (p for p in Path("/tmp").glob("naive-survey-v2-*") if p.is_dir()),
            key=lambda p: p.name
        )
    else:
        outdir = sys.argv[1]
    analyze(str(outdir))
