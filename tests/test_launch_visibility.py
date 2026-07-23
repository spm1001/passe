"""Fresh-GUI foreground + ephemeral-browser hint honesty (passe-cavudo).

Two mechanisms verified by live repro 2026-07-23:
- A tab created with background:True reports visibilityState=hidden — when
  passe launched a GUI Chrome and then worked in a background tab, the human
  watched the launch tab while the script ran invisibly. Fix: when passe
  itself just launched GUI Chrome, its tab goes in the foreground.
- Auto-launched headless Chrome is killed at connect() teardown, so the
  "tab kept open. Resume with --reuse-tab" hint promised a tab in a browser
  passe was about to kill. Fix: honest messaging on the ephemeral path.
"""

import json
from contextlib import asynccontextmanager
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest

from passe.commands import cmd_run


def _mock_connect(client, conn_info):
    @asynccontextmanager
    async def fake_connect():
        yield client, conn_info

    return fake_connect


def _make_client():
    client = AsyncMock()
    client.create_tab = AsyncMock()
    client.close_tab = AsyncMock()
    client.send = AsyncMock()
    return client


_BASE_INFO = {'cdp': 'http://localhost:9222', 'browser': 'test'}


# ── Fresh GUI launch → foreground tab ──────────────────────────────


@pytest.mark.asyncio
async def test_fresh_gui_launch_foregrounds_tab():
    client = _make_client()
    ok_summary = {'ok': True, 'steps': 1, 'total_ms': 10}
    info = dict(_BASE_INFO, launched='gui')

    with patch('passe.commands.connect', _mock_connect(client, info)), \
         patch('passe.commands.run_script', AsyncMock(return_value=ok_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO) as err, \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com')

    client.create_tab.assert_called_once_with(foreground=True)
    assert 'foreground tab' in err.getvalue()


@pytest.mark.asyncio
async def test_attach_to_running_chrome_stays_background():
    """No launch this invocation → default background tab (don't steal focus)."""
    client = _make_client()
    ok_summary = {'ok': True, 'steps': 1, 'total_ms': 10}
    info = dict(_BASE_INFO, launched=None)

    with patch('passe.commands.connect', _mock_connect(client, info)), \
         patch('passe.commands.run_script', AsyncMock(return_value=ok_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com')

    client.create_tab.assert_called_once_with(foreground=False)


@pytest.mark.asyncio
async def test_headless_launch_stays_background():
    """Auto-launched headless Chrome has no human watching — no promotion."""
    client = _make_client()
    ok_summary = {'ok': True, 'steps': 1, 'total_ms': 10}
    info = dict(_BASE_INFO, launched='headless', _process=object())

    with patch('passe.commands.connect', _mock_connect(client, info)), \
         patch('passe.commands.run_script', AsyncMock(return_value=ok_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com')

    client.create_tab.assert_called_once_with(foreground=False)


# ── Ephemeral browser → honest failure messaging ───────────────────


@pytest.mark.asyncio
async def test_ephemeral_failure_no_false_resume_promise():
    """Failed script in auto-launched headless Chrome: no 'tab kept' claim."""
    client = _make_client()
    failed_summary = {'ok': False, 'steps': 1, 'total_ms': 10,
                      'verb': 'click', 'error': 'not found', 'failed_at': 0}
    info = dict(_BASE_INFO, launched='headless', _process=object())

    with patch('passe.commands.connect', _mock_connect(client, info)), \
         patch('passe.commands.run_script', AsyncMock(return_value=failed_summary)), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO) as err, \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com')

    stderr_text = err.getvalue()
    assert 'tab kept open' not in stderr_text
    assert 'exits with the run' in stderr_text
    result = json.loads(out.getvalue())
    assert 'tab_kept' not in result
    # No pointless close of a tab the teardown is about to take anyway
    client.close_tab.assert_not_called()


@pytest.mark.asyncio
async def test_ephemeral_keep_tab_warns():
    """--keep-tab in auto-launched headless Chrome: warn it has no effect."""
    client = _make_client()
    ok_summary = {'ok': True, 'steps': 1, 'total_ms': 10}
    info = dict(_BASE_INFO, launched='headless', _process=object())

    with patch('passe.commands.connect', _mock_connect(client, info)), \
         patch('passe.commands.run_script', AsyncMock(return_value=ok_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO) as err, \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com', keep_tab=True)

    assert '--keep-tab has no effect' in err.getvalue()


@pytest.mark.asyncio
async def test_surviving_browser_failure_still_promises_resume():
    """Failed script in a browser that outlives the run: hint unchanged."""
    client = _make_client()
    failed_summary = {'ok': False, 'steps': 1, 'total_ms': 10,
                      'verb': 'click', 'error': 'not found', 'failed_at': 0}
    info = dict(_BASE_INFO, launched=None)

    with patch('passe.commands.connect', _mock_connect(client, info)), \
         patch('passe.commands.run_script', AsyncMock(return_value=failed_summary)), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO) as err, \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='goto https://example.com')

    assert 'tab kept open' in err.getvalue()
    assert json.loads(out.getvalue())['tab_kept'] is True
    client.close_tab.assert_not_called()
