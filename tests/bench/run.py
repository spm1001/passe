# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "trafilatura>=2.0",
#     "readability-lxml>=0.8",
#     "markdownify>=1.2",
#     "html2text>=2024.0",
# ]
# ///
"""
Bench runner — the learning loop engine.

Usage:
    uv run --script tests/bench/run.py                          # full suite, default extractor
    uv run --script tests/bench/run.py --quick                  # quick subset (~20 fixtures)
    uv run --script tests/bench/run.py --extractor trafilatura  # specific extractor
    uv run --script tests/bench/run.py --compare                # all extractors side by side
    uv run --script tests/bench/run.py --category docs          # single category
    uv run --script tests/bench/run.py --save-baseline          # save current scores
    uv run --script tests/bench/run.py --check-baseline         # fail if regression detected

The runner feeds frozen HTML through a pluggable extraction function, compares
output to Chrome ground truth, and reports quality scores.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Allow imports from bench directory
sys.path.insert(0, str(Path(__file__).parent))

from metrics import score_extraction, Score, count_structure
from extractors import EXTRACTORS


BENCH_DIR = Path(__file__).parent
CORPUS_DIR = BENCH_DIR / "corpus"
BASELINE_PATH = BENCH_DIR / "baseline.json"
REGRESSION_THRESHOLD = 0.05  # fail if overall drops more than this


def load_fixtures(category: str | None = None,
                  quick: bool = False) -> list[dict]:
    """Load fixtures from corpus directory.

    Each fixture is a dict with: path, category, url, source_html, ground_truth.
    """
    fixtures = []

    for category_dir in sorted(CORPUS_DIR.iterdir()):
        if not category_dir.is_dir():
            continue
        if category and category_dir.name != category:
            continue

        for fixture_dir in sorted(category_dir.iterdir()):
            if not fixture_dir.is_dir():
                continue

            source = fixture_dir / "source.html"
            truth = fixture_dir / "ground_truth.md"
            meta_path = fixture_dir / "meta.json"

            if not source.exists() or not truth.exists():
                continue

            meta = {}
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())

            fixtures.append({
                "path": fixture_dir,
                "category": category_dir.name,
                "name": fixture_dir.name,
                "url": meta.get("url", ""),
                "tags": meta.get("tags", []),
                "source_html": source.read_text(errors="replace"),
                "ground_truth": truth.read_text(errors="replace"),
            })

    if quick:
        # Take first 2 from each category for quick iteration
        by_cat: dict[str, list] = {}
        for f in fixtures:
            by_cat.setdefault(f["category"], []).append(f)
        fixtures = []
        for cat_fixtures in by_cat.values():
            fixtures.extend(cat_fixtures[:2])

    return fixtures


def run_extractor(extractor_name: str, fixtures: list[dict]) -> list[Score]:
    """Run an extractor against all fixtures and return scores."""
    extractor = EXTRACTORS[extractor_name]
    scores = []

    for fix in fixtures:
        try:
            result = extractor(fix["source_html"], fix["url"])
        except Exception as e:
            print(f"  ERROR {fix['category']}/{fix['name']}: {e}", file=sys.stderr)
            result = ""

        score = score_extraction(
            candidate=result,
            reference=fix["ground_truth"],
            category=fix["category"],
            fixture=fix["name"],
        )
        scores.append(score)

    return scores


def format_report(extractor_name: str, scores: list[Score]) -> str:
    """Format a human-readable report of scores."""
    if not scores:
        return f"No fixtures found.\n"

    lines = []
    lines.append(f"{'=' * 70}")
    lines.append(f"  Extractor: {extractor_name}")
    lines.append(f"  Fixtures:  {len(scores)}")
    lines.append(f"{'=' * 70}")

    # Per-category breakdown
    by_cat: dict[str, list[Score]] = {}
    for s in scores:
        by_cat.setdefault(s.category, []).append(s)

    lines.append("")
    lines.append(f"  {'Category':<18} {'Count':>5}  {'ROUGE-L':>8}  {'WordRatio':>9}  {'Overall':>8}")
    lines.append(f"  {'-' * 18} {'-' * 5}  {'-' * 8}  {'-' * 9}  {'-' * 8}")

    for cat in sorted(by_cat):
        cat_scores = by_cat[cat]
        n = len(cat_scores)
        avg_rouge = sum(s.rouge_l for s in cat_scores) / n
        avg_wr = sum(min(s.word_ratio, 1.0) for s in cat_scores) / n
        avg_overall = sum(s.overall for s in cat_scores) / n
        lines.append(f"  {cat:<18} {n:>5}  {avg_rouge:>8.3f}  {avg_wr:>9.3f}  {avg_overall:>8.3f}")

    # Totals
    n = len(scores)
    avg_rouge = sum(s.rouge_l for s in scores) / n
    avg_wr = sum(min(s.word_ratio, 1.0) for s in scores) / n
    avg_overall = sum(s.overall for s in scores) / n
    lines.append(f"  {'-' * 18} {'-' * 5}  {'-' * 8}  {'-' * 9}  {'-' * 8}")
    lines.append(f"  {'TOTAL':<18} {n:>5}  {avg_rouge:>8.3f}  {avg_wr:>9.3f}  {avg_overall:>8.3f}")

    # Structural preservation summary
    all_struct: dict[str, list[float]] = {}
    for s in scores:
        for elem, ratio in s.structural.items():
            if ratio is not None:
                all_struct.setdefault(elem, []).append(ratio)

    if all_struct:
        lines.append("")
        lines.append("  Structural preservation (where applicable):")
        for elem in sorted(all_struct):
            vals = all_struct[elem]
            avg = sum(vals) / len(vals)
            lines.append(f"    {elem:<14} {avg:.3f}  (n={len(vals)})")

    # Bottom 5 — worst scoring fixtures
    bottom = sorted(scores, key=lambda s: s.overall)[:5]
    if bottom:
        lines.append("")
        lines.append("  Worst fixtures:")
        for s in bottom:
            lines.append(f"    {s.overall:.3f}  {s.category}/{s.fixture}")

    lines.append("")
    return "\n".join(lines)


def save_baseline(scores: list[Score], extractor_name: str) -> None:
    """Save scores as baseline for regression detection."""
    by_cat: dict[str, dict] = {}
    for s in scores:
        by_cat.setdefault(s.category, []).append(s.overall)

    baseline = {
        "extractor": extractor_name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fixture_count": len(scores),
        "overall": sum(s.overall for s in scores) / len(scores),
        "by_category": {
            cat: sum(vals) / len(vals)
            for cat, vals in by_cat.items()
        },
    }

    BASELINE_PATH.write_text(json.dumps(baseline, indent=2) + "\n")
    print(f"Baseline saved to {BASELINE_PATH}", file=sys.stderr)


def check_baseline(scores: list[Score]) -> bool:
    """Check if current scores regress from baseline. Returns True if OK."""
    if not BASELINE_PATH.exists():
        print("No baseline found. Run with --save-baseline first.", file=sys.stderr)
        return True  # no baseline = no regression

    baseline = json.loads(BASELINE_PATH.read_text())
    current_overall = sum(s.overall for s in scores) / len(scores)
    baseline_overall = baseline["overall"]
    delta = current_overall - baseline_overall

    print(f"\n  Baseline: {baseline_overall:.3f}  Current: {current_overall:.3f}  Delta: {delta:+.3f}")

    if delta < -REGRESSION_THRESHOLD:
        print(f"  REGRESSION DETECTED: overall dropped by {abs(delta):.3f} "
              f"(threshold: {REGRESSION_THRESHOLD})", file=sys.stderr)
        return False

    # Per-category check
    by_cat: dict[str, list] = {}
    for s in scores:
        by_cat.setdefault(s.category, []).append(s.overall)

    regressions = []
    for cat, vals in by_cat.items():
        current = sum(vals) / len(vals)
        baseline_cat = baseline.get("by_category", {}).get(cat)
        if baseline_cat is not None:
            cat_delta = current - baseline_cat
            if cat_delta < -REGRESSION_THRESHOLD:
                regressions.append((cat, baseline_cat, current, cat_delta))

    if regressions:
        print(f"  Category regressions:", file=sys.stderr)
        for cat, base, curr, d in regressions:
            print(f"    {cat}: {base:.3f} → {curr:.3f} ({d:+.3f})", file=sys.stderr)
        return False

    print("  No regressions detected.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Extraction bench runner")
    parser.add_argument("--extractor", "-e", default="trafilatura",
                        choices=list(EXTRACTORS.keys()),
                        help="Extractor to test (default: trafilatura)")
    parser.add_argument("--compare", action="store_true",
                        help="Run all extractors side by side")
    parser.add_argument("--category", "-c",
                        help="Run only this category")
    parser.add_argument("--quick", "-q", action="store_true",
                        help="Quick mode: first 2 fixtures per category")
    parser.add_argument("--save-baseline", action="store_true",
                        help="Save current scores as baseline")
    parser.add_argument("--check-baseline", action="store_true",
                        help="Check for regressions against saved baseline")
    parser.add_argument("--json", action="store_true",
                        help="Output scores as JSON")

    args = parser.parse_args()

    fixtures = load_fixtures(category=args.category, quick=args.quick)
    if not fixtures:
        print("No fixtures found. Run snapshot.py to populate the corpus.", file=sys.stderr)
        sys.exit(1)

    extractors_to_run = list(EXTRACTORS.keys()) if args.compare else [args.extractor]

    all_results = {}
    for ext_name in extractors_to_run:
        t0 = time.monotonic()
        scores = run_extractor(ext_name, fixtures)
        elapsed = time.monotonic() - t0

        if args.json:
            all_results[ext_name] = {
                "elapsed_ms": round(elapsed * 1000, 1),
                "scores": [
                    {
                        "category": s.category,
                        "fixture": s.fixture,
                        "rouge_l": round(s.rouge_l, 4),
                        "word_ratio": round(s.word_ratio, 4),
                        "overall": round(s.overall, 4),
                        "structural": {
                            k: round(v, 4) if v is not None else None
                            for k, v in s.structural.items()
                        },
                    }
                    for s in scores
                ],
            }
        else:
            report = format_report(ext_name, scores)
            print(report)
            print(f"  Elapsed: {elapsed:.1f}s\n")

        if ext_name == args.extractor:
            if args.save_baseline:
                save_baseline(scores, ext_name)
            if args.check_baseline:
                ok = check_baseline(scores)
                if not ok:
                    sys.exit(1)

    if args.json:
        print(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    main()
