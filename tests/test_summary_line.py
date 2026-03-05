"""Tests for human-readable stderr summary line."""

import sys
from io import StringIO

from passe.commands import _emit_summary


def _capture(summary):
    buf = StringIO()
    old = sys.stderr
    sys.stderr = buf
    try:
        _emit_summary(summary)
    finally:
        sys.stderr = old
    return buf.getvalue().strip()


def test_success_basic():
    line = _capture({'ok': True, 'steps': 3, 'total_ms': 443.2})
    assert line.startswith('[passe] done:')
    assert '3 steps' in line
    assert '443ms' in line


def test_success_with_screenshot():
    line = _capture({
        'ok': True, 'steps': 2, 'total_ms': 200,
        'files': [{'path': '/tmp/out.png', 'verb': 'screenshot',
                    'format': 'png', 'kb': 234.5}],
    })
    assert '/tmp/out.png (234KB)' in line


def test_success_with_read():
    line = _capture({
        'ok': True, 'steps': 2, 'total_ms': 500,
        'files': [{'path': '/tmp/page.md', 'verb': 'read',
                    'source': 'trafilatura', 'word_count': 1500}],
    })
    assert '/tmp/page.md (1500 words)' in line


def test_success_with_fetch():
    line = _capture({
        'ok': True, 'steps': 1, 'total_ms': 800,
        'files': [{'path': '/tmp/article.md', 'verb': 'fetch',
                    'word_count': 3200}],
    })
    assert '3200 words' in line


def test_success_with_capture():
    line = _capture({
        'ok': True, 'steps': 5, 'total_ms': 2000,
        'files': [{'path': '/tmp/net.jsonl', 'verb': 'capture',
                    'requests': 42}],
    })
    assert '42 requests' in line


def test_success_with_final_url():
    line = _capture({
        'ok': True, 'steps': 1, 'total_ms': 100,
        'final_url': 'https://example.com/landing',
    })
    assert 'https://example.com/landing' in line


def test_failure():
    line = _capture({
        'ok': False, 'steps': 3, 'total_ms': 150,
        'failed_at': 2, 'verb': 'click', 'error': 'Element not found: #btn',
    })
    assert line.startswith('[passe] failed')
    assert 'step 2 (click)' in line
    assert 'Element not found' in line


def test_success_no_files():
    line = _capture({'ok': True, 'steps': 1, 'total_ms': 50})
    assert '[passe] done: 1 steps, 50ms' in line
