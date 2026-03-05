"""Tests for intent-level subcommands: look, check, capture CLI routing."""

import sys
from unittest.mock import AsyncMock, patch

import pytest

import passe.cli as cli


def _noop_run(coro):
    """Replace _run to capture the coroutine without executing it."""
    coro.close()  # Prevent "was never awaited" warning


class TestLookRouting:
    def test_look_dispatches(self):
        with patch.object(sys, 'argv', ['passe', 'look', 'https://example.com']), \
             patch('passe.cli.cmd_look') as mock:
            mock.return_value = AsyncMock()()
            with patch('passe.cli._run', _noop_run):
                cli.main()

    def test_look_with_path(self):
        with patch.object(sys, 'argv',
                          ['passe', 'look', 'https://example.com', '/tmp/out.jpg']), \
             patch('passe.cli._run') as mock_run:
            cli.main()
        # Inspect the coroutine that was passed to _run
        coro = mock_run.call_args[0][0]
        coro.close()

    def test_look_needs_url(self):
        with patch.object(sys, 'argv', ['passe', 'look']), \
             pytest.raises(SystemExit):
            cli.main()


class TestCheckRouting:
    def test_check_dispatches(self):
        with patch.object(sys, 'argv',
                          ['passe', 'check', 'https://example.com',
                           '--contains', 'Welcome']), \
             patch('passe.cli._run') as mock_run:
            cli.main()
        coro = mock_run.call_args[0][0]
        coro.close()

    def test_check_requires_contains(self, capsys):
        with patch.object(sys, 'argv',
                          ['passe', 'check', 'https://example.com']), \
             pytest.raises(SystemExit) as exc_info:
            cli.main()
        assert exc_info.value.code == 1

    def test_check_with_screenshot(self):
        with patch.object(sys, 'argv',
                          ['passe', 'check', 'https://example.com',
                           '--contains', 'OK',
                           '--screenshot', '/tmp/shot.jpg']), \
             patch('passe.cli._run') as mock_run:
            cli.main()
        coro = mock_run.call_args[0][0]
        coro.close()


class TestCaptureRouting:
    def test_capture_dispatches(self):
        with patch.object(sys, 'argv',
                          ['passe', 'capture', 'https://example.com',
                           '/tmp/cap.jsonl']), \
             patch('passe.cli._run') as mock_run:
            cli.main()
        coro = mock_run.call_args[0][0]
        coro.close()

    def test_capture_with_bodies(self):
        with patch.object(sys, 'argv',
                          ['passe', 'capture', '--bodies',
                           'https://example.com', '/tmp/cap.jsonl']), \
             patch('passe.cli._run') as mock_run:
            cli.main()
        coro = mock_run.call_args[0][0]
        coro.close()

    def test_capture_needs_url_and_path(self, capsys):
        with patch.object(sys, 'argv',
                          ['passe', 'capture', 'https://example.com']), \
             pytest.raises(SystemExit) as exc_info:
            cli.main()
        assert exc_info.value.code == 1
