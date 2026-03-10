"""Tests for goto+read → fetch hint detection."""

import sys
from io import StringIO

from passe.commands import _emit_fetch_hint


def _capture_hints(steps):
    buf = StringIO()
    old = sys.stderr
    sys.stderr = buf
    try:
        _emit_fetch_hint(steps)
    finally:
        sys.stderr = old
    return buf.getvalue()


def test_goto_read_emits_fetch_hint():
    steps = [('goto', ['https://example.com']), ('read', ['/tmp/out.md'])]
    output = _capture_hints(steps)
    assert 'fetch' in output
    assert 'auto-waits' not in output


def test_goto_wait_read_emits_both_hints():
    steps = [('goto', ['https://example.com']), ('wait', ['1']),
             ('read', ['/tmp/out.md'])]
    output = _capture_hints(steps)
    assert 'fetch' in output
    assert 'auto-waits' in output


def test_goto_multiple_waits_read_emits_both():
    steps = [('goto', ['https://example.com']), ('wait', ['0.5']),
             ('wait', ['0.5']), ('read', ['/tmp/out.md'])]
    output = _capture_hints(steps)
    assert 'fetch' in output
    assert 'auto-waits' in output


def test_goto_click_read_no_hint():
    steps = [('goto', ['https://example.com']), ('click', ['#btn']),
             ('read', ['/tmp/out.md'])]
    output = _capture_hints(steps)
    assert output == ''


def test_goto_screenshot_no_hint():
    steps = [('goto', ['https://example.com']), ('screenshot', ['/tmp/out.png'])]
    output = _capture_hints(steps)
    assert output == ''


def test_fetch_verb_no_hint():
    steps = [('fetch', ['https://example.com', '/tmp/out.md'])]
    output = _capture_hints(steps)
    assert output == ''


def test_hint_fires_once_for_multiple_goto_read():
    steps = [
        ('goto', ['https://a.com']), ('read', ['/tmp/a.md']),
        ('goto', ['https://b.com']), ('read', ['/tmp/b.md']),
    ]
    output = _capture_hints(steps)
    assert output.count('fetch') == 1


def test_hint_fires_once_for_mixed_patterns():
    steps = [
        ('goto', ['https://a.com']), ('read', ['/tmp/a.md']),
        ('goto', ['https://b.com']), ('wait', ['0.5']), ('read', ['/tmp/b.md']),
    ]
    output = _capture_hints(steps)
    assert output.count('fetch') == 1
    assert output.count('auto-waits') == 1


def test_standalone_read_no_hint():
    steps = [('goto', ['https://example.com']), ('click', ['#a']),
             ('wait-for', ['.content']), ('read', ['/tmp/out.md'])]
    output = _capture_hints(steps)
    assert output == ''
