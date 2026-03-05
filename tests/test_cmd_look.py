"""Tests for cmd_look: goto + fast screenshot."""

import json
import sys
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest

from passe.commands import cmd_look


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
async def test_look_success(tmp_path):
    """cmd_look navigates, screenshots --fast, closes tab."""
    client = _make_client()
    out_path = str(tmp_path / 'look.jpg')
    nav_result = {'url': 'https://example.com/', 'status_code': 200}
    shot_result = {'file': out_path, 'kb': 42.0, 'format': 'jpeg'}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_navigate',
               AsyncMock(return_value=nav_result)) as mock_nav, \
         patch('passe.commands.do_screenshot',
               AsyncMock(return_value=shot_result)) as mock_shot, \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO):
        await cmd_look('https://example.com', path=out_path)

    result = json.loads(out.getvalue())
    assert result['ok'] is True
    assert result['steps'] == 2
    assert result['final_url'] == 'https://example.com/'
    assert result['status_code'] == 200
    assert result['files'][0]['format'] == 'jpeg'
    assert result['files'][0]['kb'] == 42.0

    # Verify --fast flags: viewport_only, jpeg, q70, optimize_speed
    mock_shot.assert_called_once()
    _, kwargs = mock_shot.call_args
    assert kwargs['viewport_only'] is True
    assert kwargs['fmt'] == 'jpeg'
    assert kwargs['quality'] == 70
    assert kwargs['optimize_speed'] is True

    client.close_tab.assert_called_once()


@pytest.mark.asyncio
async def test_look_default_path(tmp_path):
    """When no path given, uses temp file."""
    client = _make_client()
    nav_result = {'url': 'https://example.com/', 'status_code': 200}
    shot_result = {'file': '/tmp/passe-look.jpg', 'kb': 10.0, 'format': 'jpeg'}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_navigate',
               AsyncMock(return_value=nav_result)), \
         patch('passe.commands.do_screenshot',
               AsyncMock(return_value=shot_result)) as mock_shot, \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO):
        await cmd_look('https://example.com')

    # Should have used a default path
    call_args = mock_shot.call_args
    assert 'passe-look.jpg' in call_args[0][1]  # second positional arg is path


@pytest.mark.asyncio
async def test_look_error_emits_json():
    """When navigation fails, cmd_look emits structured JSON error."""
    client = _make_client()

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_navigate',
               AsyncMock(side_effect=RuntimeError('net::ERR_NAME_NOT_RESOLVED'))), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO), \
         pytest.raises(SystemExit) as exc_info:
        await cmd_look('https://broken.example.com')

    assert exc_info.value.code == 1
    result = json.loads(out.getvalue())
    assert result['ok'] is False
    assert result['verb'] == 'look'
    assert 'ERR_NAME_NOT_RESOLVED' in result['error']
    client.close_tab.assert_called_once()


@pytest.mark.asyncio
async def test_look_tab_always_closed():
    """Tab closes even when screenshot fails."""
    client = _make_client()
    nav_result = {'url': 'https://example.com/', 'status_code': 200}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_navigate',
               AsyncMock(return_value=nav_result)), \
         patch('passe.commands.do_screenshot',
               AsyncMock(side_effect=RuntimeError('screenshot failed'))), \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_look('https://example.com')

    client.close_tab.assert_called_once()
