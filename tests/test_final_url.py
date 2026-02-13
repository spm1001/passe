"""
Test: final_url in run_script summary.

final_url captures window.location.href after the last step, before
tab close. It's the only moment the URL is available since cmd_run
destroys the tab in its finally block. These tests verify:
  - final_url present on success
  - final_url present even when a step fails
  - final_url absent when the eval itself fails (best-effort)
"""

from unittest.mock import AsyncMock

import pytest

from passe.cli import run_script


def _mock_client(final_url: str = 'https://example.com/done') -> AsyncMock:
    """CDPClient mock whose eval always returns final_url."""
    client = AsyncMock()
    client.send = AsyncMock(return_value={
        'result': {
            'result': {'value': final_url}
        }
    })
    return client


@pytest.mark.asyncio
async def test_final_url_present_on_success():
    """Successful script includes final_url in summary."""
    client = _mock_client('https://example.com/redirected')
    steps = [('log', ['hello'])]

    summary = await run_script(client, steps)

    assert summary['ok'] is True
    assert summary['final_url'] == 'https://example.com/redirected'


@pytest.mark.asyncio
async def test_final_url_present_on_failure():
    """Failed script still captures final_url (best-effort)."""
    client = AsyncMock()
    call_count = 0

    async def _send(method, params=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: do_assert('false') — return falsy value
            return {'result': {'result': {'value': False}}}
        # Second call: final_url eval
        return {'result': {'result': {'value': 'https://example.com/error-page'}}}

    client.send = _send
    steps = [('assert', ['false'])]

    summary = await run_script(client, steps)

    assert summary['ok'] is False
    assert summary['final_url'] == 'https://example.com/error-page'


@pytest.mark.asyncio
async def test_final_url_absent_when_eval_fails():
    """If window.location.href eval throws, final_url is omitted (not crash)."""
    client = AsyncMock()
    client.send = AsyncMock(side_effect=Exception('tab already closed'))
    steps = [('log', ['hello'])]

    summary = await run_script(client, steps)

    assert summary['ok'] is True
    assert 'final_url' not in summary
