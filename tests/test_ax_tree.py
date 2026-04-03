"""
Test: ax-tree, ax-find, ax-node verbs query the CDP Accessibility domain.

Covers:
  1. do_ax_tree calls Accessibility.getFullAXTree and builds a tree
  2. do_ax_find calls Accessibility.queryAXTree with role/name filters
  3. do_ax_find returns error when no filters given
  4. do_ax_node resolves selector and calls getPartialAXTree
  5. do_ax_node returns error for non-matching selector
  6. ax-tree, ax-find, ax-node in KNOWN_VERBS
  7. Dispatch via run_script

No browser needed: all tests mock CDP responses.
"""

import json
from unittest.mock import AsyncMock

import pytest

from passe.cli import (
    CDPClient, KNOWN_VERBS,
    do_ax_tree, do_ax_find, do_ax_node, run_script,
)


# ── Fixtures ─────────────────────────────────────────────


def _mock_client():
    """Create a mock CDPClient with controllable send() responses."""
    client = AsyncMock(spec=CDPClient)
    client.send = AsyncMock()
    client.wait_for_event = AsyncMock(return_value={})
    client._switch_session_for_screenshot = lambda: None
    return client


# Minimal CDP AXNode structures
_AX_NODES = [
    {
        'nodeId': '1', 'role': {'value': 'RootWebArea'},
        'name': {'value': 'Test Page'}, 'childIds': ['2', '3'],
    },
    {
        'nodeId': '2', 'parentId': '1', 'role': {'value': 'button'},
        'name': {'value': 'Accept'}, 'childIds': [],
    },
    {
        'nodeId': '3', 'parentId': '1', 'role': {'value': 'link'},
        'name': {'value': 'Home'}, 'childIds': [],
    },
]


def _full_tree_response():
    return {'result': {'nodes': _AX_NODES}}


def _query_response(nodes):
    return {'result': {'nodes': nodes}}


def _doc_response(node_id=1):
    return {'result': {'root': {'nodeId': node_id}}}


def _describe_response(backend_id=100):
    return {'result': {'node': {'backendNodeId': backend_id}}}


def _qs_response(node_id=10):
    return {'result': {'nodeId': node_id}}


# ── 1. do_ax_tree ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ax_tree_builds_hierarchy():
    """ax-tree returns a nested JSON tree with role/name."""
    client = _mock_client()
    client.send.return_value = _full_tree_response()

    result = await do_ax_tree(client)
    tree = json.loads(result)

    assert len(tree) == 1  # single root
    root = tree[0]
    assert root['role'] == 'RootWebArea'
    assert root['name'] == 'Test Page'
    assert len(root['children']) == 2
    assert root['children'][0]['role'] == 'button'
    assert root['children'][0]['name'] == 'Accept'
    assert root['children'][1]['role'] == 'link'

    client.send.assert_called_once_with('Accessibility.getFullAXTree', {}, timeout=30.0)


@pytest.mark.asyncio
async def test_ax_tree_passes_depth():
    """ax-tree --depth N passes depth param to CDP."""
    client = _mock_client()
    client.send.return_value = _full_tree_response()

    await do_ax_tree(client, depth=3)

    client.send.assert_called_once_with(
        'Accessibility.getFullAXTree', {'depth': 3}, timeout=30.0)


@pytest.mark.asyncio
async def test_ax_tree_truncates_large_output(capsys):
    """ax-tree caps output at MAX_AX_NODES and warns."""
    from passe.verbs_observation import MAX_AX_NODES
    client = _mock_client()
    # Generate more nodes than the cap
    nodes = [{'nodeId': str(i), 'role': {'value': 'generic'},
              'name': {'value': f'node-{i}'}, 'childIds': []}
             for i in range(MAX_AX_NODES + 500)]
    client.send.return_value = {'result': {'nodes': nodes}}

    result = await do_ax_tree(client)
    items = json.loads(result)

    assert len(items) <= MAX_AX_NODES
    captured = capsys.readouterr()
    assert 'truncated' in captured.err


@pytest.mark.asyncio
async def test_ax_tree_skips_ignored_nodes():
    """Ignored nodes are excluded from the tree."""
    client = _mock_client()
    nodes = [
        {'nodeId': '1', 'role': {'value': 'RootWebArea'},
         'name': {'value': 'Page'}, 'childIds': ['2']},
        {'nodeId': '2', 'parentId': '1', 'role': {'value': 'none'},
         'ignored': True, 'childIds': []},
    ]
    client.send.return_value = {'result': {'nodes': nodes}}

    result = await do_ax_tree(client)
    tree = json.loads(result)

    assert len(tree) == 1
    assert 'children' not in tree[0]  # pruned (child was ignored)


# ── 2. do_ax_find ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ax_find_by_role():
    """ax-find filters by role (client-side from full tree)."""
    client = _mock_client()
    client.send.return_value = _full_tree_response()

    result = await do_ax_find(client, role='button')
    matches = json.loads(result)

    assert len(matches) == 1
    assert matches[0]['role'] == 'button'
    assert matches[0]['name'] == 'Accept'


@pytest.mark.asyncio
async def test_ax_find_by_name():
    """ax-find filters by name substring (case-insensitive)."""
    client = _mock_client()
    client.send.return_value = _full_tree_response()

    result = await do_ax_find(client, name='home')
    matches = json.loads(result)

    assert len(matches) == 1
    assert matches[0]['name'] == 'Home'
    assert matches[0]['role'] == 'link'


# ── 3. do_ax_find error ──────────────────────────────────


@pytest.mark.asyncio
async def test_ax_find_no_filters():
    """ax-find returns error when no role or name given."""
    client = _mock_client()
    result = await do_ax_find(client)
    data = json.loads(result)
    assert 'error' in data


# ── 4. do_ax_node ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_ax_node_resolves_selector():
    """ax-node resolves CSS selector and returns subtree."""
    client = _mock_client()
    subtree_nodes = [
        {'nodeId': '10', 'role': {'value': 'navigation'},
         'name': {'value': 'Main Nav'}, 'childIds': ['11']},
        {'nodeId': '11', 'parentId': '10', 'role': {'value': 'link'},
         'name': {'value': 'About'}, 'childIds': []},
    ]
    client.send.side_effect = [
        _doc_response(),
        _qs_response(10),
        _describe_response(100),
        {'result': {'nodes': subtree_nodes}},
    ]

    result = await do_ax_node(client, 'nav')
    tree = json.loads(result)

    assert tree[0]['role'] == 'navigation'
    assert tree[0]['children'][0]['name'] == 'About'

    # Verify the CDP calls
    calls = [c[0][0] for c in client.send.call_args_list]
    assert calls == [
        'DOM.getDocument', 'DOM.querySelector',
        'DOM.describeNode', 'Accessibility.getPartialAXTree',
    ]


# ── 5. do_ax_node missing selector ───────────────────────


@pytest.mark.asyncio
async def test_ax_node_missing_element():
    """ax-node returns error when selector matches nothing."""
    client = _mock_client()
    client.send.side_effect = [
        _doc_response(),
        _qs_response(0),  # nodeId 0 = not found
    ]

    result = await do_ax_node(client, '#nonexistent')
    data = json.loads(result)
    assert 'error' in data


# ── 6. KNOWN_VERBS ───────────────────────────────────────


def test_ax_verbs_in_known_verbs():
    """ax-tree, ax-find, ax-node are registered in KNOWN_VERBS."""
    for verb in ('ax-tree', 'ax-find', 'ax-node'):
        assert verb in KNOWN_VERBS, f'{verb} missing from KNOWN_VERBS'


# ── 7. Dispatch via run_script ────────────────────────────


@pytest.mark.asyncio
async def test_ax_tree_dispatch():
    """ax-tree dispatches through run_script."""
    client = _mock_client()
    client.send.return_value = _full_tree_response()

    result = await run_script(client, [('ax-tree', [])])

    assert result['ok'] is True
    assert result['steps'] == 1
    # Verify Accessibility.getFullAXTree was called
    client.send.assert_any_call('Accessibility.getFullAXTree', {}, timeout=30.0)


@pytest.mark.asyncio
async def test_ax_find_dispatch_with_flags():
    """ax-find --role button dispatches correctly."""
    client = _mock_client()
    client.send.return_value = _full_tree_response()

    result = await run_script(client, [('ax-find', ['--role', 'button'])])

    assert result['ok'] is True
    # Verify getFullAXTree was called (client-side filtering)
    client.send.assert_any_call('Accessibility.getFullAXTree', {}, timeout=30.0)


@pytest.mark.asyncio
async def test_ax_find_dispatch_positional():
    """ax-find button Accept dispatches with positional args."""
    client = _mock_client()
    client.send.return_value = _full_tree_response()

    result = await run_script(client, [('ax-find', ['button', 'Accept'])])

    assert result['ok'] is True
