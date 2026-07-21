"""Tests for log_daemon — request assembly, filtering, rotation, reconnection."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from passe.log_daemon import (
    LogDaemon, LogWriter, RequestStore, DaemonState,
    should_skip_url, should_skip_mime,
)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

class TestFiltering:
    def test_skip_analytics_urls(self):
        assert should_skip_url('https://www.google-analytics.com/collect')
        assert should_skip_url('https://api.example.com/beacon')
        assert should_skip_url('https://sentry.io/api/123')

    def test_skip_static_extensions(self):
        assert should_skip_url('https://example.com/style.css')
        assert should_skip_url('https://example.com/font.woff2')
        assert should_skip_url('https://example.com/icon.ico')

    def test_allow_api_urls(self):
        assert not should_skip_url('https://api.example.com/v1/data')
        assert not should_skip_url('https://example.com/page.html')

    def test_skip_binary_mime(self):
        assert should_skip_mime('image/png')
        assert should_skip_mime('font/woff2')
        assert should_skip_mime('application/pdf')
        assert should_skip_mime('application/octet-stream')

    def test_allow_text_mime(self):
        assert not should_skip_mime('application/json')
        assert not should_skip_mime('text/html')
        assert not should_skip_mime(None)


# ---------------------------------------------------------------------------
# RequestStore
# ---------------------------------------------------------------------------

class TestRequestStore:
    def test_start_and_complete(self):
        store = RequestStore()
        store.start('req1', {'url': 'https://example.com', 'method': 'GET'})
        rec = store.complete('req1')
        assert rec['id'] == 'req1'
        assert rec['url'] == 'https://example.com'
        assert 'ts' in rec

    def test_update(self):
        store = RequestStore()
        store.start('req1', {'url': 'https://example.com'})
        store.update('req1', {'status': 200, 'mime': 'text/html'})
        rec = store.complete('req1')
        assert rec['status'] == 200

    def test_complete_missing_returns_none(self):
        store = RequestStore()
        assert store.complete('nonexistent') is None

    def test_clear(self):
        store = RequestStore()
        store.start('req1', {'url': 'a'})
        store.start('req2', {'url': 'b'})
        store.clear()
        assert store.complete('req1') is None
        assert store.complete('req2') is None


# ---------------------------------------------------------------------------
# LogWriter
# ---------------------------------------------------------------------------

class TestLogWriter:
    def test_write_creates_jsonl(self, tmp_path):
        writer = LogWriter(tmp_path)
        writer.write({'id': 'r1', 'url': 'https://example.com'})
        lines = (tmp_path / 'requests.jsonl').read_text().strip().split('\n')
        assert len(lines) == 1
        assert json.loads(lines[0])['id'] == 'r1'

    def test_write_appends(self, tmp_path):
        writer = LogWriter(tmp_path)
        writer.write({'id': 'r1'})
        writer.write({'id': 'r2'})
        lines = (tmp_path / 'requests.jsonl').read_text().strip().split('\n')
        assert len(lines) == 2

    def test_pause_suppresses_write(self, tmp_path):
        writer = LogWriter(tmp_path)
        (tmp_path / '.paused').touch()
        writer.write({'id': 'r1'})
        assert not (tmp_path / 'requests.jsonl').exists()

    def test_rotation(self, tmp_path):
        writer = LogWriter(tmp_path)
        log_file = tmp_path / 'requests.jsonl'
        log_file.write_text('x\n')
        # Lower threshold so the tiny file triggers rotation
        with patch('passe.log_daemon.MAX_LOG_SIZE', 1):
            writer.write({'id': 'after_rotation'})
        assert (tmp_path / 'requests.jsonl.1').exists()
        lines = log_file.read_text().strip().split('\n')
        assert json.loads(lines[0])['id'] == 'after_rotation'

    def test_rotation_shifts_files(self, tmp_path):
        writer = LogWriter(tmp_path)
        (tmp_path / 'requests.jsonl.1').write_text('old1\n')
        (tmp_path / 'requests.jsonl.2').write_text('old2\n')
        log_file = tmp_path / 'requests.jsonl'
        log_file.write_text('current\n')
        with patch('passe.log_daemon.MAX_LOG_SIZE', 1):
            writer.write({'id': 'new'})
        assert (tmp_path / 'requests.jsonl.3').read_text() == 'old2\n'
        assert (tmp_path / 'requests.jsonl.2').read_text() == 'old1\n'
        assert (tmp_path / 'requests.jsonl.1').read_text() == 'current\n'


# ---------------------------------------------------------------------------
# Daemon: message dispatch and request assembly
# ---------------------------------------------------------------------------

class TestDaemonDispatch:
    def _make_daemon(self, tmp_path):
        d = LogDaemon(log_dir=tmp_path)
        d.sessions['sess1'] = {
            'targetId': 'tab1', 'url': 'https://app.example.com', 'type': 'page',
        }
        return d

    @pytest.mark.asyncio
    async def test_full_request_lifecycle(self, tmp_path):
        """requestWillBeSent → responseReceived → loadingFinished → JSONL."""
        d = self._make_daemon(tmp_path)

        # Stub send() so _finish_request's getResponseBody doesn't hang
        async def fake_send(method, params=None, session_id=None):
            return {'error': {'message': 'no body'}}
        d.send = fake_send

        # Capture tasks created by _dispatch so we can await them
        created_tasks = []
        orig_create_task = asyncio.create_task

        def capturing_create_task(coro, **kwargs):
            task = orig_create_task(coro, **kwargs)
            created_tasks.append(task)
            return task

        # 1. requestWillBeSent
        d._dispatch(json.dumps({
            'method': 'Network.requestWillBeSent',
            'params': {
                'requestId': 'R1',
                'request': {
                    'url': 'https://api.example.com/data',
                    'method': 'GET',
                    'headers': {'Accept': 'application/json'},
                },
                'type': 'XHR',
            },
            'sessionId': 'sess1',
        }))

        rec = d.store.get('R1')
        assert rec is not None
        assert rec['method'] == 'GET'
        assert rec['resource_type'] == 'XHR'

        # 2. responseReceived
        d._dispatch(json.dumps({
            'method': 'Network.responseReceived',
            'params': {
                'requestId': 'R1',
                'response': {
                    'status': 200,
                    'mimeType': 'application/json',
                    'headers': {'Content-Type': 'application/json'},
                },
            },
            'sessionId': 'sess1',
        }))

        rec = d.store.get('R1')
        assert rec['status'] == 200
        assert rec['mime'] == 'application/json'

        # 3. loadingFinished — triggers async _finish_request
        with patch('passe.log_daemon.asyncio.create_task',
                   side_effect=capturing_create_task):
            d._dispatch(json.dumps({
                'method': 'Network.loadingFinished',
                'params': {'requestId': 'R1', 'encodedDataLength': 1234},
                'sessionId': 'sess1',
            }))

        # Await the _finish_request task deterministically
        assert len(created_tasks) == 1
        await created_tasks[0]

        # Verify JSONL was written
        log_file = tmp_path / 'requests.jsonl'
        assert log_file.exists()
        written = json.loads(log_file.read_text().strip())
        assert written['id'] == 'R1'
        assert written['url'] == 'https://api.example.com/data'
        assert written['status'] == 200
        assert written['size'] == 1234
        assert written['tab']['id'] == 'tab1'
        # Internal fields should NOT appear (they live in store.meta, not records)
        for key in written:
            assert not key.startswith('_'), f'internal field leaked: {key}'

    def test_filtered_url_not_stored(self, tmp_path):
        d = self._make_daemon(tmp_path)
        d._dispatch(json.dumps({
            'method': 'Network.requestWillBeSent',
            'params': {
                'requestId': 'R2',
                'request': {
                    'url': 'https://www.google-analytics.com/collect',
                    'method': 'POST',
                    'headers': {},
                },
            },
            'sessionId': 'sess1',
        }))
        assert d.store.get('R2') is None

    def test_binary_mime_discarded_on_response(self, tmp_path):
        d = self._make_daemon(tmp_path)
        d.store.start('R3', {
            'url': 'https://example.com/logo.png',
            'method': 'GET',
        }, meta={'session_id': 'sess1'})
        d._dispatch(json.dumps({
            'method': 'Network.responseReceived',
            'params': {
                'requestId': 'R3',
                'response': {'status': 200, 'mimeType': 'image/png', 'headers': {}},
            },
            'sessionId': 'sess1',
        }))
        # Discarded — complete was called
        assert d.store.get('R3') is None

    def test_loading_failed_cleans_up(self, tmp_path):
        d = self._make_daemon(tmp_path)
        d.store.start('R4', {
            'url': 'https://example.com/fail',
            'method': 'GET',
        }, meta={'session_id': 'sess1'})
        d._dispatch(json.dumps({
            'method': 'Network.loadingFailed',
            'params': {'requestId': 'R4'},
            'sessionId': 'sess1',
        }))
        assert d.store.get('R4') is None

    def test_extra_info_merges_headers(self, tmp_path):
        d = self._make_daemon(tmp_path)
        d._dispatch(json.dumps({
            'method': 'Network.requestWillBeSent',
            'params': {
                'requestId': 'R5',
                'request': {
                    'url': 'https://api.example.com/data',
                    'method': 'GET',
                    'headers': {'Accept': 'application/json'},
                },
            },
            'sessionId': 'sess1',
        }))
        d._dispatch(json.dumps({
            'method': 'Network.requestWillBeSentExtraInfo',
            'params': {
                'requestId': 'R5',
                'headers': {'Cookie': 'session=abc123'},
            },
            'sessionId': 'sess1',
        }))
        rec = d.store.get('R5')
        assert rec['request_headers']['Cookie'] == 'session=abc123'
        assert rec['request_headers']['Accept'] == 'application/json'

    def test_response_extra_info_merges_headers(self, tmp_path):
        d = self._make_daemon(tmp_path)
        d.store.start('R6', {
            'url': 'https://example.com',
            'method': 'GET', 'response_headers': {'X-Existing': 'yes'},
        }, meta={'session_id': 'sess1'})
        d._dispatch(json.dumps({
            'method': 'Network.responseReceivedExtraInfo',
            'params': {
                'requestId': 'R6',
                'headers': {'Set-Cookie': 'token=xyz'},
            },
            'sessionId': 'sess1',
        }))
        rec = d.store.get('R6')
        assert rec['response_headers']['Set-Cookie'] == 'token=xyz'
        assert rec['response_headers']['X-Existing'] == 'yes'


# ---------------------------------------------------------------------------
# Daemon: target management
# ---------------------------------------------------------------------------

class TestTargetManagement:
    @pytest.mark.asyncio
    async def test_attached_to_target_registers_session(self, tmp_path):
        d = LogDaemon(log_dir=tmp_path)
        # Stub _enable_network to avoid send() without a websocket
        d._enable_network = AsyncMock()
        d._dispatch(json.dumps({
            'method': 'Target.attachedToTarget',
            'params': {
                'sessionId': 'sess_new',
                'targetInfo': {
                    'targetId': 'tab_new',
                    'url': 'https://new-tab.example.com',
                    'type': 'page',
                },
            },
        }))
        assert 'sess_new' in d.sessions
        assert d.sessions['sess_new']['targetId'] == 'tab_new'

    def test_detached_removes_session(self, tmp_path):
        d = LogDaemon(log_dir=tmp_path)
        d.sessions['sess_old'] = {'targetId': 'tab_old', 'url': 'old'}
        d._dispatch(json.dumps({
            'method': 'Target.detachedFromTarget',
            'params': {'sessionId': 'sess_old'},
        }))
        assert 'sess_old' not in d.sessions

    def test_target_info_changed_updates_url(self, tmp_path):
        d = LogDaemon(log_dir=tmp_path)
        d.sessions['sess1'] = {'targetId': 'tab1', 'url': 'https://old.com'}
        d._dispatch(json.dumps({
            'method': 'Target.targetInfoChanged',
            'params': {
                'targetInfo': {
                    'targetId': 'tab1',
                    'url': 'https://new.com/page',
                    'type': 'page',
                },
            },
        }))
        assert d.sessions['sess1']['url'] == 'https://new.com/page'

    @pytest.mark.asyncio
    async def test_non_page_targets_ignored(self, tmp_path):
        d = LogDaemon(log_dir=tmp_path)
        d._enable_network = AsyncMock()
        d._dispatch(json.dumps({
            'method': 'Target.attachedToTarget',
            'params': {
                'sessionId': 'sess_sw',
                'targetInfo': {
                    'targetId': 'sw1',
                    'url': 'sw.js',
                    'type': 'service_worker',
                },
            },
        }))
        assert 'sess_sw' not in d.sessions


# ---------------------------------------------------------------------------
# Daemon: command response routing
# ---------------------------------------------------------------------------

class TestCommandRouting:
    def test_response_resolves_future(self, tmp_path):
        d = LogDaemon(log_dir=tmp_path)
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        d._pending[42] = future
        d._dispatch(json.dumps({'id': 42, 'result': {'ok': True}}))
        assert future.done()
        assert future.result() == {'id': 42, 'result': {'ok': True}}
        loop.close()


# ---------------------------------------------------------------------------
# Daemon: reconnection state
# ---------------------------------------------------------------------------

class TestReconnection:
    def test_reset_clears_state(self, tmp_path):
        d = LogDaemon(log_dir=tmp_path)
        d.sessions['s1'] = {'url': 'x'}
        d.store.start('r1', {'url': 'y'})
        loop = asyncio.new_event_loop()
        d._pending[1] = loop.create_future()
        d._reset_session_state()
        assert len(d.sessions) == 0
        assert d.store.get('r1') is None
        assert len(d._pending) == 0
        loop.close()

    @pytest.mark.asyncio
    async def test_connection_error_triggers_reconnect(self, tmp_path):
        """When discover_chrome raises ConnectionError, daemon retries."""
        d = LogDaemon(log_dir=tmp_path)
        call_count = 0

        original_connect = d._connect_and_attach

        async def failing_connect():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                d._running = False
                return
            raise ConnectionError('Chrome unreachable')

        d._connect_and_attach = failing_connect
        # Override sleep to not actually wait
        with patch('passe.log_daemon.asyncio.sleep', new_callable=AsyncMock):
            await d.run()

        assert call_count == 3
        assert d.state == DaemonState.DEAD


# ---------------------------------------------------------------------------
# discover_chrome extraction
# ---------------------------------------------------------------------------

class TestDiscoverChrome:
    def test_discover_raises_on_failure(self):
        with patch('passe.connection.urllib.request.urlopen',
                   side_effect=ConnectionRefusedError('refused')):
            with pytest.raises(ConnectionError, match='Cannot connect'):
                from passe.connection import discover_chrome
                discover_chrome('http://localhost:9222')

    def test_discover_returns_ws_url(self):
        from passe.connection import discover_chrome
        from unittest.mock import MagicMock
        from io import BytesIO
        version_json = json.dumps({
            'webSocketDebuggerUrl': 'ws://localhost:9222/devtools/browser/abc',
            'Browser': 'Chrome/120',
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = version_json
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch('passe.connection.urllib.request.urlopen', return_value=mock_resp):
            ws_url, info = discover_chrome('http://localhost:9222')
        assert ws_url == 'ws://localhost:9222/devtools/browser/abc'
        assert info['browser'] == 'Chrome/120'
        assert info['remote'] is False

    def test_discover_rewrites_remote_ws_url(self):
        from passe.connection import discover_chrome
        from unittest.mock import MagicMock
        version_json = json.dumps({
            'webSocketDebuggerUrl': 'ws://localhost:9222/devtools/browser/abc',
            'Browser': 'Chrome/120',
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = version_json
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch('passe.connection.urllib.request.urlopen', return_value=mock_resp), \
             patch('passe.connection._is_loopback', return_value=False):
            ws_url, info = discover_chrome('http://remote-host:9222')
        assert ws_url == 'ws://remote-host:9222/devtools/browser/abc'
        assert info['remote'] is True
