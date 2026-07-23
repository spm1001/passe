"""Deterministic --reuse-tab targeting (passe-ketome).

--reuse-tab used to attach to the first non-chrome:// tab when it had no
origin to match — on a shared browser that was the human's live tab
(near-miss 2026-07-21); after the kept tab vanished it was chrome://newtab
(2026-07-23). The resolution ladder replaces the silent grab:

    --tab pattern > cached eN refs > last kept tab > goto-origin match

and unresolvable now FAILS with the open-tab list instead of guessing.
"""

import json
import os
import time
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest

import passe.refcache as refcache
import passe.tabmemory as tabmemory
from passe.commands import _resolve_reuse_tab, _script_uses_cached_refs

ENDPOINT = 'http://localhost:9222'


def _client(tabs):
    client = AsyncMock()
    client.list_tabs = AsyncMock(return_value=tabs)
    return client


def _tabs():
    return [
        {'target_id': 'AAA111', 'url': 'https://news.example.com/front',
         'title': 'News'},
        {'target_id': 'BBB222', 'url': 'https://app.example.com/dash',
         'title': 'App'},
    ]


@pytest.fixture
def state_dirs(tmp_path):
    """Point refcache + tabmemory at throwaway state."""
    refs_dir = tmp_path / 'refs'
    refs_dir.mkdir()
    last_tab = tmp_path / 'last-tab.json'
    with patch.object(refcache, 'REFS_DIR', refs_dir), \
         patch.object(tabmemory, 'LAST_TAB_PATH', last_tab):
        yield refs_dir, last_tab


# ── _script_uses_cached_refs ───────────────────────────────────────


def test_en_ref_before_goto_is_cached_refs():
    assert _script_uses_cached_refs([('click', ['e1'])]) is True


def test_goto_first_is_not_cached_refs():
    steps = [('goto', ['https://x.com']), ('click', ['e1'])]
    assert _script_uses_cached_refs(steps) is False


def test_css_selector_is_not_cached_refs():
    assert _script_uses_cached_refs([('click', ['.btn'])]) is False


def test_type_with_ref_counts():
    assert _script_uses_cached_refs([('type', ['e3', 'hello'])]) is True


# ── Ladder rung 1: --tab pattern ───────────────────────────────────


@pytest.mark.asyncio
async def test_tab_pattern_matches_url_substring(state_dirs):
    target, url, via = await _resolve_reuse_tab(
        _client(_tabs()), [], None, 'app.example', ENDPOINT)
    assert target == 'BBB222'
    assert 'app.example' in via


@pytest.mark.asyncio
async def test_tab_pattern_matches_id_prefix(state_dirs):
    target, _url, _via = await _resolve_reuse_tab(
        _client(_tabs()), [], None, 'AAA', ENDPOINT)
    assert target == 'AAA111'


@pytest.mark.asyncio
async def test_tab_pattern_ambiguous_raises_with_matches(state_dirs):
    with pytest.raises(RuntimeError, match='matches multiple tabs'):
        await _resolve_reuse_tab(
            _client(_tabs()), [], None, 'example.com', ENDPOINT)


@pytest.mark.asyncio
async def test_tab_pattern_no_match_raises_with_tab_list(state_dirs):
    with pytest.raises(RuntimeError, match='matches no open tab'):
        await _resolve_reuse_tab(
            _client(_tabs()), [], None, 'zzz-nope', ENDPOINT)


# ── Ladder rung 2: cached eN refs ──────────────────────────────────


@pytest.mark.asyncio
async def test_en_script_attaches_to_refs_tab_not_first(state_dirs):
    """THE ketome scenario: refs snapped in tab B, tab A first in register."""
    refs_dir, _ = state_dirs
    refcache.save_refs('BBB222', {'e0': 11, 'e1': 12})
    target, _url, via = await _resolve_reuse_tab(
        _client(_tabs()), [('click', ['e1'])], None, None, ENDPOINT)
    assert target == 'BBB222'
    assert via == 'cached eN refs'


@pytest.mark.asyncio
async def test_en_refs_for_dead_tab_fall_through_with_note(state_dirs):
    """Refs exist only for a closed tab → clear error, not a silent grab."""
    refcache.save_refs('DEAD99', {'e0': 11})
    with pytest.raises(RuntimeError) as exc_info:
        await _resolve_reuse_tab(
            _client(_tabs()), [('click', ['e1'])], None, None, ENDPOINT)
    assert 'no open tab has cached refs' in str(exc_info.value)
    assert '--tab' in str(exc_info.value)


@pytest.mark.asyncio
async def test_newest_refs_win(state_dirs):
    """Two live tabs with refs — the most recently snapped wins."""
    refs_dir, _ = state_dirs
    refcache.save_refs('AAA111', {'e0': 1})
    refcache.save_refs('BBB222', {'e0': 2})
    old = refs_dir / 'AAA111.json'
    past = time.time() - 3600
    os.utime(old, (past, past))
    target, _url, _via = await _resolve_reuse_tab(
        _client(_tabs()), [('click', ['e0'])], None, None, ENDPOINT)
    assert target == 'BBB222'


# ── Ladder rung 3: last kept tab ───────────────────────────────────


@pytest.mark.asyncio
async def test_last_kept_tab_resumed(state_dirs):
    tabmemory.save_last_tab(ENDPOINT, 'BBB222', 'https://app.example.com/dash')
    target, _url, via = await _resolve_reuse_tab(
        _client(_tabs()), [('eval', ['1+1'])], None, None, ENDPOINT)
    assert target == 'BBB222'
    assert via == 'last kept tab'


@pytest.mark.asyncio
async def test_dead_last_tab_cleared_and_named_in_error(state_dirs):
    """The Mac scenario: kept tab gone → clear error naming it, no grab."""
    tabmemory.save_last_tab(ENDPOINT, 'GONE42', 'https://activevoice.example')
    with pytest.raises(RuntimeError) as exc_info:
        await _resolve_reuse_tab(
            _client(_tabs()), [('eval', ['1+1'])], None, None, ENDPOINT)
    msg = str(exc_info.value)
    assert 'last kept tab is gone' in msg
    assert 'activevoice' in msg
    # Record was cleared — next run won't repeat the note
    assert tabmemory.load_last_tab(ENDPOINT) is None


@pytest.mark.asyncio
async def test_last_tab_is_per_endpoint(state_dirs):
    tabmemory.save_last_tab('http://other:9250', 'BBB222', 'x')
    with pytest.raises(RuntimeError):
        await _resolve_reuse_tab(
            _client(_tabs()), [('eval', ['1+1'])], None, None, ENDPOINT)


# ── Ladder rung 4: goto-origin match ───────────────────────────────


@pytest.mark.asyncio
async def test_goto_origin_matches_tab(state_dirs):
    target, _url, via = await _resolve_reuse_tab(
        _client(_tabs()), [('goto', ['https://news.example.com/x'])],
        'https://news.example.com', None, ENDPOINT)
    assert target == 'AAA111'
    assert 'origin' in via


@pytest.mark.asyncio
async def test_no_resolution_never_grabs_first_tab(state_dirs):
    """No --tab, no refs, no memory, no origin → error, NOT pages[0]."""
    client = _client(_tabs())
    with pytest.raises(RuntimeError, match='cannot determine which tab'):
        await _resolve_reuse_tab(client, [('eval', ['1+1'])], None, None,
                                 ENDPOINT)
    client.send.assert_not_called()


# ── tabmemory round-trip ───────────────────────────────────────────


def test_tabmemory_roundtrip(state_dirs):
    tabmemory.save_last_tab(ENDPOINT, 'T1', 'https://a.com')
    rec = tabmemory.load_last_tab(ENDPOINT)
    assert rec['target_id'] == 'T1'
    assert rec['url'] == 'https://a.com'
    tabmemory.clear_last_tab(ENDPOINT)
    assert tabmemory.load_last_tab(ENDPOINT) is None


def test_tabmemory_corrupt_file_degrades_to_none(state_dirs):
    _refs_dir, last_tab = state_dirs
    last_tab.write_text('not json{{{')
    assert tabmemory.load_last_tab(ENDPOINT) is None
    # And save still works after corruption
    tabmemory.save_last_tab(ENDPOINT, 'T2', 'u')
    assert tabmemory.load_last_tab(ENDPOINT)['target_id'] == 'T2'


# ── refcache hygiene ───────────────────────────────────────────────


def test_save_refs_prunes_stale_files(state_dirs):
    refs_dir, _ = state_dirs
    refcache.save_refs('OLD1', {'e0': 1})
    stale = refs_dir / 'OLD1.json'
    ancient = time.time() - refcache.STALE_AFTER_S - 60
    os.utime(stale, (ancient, ancient))
    refcache.save_refs('NEW1', {'e0': 2})
    assert not stale.exists()
    assert (refs_dir / 'NEW1.json').exists()


def test_save_refs_keeps_fresh_files(state_dirs):
    refs_dir, _ = state_dirs
    refcache.save_refs('FRESH1', {'e0': 1})
    refcache.save_refs('FRESH2', {'e0': 2})
    assert (refs_dir / 'FRESH1.json').exists()
    assert (refs_dir / 'FRESH2.json').exists()


# ── cmd_run integration: resolution wired into --reuse-tab ────────


def _mock_connect(client, conn_info):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_connect():
        yield client, conn_info

    return fake_connect


@pytest.mark.asyncio
async def test_cmd_run_reuse_attaches_to_resolved_tab(state_dirs):
    """End-to-end: eN script + refs in tab B → attach_to_tab('BBB222')."""
    from passe.commands import cmd_run

    refcache.save_refs('BBB222', {'e1': 12})
    client = _client(_tabs())
    client._target_id = 'BBB222'
    info = {'cdp': ENDPOINT, 'browser': 'test', 'launched': None}
    ok_summary = {'ok': True, 'steps': 1, 'total_ms': 5}

    with patch('passe.commands.connect', _mock_connect(client, info)), \
         patch('passe.commands.run_script', AsyncMock(return_value=ok_summary)), \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO) as err, \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='click e1', reuse_tab=True)

    client.attach_to_tab.assert_called_once_with('BBB222')
    assert 'via cached eN refs' in err.getvalue()


@pytest.mark.asyncio
async def test_cmd_run_kept_tab_recorded(state_dirs):
    """A failed keep-on-fail run records its tab for later --reuse-tab."""
    from passe.commands import cmd_run

    client = _client(_tabs())
    client._target_id = 'AAA111'
    info = {'cdp': ENDPOINT, 'browser': 'test', 'launched': None}
    failed = {'ok': False, 'steps': 1, 'total_ms': 5, 'verb': 'click',
              'error': 'nope', 'failed_at': 0,
              'final_url': 'https://news.example.com/front'}

    with patch('passe.commands.connect', _mock_connect(client, info)), \
         patch('passe.commands.run_script', AsyncMock(return_value=failed)), \
         patch('sys.stdout', new_callable=StringIO), \
         patch('sys.stderr', new_callable=StringIO), \
         pytest.raises(SystemExit):
        await cmd_run(None, inline='click .btn')

    rec = tabmemory.load_last_tab(ENDPOINT)
    assert rec['target_id'] == 'AAA111'
    assert rec['url'] == 'https://news.example.com/front'


def test_cli_tab_flag_implies_reuse():
    """--tab reaches cmd_run and switches on reuse semantics."""
    import sys as _sys
    from unittest.mock import MagicMock
    import passe.cli as cli

    mock_cmd = MagicMock(return_value='sentinel')
    with patch.object(_sys, 'argv',
                      ['passe', 'run', '--tab', 'app.example', '-c',
                       'eval 1+1']):
        with patch('passe.cli.cmd_run', mock_cmd), \
             patch('passe.cli._run'):
            cli.main()
        _, kwargs = mock_cmd.call_args
        assert kwargs['tab'] == 'app.example'
        assert kwargs['reuse_tab'] is True
