"""Tests for inline -c script complexity hints."""

import sys
from io import StringIO

from passe.commands import _emit_inline_hints


def _capture_hints(steps, inline_text):
    """Run _emit_inline_hints and return captured stderr."""
    buf = StringIO()
    old = sys.stderr
    sys.stderr = buf
    try:
        _emit_inline_hints(steps, inline_text)
    finally:
        sys.stderr = old
    return buf.getvalue()


def test_short_script_no_hint():
    steps = [('goto', ['https://example.com']), ('screenshot', ['/tmp/out.png'])]
    output = _capture_hints(steps, 'goto https://example.com; screenshot /tmp/out.png')
    assert output == ''


def test_five_verbs_emits_heredoc_hint():
    steps = [('goto', ['u']), ('click', ['a']), ('wait', ['0.5']),
             ('type', ['b', 'c']), ('screenshot', ['p'])]
    output = _capture_hints(steps, 'goto u; click a; wait 0.5; type b c; screenshot p')
    assert 'heredoc' in output
    assert 'eval-file' not in output


def test_long_inline_emits_heredoc_hint():
    steps = [('goto', ['https://example.com']), ('screenshot', ['/tmp/out.png'])]
    inline = 'x' * 201
    output = _capture_hints(steps, inline)
    assert 'heredoc' in output


def test_long_eval_emits_evalfile_hint():
    long_js = '(async () => { const r = await fetch("/api/search?q=test"); const data = await r.json(); return JSON.stringify(data.results.map(x => x.title)); })()'
    assert len(long_js) > 120
    steps = [('goto', ['https://example.com']), ('eval', [long_js])]
    output = _capture_hints(steps, f'goto https://example.com; eval {long_js}')
    assert 'eval-file' in output


def test_long_eval_to_emits_evalfile_hint():
    long_js = 'a' * 121
    steps = [('eval-to', ['/tmp/out.json', long_js])]
    output = _capture_hints(steps, f'eval-to /tmp/out.json {long_js}')
    assert 'eval-file' in output


def test_long_assert_emits_evalfile_hint():
    long_js = 'document.querySelectorAll(".item").length > 0 && ' + 'x' * 100
    assert len(long_js) > 120
    steps = [('assert', [long_js])]
    output = _capture_hints(steps, f'assert {long_js}')
    assert 'eval-file' in output


def test_eval_hint_fires_once():
    long_js = 'a' * 121
    steps = [('eval', [long_js]), ('eval', [long_js])]
    output = _capture_hints(steps, f'eval {long_js}; eval {long_js}')
    assert output.count('eval-file') == 1


def test_both_hints_can_fire():
    long_js = 'a' * 121
    steps = [('goto', ['u']), ('click', ['a']), ('wait', ['0.5']),
             ('type', ['b', 'c']), ('eval', [long_js])]
    inline = f'goto u; click a; wait 0.5; type b c; eval {long_js}'
    output = _capture_hints(steps, inline)
    assert 'heredoc' in output
    assert 'eval-file' in output


def test_short_eval_no_hint():
    steps = [('eval', ['document.title'])]
    output = _capture_hints(steps, 'eval document.title')
    assert output == ''
