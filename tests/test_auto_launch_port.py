"""Auto-launch honours the resolved --cdp port (passe-besohe).

Before the fix, connect() launched Chrome on a hardcoded port 9222 while
the readiness poll checked the resolved endpoint — so `--cdp localhost:9224`
on a machine with nothing at 9224 launched Chrome on 9222, polled 9224,
and died after 15s with a misleading "never became reachable" error.
"""

import os
from unittest.mock import patch

import pytest

import passe.connection as conn


class _StopHere(RuntimeError):
    """Sentinel to short-circuit connect() right after the launch call."""


async def _drive_connect_to_launch():
    """Run connect() until _start_chrome fires; return the mock's call."""
    with patch('passe.connection._chrome_running', return_value=False), \
         patch('passe.connection._start_chrome',
               side_effect=_StopHere()) as mock_start:
        with pytest.raises(_StopHere):
            async with conn.connect():
                pass  # pragma: no cover — never reached
    return mock_start.call_args


@pytest.mark.asyncio
async def test_explicit_nondefault_port_launches_on_that_port():
    original = conn._cdp_override
    try:
        conn.set_cdp_override('localhost:9224')
        call = await _drive_connect_to_launch()
    finally:
        conn.set_cdp_override(original)
    assert call.args[0] == 9224
    # Explicit CDP target → user wants a visible Chrome
    assert call.kwargs['headless'] is False


@pytest.mark.asyncio
async def test_default_endpoint_launches_on_9222_headless():
    original = conn._cdp_override
    try:
        conn.set_cdp_override(None)
        with patch.dict(os.environ, {'PASSE_CDP': ''}):
            call = await _drive_connect_to_launch()
    finally:
        conn.set_cdp_override(original)
    assert call.args[0] == 9222
    # No explicit target → passe owns the browser, headless
    assert call.kwargs['headless'] is True


@pytest.mark.asyncio
async def test_portless_endpoint_falls_back_to_9222():
    original = conn._cdp_override
    try:
        conn.set_cdp_override('http://localhost')
        call = await _drive_connect_to_launch()
    finally:
        conn.set_cdp_override(original)
    assert call.args[0] == 9222
    assert call.kwargs['headless'] is False


@pytest.mark.asyncio
async def test_env_var_port_launches_on_that_port():
    original = conn._cdp_override
    try:
        conn.set_cdp_override(None)
        with patch.dict(os.environ, {'PASSE_CDP': 'localhost:9231'}):
            call = await _drive_connect_to_launch()
    finally:
        conn.set_cdp_override(original)
    assert call.args[0] == 9231
    assert call.kwargs['headless'] is False


def test_start_chrome_passes_no_first_run():
    """Fresh profiles must not open on Chrome's welcome page (passe-cavudo)."""
    with patch('passe.connection._find_chrome',
               return_value='/usr/bin/fake-chrome'), \
         patch('passe.connection._chrome_running', return_value=True), \
         patch('subprocess.Popen') as mock_popen:
        conn._start_chrome(9224, headless=False)
    cmd = mock_popen.call_args[0][0]
    assert '--no-first-run' in cmd
    assert '--remote-debugging-port=9224' in cmd


@pytest.mark.asyncio
async def test_conn_info_reports_launch_kind():
    """conn_info['launched'] tells callers whether THIS run launched Chrome."""
    from unittest.mock import AsyncMock

    fake_ws = AsyncMock()
    disc = ('ws://localhost:9224/devtools/browser/x',
            {'cdp': 'http://localhost:9224', 'browser': 'T', 'remote': False})
    original = conn._cdp_override
    try:
        conn.set_cdp_override('localhost:9224')
        with patch('passe.connection._chrome_running', return_value=False), \
             patch('passe.connection._start_chrome', return_value=None), \
             patch('passe.connection.discover_chrome', return_value=disc), \
             patch('passe.connection.websockets.connect',
                   AsyncMock(return_value=fake_ws)), \
             patch('passe.connection.CDPClient') as mock_client:
            mock_client.return_value.start = AsyncMock()
            mock_client.return_value.stop = AsyncMock()
            async with conn.connect() as (_client, info):
                assert info['launched'] == 'gui'

        # Already-running Chrome → launched is None
        with patch('passe.connection._chrome_running', return_value=True), \
             patch('passe.connection.discover_chrome', return_value=disc), \
             patch('passe.connection.websockets.connect',
                   AsyncMock(return_value=fake_ws)), \
             patch('passe.connection.CDPClient') as mock_client:
            mock_client.return_value.start = AsyncMock()
            mock_client.return_value.stop = AsyncMock()
            async with conn.connect() as (_client, info):
                assert info['launched'] is None
    finally:
        conn.set_cdp_override(original)
