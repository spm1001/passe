"""Tests for cmd_explain: dry-run script validation."""

import json
from io import StringIO
from unittest.mock import patch

import pytest

from passe.commands import cmd_explain


def _run_explain(inline=None, source=None):
    """Run cmd_explain capturing stdout. Returns (parsed_json, exit_code)."""
    with patch('sys.stdout', new_callable=StringIO) as out:
        try:
            if inline is not None:
                cmd_explain(None, inline=inline)
            else:
                cmd_explain(source)
        except SystemExit as e:
            return json.loads(out.getvalue()), e.code
    return json.loads(out.getvalue()), 0


def test_valid_script():
    result, code = _run_explain(inline='goto https://example.com; screenshot /tmp/out.png')
    assert code == 0
    assert result['ok'] is True
    assert result['steps'] == 2
    assert result['verbs'] == ['goto', 'screenshot']
    assert result['urls'] == ['https://example.com']
    assert result['errors'] == []


def test_empty_script():
    result, code = _run_explain(inline='')
    assert code == 0
    assert result['steps'] == 0


def test_unknown_verb_with_suggestion():
    result, code = _run_explain(inline='navigate https://example.com')
    assert code == 1
    assert result['ok'] is False
    assert len(result['errors']) == 1
    assert 'did you mean "goto"' in result['errors'][0]['error']


def test_missing_args():
    result, code = _run_explain(inline='goto')
    assert code == 1
    assert 'requires at least 1' in result['errors'][0]['error']


def test_multiple_errors():
    result, code = _run_explain(inline='goto; click')
    assert code == 1
    assert len(result['errors']) == 2


def test_goto_read_warning():
    result, code = _run_explain(inline='goto https://example.com; read /tmp/out.md')
    assert code == 0
    assert any('fetch verb' in w for w in result['warnings'])


def test_goto_wait_read_warning():
    result, code = _run_explain(inline='goto https://example.com; wait 1000; read /tmp/out.md')
    assert code == 0
    assert any('auto-waits' in w for w in result['warnings'])


def test_selectors_collected():
    result, code = _run_explain(inline='goto https://example.com; click .btn; type #input hello')
    assert code == 0
    assert '.btn' in result['selectors']
    assert '#input' in result['selectors']


def test_files_collected():
    result, code = _run_explain(inline='goto https://example.com; screenshot /tmp/out.png; eval-to /tmp/data.json document.title')
    assert code == 0
    paths = [f['path'] for f in result['files']]
    assert '/tmp/out.png' in paths
    assert '/tmp/data.json' in paths


def test_capture_not_first_warning():
    result, code = _run_explain(inline='goto https://example.com; capture /tmp/reqs.jsonl')
    assert code == 0
    assert any('not the first verb' in w for w in result['warnings'])


def test_capture_first_no_warning():
    result, code = _run_explain(inline='capture /tmp/reqs.jsonl; goto https://example.com')
    assert code == 0
    assert not any('not the first verb' in w for w in result['warnings'])


def test_eval_file_missing():
    result, code = _run_explain(inline='eval-file /nonexistent/script.js')
    assert code == 1
    assert 'File not found' in result['errors'][0]['error']


def test_from_file(tmp_path):
    script = tmp_path / 'test.passe'
    script.write_text('goto https://example.com\nscreenshot /tmp/out.png\n')
    result, code = _run_explain(source=str(script))
    assert code == 0
    assert result['steps'] == 2


def test_click_text_selector():
    result, code = _run_explain(inline='goto https://example.com; click-text "Accept"')
    assert code == 0
    assert 'text:Accept' in result['selectors']


def test_complex_inline_warning():
    """Long inline scripts trigger complexity warning."""
    long_script = 'goto https://example.com; click .a; click .b; click .c; click .d; click .e'
    result, code = _run_explain(inline=long_script)
    assert code == 0
    assert any('heredoc' in w for w in result['warnings'])
