"""Tests for self-healing: snapshot on click/type failure."""

import asyncio
import json
from io import StringIO
from unittest.mock import AsyncMock, patch
import sys

import pytest

from passe.parser import parse_script
from passe.runner import run_script


FAKE_SNAPSHOT = (
    '[0] button "Sign in" css=#sign-in\n'
    '[1] link "Blog" css=nav > a:nth-of-type(1) href=/blog\n'
    '[2] input[email] "Email" css=input[name="email"]\n'
    '[3] button "Reject" css=.cookie-banner > button:nth-of-type(1)\n'
)


def _mock_client():
    return AsyncMock()


def _find_json_line(stderr_text):
    """Find and parse the first JSON line in stderr output."""
    for line in stderr_text.strip().splitlines():
        if line.startswith('{'):
            return json.loads(line)
    raise ValueError(f'No JSON line found in: {stderr_text!r}')


def _run_capturing_stderr(script_text):
    """Run a script and return (summary, stderr_output)."""
    steps = parse_script(script_text)
    client = _mock_client()
    buf = StringIO()
    old = sys.stderr
    sys.stderr = buf
    try:
        summary = asyncio.run(run_script(client, steps))
    finally:
        sys.stderr = old
    return summary, buf.getvalue()


class TestSelfHealingSnapshot:
    @patch('passe.runner.do_snapshot', new_callable=AsyncMock,
           return_value=FAKE_SNAPSHOT)
    @patch('passe.runner.do_click', new_callable=AsyncMock,
           side_effect=RuntimeError('Element not found: #nonexistent'))
    def test_click_failure_includes_elements(self, mock_click, mock_snap):
        summary, stderr = _run_capturing_stderr(
            'click #nonexistent')
        assert not summary['ok']
        assert 'Element not found' in summary['error']
        # Snapshot elements should be in step NDJSON
        step = _find_json_line(stderr)
        assert 'elements' in step
        assert len(step['elements']) == 4
        assert 'Sign in' in step['elements'][0]

    @patch('passe.runner.do_snapshot', new_callable=AsyncMock,
           return_value=FAKE_SNAPSHOT)
    @patch('passe.runner.do_click', new_callable=AsyncMock,
           side_effect=RuntimeError('Element not found: #btn'))
    def test_click_failure_stderr_hint(self, mock_click, mock_snap):
        _, stderr = _run_capturing_stderr('click #btn')
        assert '[passe] click failed' in stderr
        assert 'Page has:' in stderr
        assert 'Sign in' in stderr

    @patch('passe.runner.do_snapshot', new_callable=AsyncMock,
           return_value=FAKE_SNAPSHOT)
    @patch('passe.runner.do_type', new_callable=AsyncMock,
           side_effect=RuntimeError('Element not found: #username'))
    def test_type_failure_includes_snapshot(self, mock_type, mock_snap):
        summary, stderr = _run_capturing_stderr(
            'type #username hello')
        assert not summary['ok']
        step = _find_json_line(stderr)
        assert 'elements' in step

    @patch('passe.runner.do_snapshot', new_callable=AsyncMock,
           side_effect=Exception('CDP connection lost'))
    @patch('passe.runner.do_click', new_callable=AsyncMock,
           side_effect=RuntimeError('Element not found: #btn'))
    def test_snapshot_failure_doesnt_crash(self, mock_click, mock_snap):
        """If the recovery snapshot itself fails, the original error still works."""
        summary, stderr = _run_capturing_stderr('click #btn')
        assert not summary['ok']
        assert 'Element not found' in summary['error']
        # No elements since snapshot failed, but no crash
        step = json.loads(stderr.strip().splitlines()[0])
        assert 'elements' not in step

    @patch('passe.runner.do_snapshot', new_callable=AsyncMock,
           return_value=FAKE_SNAPSHOT)
    @patch('passe.runner.do_navigate', new_callable=AsyncMock,
           side_effect=RuntimeError('net::ERR_NAME_NOT_RESOLVED'))
    def test_goto_failure_no_snapshot(self, mock_nav, mock_snap):
        """Navigation verbs should NOT trigger recovery snapshot."""
        summary, _ = _run_capturing_stderr(
            'goto https://nonexistent.invalid')
        assert not summary['ok']
        mock_snap.assert_not_called()

    @patch('passe.runner.do_snapshot', new_callable=AsyncMock,
           return_value='\n'.join(
               f'[{i}] button "Btn{i}" css=#btn{i}'
               for i in range(20)) + '\n')
    @patch('passe.runner.do_click', new_callable=AsyncMock,
           side_effect=RuntimeError('Element not found'))
    def test_elements_capped_at_10(self, mock_click, mock_snap):
        _, stderr = _run_capturing_stderr('click #missing')
        step = _find_json_line(stderr)
        assert len(step['elements']) == 10

    @patch('passe.runner.do_snapshot', new_callable=AsyncMock,
           return_value=FAKE_SNAPSHOT)
    @patch('passe.runner.do_hover', new_callable=AsyncMock,
           side_effect=RuntimeError('Element not found'))
    def test_hover_triggers_snapshot(self, mock_hover, mock_snap):
        summary, _ = _run_capturing_stderr('hover #tooltip')
        assert not summary['ok']
        mock_snap.assert_called_once()

    @patch('passe.runner.do_snapshot', new_callable=AsyncMock,
           return_value=FAKE_SNAPSHOT)
    @patch('passe.runner.do_tap', new_callable=AsyncMock,
           side_effect=RuntimeError('Element not found'))
    def test_tap_triggers_snapshot(self, mock_tap, mock_snap):
        summary, _ = _run_capturing_stderr('tap #button')
        assert not summary['ok']
        mock_snap.assert_called_once()
