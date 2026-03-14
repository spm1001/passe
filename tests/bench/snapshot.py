# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Corpus snapshot tool — captures frozen HTML + Chrome ground truth.

Usage:
    uv run --script tests/bench/snapshot.py <category> <url>
    uv run --script tests/bench/snapshot.py article https://simonwillison.net/2024/Dec/19/...
    uv run --script tests/bench/snapshot.py --from-list urls.txt
    uv run --script tests/bench/snapshot.py --refresh article/simonwillison-net--some-post

urls.txt format (one per line):
    article https://simonwillison.net/2024/Dec/19/some-post
    docs https://docs.python.org/3/library/json.html
    # comments ignored, blank lines ignored

For each URL, this tool:
1. curl -s to get raw HTTP HTML (what the fast-path would see)
2. passe fetch to get Chrome-rendered extraction (ground truth)
3. Saves both as fixtures with metadata
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse


CORPUS_DIR = Path(__file__).parent / "corpus"
VALID_CATEGORIES = [
    "article", "docs", "code-heavy", "table-heavy",
    "spa", "nextjs", "paywall", "complex",
]


def slugify(url: str) -> str:
    """URL → short directory name."""
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "")
    # Take the path, strip leading/trailing slashes, replace slashes with --
    path = parsed.path.strip("/").replace("/", "--")
    # Clean non-alphanumeric
    slug = re.sub(r'[^a-z0-9\-]', '-', f"{host}--{path}".lower())
    slug = re.sub(r'-{2,}', '-', slug).strip('-')
    # Truncate but keep unique
    if len(slug) > 60:
        h = hashlib.md5(url.encode()).hexdigest()[:8]
        slug = slug[:50] + "--" + h
    return slug


def fetch_raw_html(url: str) -> tuple[str, int]:
    """Fetch raw HTML via curl (what HTTP fast-path would see)."""
    result = subprocess.run(
        ["curl", "-sL", "-o", "-", "-w", "\n%{http_code}",
         "-H", "User-Agent: Mozilla/5.0 (compatible; passe-bench/1.0)",
         "-H", "Accept: text/html,application/xhtml+xml",
         "--max-time", "30",
         url],
        capture_output=True, text=True, timeout=35,
    )
    # Last line is status code
    lines = result.stdout.rsplit("\n", 1)
    if len(lines) == 2:
        html, status_str = lines
        try:
            status = int(status_str)
        except ValueError:
            status = 0
    else:
        html = result.stdout
        status = 0

    return html, status


def fetch_chrome_ground_truth(url: str, cdp: str | None = None) -> tuple[str, dict]:
    """Fetch via passe (Chrome ground truth). Returns (markdown, summary_json)."""
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, prefix="bench-") as f:
        tmp_path = f.name

    env = dict(os.environ)
    if cdp:
        env["PASSE_CDP"] = cdp

    try:
        result = subprocess.run(
            ["passe", "fetch", url, tmp_path],
            capture_output=True, text=True, timeout=60,
            env=env,
        )

        summary = {}
        if result.stdout.strip():
            try:
                summary = json.loads(result.stdout.strip())
            except json.JSONDecodeError:
                pass

        md_content = ""
        tmp = Path(tmp_path)
        if tmp.exists():
            md_content = tmp.read_text(errors="replace")
            tmp.unlink()

        if not md_content and summary.get("content"):
            md_content = summary["content"]

        return md_content, summary
    except subprocess.TimeoutExpired:
        return "", {"error": "timeout"}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def snapshot_url(category: str, url: str, tags: list[str] | None = None,
                 cdp: str | None = None) -> Path | None:
    """Snapshot a single URL into the corpus. Returns fixture path or None."""
    slug = slugify(url)
    fixture_dir = CORPUS_DIR / category / slug

    if fixture_dir.exists():
        print(f"  EXISTS: {category}/{slug} — skipping (use --refresh to re-snapshot)")
        return fixture_dir

    print(f"  Fetching raw HTML... ", end="", flush=True)
    html, status = fetch_raw_html(url)
    if not html or status >= 400:
        print(f"FAILED (status {status})")
        return None
    print(f"OK ({len(html):,} bytes, status {status})")

    print(f"  Fetching Chrome ground truth... ", end="", flush=True)
    ground_truth, summary = fetch_chrome_ground_truth(url, cdp=cdp)
    if not ground_truth:
        print(f"FAILED ({summary.get('error', 'empty')})")
        return None
    source = "unknown"
    if summary.get("files"):
        source = summary["files"][0].get("source", "unknown")
    elif summary.get("source"):
        source = summary["source"]
    words = len(ground_truth.split())
    print(f"OK ({words} words, source: {source})")

    # Save
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "source.html").write_text(html)
    (fixture_dir / "ground_truth.md").write_text(ground_truth)
    (fixture_dir / "meta.json").write_text(json.dumps({
        "url": url,
        "category": category,
        "tags": tags or [],
        "snapshot_date": time.strftime("%Y-%m-%d"),
        "http_status": status,
        "html_bytes": len(html),
        "ground_truth_words": words,
        "ground_truth_source": source,
        "chrome_summary": summary,
    }, indent=2) + "\n")

    print(f"  SAVED: {category}/{slug}")
    return fixture_dir


def refresh_fixture(fixture_path: str) -> None:
    """Re-snapshot an existing fixture."""
    parts = fixture_path.split("/")
    if len(parts) != 2:
        print(f"Expected category/fixture-name, got: {fixture_path}", file=sys.stderr)
        sys.exit(1)

    category, name = parts
    fixture_dir = CORPUS_DIR / category / name
    meta_path = fixture_dir / "meta.json"

    if not meta_path.exists():
        print(f"Fixture not found: {fixture_path}", file=sys.stderr)
        sys.exit(1)

    meta = json.loads(meta_path.read_text())
    url = meta["url"]

    # Remove and re-snapshot
    import shutil
    shutil.rmtree(fixture_dir)
    snapshot_url(category, url, tags=meta.get("tags", []))


def main():
    parser = argparse.ArgumentParser(description="Corpus snapshot tool")
    parser.add_argument("category", nargs="?", choices=VALID_CATEGORIES,
                        help="Fixture category")
    parser.add_argument("url", nargs="?", help="URL to snapshot")
    parser.add_argument("--from-list", metavar="FILE",
                        help="Read category+URL pairs from file")
    parser.add_argument("--refresh", metavar="CATEGORY/NAME",
                        help="Re-snapshot an existing fixture")
    parser.add_argument("--tags", nargs="*", default=[],
                        help="Tags for the fixture")
    parser.add_argument("--cdp", default=None,
                        help="CDP endpoint for Chrome (default: PASSE_CDP or localhost:9222)")

    args = parser.parse_args()

    if args.refresh:
        refresh_fixture(args.refresh)
        return

    if args.from_list:
        urls_file = Path(args.from_list)
        if not urls_file.exists():
            print(f"File not found: {args.from_list}", file=sys.stderr)
            sys.exit(1)

        entries = []
        for line in urls_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                print(f"Bad line (expected 'category url'): {line}", file=sys.stderr)
                continue
            cat, url = parts
            if cat not in VALID_CATEGORIES:
                print(f"Unknown category '{cat}' for {url}", file=sys.stderr)
                continue
            entries.append((cat, url))

        print(f"Snapshotting {len(entries)} URLs...\n")
        ok = 0
        for cat, url in entries:
            print(f"[{cat}] {url}")
            if snapshot_url(cat, url, cdp=args.cdp):
                ok += 1
            print()

        print(f"\nDone: {ok}/{len(entries)} snapshots saved to {CORPUS_DIR}")
        return

    if not args.category or not args.url:
        parser.print_help()
        sys.exit(1)

    print(f"[{args.category}] {args.url}")
    snapshot_url(args.category, args.url, tags=args.tags, cdp=args.cdp)


if __name__ == "__main__":
    main()
