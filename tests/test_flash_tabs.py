"""Tests for flash tab auto-cleanup behavior.

Flash tabs inject a JS timer that calls window.close() after a timeout,
cancelled by user interaction (click/keydown/scroll/mousemove).
"""

import json
import sys
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from passe.commands import cmd_run, _FLASH_JS


def _mock_connect(client):
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


# ── --flash flag keeps tab and injects timer ───────────────────────


@pytest.mark.asyncio
async def test_flash_injects_timer():
    """--flash keeps tab and injects setTimeout JS."""
    client = _make_client()
    ok_summary = {'ok': True, 'steps': 1, 'total_ms': 50}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script', AsyncMock(return_value=ok_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com',
                      keep_tab=True, flash=30)

    # Tab not closed
    client.close_tab.assert_not_called()
    # Runtime.evaluate called with flash JS
    eval_calls = [c for c in client.send.call_args_list
                  if c[0][0] == 'Runtime.evaluate']
    assert len(eval_calls) == 1
    js = eval_calls[0][0][1]['expression']
    assert 'setTimeout' in js
    assert '30000' in js


@pytest.mark.asyncio
async def test_flash_custom_timeout():
    """--flash 60 uses 60s timeout."""
    client = _make_client()
    ok_summary = {'ok': True, 'steps': 1, 'total_ms': 50}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script', AsyncMock(return_value=ok_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com',
                      keep_tab=True, flash=60)

    eval_calls = [c for c in client.send.call_args_list
                  if c[0][0] == 'Runtime.evaluate']
    assert '60000' in eval_calls[0][0][1]['expression']


# ── Keep-on-fail tabs get flash automatically ──────────────────────


@pytest.mark.asyncio
async def test_keep_on_fail_gets_flash():
    """Failed script tabs get 30s flash timer by default."""
    client = _make_client()
    failed_summary = {'ok': False, 'steps': 2, 'total_ms': 100,
                      'verb': 'click', 'error': 'not found',
                      'failed_at': 1}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script', AsyncMock(return_value=failed_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com')

    client.close_tab.assert_not_called()
    eval_calls = [c for c in client.send.call_args_list
                  if c[0][0] == 'Runtime.evaluate']
    assert len(eval_calls) == 1
    assert '30000' in eval_calls[0][0][1]['expression']


@pytest.mark.asyncio
async def test_no_keep_on_fail_no_flash():
    """--no-keep-on-fail skips flash (tab is closed)."""
    client = _make_client()
    failed_summary = {'ok': False, 'steps': 1, 'total_ms': 10,
                      'verb': 'goto', 'error': 'timeout', 'failed_at': 0}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script', AsyncMock(return_value=failed_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com',
                      keep_on_fail=False)

    client.close_tab.assert_called_once()


# ── Success without --flash or --keep-tab closes normally ──────────


@pytest.mark.asyncio
async def test_success_no_flash_closes():
    """Successful run without --flash closes tab normally."""
    client = _make_client()
    ok_summary = {'ok': True, 'steps': 1, 'total_ms': 50}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script', AsyncMock(return_value=ok_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com')

    client.close_tab.assert_called_once()


# ── --keep-tab without --flash: no timer injected ─────────────────


@pytest.mark.asyncio
async def test_keep_tab_without_flash_no_timer():
    """Plain --keep-tab doesn't inject flash timer."""
    client = _make_client()
    ok_summary = {'ok': True, 'steps': 1, 'total_ms': 50}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script', AsyncMock(return_value=ok_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com',
                      keep_tab=True)

    client.close_tab.assert_not_called()
    eval_calls = [c for c in client.send.call_args_list
                  if c[0][0] == 'Runtime.evaluate']
    assert len(eval_calls) == 0


# ── Exception path with flash ─────────────────────────────────────


@pytest.mark.asyncio
async def test_exception_gets_flash():
    """When run_script throws, keep-on-fail tab gets flash timer."""
    client = _make_client()

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.commands.run_script',
               AsyncMock(side_effect=RuntimeError('ws closed'))), \
         pytest.raises(RuntimeError):
        await cmd_run(None, inline='goto https://example.com')

    client.close_tab.assert_not_called()
    eval_calls = [c for c in client.send.call_args_list
                  if c[0][0] == 'Runtime.evaluate']
    assert len(eval_calls) == 1


# ── CLI flag parsing ──────────────────────────────────────────────


class TestFlashFlagParsing:

    def test_bare_flash_defaults_30(self):
        import passe.cli as cli
        mock_cmd = MagicMock(return_value='sentinel')
        with patch.object(sys, 'argv',
                          ['passe', 'run', '--flash', '-c',
                           'goto https://example.com']):
            with patch('passe.cli.cmd_run', mock_cmd), \
                 patch('passe.cli._run'):
                cli.main()
            _, kwargs = mock_cmd.call_args
            assert kwargs['flash'] == 30
            assert kwargs['keep_tab'] is True

    def test_flash_with_value(self):
        import passe.cli as cli
        mock_cmd = MagicMock(return_value='sentinel')
        with patch.object(sys, 'argv',
                          ['passe', 'run', '--flash', '60', '-c',
                           'goto https://example.com']):
            with patch('passe.cli.cmd_run', mock_cmd), \
                 patch('passe.cli._run'):
                cli.main()
            _, kwargs = mock_cmd.call_args
            assert kwargs['flash'] == 60

    def test_no_flash_is_none(self):
        import passe.cli as cli
        mock_cmd = MagicMock(return_value='sentinel')
        with patch.object(sys, 'argv',
                          ['passe', 'run', '-c',
                           'goto https://example.com']):
            with patch('passe.cli.cmd_run', mock_cmd), \
                 patch('passe.cli._run'):
                cli.main()
            _, kwargs = mock_cmd.call_args
            assert kwargs['flash'] is None


# ── Flash JS structure ────────────────────────────────────────────


def test_flash_js_has_interaction_cancel():
    """Flash JS includes interaction listeners that cancel the timer."""
    js = _FLASH_JS % (30000, 30)
    assert 'clearTimeout' in js
    assert 'click' in js
    assert 'keydown' in js
    assert 'scroll' in js
    assert 'mousemove' in js
    assert 'once: true' in js
