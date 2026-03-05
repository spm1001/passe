"""Tests for PASSE_HINTS=0 and --quiet hint suppression."""

import os
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from passe.commands import _emit_fetch_hint, _emit_inline_hints
from passe.parser import parse_script


class TestHintSuppression:
    """PASSE_HINTS=0 suppresses all hint output."""

    def test_fetch_hint_suppressed(self):
        steps = parse_script('goto https://example.com\nread /tmp/out.md')
        with patch.dict(os.environ, {'PASSE_HINTS': '0'}):
            with patch('sys.stderr', new_callable=StringIO) as err:
                _emit_fetch_hint(steps)
            assert err.getvalue() == ''

    def test_fetch_hint_enabled_by_default(self):
        steps = parse_script('goto https://example.com\nread /tmp/out.md')
        with patch.dict(os.environ, {}, clear=True):
            with patch('sys.stderr', new_callable=StringIO) as err:
                _emit_fetch_hint(steps)
            assert 'hint' in err.getvalue()

    def test_inline_hint_suppressed(self):
        steps = parse_script('goto https://a.com\nclick b\ntype c d\n'
                             'press Enter\nwait-for .x\nscreenshot /tmp/o.png')
        with patch.dict(os.environ, {'PASSE_HINTS': '0'}):
            with patch('sys.stderr', new_callable=StringIO) as err:
                _emit_inline_hints(steps, 'x' * 300)
            assert err.getvalue() == ''

    def test_inline_hint_enabled_by_default(self):
        steps = parse_script('goto https://a.com\nclick b\ntype c d\n'
                             'press Enter\nwait-for .x\nscreenshot /tmp/o.png')
        with patch.dict(os.environ, {}, clear=True):
            with patch('sys.stderr', new_callable=StringIO) as err:
                _emit_inline_hints(steps, 'x' * 300)
            assert 'hint' in err.getvalue()


class TestQuietFlag:
    """--quiet flag sets PASSE_HINTS=0 before running."""

    def setup_method(self):
        self._orig_hints = os.environ.pop('PASSE_HINTS', None)

    def teardown_method(self):
        if self._orig_hints is not None:
            os.environ['PASSE_HINTS'] = self._orig_hints
        else:
            os.environ.pop('PASSE_HINTS', None)

    def test_quiet_flag_sets_env(self):
        import passe.cli as cli

        mock_cmd = MagicMock(return_value='sentinel')
        with patch.object(sys, 'argv',
                          ['passe', 'run', '--quiet', '-c',
                           'goto https://example.com']):
            with patch('passe.cli.cmd_run', mock_cmd), \
                 patch('passe.cli._run'):
                cli.main()

            assert os.environ.get('PASSE_HINTS') == '0'

    def test_q_shorthand(self):
        import passe.cli as cli

        mock_cmd = MagicMock(return_value='sentinel')
        with patch.object(sys, 'argv',
                          ['passe', 'run', '-q', '-c',
                           'goto https://example.com']):
            with patch('passe.cli.cmd_run', mock_cmd), \
                 patch('passe.cli._run'):
                cli.main()

            assert os.environ.get('PASSE_HINTS') == '0'
