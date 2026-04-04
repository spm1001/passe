"""
Test: exists, count, visible, pdf convenience verbs.

Covers:
  1. do_exists returns bool from querySelector
  2. do_count returns int from querySelectorAll.length
  3. do_visible checks display/visibility/opacity and bounding rect
  4. do_pdf writes PDF via Page.printToPDF
  5. All four in KNOWN_VERBS
  6. Verb dispatch in run_script

No browser needed: all tests mock CDP responses.
"""

import base64
import os
from unittest.mock import AsyncMock

import pytest

from passe.cli import CDPClient, KNOWN_VERBS, run_script
from passe.verbs_observation import do_exists, do_count, do_visible, do_pdf


# ── Helpers ───────────────────────────────────────────────


def _mock_client():
    client = AsyncMock(spec=CDPClient)
    client.send = AsyncMock()
    client.wait_for_event = AsyncMock(return_value={})
    client._network_requests = {}
    return client


def _eval_response(value):
    return {'result': {'result': {'value': value}}}


# ── 1. do_exists ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_exists_true():
    client = _mock_client()
    client.send.return_value = _eval_response(True)
    assert await do_exists(client, '#login-btn') is True


@pytest.mark.asyncio
async def test_exists_false():
    client = _mock_client()
    client.send.return_value = _eval_response(False)
    assert await do_exists(client, '.nonexistent') is False


@pytest.mark.asyncio
async def test_exists_sends_queryselector():
    client = _mock_client()
    client.send.return_value = _eval_response(True)
    await do_exists(client, 'h1')
    method, params = client.send.call_args[0]
    assert method == 'Runtime.evaluate'
    assert 'querySelector' in params['expression']
    assert '!== null' in params['expression']


# ── 2. do_count ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_count_returns_int():
    client = _mock_client()
    client.send.return_value = _eval_response(42)
    assert await do_count(client, 'a') == 42


@pytest.mark.asyncio
async def test_count_zero():
    client = _mock_client()
    client.send.return_value = _eval_response(0)
    assert await do_count(client, '.missing') == 0


@pytest.mark.asyncio
async def test_count_sends_queryselectorall():
    client = _mock_client()
    client.send.return_value = _eval_response(5)
    await do_count(client, 'li')
    method, params = client.send.call_args[0]
    assert method == 'Runtime.evaluate'
    assert 'querySelectorAll' in params['expression']
    assert '.length' in params['expression']


# ── 3. do_visible ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_visible_true():
    client = _mock_client()
    client.send.return_value = _eval_response(True)
    assert await do_visible(client, '#header') is True


@pytest.mark.asyncio
async def test_visible_false():
    client = _mock_client()
    client.send.return_value = _eval_response(False)
    assert await do_visible(client, '#hidden-el') is False


@pytest.mark.asyncio
async def test_visible_checks_computed_style():
    client = _mock_client()
    client.send.return_value = _eval_response(True)
    await do_visible(client, '.btn')
    method, params = client.send.call_args[0]
    assert method == 'Runtime.evaluate'
    js = params['expression']
    assert 'getComputedStyle' in js
    assert 'getBoundingClientRect' in js
    assert 'display' in js
    assert 'visibility' in js


# ── 4. do_pdf ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pdf_writes_file(tmp_path):
    client = _mock_client()
    pdf_bytes = b'%PDF-1.4 fake content'
    client.send.return_value = {'result': {'data': base64.b64encode(pdf_bytes).decode()}}
    path = str(tmp_path / 'test.pdf')

    result = await do_pdf(client, path)

    assert result['file'] == path
    assert os.path.exists(path)
    with open(path, 'rb') as f:
        assert f.read() == pdf_bytes


@pytest.mark.asyncio
async def test_pdf_default_path():
    client = _mock_client()
    pdf_bytes = b'%PDF-1.4'
    client.send.return_value = {'result': {'data': base64.b64encode(pdf_bytes).decode()}}

    result = await do_pdf(client)

    assert result['file'].startswith('/tmp/passe-')
    assert result['file'].endswith('.pdf')
    # Clean up
    os.unlink(result['file'])


@pytest.mark.asyncio
async def test_pdf_sends_print_to_pdf():
    client = _mock_client()
    client.send.return_value = {'result': {'data': base64.b64encode(b'%PDF').decode()}}
    result = await do_pdf(client, '/tmp/test-pdf-verb.pdf')
    method, params = client.send.call_args[0]
    assert method == 'Page.printToPDF'
    assert params['printBackground'] is True
    os.unlink(result['file'])


# ── 5. KNOWN_VERBS ────────────────────────────────────────


def test_convenience_verbs_in_known():
    for verb in ('exists', 'count', 'visible', 'pdf'):
        assert verb in KNOWN_VERBS, f'{verb} not in KNOWN_VERBS'


# ── 6. Verb dispatch via run_script ───────────────────────


@pytest.mark.asyncio
async def test_exists_dispatch():
    client = _mock_client()
    client.send.return_value = _eval_response(True)
    result = await run_script(client, [('exists', ['#foo'])])
    assert result['ok'] is True


@pytest.mark.asyncio
async def test_count_dispatch():
    client = _mock_client()
    client.send.return_value = _eval_response(7)
    result = await run_script(client, [('count', ['.item'])])
    assert result['ok'] is True


@pytest.mark.asyncio
async def test_visible_dispatch():
    client = _mock_client()
    client.send.return_value = _eval_response(False)
    result = await run_script(client, [('visible', ['#gone'])])
    assert result['ok'] is True


@pytest.mark.asyncio
async def test_pdf_dispatch(tmp_path):
    client = _mock_client()
    pdf_bytes = b'%PDF-1.4 test'
    client.send.return_value = {'result': {'data': base64.b64encode(pdf_bytes).decode()}}
    path = str(tmp_path / 'dispatch.pdf')
    result = await run_script(client, [('pdf', [path])])
    assert result['ok'] is True
    assert any(f['verb'] == 'pdf' for f in result.get('files', []))
