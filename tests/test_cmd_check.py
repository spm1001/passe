"""Tests for cmd_check: goto + assert text + optional screenshot."""

import json
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest

from passe.commands import cmd_check


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
async def test_check_success():
    """cmd_check exits 0 when assertion passes."""
    client = _make_client()
    nav_result = {'url': 'https://example.com/', 'status_code': 200}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_navigate',
               AsyncMock(return_value=nav_result)), \
         patch('passe.verbs.do_assert', AsyncMock()) as mock_assert, \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO):
        await cmd_check('https://example.com', contains='Welcome')

    result = json.loads(out.getvalue())
    assert result['ok'] is True
    assert result['contains'] == 'Welcome'
    assert result['final_url'] == 'https://example.com/'

    # Verify the assertion expression
    mock_assert.assert_called_once()
    expr = mock_assert.call_args[0][1]
    assert "document.body.innerText.includes('Welcome')" in expr
    client.close_tab.assert_called_once()


@pytest.mark.asyncio
async def test_check_failure_exits_1():
    """cmd_check exits 1 when assertion fails."""
    client = _make_client()
    nav_result = {'url': 'https://example.com/', 'status_code': 200}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_navigate',
               AsyncMock(return_value=nav_result)), \
         patch('passe.verbs.do_assert',
               AsyncMock(side_effect=AssertionError('false'))), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO), \
         pytest.raises(SystemExit) as exc_info:
        await cmd_check('https://example.com', contains='Missing text')

    assert exc_info.value.code == 1
    result = json.loads(out.getvalue())
    assert result['ok'] is False
    assert result['verb'] == 'check'
    assert result['contains'] == 'Missing text'
    client.close_tab.assert_called_once()


@pytest.mark.asyncio
async def test_check_with_screenshot(tmp_path):
    """--screenshot captures image alongside assertion."""
    client = _make_client()
    nav_result = {'url': 'https://example.com/', 'status_code': 200}
    shot_path = str(tmp_path / 'check.jpg')
    shot_result = {'file': shot_path, 'kb': 30.0, 'format': 'jpeg'}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_navigate',
               AsyncMock(return_value=nav_result)), \
         patch('passe.verbs.do_assert', AsyncMock()), \
         patch('passe.commands.do_screenshot',
               AsyncMock(return_value=shot_result)), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO):
        await cmd_check('https://example.com', contains='OK',
                        screenshot_path=shot_path)

    result = json.loads(out.getvalue())
    assert result['ok'] is True
    assert result['steps'] == 3  # goto + assert + screenshot
    assert result['files'][0]['verb'] == 'screenshot'


@pytest.mark.asyncio
async def test_check_escapes_quotes():
    """Text with quotes is properly escaped in the assertion."""
    client = _make_client()
    nav_result = {'url': 'https://example.com/', 'status_code': 200}

    with patch('passe.commands.connect', _mock_connect(client)), \
         patch('passe.verbs.do_navigate',
               AsyncMock(return_value=nav_result)), \
         patch('passe.verbs.do_assert', AsyncMock()) as mock_assert, \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO):
        await cmd_check('https://example.com', contains="it's working")

    expr = mock_assert.call_args[0][1]
    assert "it\\'s working" in expr
