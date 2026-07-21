"""ax-tree --flat-refs + eN ref targeting (passe-cosapu).

Scout once (flat refs + per-tab cache), act by ref in a later call:
  passe run --keep-tab  -c 'goto https://news.ycombinator.com'
  passe run --reuse-tab -c 'ax-tree --flat-refs'
  passe run --reuse-tab -c 'click e1'
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

import passe.refcache as refcache
from passe.refcache import clear_refs, load_refs, save_refs
from passe.runner import run_script
from passe.verbs_interaction import do_click
from passe.verbs_observation import _flat_refs, do_ax_tree


@pytest.fixture(autouse=True)
def _isolated_refs(tmp_path, monkeypatch):
    monkeypatch.setattr(refcache, 'REFS_DIR', tmp_path / 'refs')


AX_NODES = [
    {'nodeId': '1', 'role': {'value': 'RootWebArea'},
     'name': {'value': 'HN'}, 'backendDOMNodeId': 1},
    {'nodeId': '2', 'role': {'value': 'link'},
     'name': {'value': 'Hacker News'}, 'backendDOMNodeId': 10},
    {'nodeId': '3', 'role': {'value': 'StaticText'},
     'name': {'value': 'noise'}, 'backendDOMNodeId': 11},
    {'nodeId': '4', 'role': {'value': 'link'},
     'name': {'value': 'new'}, 'backendDOMNodeId': 12},
    {'nodeId': '5', 'role': {'value': 'button'},
     'name': {'value': 'search'}, 'backendDOMNodeId': 13},
    {'nodeId': '6', 'role': {'value': 'link'}, 'ignored': True,
     'name': {'value': 'hidden'}, 'backendDOMNodeId': 14},
    {'nodeId': '7', 'role': {'value': 'textbox'}},  # no backendDOMNodeId
]


class TestFlatRefs:
    def test_filters_and_orders(self):
        entries, mapping = _flat_refs(AX_NODES)
        assert [e['ref'] for e in entries] == ['e0', 'e1', 'e2']
        assert entries[0] == {'ref': 'e0', 'role': 'link', 'name': 'Hacker News'}
        assert entries[1]['name'] == 'new'
        assert entries[2]['role'] == 'button'
        assert mapping == {'e0': 10, 'e1': 12, 'e2': 13}

    @pytest.mark.asyncio
    async def test_do_ax_tree_writes_cache_and_flat_output(self):
        client = AsyncMock()
        client._target_id = 'TAB1'
        client.send = AsyncMock(return_value={'result': {'nodes': AX_NODES}})
        out = await do_ax_tree(client, flat_refs=True)
        parsed = json.loads(out)
        assert [e['ref'] for e in parsed] == ['e0', 'e1', 'e2']
        assert load_refs('TAB1') == {'e0': 10, 'e1': 12, 'e2': 13}


class _RefClient:
    """Fake CDP client routing send() by method name."""

    def __init__(self, routes):
        self._target_id = 'TAB1'
        self.routes = routes
        self.calls = []

    async def send(self, method, params=None, timeout=15.0):
        self.calls.append((method, params or {}))
        if method in self.routes:
            return self.routes[method]
        return {'result': {}}


class TestRefResolution:
    @pytest.mark.asyncio
    async def test_click_by_ref_resolves_and_calls(self):
        save_refs('TAB1', {'e1': 42})
        client = _RefClient({
            'DOM.resolveNode': {'result': {'object': {'objectId': 'obj-1'}}},
            'Runtime.callFunctionOn': {'result': {'result': {}}},
        })
        await do_click(client, 'e1')
        resolve = [p for m, p in client.calls if m == 'DOM.resolveNode']
        assert resolve == [{'backendNodeId': 42}]
        call = [p for m, p in client.calls if m == 'Runtime.callFunctionOn']
        assert call[0]['objectId'] == 'obj-1'
        assert 'this.click()' in call[0]['functionDeclaration']

    @pytest.mark.asyncio
    async def test_unknown_ref_names_the_fix(self):
        client = _RefClient({})
        with pytest.raises(RuntimeError, match='ax-tree --flat-refs'):
            await do_click(client, 'e7')

    @pytest.mark.asyncio
    async def test_stale_ref_names_the_fix(self):
        save_refs('TAB1', {'e1': 42})
        # resolveNode returns a CDP error payload (no 'result' key)
        client = _RefClient({
            'DOM.resolveNode': {'error': {'message': 'No node found'}},
        })
        with pytest.raises(RuntimeError, match='stale'):
            await do_click(client, 'e1')


class TestRunnerRouting:
    @pytest.mark.asyncio
    async def test_click_ref_routes_to_do_click_not_text(self):
        """'e1' has no CSS chars — without the ref guard it would text-click
        the literal string 'e1'."""
        client = AsyncMock()
        with patch('passe.runner.do_click', AsyncMock()) as click, \
             patch('passe.runner.do_click_text', AsyncMock()) as click_text:
            await run_script(client, [('click', ['e1'])])
        click.assert_called_once()
        click_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_plain_text_still_routes_to_text_click(self):
        client = AsyncMock()
        with patch('passe.runner.do_click', AsyncMock()) as click, \
             patch('passe.runner.do_click_text', AsyncMock()) as click_text:
            await run_script(client, [('click', ['Reject cookies'])])
        click_text.assert_called_once()
        click.assert_not_called()

    @pytest.mark.asyncio
    async def test_flat_refs_flag_parsed(self):
        client = AsyncMock()
        with patch('passe.runner.do_ax_tree',
                   AsyncMock(return_value='[]')) as ax:
            await run_script(client, [('ax-tree', ['--flat-refs'])])
        assert ax.call_args.kwargs.get('flat_refs') is True


class TestCacheLifecycle:
    def test_clear_refs_removes_file(self):
        save_refs('TAB1', {'e0': 1})
        assert load_refs('TAB1') == {'e0': 1}
        clear_refs('TAB1')
        assert load_refs('TAB1') is None

    def test_missing_tab_id_is_noop(self):
        save_refs('', {'e0': 1})
        assert load_refs('') is None
        clear_refs('')  # must not raise
