"""passe login — the human-login moment (passe-gilizu).

Auto-start is headless unless the CDP endpoint is explicit, so on a bare
machine a bare `passe run` rendered offscreen and the human saw no window
to log in to (PCA spike 2026-07-23 — ~15 min lost to an invisible browser).
`passe login [url]` is the workaround with a name: visible Chrome,
foreground tab, tab kept and remembered for --reuse-tab.
"""

import json
import sys
from contextlib import asynccontextmanager
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import passe.connection as conn
import passe.tabmemory as tabmemory
from passe.commands import cmd_login

ENDPOINT = 'http://localhost:9222'


def _mock_connect(client, conn_info, capture):
    @asynccontextmanager
    async def fake_connect(force_visible=False):
        capture['force_visible'] = force_visible
        yield client, conn_info

    return fake_connect


def _make_client():
    client = AsyncMock()
    client.create_tab = AsyncMock()
    client.close_tab = AsyncMock()
    client.send = AsyncMock()
    client._target_id = 'LOGIN_TAB'
    return client


@pytest.fixture
def last_tab_file(tmp_path):
    path = tmp_path / 'last-tab.json'
    with patch.object(tabmemory, 'LAST_TAB_PATH', path):
        yield path


@pytest.mark.asyncio
async def test_login_opens_foreground_tab_and_keeps_it(last_tab_file):
    client = _make_client()
    info = {'cdp': ENDPOINT, 'browser': 'test', 'launched': 'gui'}
    capture = {}
    nav = {'url': 'https://adalyser.example/login', 'status_code': 200}

    with patch('passe.commands.connect', _mock_connect(client, info, capture)), \
         patch('passe.commands.do_navigate', AsyncMock(return_value=nav),
               create=True), \
         patch('passe.verbs.do_navigate', AsyncMock(return_value=nav)), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO) as err:
        await cmd_login('https://adalyser.example/login')

    assert capture['force_visible'] is True
    client.create_tab.assert_called_once_with(foreground=True)
    client.close_tab.assert_not_called()
    assert 'Log in there' in err.getvalue()
    result = json.loads(out.getvalue())
    assert result['ok'] is True
    assert result['tab_kept'] is True
    # The login tab is remembered so --reuse-tab lands on it
    rec = tabmemory.load_last_tab(ENDPOINT)
    assert rec['target_id'] == 'LOGIN_TAB'


@pytest.mark.asyncio
async def test_login_adds_https_scheme(last_tab_file):
    client = _make_client()
    info = {'cdp': ENDPOINT, 'browser': 'test', 'launched': 'gui'}
    nav_mock = AsyncMock(return_value={'url': 'https://adalyser.example/',
                                       'status_code': 200})

    with patch('passe.commands.connect', _mock_connect(client, info, {})), \
         patch('passe.verbs.do_navigate', nav_mock), \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO):
        await cmd_login('adalyser.example')

    nav_url = nav_mock.call_args[0][1]
    assert nav_url == 'https://adalyser.example'


@pytest.mark.asyncio
async def test_login_without_url_just_opens_window(last_tab_file):
    client = _make_client()
    info = {'cdp': ENDPOINT, 'browser': 'test', 'launched': 'gui'}

    with patch('passe.commands.connect', _mock_connect(client, info, {})), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO):
        await cmd_login(None)

    client.create_tab.assert_called_once_with(foreground=True)
    assert json.loads(out.getvalue())['ok'] is True


@pytest.mark.asyncio
async def test_connect_force_visible_launches_gui_at_default_endpoint():
    """The seam: force_visible must defeat the implicit-endpoint headless rule."""
    import os

    class _StopHere(RuntimeError):
        pass

    original = conn._cdp_override
    try:
        conn.set_cdp_override(None)
        with patch.dict(os.environ, {'PASSE_CDP': ''}), \
             patch('passe.connection._chrome_running', return_value=False), \
             patch('passe.connection._start_chrome',
                   side_effect=_StopHere()) as mock_start:
            with pytest.raises(_StopHere):
                async with conn.connect(force_visible=True):
                    pass  # pragma: no cover
    finally:
        conn.set_cdp_override(original)
    assert mock_start.call_args.kwargs['headless'] is False


def test_cli_login_parses_url():
    import passe.cli as cli

    mock_login = MagicMock(return_value='sentinel')
    with patch.object(sys, 'argv', ['passe', 'login', 'adalyser.example']):
        with patch('passe.cli.cmd_login', mock_login), \
             patch('passe.cli._run'):
            cli.main()
    assert mock_login.call_args[0][0] == 'adalyser.example'


def test_cli_login_without_url():
    import passe.cli as cli

    mock_login = MagicMock(return_value='sentinel')
    with patch.object(sys, 'argv', ['passe', 'login']):
        with patch('passe.cli.cmd_login', mock_login), \
             patch('passe.cli._run'):
            cli.main()
    assert mock_login.call_args[0][0] is None
