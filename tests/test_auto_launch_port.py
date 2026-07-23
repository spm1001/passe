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
