"""Tests for keep-tab-on-failure behavior in cmd_run.

When a script fails (ok: false or exception), the tab should be kept open
by default so Claude can debug the failure state. --no-keep-on-fail reverts
to the old behavior (always close).
"""

import json
import sys
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from passe.commands import cmd_run


def _mock_connect(client):
    """Build an async context manager that yields (client, conn_info)."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_connect():
        yield client, {'cdp': 'http://localhost:9222', 'browser': 'test'}

    return fake_connect


def _make_client():
    client = AsyncMock()
    client.create_tab = AsyncMock()
    client.close_tab = AsyncMock()
    client.send = AsyncMock()
    return client


# ── Script failure (ok: false) keeps tab by default ────────────────


@pytest.mark.asyncio
async def test_failed_script_keeps_tab():
    """When run_script returns ok:false, tab stays open."""
    client = _make_client()
    failed_summary = {'ok': False, 'steps': 3, 'total_ms': 100,
                      'verb': 'click', 'error': 'not found',
                      'failed_at': 2}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script', AsyncMock(return_value=failed_summary)), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO) as err, \
         pytest.raises(SystemExit) as exc_info:
        await cmd_run(None, inline='goto https://example.com')

    assert exc_info.value.code == 1
    client.close_tab.assert_not_called()
    assert 'tab kept open' in err.getvalue()
    result = json.loads(out.getvalue())
    assert result['tab_kept'] is True


@pytest.mark.asyncio
async def test_successful_script_closes_tab():
    """When run_script returns ok:true, tab is closed as normal."""
    client = _make_client()
    ok_summary = {'ok': True, 'steps': 2, 'total_ms': 50}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script', AsyncMock(return_value=ok_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         pytest.raises(SystemExit) as exc_info:
        await cmd_run(None, inline='goto https://example.com')

    assert exc_info.value.code == 0
    client.close_tab.assert_called_once()


# ── --no-keep-on-fail forces cleanup ───────────────────────────────


@pytest.mark.asyncio
async def test_no_keep_on_fail_closes_tab():
    """With keep_on_fail=False, failed script still closes tab."""
    client = _make_client()
    failed_summary = {'ok': False, 'steps': 1, 'total_ms': 10,
                      'verb': 'goto', 'error': 'timeout', 'failed_at': 0}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script', AsyncMock(return_value=failed_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO) as err, \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com',
                      keep_on_fail=False)

    client.close_tab.assert_called_once()
    assert 'tab kept open' not in err.getvalue()


# ── Exception from run_script keeps tab ────────────────────────────


@pytest.mark.asyncio
async def test_exception_keeps_tab():
    """When run_script throws, tab stays open."""
    client = _make_client()

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script',
               AsyncMock(side_effect=RuntimeError('websocket closed'))), \
         pytest.raises(RuntimeError):
        await cmd_run(None, inline='goto https://example.com')

    client.close_tab.assert_not_called()


@pytest.mark.asyncio
async def test_exception_with_no_keep_on_fail_closes():
    """When run_script throws and keep_on_fail=False, tab is closed."""
    client = _make_client()

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script',
               AsyncMock(side_effect=RuntimeError('websocket closed'))), \
         pytest.raises(RuntimeError):
        await cmd_run(None, inline='goto https://example.com',
                      keep_on_fail=False)

    client.close_tab.assert_called_once()


# ── --keep-tab still overrides everything ──────────────────────────


@pytest.mark.asyncio
async def test_keep_tab_still_keeps_on_success():
    """--keep-tab keeps tab even on success (unchanged behavior)."""
    client = _make_client()
    ok_summary = {'ok': True, 'steps': 1, 'total_ms': 10}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script', AsyncMock(return_value=ok_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com',
                      keep_tab=True)

    client.close_tab.assert_not_called()


# ── CLI flag parsing ───────────────────────────────────────────────


def test_no_keep_on_fail_flag_parsed():
    """--no-keep-on-fail reaches cmd_run as keep_on_fail=False."""
    import passe.cli as cli

    mock_cmd = MagicMock(return_value='sentinel')
    with patch.object(sys, 'argv',
                      ['passe', 'run', '--no-keep-on-fail', '-c',
                       'goto https://example.com']):
        with patch('passe.cli.cmd_run', mock_cmd), \
             patch('passe.cli._run'):
            cli.main()

        _, kwargs = mock_cmd.call_args
        assert kwargs['keep_on_fail'] is False


def test_default_keep_on_fail_is_true():
    """Without --no-keep-on-fail, keep_on_fail defaults to True."""
    import passe.cli as cli

    mock_cmd = MagicMock(return_value='sentinel')
    with patch.object(sys, 'argv',
                      ['passe', 'run', '-c', 'goto https://example.com']):
        with patch('passe.cli.cmd_run', mock_cmd), \
             patch('passe.cli._run'):
            cli.main()

        _, kwargs = mock_cmd.call_args
        assert kwargs['keep_on_fail'] is True
