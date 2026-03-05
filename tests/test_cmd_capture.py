"""Tests for cmd_capture: goto + wait-idle + network recording."""

import json
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest

from passe.commands import cmd_capture


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
    client.enable_network = AsyncMock()
    client.get_network_requests = lambda: [
        {'url': 'https://example.com/', 'status': 200,
         'resource_type': 'Document', 'timestamp': 1},
        {'url': 'https://example.com/api/data', 'status': 200,
         'resource_type': 'XHR', 'timestamp': 2},
    ]
    return client


@pytest.mark.asyncio
async def test_capture_success(tmp_path):
    """cmd_capture writes JSONL and emits summary."""
    client = _make_client()
    out_path = str(tmp_path / 'capture.jsonl')
    nav_result = {'url': 'https://example.com/', 'status_code': 200}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_navigate',
               AsyncMock(return_value=nav_result)), \
         patch('passe.verbs.do_wait_idle', AsyncMock()), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO):
        await cmd_capture('https://example.com', path=out_path)

    result = json.loads(out.getvalue())
    assert result['ok'] is True
    assert result['steps'] == 3
    assert result['files'][0]['verb'] == 'capture'
    assert result['files'][0]['requests'] == 2
    assert 'example.com' in result['files'][0]['domains']
    assert result['final_url'] == 'https://example.com/'

    # Verify JSONL was written
    with open(out_path) as f:
        lines = f.readlines()
    assert len(lines) == 2

    client.enable_network.assert_called_once()
    client.close_tab.assert_called_once()


@pytest.mark.asyncio
async def test_capture_error_emits_json():
    """When navigation fails, cmd_capture emits structured JSON error."""
    client = _make_client()

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_navigate',
               AsyncMock(side_effect=RuntimeError('timeout'))), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO), \
         pytest.raises(SystemExit) as exc_info:
        await cmd_capture('https://broken.example.com', path='/tmp/cap.jsonl')

    assert exc_info.value.code == 1
    result = json.loads(out.getvalue())
    assert result['ok'] is False
    assert result['verb'] == 'capture'
    client.close_tab.assert_called_once()


@pytest.mark.asyncio
async def test_capture_tab_always_closed(tmp_path):
    """Tab closes even on wait-idle failure."""
    client = _make_client()
    nav_result = {'url': 'https://example.com/', 'status_code': 200}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_navigate',
               AsyncMock(return_value=nav_result)), \
         patch('passe.verbs.do_wait_idle',
               AsyncMock(side_effect=RuntimeError('idle timeout'))), \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_capture('https://example.com', path=str(tmp_path / 'cap.jsonl'))

    client.close_tab.assert_called_once()
