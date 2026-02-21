"""
Test: Network capture infrastructure — event buffering, correlation,
JSONL serialization, and summary generation.

CDPClient._network_requests collects Network domain events into a dict
keyed by requestId. requestWillBeSent, responseReceived, loadingFinished,
and loadingFailed are correlated into a single entry per request.

Non-consuming: network events are collected AND still routed to
waiters/queues so future consumers (wait-idle) can coexist.
"""

import asyncio
import json
import os

import pytest

from passe.cli import CDPClient, _build_capture_summary, _write_capture_jsonl


class FakeWS:
    """Minimal fake WebSocket that feeds canned messages."""

    def __init__(self, messages: list[dict]):
        self._messages = [json.dumps(m) for m in messages]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def send(self, data):
        pass

    async def close(self):
        pass


def _request_will_be_sent(request_id: str, url: str, method: str = 'GET',
                          resource_type: str = 'XHR', timestamp: float = 1.0) -> dict:
    return {
        'method': 'Network.requestWillBeSent',
        'params': {
            'requestId': request_id,
            'request': {
                'url': url,
                'method': method,
                'headers': {'Accept': 'application/json'},
            },
            'type': resource_type,
            'timestamp': timestamp,
            'wallTime': 1708000000 + timestamp,
        },
    }


def _response_received(request_id: str, status: int = 200,
                       mime_type: str = 'application/json',
                       timestamp: float = 1.5) -> dict:
    return {
        'method': 'Network.responseReceived',
        'params': {
            'requestId': request_id,
            'response': {
                'status': status,
                'statusText': 'OK' if status == 200 else 'Not Found',
                'mimeType': mime_type,
                'headers': {'Content-Type': mime_type},
            },
            'timestamp': timestamp,
        },
    }


def _loading_finished(request_id: str, encoded_data_length: int = 1234) -> dict:
    return {
        'method': 'Network.loadingFinished',
        'params': {
            'requestId': request_id,
            'encodedDataLength': encoded_data_length,
        },
    }


def _loading_failed(request_id: str, error_text: str = 'net::ERR_FAILED') -> dict:
    return {
        'method': 'Network.loadingFailed',
        'params': {
            'requestId': request_id,
            'errorText': error_text,
        },
    }


# ── Basic collection ─────────────────────────────────────


@pytest.mark.asyncio
async def test_collects_request_response_pair():
    """A requestWillBeSent + responseReceived + loadingFinished produces one merged entry."""
    events = [
        _request_will_be_sent('r1', 'https://api.example.com/data'),
        _response_received('r1', 200),
        _loading_finished('r1', 5678),
    ]
    ws = FakeWS(events)
    client = CDPClient(ws)
    client._network_enabled = True
    await client.start()
    await asyncio.sleep(0.05)

    requests = client.get_network_requests()
    assert len(requests) == 1
    r = requests[0]
    assert r['requestId'] == 'r1'
    assert r['url'] == 'https://api.example.com/data'
    assert r['method'] == 'GET'
    assert r['status'] == 200
    assert r['content_type'] == 'application/json'
    assert r['completed'] is True
    assert r['encoded_data_length'] == 5678
    assert r['resource_type'] == 'XHR'


@pytest.mark.asyncio
async def test_collects_multiple_requests():
    """Multiple requests are stored independently, ordered by timestamp."""
    events = [
        _request_will_be_sent('r1', 'https://api.example.com/a', timestamp=1.0),
        _request_will_be_sent('r2', 'https://api.example.com/b', timestamp=2.0),
        _response_received('r1', 200, timestamp=1.5),
        _response_received('r2', 404, timestamp=2.5),
    ]
    ws = FakeWS(events)
    client = CDPClient(ws)
    client._network_enabled = True
    await client.start()
    await asyncio.sleep(0.05)

    requests = client.get_network_requests()
    assert len(requests) == 2
    assert requests[0]['url'] == 'https://api.example.com/a'
    assert requests[1]['url'] == 'https://api.example.com/b'
    assert requests[0]['status'] == 200
    assert requests[1]['status'] == 404


@pytest.mark.asyncio
async def test_failed_request():
    """loadingFailed marks the request with error details."""
    events = [
        _request_will_be_sent('r1', 'https://unreachable.example.com'),
        _loading_failed('r1', 'net::ERR_CONNECTION_REFUSED'),
    ]
    ws = FakeWS(events)
    client = CDPClient(ws)
    client._network_enabled = True
    await client.start()
    await asyncio.sleep(0.05)

    requests = client.get_network_requests()
    assert len(requests) == 1
    assert requests[0]['failed'] is True
    assert requests[0]['error_text'] == 'net::ERR_CONNECTION_REFUSED'
    assert 'status' not in requests[0]  # no response received


# ── Enable/disable gating ────────────────────────────────


@pytest.mark.asyncio
async def test_disabled_by_default():
    """Network events are ignored when _network_enabled is False."""
    events = [
        _request_will_be_sent('r1', 'https://api.example.com/data'),
        _response_received('r1', 200),
    ]
    ws = FakeWS(events)
    client = CDPClient(ws)
    # _network_enabled defaults to False
    await client.start()
    await asyncio.sleep(0.05)

    assert len(client._network_requests) == 0


@pytest.mark.asyncio
async def test_enable_clears_previous():
    """enable_network() clears any previously collected requests.

    We feed a canned Network.enable response so client.send() resolves.
    """
    # FakeWS that responds to Network.enable with a success result
    enable_response = {'id': 1, 'result': {}}
    ws = FakeWS([enable_response])
    client = CDPClient(ws)
    await client.start()

    # Manually add stale data
    client._network_requests['old'] = {'requestId': 'old', 'url': 'stale'}

    await client.enable_network()

    assert len(client._network_requests) == 0
    assert client._network_enabled is True


# ── Non-consuming: events still reach queues ─────────────


@pytest.mark.asyncio
async def test_network_events_still_reach_queues():
    """Network capture is non-consuming — events also go to event_queues.

    This is critical for wait-idle coexistence: both the collector and
    a queue subscriber see the same events.
    """
    events = [
        _request_will_be_sent('r1', 'https://api.example.com/data'),
        _loading_finished('r1'),
    ]
    ws = FakeWS(events)
    client = CDPClient(ws)
    client._network_enabled = True

    # Subscribe to loadingFinished via event_queues (like wait-idle would)
    queue = client.subscribe('Network.loadingFinished')

    await client.start()
    await asyncio.sleep(0.05)

    # Collector got the request
    assert 'r1' in client._network_requests
    assert client._network_requests['r1']['completed'] is True

    # Queue also got the loadingFinished event
    assert not queue.empty()
    msg = queue.get_nowait()
    assert msg['params']['requestId'] == 'r1'


# ── Edge cases ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_response_without_request_ignored():
    """A responseReceived for an unknown requestId doesn't create an entry."""
    events = [
        _response_received('orphan', 200),
    ]
    ws = FakeWS(events)
    client = CDPClient(ws)
    client._network_enabled = True
    await client.start()
    await asyncio.sleep(0.05)

    assert len(client._network_requests) == 0


@pytest.mark.asyncio
async def test_no_request_id_ignored():
    """Network events without requestId are silently ignored."""
    events = [
        {'method': 'Network.dataReceived', 'params': {'dataLength': 100}},
    ]
    ws = FakeWS(events)
    client = CDPClient(ws)
    client._network_enabled = True
    await client.start()
    await asyncio.sleep(0.05)

    assert len(client._network_requests) == 0


@pytest.mark.asyncio
async def test_redirect_overwrites_request():
    """Redirects send a second requestWillBeSent with the same requestId.

    Chrome reuses the requestId for the redirected request. Our collector
    overwrites the first entry — the final URL is what matters.
    """
    events = [
        _request_will_be_sent('r1', 'https://old.example.com/page', timestamp=1.0),
        _request_will_be_sent('r1', 'https://new.example.com/page', timestamp=1.1),
        _response_received('r1', 200, timestamp=1.5),
    ]
    ws = FakeWS(events)
    client = CDPClient(ws)
    client._network_enabled = True
    await client.start()
    await asyncio.sleep(0.05)

    requests = client.get_network_requests()
    assert len(requests) == 1
    assert requests[0]['url'] == 'https://new.example.com/page'
    assert requests[0]['status'] == 200


@pytest.mark.asyncio
async def test_get_network_requests_sorted_by_timestamp():
    """get_network_requests returns entries sorted by request timestamp."""
    events = [
        _request_will_be_sent('r3', 'https://api.com/c', timestamp=3.0),
        _request_will_be_sent('r1', 'https://api.com/a', timestamp=1.0),
        _request_will_be_sent('r2', 'https://api.com/b', timestamp=2.0),
    ]
    ws = FakeWS(events)
    client = CDPClient(ws)
    client._network_enabled = True
    await client.start()
    await asyncio.sleep(0.05)

    requests = client.get_network_requests()
    urls = [r['url'] for r in requests]
    assert urls == ['https://api.com/a', 'https://api.com/b', 'https://api.com/c']


# ── JSONL serialization ──────────────────────────────────


def test_write_capture_jsonl(tmp_path):
    """Writes one JSON line per request, valid JSON on each."""
    requests = [
        {'requestId': 'r1', 'url': 'https://api.com/a', 'method': 'GET',
         'status': 200, 'resource_type': 'XHR', 'timestamp': 1.0},
        {'requestId': 'r2', 'url': 'https://api.com/b', 'method': 'POST',
         'status': 201, 'resource_type': 'XHR', 'timestamp': 2.0},
    ]
    path = str(tmp_path / 'reqs.jsonl')
    _write_capture_jsonl(path, requests)

    with open(path) as f:
        lines = f.readlines()
    assert len(lines) == 2
    # Each line is valid JSON
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]['url'] == 'https://api.com/a'
    assert parsed[1]['url'] == 'https://api.com/b'


def test_write_capture_jsonl_empty(tmp_path):
    """Empty request list produces empty file."""
    path = str(tmp_path / 'empty.jsonl')
    _write_capture_jsonl(path, [])

    with open(path) as f:
        content = f.read()
    assert content == ''


# ── Summary generation ────────────────────────────────────


def test_summary_counts_by_type():
    """Summary breaks down requests by resource_type."""
    requests = [
        {'url': 'https://api.com/data', 'resource_type': 'XHR', 'status': 200},
        {'url': 'https://api.com/data2', 'resource_type': 'XHR', 'status': 200},
        {'url': 'https://cdn.com/style.css', 'resource_type': 'Stylesheet', 'status': 200},
        {'url': 'https://cdn.com/app.js', 'resource_type': 'Script', 'status': 200},
    ]
    summary = _build_capture_summary(requests)
    assert summary['requests'] == 4
    assert summary['by_type'] == {'XHR': 2, 'Stylesheet': 1, 'Script': 1}


def test_summary_extracts_domains():
    """Summary lists unique domains, sorted."""
    requests = [
        {'url': 'https://api.example.com/data', 'resource_type': 'XHR', 'status': 200},
        {'url': 'https://cdn.example.com/file.js', 'resource_type': 'Script', 'status': 200},
        {'url': 'https://api.example.com/more', 'resource_type': 'XHR', 'status': 200},
    ]
    summary = _build_capture_summary(requests)
    assert summary['domains'] == ['api.example.com', 'cdn.example.com']


def test_summary_captures_errors():
    """Non-2xx status codes and failed requests appear in errors."""
    requests = [
        {'url': 'https://api.com/ok', 'resource_type': 'XHR', 'status': 200},
        {'url': 'https://api.com/forbidden', 'resource_type': 'XHR', 'status': 403},
        {'url': 'https://api.com/missing', 'resource_type': 'XHR', 'status': 404},
        {'url': 'https://bad.com/fail', 'resource_type': 'XHR',
         'failed': True, 'error_text': 'net::ERR_FAILED'},
    ]
    summary = _build_capture_summary(requests)
    assert len(summary['errors']) == 3
    urls = [e['url'] for e in summary['errors']]
    assert 'https://api.com/ok' not in urls
    assert 'https://api.com/forbidden' in urls
    assert 'https://bad.com/fail' in urls


def test_summary_no_errors_key_when_all_ok():
    """errors key is absent when all requests are 2xx."""
    requests = [
        {'url': 'https://api.com/ok', 'resource_type': 'XHR', 'status': 200},
        {'url': 'https://api.com/created', 'resource_type': 'XHR', 'status': 201},
    ]
    summary = _build_capture_summary(requests)
    assert 'errors' not in summary


def test_summary_empty_requests():
    """Summary handles empty request list."""
    summary = _build_capture_summary([])
    assert summary['requests'] == 0
    assert summary['by_type'] == {}
    assert summary['domains'] == []


# ── Verb parsing ─────────────────────────────────────────


def test_capture_in_known_verbs():
    """capture is registered as a known verb."""
    from passe.cli import KNOWN_VERBS
    assert 'capture' in KNOWN_VERBS


def test_parse_capture_verb():
    """capture verb parses path and --bodies flag."""
    from passe.cli import parse_script
    steps = parse_script('capture /tmp/reqs.jsonl')
    assert steps == [('capture', ['/tmp/reqs.jsonl'])]


def test_parse_capture_with_bodies():
    """capture --bodies parses both flag and path."""
    from passe.cli import parse_script
    steps = parse_script('capture --bodies /tmp/reqs.jsonl')
    assert steps == [('capture', ['--bodies', '/tmp/reqs.jsonl'])]


def test_parse_capture_bodies_after_path():
    """capture path --bodies — flag after path also works."""
    from passe.cli import parse_script
    steps = parse_script('capture /tmp/reqs.jsonl --bodies')
    assert steps == [('capture', ['/tmp/reqs.jsonl', '--bodies'])]


def test_summary_includes_body_bytes():
    """When body_size is present, summary can report total."""
    requests = [
        {'url': 'https://api.com/a', 'resource_type': 'XHR', 'status': 200,
         'body_size': 1000},
        {'url': 'https://api.com/b', 'resource_type': 'XHR', 'status': 200,
         'body_size': 2000},
    ]
    # body_bytes is added by run_script, not _build_capture_summary,
    # so we just verify summary doesn't break with extra keys
    summary = _build_capture_summary(requests)
    assert summary['requests'] == 2


# ── Capture position warning ─────────────────────────────


@pytest.mark.asyncio
async def test_capture_mid_script_warns(capsys):
    """capture not at index 0 emits a position warning on stderr."""
    from unittest.mock import AsyncMock
    from passe.cli import run_script

    client = AsyncMock(spec=CDPClient)
    client.send = AsyncMock(return_value={'result': {'result': {'value': 'http://mock/'}}})
    client.wait_for_event = AsyncMock(return_value={})
    client._network_requests = {}

    steps = [
        ('goto', ['http://example.com']),
        ('capture', ['/tmp/reqs.jsonl']),
    ]
    await run_script(client, steps)

    stderr = capsys.readouterr().err
    assert 'Warning: capture is not the first verb' in stderr


@pytest.mark.asyncio
async def test_capture_first_verb_no_warning(capsys):
    """capture at index 0 produces no position warning."""
    from unittest.mock import AsyncMock
    from passe.cli import run_script

    client = AsyncMock(spec=CDPClient)
    client.send = AsyncMock(return_value={'result': {'result': {'value': 'http://mock/'}}})
    client.wait_for_event = AsyncMock(return_value={})
    client._network_requests = {}

    steps = [
        ('capture', ['/tmp/reqs.jsonl']),
    ]
    await run_script(client, steps)

    stderr = capsys.readouterr().err
    assert 'Warning: capture is not the first verb' not in stderr


# ── ensure_network idempotency ────────────────────────────


@pytest.mark.asyncio
async def test_ensure_network_does_not_clear_requests():
    """ensure_network (used by goto) preserves existing network requests."""
    ws = FakeWS([])
    client = CDPClient(ws)
    client._network_enabled = True
    client._network_requests = {'req1': {'url': 'https://example.com'}}

    await client.ensure_network()

    # Requests preserved — ensure_network skips when already enabled
    assert 'req1' in client._network_requests


@pytest.mark.asyncio
async def test_enable_network_clears_requests():
    """enable_network (used by capture) clears existing requests for fresh capture."""
    ws = FakeWS([])
    client = CDPClient(ws)
    client._network_requests = {'req1': {'url': 'https://example.com'}}

    # Mock send to avoid actual WebSocket call
    from unittest.mock import AsyncMock
    client.send = AsyncMock(return_value=None)
    await client.enable_network()

    assert client._network_requests == {}
    assert client._network_enabled is True
