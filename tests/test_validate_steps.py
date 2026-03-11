"""Tests for validate_steps — static script validation."""

from passe.parser import validate_steps


def test_valid_script_no_errors():
    steps = [
        ('goto', ['https://example.com']),
        ('click', ['.btn']),
        ('screenshot', ['/tmp/out.png']),
    ]
    assert validate_steps(steps) == []


def test_unknown_verb():
    steps = [('navigate', ['https://example.com'])]
    errors = validate_steps(steps)
    assert len(errors) == 1
    assert errors[0]['line'] == 1
    assert 'did you mean "goto"' in errors[0]['error']


def test_unknown_verb_no_suggestion():
    steps = [('xyzzy', [])]
    errors = validate_steps(steps)
    assert len(errors) == 1
    assert 'Unknown verb: xyzzy' in errors[0]['error']


def test_missing_args():
    steps = [('goto', []), ('type', ['#input'])]  # type needs 2 args
    errors = validate_steps(steps)
    assert len(errors) == 2
    assert 'goto requires at least 1' in errors[0]['error']
    assert 'type requires at least 2' in errors[1]['error']


def test_zero_arg_verbs_ok():
    """Verbs like back, forward, wait-idle accept 0 args."""
    steps = [
        ('back', []),
        ('forward', []),
        ('wait-idle', []),
        ('screenshot', []),
        ('snapshot', []),
        ('read', []),
    ]
    assert validate_steps(steps) == []


def test_eval_file_missing(tmp_path):
    steps = [('eval-file', ['/nonexistent/file.js'])]
    errors = validate_steps(steps)
    assert len(errors) == 1
    assert 'File not found' in errors[0]['error']


def test_eval_file_exists(tmp_path):
    js_file = tmp_path / 'test.js'
    js_file.write_text('1+1')
    steps = [('eval-file', [str(js_file)])]
    assert validate_steps(steps) == []


def test_eval_file_to_missing(tmp_path):
    steps = [('eval-file-to', ['/tmp/out.json', '/nonexistent/extract.js'])]
    errors = validate_steps(steps)
    assert len(errors) == 1
    assert 'File not found' in errors[0]['error']


def test_multiple_errors():
    steps = [
        ('navigate', ['url']),     # unknown verb
        ('click', []),             # missing arg
        ('fill', ['selector']),    # needs 2 args
    ]
    errors = validate_steps(steps)
    assert len(errors) == 3


def test_line_numbers_are_1_based():
    steps = [
        ('goto', ['url']),
        ('click', []),  # error on step 2
    ]
    errors = validate_steps(steps)
    assert errors[0]['line'] == 2
