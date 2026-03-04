"""
Test: CLI flag parsing and platform-aware Chrome discovery.

Tests _extract_flag directly (pure function, no browser needed),
_find_chrome platform logic, and main() integration for flag-to-command
passthrough.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from passe.cli import _extract_flag, _find_chrome, cmd_devices


# ── _extract_flag unit tests ─────────────────────────────


class TestExtractFlag:
    """Direct tests for the flag extraction function."""

    def test_flag_present_returns_value(self):
        val, remaining = _extract_flag(['--cdp', 'ws://remote:9222', 'run', '-c', 'goto x'], '--cdp')
        assert val == 'ws://remote:9222'
        assert remaining == ['run', '-c', 'goto x']

    def test_flag_absent_returns_none(self):
        val, remaining = _extract_flag(['run', '-c', 'goto x'], '--cdp')
        assert val is None
        assert remaining == ['run', '-c', 'goto x']

    def test_flag_at_end_missing_value_exits(self):
        """Flag at end of args with no value — should exit."""
        with pytest.raises(SystemExit):
            _extract_flag(['run', '--cdp'], '--cdp')

    def test_flag_in_middle(self):
        val, remaining = _extract_flag(['--device', 'iPhone 14 Pro', 'run', '-c', 'goto x'], '--device')
        assert val == 'iPhone 14 Pro'
        assert remaining == ['run', '-c', 'goto x']

    def test_flag_does_not_consume_non_flag_args(self):
        """Args that aren't the flag should survive untouched."""
        args = ['run', '-c', 'goto https://example.com; screenshot /tmp/x.png']
        val, remaining = _extract_flag(args, '--device')
        assert val is None
        assert remaining == args

    def test_multiple_extractions_chain(self):
        """Simulates main()'s sequential extraction pattern."""
        args = ['--cdp', 'ws://r:9222', '--device', 'Pixel 7', '--dpr', '1', 'run', '-c', 'goto x']

        cdp, args = _extract_flag(args, '--cdp')
        device, args = _extract_flag(args, '--device')
        dpr, args = _extract_flag(args, '--dpr')

        assert cdp == 'ws://r:9222'
        assert device == 'Pixel 7'
        assert dpr == '1'
        assert args == ['run', '-c', 'goto x']

    def test_flag_value_that_looks_like_flag(self):
        """Value starting with -- is still consumed as the value."""
        val, remaining = _extract_flag(['--cdp', '--weird-url', 'run'], '--cdp')
        assert val == '--weird-url'
        assert remaining == ['run']

    def test_only_first_occurrence_consumed(self):
        """If flag appears twice, only first is extracted."""
        val, remaining = _extract_flag(['--dpr', '2', '--dpr', '1', 'run'], '--dpr')
        assert val == '2'
        assert remaining == ['--dpr', '1', 'run']

    def test_empty_args(self):
        val, remaining = _extract_flag([], '--cdp')
        assert val is None
        assert remaining == []


# ── cmd_devices ──────────────────────────────────────────


def test_cmd_devices_lists_all_presets(capsys):
    """cmd_devices prints all device presets with dimensions."""
    cmd_devices()
    output = capsys.readouterr().out
    # All known devices should appear
    assert 'iPhone 14 Pro' in output
    assert 'iPhone SE' in output
    assert 'Pixel 7' in output
    assert 'iPad Air' in output
    assert 'iPad Pro 11' in output
    assert 'Desktop 1080p' in output
    # Should show dimensions and type
    assert '393×852' in output
    assert 'mobile' in output
    assert 'desktop' in output


def test_cmd_devices_main_dispatch(capsys):
    """'passe devices' subcommand dispatches to cmd_devices."""
    import passe.cli as cli
    with patch.object(sys, 'argv', ['passe', 'devices']):
        cli.main()
    output = capsys.readouterr().out
    assert 'iPhone 14 Pro' in output


# ── _find_chrome platform-aware discovery ────────────────


class TestFindChrome:
    """Tests for platform-aware Chrome/Chromium discovery."""

    def test_macos_finds_chrome_app(self):
        """On macOS, finds /Applications/Google Chrome.app."""
        with patch('passe.connection.sys') as mock_sys, \
             patch('os.path.isfile', return_value=True):
            mock_sys.platform = 'darwin'
            result = _find_chrome()
        assert result == '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

    def test_macos_returns_none_when_missing(self):
        """On macOS with no Chrome installed, returns None."""
        with patch('passe.connection.sys') as mock_sys, \
             patch('os.path.isfile', return_value=False):
            mock_sys.platform = 'darwin'
            result = _find_chrome()
        assert result is None

    def test_linux_finds_chromium_browser(self):
        """On Linux, finds first candidate in PATH."""
        def fake_which(name):
            return '/usr/bin/chromium-browser' if name == 'chromium-browser' else None

        with patch('passe.connection.sys') as mock_sys, \
             patch('shutil.which', side_effect=fake_which):
            mock_sys.platform = 'linux'
            result = _find_chrome()
        assert result == '/usr/bin/chromium-browser'

    def test_linux_falls_through_to_google_chrome(self):
        """On Linux, tries candidates in order until one is found."""
        def fake_which(name):
            return '/usr/bin/google-chrome' if name == 'google-chrome' else None

        with patch('passe.connection.sys') as mock_sys, \
             patch('shutil.which', side_effect=fake_which):
            mock_sys.platform = 'linux'
            result = _find_chrome()
        assert result == '/usr/bin/google-chrome'

    def test_linux_returns_none_when_no_chrome(self):
        """On Linux with nothing installed, returns None."""
        with patch('passe.connection.sys') as mock_sys, \
             patch('shutil.which', return_value=None):
            mock_sys.platform = 'linux'
            result = _find_chrome()
        assert result is None

    def test_linux_prefers_chromium_browser_over_google_chrome(self):
        """chromium-browser is tried first (common on Debian/Ubuntu)."""
        def fake_which(name):
            if name in ('chromium-browser', 'google-chrome'):
                return f'/usr/bin/{name}'
            return None

        with patch('passe.connection.sys') as mock_sys, \
             patch('shutil.which', side_effect=fake_which):
            mock_sys.platform = 'linux'
            result = _find_chrome()
        assert result == '/usr/bin/chromium-browser'


# ── main() integration: flags pass through to commands ───


def _run_main(argv_tail: list[str], mock_target: str) -> dict:
    """Call main() with mocked sys.argv and capture the args passed to the target command.

    Returns dict with 'device' and 'dpr' kwargs captured from the mock.
    """
    captured = {}

    async def capture_cmd(*args, **kwargs):
        captured.update(kwargs)

    with patch.object(sys, 'argv', ['passe'] + argv_tail):
        with patch(f'passe.cli.{mock_target}', side_effect=capture_cmd) as mock:
            with patch('passe.cli._run'):  # Don't actually run asyncio
                # _run is called with the coroutine — we need to intercept before that
                # Better: patch the command to capture, then let main() call _run with it
                pass

    return captured


class TestMainFlagPassthrough:
    """Test that main() passes --device and --dpr to subcommands."""

    def test_cdp_sets_override(self):
        """--cdp sets _cdp_override in connection module."""
        import passe.cli as cli
        import passe.connection as conn
        original = conn._cdp_override
        try:
            with patch.object(sys, 'argv', ['passe', '--cdp', 'ws://remote:9222', '--help']):
                with pytest.raises(SystemExit):
                    cli.main()
            assert conn._cdp_override == 'ws://remote:9222'
        finally:
            conn.set_cdp_override(original)

    def test_device_and_dpr_passed_to_cmd_run(self):
        """--device and --dpr reach cmd_run as kwargs."""
        import passe.cli as cli

        mock_cmd = MagicMock(return_value='sentinel')
        with patch.object(sys, 'argv',
                          ['passe', '--device', 'iPhone 14 Pro', '--dpr', '1',
                           'run', '-c', 'goto https://example.com']):
            with patch('passe.cli.cmd_run', mock_cmd):
                with patch('passe.cli._run'):
                    cli.main()

            _, kwargs = mock_cmd.call_args
            assert kwargs['device'] == 'iPhone 14 Pro'
            assert kwargs['dpr'] == 1.0

    def test_device_and_dpr_passed_to_cmd_screenshot(self):
        """--device and --dpr reach cmd_screenshot as kwargs."""
        import passe.cli as cli

        mock_cmd = MagicMock(return_value='sentinel')
        with patch.object(sys, 'argv',
                          ['passe', '--device', 'Pixel 7', '--dpr', '2',
                           'screenshot', '/tmp/x.png']):
            with patch('passe.cli.cmd_screenshot', mock_cmd):
                with patch('passe.cli._run'):
                    cli.main()

            _, kwargs = mock_cmd.call_args
            assert kwargs['device'] == 'Pixel 7'
            assert kwargs['dpr'] == 2.0

    def test_no_device_passes_none(self):
        """Without --device, cmd_run gets device=None."""
        import passe.cli as cli

        mock_cmd = MagicMock(return_value='sentinel')
        with patch.object(sys, 'argv',
                          ['passe', 'run', '-c', 'goto https://example.com']):
            with patch('passe.cli.cmd_run', mock_cmd):
                with patch('passe.cli._run'):
                    cli.main()

            _, kwargs = mock_cmd.call_args
            assert kwargs['device'] is None
            assert kwargs['dpr'] is None

    def test_flags_before_subcommand(self):
        """Global flags work regardless of position before the subcommand."""
        import passe.cli as cli
        import passe.connection as conn
        original = conn._cdp_override
        try:
            mock_cmd = MagicMock(return_value='sentinel')
            with patch.object(sys, 'argv',
                              ['passe', '--cdp', 'ws://x:9222', '--device', 'iPad Air',
                               'run', '-c', 'goto https://example.com']):
                with patch('passe.cli.cmd_run', mock_cmd):
                    with patch('passe.cli._run'):
                        cli.main()

                assert conn._cdp_override == 'ws://x:9222'
                _, kwargs = mock_cmd.call_args
                assert kwargs['device'] == 'iPad Air'
        finally:
            conn.set_cdp_override(original)
