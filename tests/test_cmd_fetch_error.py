"""Tests for cmd_fetch structured error JSON on failure."""

import json
import sys
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest

from passe.commands import cmd_fetch


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


@pytest.mark.asyncio
async def test_fetch_error_emits_json():
    """When do_fetch throws, cmd_fetch emits structured JSON error."""
    client = _make_client()

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_fetch',
               AsyncMock(side_effect=RuntimeError('Navigation timeout'))), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO) as err, \
         pytest.raises(SystemExit) as exc_info:
        await cmd_fetch('https://broken.example.com')

    assert exc_info.value.code == 1
    result = json.loads(out.getvalue())
    assert result['ok'] is False
    assert result['verb'] == 'fetch'
    assert 'Navigation timeout' in result['error']
    assert 'total_ms' in result
    client.close_tab.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_error_summary_on_stderr():
    """Error summary appears on stderr."""
    client = _make_client()

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_fetch',
               AsyncMock(side_effect=ValueError('bad selector'))), \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO) as err, \
         pytest.raises(SystemExit):
        await cmd_fetch('https://example.com')

    assert 'failed' in err.getvalue()


@pytest.mark.asyncio
async def test_fetch_success_unchanged():
    """Successful fetch still produces ok:true JSON."""
    client = _make_client()
    fetch_result = {
        'markdown': 'Hello world',
        'source': 'trafilatura',
        'nav_url': 'https://example.com/',
    }

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_fetch',
               AsyncMock(return_value=fetch_result)), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO):
        # cmd_fetch calls sys.exit only on failure; success just returns
        await cmd_fetch('https://example.com')

    result = json.loads(out.getvalue())
    assert result['ok'] is True
