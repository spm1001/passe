# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Extraction quality metrics for the bench harness.

No external deps — everything here is stdlib. ROUGE-L uses dynamic programming,
structural metrics use regex counting. Fast enough to run thousands of comparisons
per second.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class StructuralCounts:
    """Counts of structural elements in markdown."""
    headings: int = 0
    tables: int = 0          # pipe-table rows (lines starting with |)
    code_blocks: int = 0     # fenced code blocks (``` or ~~~)
    links: int = 0           # [text](url) patterns
    list_items: int = 0      # lines starting with - or * or 1.
    images: int = 0          # ![alt](url) patterns
    words: int = 0


@dataclass
class Score:
    """Quality score for a single extraction."""
    rouge_l: float = 0.0           # 0-1, F1 of longest common subsequence
    word_ratio: float = 0.0        # extracted_words / truth_words
    structural: dict = field(default_factory=dict)  # per-element preservation ratios
    category: str = ""
    fixture: str = ""

    @property
    def overall(self) -> float:
        """Weighted composite: 60% ROUGE-L, 20% word ratio, 20% structural mean."""
        struct_scores = [v for v in self.structural.values() if v is not None]
        struct_mean = sum(struct_scores) / len(struct_scores) if struct_scores else 1.0
        # Clamp word_ratio contribution (over-extraction shouldn't score > 1)
        wr = min(self.word_ratio, 1.0)
        return 0.6 * self.rouge_l + 0.2 * wr + 0.2 * struct_mean


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase word tokens for ROUGE-L."""
    return re.findall(r'\w+', text.lower())


def _lcs_length(a: list[str], b: list[str]) -> int:
    """Length of longest common subsequence. O(nm) DP."""
    if not a or not b:
        return 0
    # Space-optimized: only keep two rows
    m, n = len(a), len(b)
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)
    return prev[n]


def rouge_l(candidate: str, reference: str) -> float:
    """ROUGE-L F1 score between candidate and reference text."""
    cand_tokens = _tokenize(candidate)
    ref_tokens = _tokenize(reference)
    if not cand_tokens or not ref_tokens:
        return 0.0
    lcs = _lcs_length(cand_tokens, ref_tokens)
    precision = lcs / len(cand_tokens)
    recall = lcs / len(ref_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def count_structure(markdown: str) -> StructuralCounts:
    """Count structural elements in markdown text."""
    counts = StructuralCounts()
    lines = markdown.split('\n')
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Code blocks (fenced)
        if stripped.startswith('```') or stripped.startswith('~~~'):
            if not in_code_block:
                counts.code_blocks += 1
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # Headings
        if re.match(r'^#{1,6}\s', stripped):
            counts.headings += 1

        # Table rows (pipe tables)
        if stripped.startswith('|') and stripped.endswith('|'):
            # Skip separator rows
            if not re.match(r'^\|[\s\-:|]+\|$', stripped):
                counts.tables += 1

        # List items
        if re.match(r'^[\-\*]\s', stripped) or re.match(r'^\d+\.\s', stripped):
            counts.list_items += 1

    # Links and images (can span across lines, count in full text)
    counts.links = len(re.findall(r'\[(?!!)([^\]]+)\]\([^)]+\)', markdown))
    counts.images = len(re.findall(r'!\[[^\]]*\]\([^)]+\)', markdown))
    counts.words = len(_tokenize(markdown))

    return counts


def structural_preservation(candidate: str, reference: str) -> dict[str, float | None]:
    """How well does candidate preserve structural elements from reference?

    Returns ratios per element type. None means the element wasn't present
    in the reference (not applicable). Values > 1.0 mean over-detection.
    """
    cand = count_structure(candidate)
    ref = count_structure(reference)

    result = {}
    for element in ('headings', 'tables', 'code_blocks', 'links', 'list_items', 'images'):
        ref_count = getattr(ref, element)
        cand_count = getattr(cand, element)
        if ref_count == 0:
            result[element] = None  # not applicable
        else:
            result[element] = min(cand_count / ref_count, 1.0)  # cap at 1.0

    return result


def score_extraction(candidate: str, reference: str,
                     category: str = "", fixture: str = "") -> Score:
    """Full quality score comparing candidate extraction to ground truth."""
    ref_words = len(_tokenize(reference))
    cand_words = len(_tokenize(candidate))

    return Score(
        rouge_l=rouge_l(candidate, reference),
        word_ratio=cand_words / ref_words if ref_words > 0 else 0.0,
        structural=structural_preservation(candidate, reference),
        category=category,
        fixture=fixture,
    )
