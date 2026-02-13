# /// script
# requires-python = ">=3.10"
# dependencies = ["rjsmin"]
# ///
"""Minify JS constants in _libs.py.

Reads the current _libs.py, minifies each JS string constant with rjsmin,
and writes back. Preserves the EXTRACT_JS logic while stripping comments
and whitespace from Readability.js and Turndown.js.

Usage: uv run --script scripts/minify_libs.py
"""

import ast
import sys
from pathlib import Path

import rjsmin

LIBS_PATH = Path(__file__).parent.parent / "src" / "passe" / "_libs.py"

CONSTANTS = ["READABILITY_JS", "TURNDOWN_JS", "EXTRACT_JS"]


def main():
    content = LIBS_PATH.read_text()
    lines = content.split("\n")
    before_size = len(content)

    new_lines = []
    for line in lines:
        matched = False
        for name in CONSTANTS:
            if line.startswith(f"{name} = "):
                old_val = ast.literal_eval(line.split(" = ", 1)[1])
                new_val = rjsmin.jsmin(old_val)
                new_lines.append(f"{name} = {new_val!r}")
                saved = len(old_val) - len(new_val)
                print(f"  {name}: {len(old_val):,} → {len(new_val):,} chars ({saved:,} saved)")
                matched = True
                break
        if not matched:
            new_lines.append(line)

    new_content = "\n".join(new_lines)
    LIBS_PATH.write_text(new_content)
    after_size = len(new_content)
    print(f"\n  _libs.py: {before_size:,} → {after_size:,} bytes ({before_size - after_size:,} saved)")


if __name__ == "__main__":
    main()
